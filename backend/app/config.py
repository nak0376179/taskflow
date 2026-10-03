"""環境変数から読む設定。

ローカル (Floci) か本番 (AWS) かは AWS_ENDPOINT_URL の有無で決まる。
ローカルでは起動時にテーブル・ユーザープール・開発用ユーザーを自動で用意し、
admin/admin でのログインを許す。本番ではどちらも無効 (明示的に有効にもできない)。
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    aws_endpoint_url: str | None = None
    aws_region: str = Field(default="ap-northeast-1", validation_alias="AWS_DEFAULT_REGION")

    tasks_table: str = "TaskflowTasks"
    tokens_table: str = "TaskflowTokens"

    # 本番では必須。ローカルでは未指定なら起動時にプール名で探す/作る
    cognito_user_pool_id: str | None = None
    cognito_client_id: str | None = None
    # 既定は https://cognito-idp.<region>.amazonaws.com/<pool> (ローカルは <endpoint>/<pool>)
    cognito_issuer: str | None = None

    local_pool_name: str = "taskflow-local"
    dev_admin_email: str = "admin@example.com"
    dev_admin_password: str = "Admin-local-1!"
    # ローカルでもサンプルのタスクを入れたくなければ false
    seed_sample_tasks: bool = True

    # MCP の保護リソースのメタデータに載せる、このサーバの外向きの URL
    public_base_url: str = "http://localhost:8050"
    cors_origins: list[str] = ["http://localhost:5189"]

    @property
    def is_local(self) -> bool:
        return bool(self.aws_endpoint_url)

    @property
    def dev_login(self) -> bool:
        """admin/admin を開発用ユーザーに読み替えるか。ローカル (Floci) のときだけ。"""
        return self.is_local


@lru_cache
def get_settings() -> Settings:
    return Settings()
