"""One-time (and, in Testing mode, weekly) Google Health OAuth consent.

Opens your browser, catches the redirect on http://localhost:8765/callback,
exchanges the code for tokens, prints your Google Health identity and stores
the client + token in SSM so the ingest Lambda can use them.

Usage:
    python scripts/google_health_auth.py --client-id ... --client-secret ... \
        [--token-param /life-api/google-health/token] \
        [--client-param /life-api/google-health/client] [--region us-east-1] [--no-ssm]

Add http://localhost:8765/callback as an Authorized redirect URI on your
OAuth client in Google Cloud Console first.
"""

from __future__ import annotations

import argparse
import http.server
import json
import secrets
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path

import boto3
import httpx

from life_api.ingest.google_health import AUTH_URL, BASE_URL, SCOPES, TOKEN_URL

REDIRECT_URI = "http://localhost:8765/callback"


def _wait_for_code(expected_state: str) -> str:
    result: dict[str, str] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if query.get("state", [""])[0] != expected_state:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"State mismatch.")
                return
            result["code"] = query.get("code", [""])[0]
            result["error"] = query.get("error", [""])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Done. You can close this tab and return to the terminal.")

        def log_message(self, *args: object) -> None:
            pass

    server = http.server.HTTPServer(("localhost", 8765), Handler)
    thread = threading.Thread(target=server.handle_request)
    thread.start()
    thread.join(timeout=300)
    server.server_close()
    if result.get("error") or not result.get("code"):
        raise SystemExit(f"Authorization failed: {result.get('error') or 'timed out'}")
    return result["code"]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--client-id", required=True)
    p.add_argument("--client-secret", required=True)
    p.add_argument("--token-param", default="/life-api/prod/google-health/token")
    p.add_argument("--client-param", default="/life-api/prod/google-health/client")
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--no-ssm", action="store_true", help="save to a local file instead")
    args = p.parse_args()

    state = secrets.token_urlsafe(16)
    url = (
        AUTH_URL
        + "?"
        + urllib.parse.urlencode(
            {
                "client_id": args.client_id,
                "redirect_uri": REDIRECT_URI,
                "response_type": "code",
                "access_type": "offline",
                "prompt": "consent",
                "scope": " ".join(SCOPES),
                "state": state,
            }
        )
    )
    print("Opening browser for Google consent...\n", url, "\n")
    webbrowser.open(url)
    code = _wait_for_code(state)

    resp = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": args.client_id,
            "client_secret": args.client_secret,
            "redirect_uri": REDIRECT_URI,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "refresh_token" not in data:
        raise SystemExit("No refresh token returned. Remove the app's access and try again.")

    token = {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_at": time.time() + float(data.get("expires_in", 3600)),
    }
    ident = httpx.get(
        f"{BASE_URL}/users/me/identity",
        headers={"Authorization": f"Bearer {data['access_token']}"},
        timeout=30,
    )
    print("Identity:", ident.status_code, ident.text[:300])

    client = {"client_id": args.client_id, "client_secret": args.client_secret}
    if args.no_ssm:
        Path(".google_health_token.json").write_text(json.dumps({"client": client, "token": token}))
        print("Saved to .google_health_token.json (git-ignored).")
        return
    ssm = boto3.client("ssm", region_name=args.region)
    ssm.put_parameter(
        Name=args.client_param, Value=json.dumps(client), Type="SecureString", Overwrite=True
    )
    ssm.put_parameter(
        Name=args.token_param, Value=json.dumps(token), Type="SecureString", Overwrite=True
    )
    print(f"Stored client in {args.client_param} and token in {args.token_param}.")


if __name__ == "__main__":
    main()
