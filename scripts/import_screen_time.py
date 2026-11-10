"""Upload a screen-time CSV (date,package,app_name,minutes) to the Life API.

Usage:
    python scripts/import_screen_time.py usage.csv --api https://xxxx.execute-api.us-east-1.amazonaws.com
    (reads the API key from the LIFE_API_KEY environment variable)
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import httpx

from life_api.ingest.screen_time import parse_csv


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("csv", type=Path)
    p.add_argument("--api", required=True)
    args = p.parse_args()

    key = os.environ.get("LIFE_API_KEY")
    if not key:
        raise SystemExit("Set LIFE_API_KEY first.")

    uploads = parse_csv(args.csv.read_text(encoding="utf-8"))
    with httpx.Client(base_url=args.api.rstrip("/"), headers={"X-API-Key": key}, timeout=30) as c:
        for upload in uploads:
            r = c.post("/v1/screen-time", json=upload.model_dump(mode="json"))
            r.raise_for_status()
            day = r.json()
            print(
                f"{upload.day}: {day['screen_minutes']} min total, "
                f"{day['doomscroll_minutes']} min doomscrolling"
            )


if __name__ == "__main__":
    main()
