"""DynamoDB repository (single-table design).

Item layout
-----------
==========  ==============  ==========================================
pk          sk              what
==========  ==============  ==========================================
``APP``     ``<app id>``    one job application
``DAY``     ``YYYY-MM-DD``  merged daily metrics (health + screen time)
==========  ==============  ==========================================

A constant partition key is fine at one-person scale (a few thousand items).
If this ever served many users, the partition key would become ``USER#<id>``.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from life_api.config import Settings
from life_api.domain import Application, ApplicationUpdate, DaySummary

APP_PK = "APP"
DAY_PK = "DAY"


class NotFoundError(Exception):
    pass


def _to_dynamo(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _to_dynamo(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_dynamo(v) for v in value]
    return value


def _from_dynamo(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: _from_dynamo(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_from_dynamo(v) for v in value]
    return value


def _strip_keys(item: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in _from_dynamo(item).items() if k not in ("pk", "sk")}


class LifeRepository:
    def __init__(self, table: Any) -> None:
        self._table = table

    @classmethod
    def from_settings(cls, settings: Settings) -> LifeRepository:
        resource = boto3.resource("dynamodb", region_name=settings.aws_region)
        return cls(resource.Table(settings.table_name))

    # ---------------------------------------------------------------- applications
    def put_application(self, app: Application) -> None:
        item = {"pk": APP_PK, "sk": app.id, **app.model_dump(mode="json", exclude_none=True)}
        self._table.put_item(Item=_to_dynamo(item))

    def get_application(self, app_id: str) -> Application:
        resp = self._table.get_item(Key={"pk": APP_PK, "sk": app_id})
        if "Item" not in resp:
            raise NotFoundError(app_id)
        return Application.model_validate(_strip_keys(resp["Item"]))

    def list_applications(self) -> list[Application]:
        items = self._query_all(Key("pk").eq(APP_PK))
        apps = [Application.model_validate(_strip_keys(i)) for i in items]
        return sorted(apps, key=lambda a: (a.applied_on, a.created_at), reverse=True)

    def update_application(
        self, app_id: str, update: ApplicationUpdate, updated_at: str
    ) -> Application:
        fields = {**update.model_dump(mode="json", exclude_none=True), "updated_at": updated_at}
        names = {f"#{k}": k for k in fields}
        values = {f":{k}": v for k, v in fields.items()}
        expr = "SET " + ", ".join(f"#{k} = :{k}" for k in fields)
        try:
            resp = self._table.update_item(
                Key={"pk": APP_PK, "sk": app_id},
                UpdateExpression=expr,
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=_to_dynamo(values),
                ConditionExpression="attribute_exists(pk)",
                ReturnValues="ALL_NEW",
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise NotFoundError(app_id) from exc
            raise
        return Application.model_validate(_strip_keys(resp["Attributes"]))

    def delete_application(self, app_id: str) -> None:
        try:
            self._table.delete_item(
                Key={"pk": APP_PK, "sk": app_id}, ConditionExpression="attribute_exists(pk)"
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise NotFoundError(app_id) from exc
            raise

    # ------------------------------------------------------------------------ days
    def upsert_day(self, day: date, fields: dict[str, Any]) -> None:
        """Merge ``fields`` into the day's item. ``None`` values are skipped, so a
        health ingest never wipes screen-time numbers and vice versa."""
        fields = {k: v for k, v in fields.items() if v is not None and k != "day"}
        if not fields:
            return
        self._table.update_item(
            Key={"pk": DAY_PK, "sk": day.isoformat()},
            UpdateExpression="SET " + ", ".join(f"#{k} = :{k}" for k in fields),
            ExpressionAttributeNames={f"#{k}": k for k in fields},
            ExpressionAttributeValues=_to_dynamo({f":{k}": v for k, v in fields.items()}),
        )

    def get_days(self, start: date, end: date) -> list[DaySummary]:
        """Days in ``[start, end]`` inclusive, oldest first."""
        items = self._query_all(
            Key("pk").eq(DAY_PK) & Key("sk").between(start.isoformat(), end.isoformat())
        )
        return [DaySummary.model_validate({**_strip_keys(i), "day": i["sk"]}) for i in items]

    # --------------------------------------------------------------------- helpers
    def _query_all(self, condition: Any) -> Iterable[dict[str, Any]]:
        kwargs: dict[str, Any] = {"KeyConditionExpression": condition}
        items: list[dict[str, Any]] = []
        while True:
            resp = self._table.query(**kwargs)
            items.extend(resp.get("Items", []))
            if "LastEvaluatedKey" not in resp:
                return items
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
