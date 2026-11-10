from __future__ import annotations

import json

import httpx
import pytest

from life_api.ingest.google_health import (
    TOKEN_URL,
    GoogleHealthClient,
    GoogleHealthError,
    ReauthRequiredError,
)
from life_api.ingest.tokens import OAuthClientConfig, Token

NOW = 1_000_000.0


class MemoryTokenStore:
    def __init__(self, token: Token) -> None:
        self.token = token
        self.saves = 0

    def load(self) -> Token:
        return self.token

    def save(self, token: Token) -> None:
        self.token = token
        self.saves += 1


def make_client(handler, token: Token | None = None):
    store = MemoryTokenStore(token or Token("valid", "refresh-1", NOW + 3600))
    sleeps: list[float] = []
    client = GoogleHealthClient(
        OAuthClientConfig("cid", "secret"),
        store,
        httpx.Client(transport=httpx.MockTransport(handler)),
        clock=lambda: NOW,
        sleep=sleeps.append,
    )
    return client, store, sleeps


def test_pagination_follows_next_page_token():
    pages = {
        None: {"dataPoints": [{"n": 1}], "nextPageToken": "p2"},
        "p2": {"dataPoints": [{"n": 2}]},
    }
    seen_filters = []

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.headers["Authorization"] == "Bearer valid"
        seen_filters.append(req.url.params.get("filter"))
        return httpx.Response(200, json=pages[req.url.params.get("pageToken")])

    client, _, _ = make_client(handler)
    points = client.list_data_points(
        "sleep", filter='sleep.interval.civil_end_time >= "2026-11-08"'
    )
    assert points == [{"n": 1}, {"n": 2}]
    assert seen_filters == ['sleep.interval.civil_end_time >= "2026-11-08"'] * 2


def test_expired_token_is_refreshed_and_rotation_saved():
    def handler(req: httpx.Request) -> httpx.Response:
        if str(req.url) == TOKEN_URL:
            body = dict(x.split("=") for x in req.content.decode().split("&"))
            assert body["refresh_token"] == "refresh-1"
            return httpx.Response(
                200,
                json={"access_token": "fresh", "expires_in": 3599, "refresh_token": "refresh-2"},
            )
        assert req.headers["Authorization"] == "Bearer fresh"
        return httpx.Response(200, json={"healthUserId": "111"})

    client, store, _ = make_client(handler, Token("old", "refresh-1", NOW - 10))
    assert client.identity() == {"healthUserId": "111"}
    assert store.token.refresh_token == "refresh-2"
    assert store.saves == 1


def test_invalid_grant_raises_reauth():
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "invalid_grant"})

    client, _, _ = make_client(handler, Token("old", "dead", NOW - 10))
    with pytest.raises(ReauthRequiredError):
        client.identity()


def test_retries_on_429_with_backoff():
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429)
        return httpx.Response(200, json={"rollupDataPoints": [{"ok": True}]})

    client, _, sleeps = make_client(handler)
    from datetime import date

    assert client.daily_rollup("steps", date(2026, 11, 8), date(2026, 11, 9)) == [{"ok": True}]
    assert sleeps == [1, 2]


def test_rollup_sends_civil_date_range():
    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        assert req.url.path.endswith("/steps/dataPoints:dailyRollUp")
        assert body["range"]["start"]["date"] == {"year": 2026, "month": 11, "day": 8}
        assert body["windowSizeDays"] == 1
        return httpx.Response(200, json={})

    from datetime import date

    client, _, _ = make_client(handler)
    assert client.daily_rollup("steps", date(2026, 11, 8), date(2026, 11, 9)) == []


def test_401_triggers_single_refresh_then_fails():
    def handler(req: httpx.Request) -> httpx.Response:
        if str(req.url) == TOKEN_URL:
            return httpx.Response(200, json={"access_token": "fresh", "expires_in": 3599})
        return httpx.Response(401, text="nope")

    client, _, _ = make_client(handler)
    with pytest.raises(GoogleHealthError, match="401"):
        client.identity()


def test_ssm_token_store_roundtrip(aws):
    import boto3

    from life_api.ingest.tokens import SsmTokenStore, load_client_config

    ssm = boto3.client("ssm", region_name="us-east-1")
    ssm.put_parameter(
        Name="/c", Value=json.dumps({"client_id": "a", "client_secret": "b"}), Type="SecureString"
    )
    ssm.put_parameter(Name="/t", Value=json.dumps({"refresh_token": "r"}), Type="SecureString")
    store = SsmTokenStore(ssm, "/t")
    assert store.load().refresh_token == "r"
    store.save(Token("acc", "r2", 5.0))
    assert store.load() == Token("acc", "r2", 5.0)
    assert load_client_config(ssm, "/c").client_id == "a"


def test_max_pages_stops_pagination():
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(
            200, json={"dataPoints": [{"n": calls["n"]}], "nextPageToken": "more"}
        )

    client, _, _ = make_client(handler)
    assert client.list_data_points("daily-resting-heart-rate", max_pages=1) == [{"n": 1}]
    assert calls["n"] == 1
