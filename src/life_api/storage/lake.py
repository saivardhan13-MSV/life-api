"""S3 data lake writer.

Layout (all partitions are Hive style so Athena partition projection works)::

    raw/source=<source>/dataset=<dataset>/dt=YYYY-MM-DD/<name>.json   verbatim API payloads
    clean/<dataset>/dt=YYYY-MM-DD/<name>.jsonl                         flattened, typed rows
    curated/...                                                        Parquet, built by dbt

Writes overwrite the same key for the same day, so re-running a job is idempotent.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any

import boto3

from life_api.config import Settings


class Lake:
    def __init__(self, s3_client: Any, bucket: str) -> None:
        self._s3 = s3_client
        self.bucket = bucket

    @classmethod
    def from_settings(cls, settings: Settings) -> Lake:
        return cls(boto3.client("s3", region_name=settings.aws_region), settings.lake_bucket)

    def write_raw(
        self, source: str, dataset: str, dt: date, payload: Any, name: str = "data"
    ) -> str:
        key = f"raw/source={source}/dataset={dataset}/dt={dt.isoformat()}/{name}.json"
        self._put(key, json.dumps(payload, default=str), "application/json")
        return key

    def write_records(
        self, dataset: str, dt: date, records: list[dict[str, Any]], name: str = "data"
    ) -> str:
        ingested_at = datetime.now(UTC).isoformat()
        body = "\n".join(
            json.dumps({**r, "_ingested_at": ingested_at}, default=str) for r in records
        )
        key = f"clean/{dataset}/dt={dt.isoformat()}/{name}.jsonl"
        self._put(key, body + ("\n" if body else ""), "application/x-ndjson")
        return key

    def _put(self, key: str, body: str, content_type: str) -> None:
        self._s3.put_object(
            Bucket=self.bucket, Key=key, Body=body.encode("utf-8"), ContentType=content_type
        )
