from __future__ import annotations

from datetime import date, timedelta

from life_api.config import get_settings


def _today() -> date:
    return get_settings().today()


def test_health_is_public(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_private_routes_require_key(client):
    assert client.get("/v1/applications").status_code == 401
    assert client.get("/v1/applications", headers={"X-API-Key": "wrong"}).status_code == 401


def test_application_crud(client, auth):
    created = client.post(
        "/v1/applications",
        json={"company": "Amazon", "role": "SDE I", "url": "https://amazon.jobs/123"},
        headers=auth,
    )
    assert created.status_code == 201
    app = created.json()
    assert app["status"] == "applied"
    assert app["applied_on"] == _today().isoformat()

    got = client.get(f"/v1/applications/{app['id']}", headers=auth).json()
    assert got["company"] == "Amazon"

    patched = client.patch(
        f"/v1/applications/{app['id']}", json={"status": "interviewing"}, headers=auth
    )
    assert patched.json()["status"] == "interviewing"

    listed = client.get("/v1/applications?status=interviewing", headers=auth).json()
    assert [a["id"] for a in listed] == [app["id"]]

    assert client.delete(f"/v1/applications/{app['id']}", headers=auth).status_code == 204
    assert client.get(f"/v1/applications/{app['id']}", headers=auth).status_code == 404


def test_patch_missing_application_is_404(client, auth):
    r = client.patch("/v1/applications/nope", json={"status": "rejected"}, headers=auth)
    assert r.status_code == 404


def test_validation_errors(client, auth):
    assert client.post("/v1/applications", json={"company": ""}, headers=auth).status_code == 422
    r = client.patch("/v1/applications/x", json={}, headers=auth)
    assert r.status_code == 422


def test_screen_time_upload_merges_with_health(client, auth, repo, s3):
    day = _today() - timedelta(days=1)
    repo.upsert_day(day, {"sleep_minutes": 400, "steps": 8000})
    r = client.post(
        "/v1/screen-time",
        json={
            "day": day.isoformat(),
            "apps": [
                {"package": "com.instagram.android", "minutes": 75},
                {"package": "com.linkedin.android", "minutes": 30},
            ],
        },
        headers=auth,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["screen_minutes"] == 105
    assert body["doomscroll_minutes"] == 75
    assert body["sleep_minutes"] == 400  # not overwritten

    keys = [o["Key"] for o in s3.list_objects_v2(Bucket="test-lake")["Contents"]]
    assert keys == [f"clean/screen_time/dt={day.isoformat()}/data.jsonl"]


def test_public_summary_has_no_company_names(client, auth, repo):
    today = _today()
    for company in ("Acme", "Globex"):
        client.post("/v1/applications", json={"company": company, "role": "SDE"}, headers=auth)
    repo.upsert_day(today, {"sleep_minutes": 420, "screen_minutes": 120, "doomscroll_minutes": 60})

    r = client.get("/public/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["applications_total"] == 2
    assert body["applications_today"] == 2
    assert body["last_night_sleep_hours"] == 7.0
    assert "Acme" not in r.text and "Globex" not in r.text
    assert r.headers["cache-control"].startswith("public")


def test_days_range_validation(client, auth):
    assert client.get("/v1/days?start=2026-02-01&end=2026-01-01", headers=auth).status_code == 422
    assert client.get("/v1/days?start=2024-01-01&end=2026-01-01", headers=auth).status_code == 422


def test_get_day_404(client, auth):
    assert client.get("/v1/days/2020-01-01", headers=auth).status_code == 404


def test_insight_endpoint(client, auth):
    r = client.get("/v1/insights/scroll-vs-sleep", headers=auth)
    assert r.status_code == 200
    assert r.json()["days_compared"] == 0


def test_public_timeseries_counts_only(client, auth, repo):
    today = _today()
    for company in ("Acme", "Globex"):
        client.post("/v1/applications", json={"company": company, "role": "SDE"}, headers=auth)
    repo.upsert_day(today - timedelta(days=1), {"sleep_minutes": 400, "steps": 9000})

    r = client.get("/public/timeseries?days=7")
    assert r.status_code == 200
    body = r.json()
    assert len(body["days"]) == 7  # gaps are filled
    assert body["days"][-1]["day"] == today.isoformat()
    assert body["days"][-1]["applications_sent"] == 2
    assert body["days"][-2]["sleep_minutes"] == 400
    assert body["status_counts"]["applied"] == 2
    assert "Acme" not in r.text and "Globex" not in r.text


def test_public_timeseries_range_limits(client):
    assert client.get("/public/timeseries?days=3").status_code == 422
    assert client.get("/public/timeseries?days=500").status_code == 422
