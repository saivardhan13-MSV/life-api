"""Minimal client for the Google Health API (successor of the Fitbit Web API).

Docs: https://developers.google.com/health  (v4, stable channel)

The legacy Fitbit Web API was turned off on 2026-11-02, so Fitbit data
(Fitbit Air, Charge, Pixel Watch) is read from here.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import date
from typing import Any

import httpx

from life_api.ingest.tokens import OAuthClientConfig, Token, TokenStore

log = logging.getLogger(__name__)

BASE_URL = "https://health.googleapis.com/v4"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 - URL, not a secret
SCOPES = (
    "https://www.googleapis.com/auth/googlehealth.sleep.readonly",
    "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly",
    "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly",
)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class GoogleHealthError(Exception):
    pass


class ReauthRequiredError(GoogleHealthError):
    """The refresh token was revoked or expired. Run scripts/google_health_auth.py again."""


def _civil_date(d: date) -> dict[str, int]:
    return {"year": d.year, "month": d.month, "day": d.day}


class GoogleHealthClient:
    def __init__(
        self,
        oauth: OAuthClientConfig,
        tokens: TokenStore,
        http: httpx.Client | None = None,
        *,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
        max_retries: int = 4,
    ) -> None:
        self._oauth = oauth
        self._tokens = tokens
        self._http = http or httpx.Client(timeout=30)
        self._clock = clock
        self._sleep = sleep
        self._max_retries = max_retries
        self._token: Token | None = None

    # ------------------------------------------------------------------ public API
    def identity(self) -> dict[str, Any]:
        return self._request("GET", "/users/me/identity")

    def list_data_points(
        self,
        data_type: str,
        *,
        filter: str | None = None,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        """Data points for ``data_type`` (kebab-case, e.g. ``sleep``), newest first.

        Follows pagination until done, or until ``max_pages`` pages were read.
        """
        params: dict[str, Any] = {}
        if filter:
            params["filter"] = filter
        if page_size:
            params["pageSize"] = page_size
        points: list[dict[str, Any]] = []
        pages = 0
        while True:
            body = self._request(
                "GET", f"/users/me/dataTypes/{data_type}/dataPoints", params=params
            )
            points.extend(body.get("dataPoints", []))
            pages += 1
            token = body.get("nextPageToken")
            if not token or (max_pages is not None and pages >= max_pages):
                return points
            params["pageToken"] = token

    def daily_rollup(self, data_type: str, start: date, end: date) -> list[dict[str, Any]]:
        """Daily aggregates for ``[start, end)``."""
        body = self._request(
            "POST",
            f"/users/me/dataTypes/{data_type}/dataPoints:dailyRollUp",
            json={
                "range": {"start": {"date": _civil_date(start)}, "end": {"date": _civil_date(end)}},
                "windowSizeDays": 1,
            },
        )
        return body.get("rollupDataPoints", [])

    # ------------------------------------------------------------------ internals
    def _access_token(self, *, force_refresh: bool = False) -> str:
        if self._token is None:
            self._token = self._tokens.load()
        if force_refresh or self._token.expires_at - 60 <= self._clock():
            self._refresh()
        return self._token.access_token

    def _refresh(self) -> None:
        assert self._token is not None
        resp = self._http.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": self._oauth.client_id,
                "client_secret": self._oauth.client_secret,
                "refresh_token": self._token.refresh_token,
            },
        )
        if resp.status_code in (400, 401) and "invalid_grant" in resp.text:
            raise ReauthRequiredError(
                "Google refresh token expired or revoked; re-run scripts/google_health_auth.py"
            )
        if resp.status_code != 200:
            raise GoogleHealthError(f"token refresh failed: {resp.status_code} {resp.text[:200]}")
        data = resp.json()
        self._token = Token(
            access_token=data["access_token"],
            # Google may rotate the refresh token; keep the old one if it doesn't.
            refresh_token=data.get("refresh_token", self._token.refresh_token),
            expires_at=self._clock() + float(data.get("expires_in", 3600)),
        )
        self._tokens.save(self._token)
        log.info("refreshed Google Health access token")

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        refreshed_after_401 = False
        attempt = 0
        while True:
            headers = {
                "Authorization": f"Bearer {self._access_token()}",
                "Accept": "application/json",
            }
            resp = self._http.request(
                method, BASE_URL + path, params=params, json=json, headers=headers
            )
            if resp.status_code == 401 and not refreshed_after_401:
                refreshed_after_401 = True
                self._access_token(force_refresh=True)
                continue
            if resp.status_code in RETRYABLE_STATUS and attempt < self._max_retries:
                delay = min(2**attempt, 30)
                log.warning(
                    "Google Health %s on %s, retrying in %ss", resp.status_code, path, delay
                )
                self._sleep(delay)
                attempt += 1
                continue
            if resp.status_code >= 400:
                raise GoogleHealthError(
                    f"{method} {path} failed: {resp.status_code} {resp.text[:300]}"
                )
            return resp.json()
