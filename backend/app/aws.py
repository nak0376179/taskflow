"""boto3 のクライアント。ローカルでは AWS_ENDPOINT_URL (Floci) へ向ける。"""

from functools import lru_cache

import boto3

from .config import get_settings


def _kwargs() -> dict:
    s = get_settings()
    kw: dict = {"region_name": s.aws_region}
    if s.aws_endpoint_url:
        kw["endpoint_url"] = s.aws_endpoint_url
    return kw


@lru_cache
def dynamodb():
    return boto3.resource("dynamodb", **_kwargs())


@lru_cache
def cognito():
    return boto3.client("cognito-idp", **_kwargs())


def table(name: str):
    return dynamodb().Table(name)
