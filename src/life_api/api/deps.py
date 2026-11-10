"""FastAPI dependencies. Tests override these with ``app.dependency_overrides``."""

from __future__ import annotations

import hmac
from functools import lru_cache
from typing import Annotated

import boto3
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from life_api.config import Settings, get_settings
from life_api.storage.dynamo import LifeRepository
from life_api.storage.lake import Lake

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@lru_cache
def _repo() -> LifeRepository:
    return LifeRepository.from_settings(get_settings())


@lru_cache
def _lake() -> Lake:
    return Lake.from_settings(get_settings())


@lru_cache
def _expected_api_key() -> str | None:
    settings = get_settings()
    if settings.api_key:
        return settings.api_key
    if settings.api_key_param:
        ssm = boto3.client("ssm", region_name=settings.aws_region)
        return ssm.get_parameter(Name=settings.api_key_param, WithDecryption=True)["Parameter"][
            "Value"
        ]
    return None


def get_repo() -> LifeRepository:
    return _repo()


def get_lake() -> Lake:
    return _lake()


def get_expected_api_key() -> str | None:
    return _expected_api_key()


def require_api_key(
    provided: Annotated[str | None, Security(_api_key_header)],
    expected: Annotated[str | None, Depends(get_expected_api_key)],
) -> None:
    if not expected:  # fail closed if the deployment is misconfigured
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "API key not configured")
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing API key")


SettingsDep = Annotated[Settings, Depends(get_settings)]
RepoDep = Annotated[LifeRepository, Depends(get_repo)]
LakeDep = Annotated[Lake, Depends(get_lake)]
