from __future__ import annotations

import os
from collections.abc import Iterator

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ["AWS_REGION"] = "us-east-1"
os.environ["LIFE_API_KEY"] = "test-key"
os.environ["LIFE_TIMEZONE"] = "UTC"

from life_api.api import deps
from life_api.api.app import create_app
from life_api.storage.dynamo import LifeRepository
from life_api.storage.lake import Lake

BUCKET = "test-lake"
API_KEY = "test-key"


@pytest.fixture
def aws() -> Iterator[None]:
    with mock_aws():
        yield


@pytest.fixture
def repo(aws: None) -> LifeRepository:
    ddb = boto3.resource("dynamodb", region_name="us-east-1")
    table = ddb.create_table(
        TableName="life-test",
        KeySchema=[
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    return LifeRepository(table)


@pytest.fixture
def s3(aws: None):
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket=BUCKET)
    return client


@pytest.fixture
def lake(s3) -> Lake:
    return Lake(s3, BUCKET)


@pytest.fixture
def client(repo: LifeRepository, lake: Lake) -> TestClient:
    app = create_app()
    app.dependency_overrides[deps.get_repo] = lambda: repo
    app.dependency_overrides[deps.get_lake] = lambda: lake
    app.dependency_overrides[deps.get_expected_api_key] = lambda: API_KEY
    return TestClient(app)


@pytest.fixture
def auth() -> dict[str, str]:
    return {"X-API-Key": API_KEY}
