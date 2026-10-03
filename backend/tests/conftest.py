import os

import pytest
from moto import mock_aws

# 本物の AWS や Floci に向かないよう、moto 用のダミーにする
os.environ.pop("AWS_ENDPOINT_URL", None)
os.environ.update(
    AWS_ACCESS_KEY_ID="testing",
    AWS_SECRET_ACCESS_KEY="testing",
    AWS_DEFAULT_REGION="ap-northeast-1",
)


@pytest.fixture(autouse=True)
def aws():
    from app import aws as aws_mod
    from app import bootstrap
    from app.config import get_settings

    get_settings.cache_clear()
    aws_mod.dynamodb.cache_clear()
    aws_mod.cognito.cache_clear()
    with mock_aws():
        bootstrap.ensure_tables()
        yield


@pytest.fixture
def owner() -> str:
    return "user-1"
