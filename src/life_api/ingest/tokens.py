"""OAuth client + token persistence in SSM Parameter Store (SecureString, free tier)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Protocol

import boto3


@dataclass(frozen=True)
class OAuthClientConfig:
    client_id: str
    client_secret: str


@dataclass
class Token:
    access_token: str
    refresh_token: str
    expires_at: float  # unix seconds


class TokenStore(Protocol):
    def load(self) -> Token: ...
    def save(self, token: Token) -> None: ...


class SsmTokenStore:
    def __init__(self, ssm_client: Any, token_param: str) -> None:
        self._ssm = ssm_client
        self._param = token_param

    @classmethod
    def create(cls, token_param: str, region: str) -> SsmTokenStore:
        return cls(boto3.client("ssm", region_name=region), token_param)

    def load(self) -> Token:
        raw = self._ssm.get_parameter(Name=self._param, WithDecryption=True)["Parameter"]["Value"]
        data = json.loads(raw)
        return Token(
            access_token=data.get("access_token", ""),
            refresh_token=data["refresh_token"],
            expires_at=float(data.get("expires_at", 0)),
        )

    def save(self, token: Token) -> None:
        self._ssm.put_parameter(
            Name=self._param, Value=json.dumps(asdict(token)), Type="SecureString", Overwrite=True
        )


def load_client_config(ssm_client: Any, client_param: str) -> OAuthClientConfig:
    raw = ssm_client.get_parameter(Name=client_param, WithDecryption=True)["Parameter"]["Value"]
    data = json.loads(raw)
    return OAuthClientConfig(client_id=data["client_id"], client_secret=data["client_secret"])
