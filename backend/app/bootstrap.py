"""起動時の準備。

本番: COGNITO_USER_POOL_ID / COGNITO_CLIENT_ID を読むだけ (テーブル・プールは IaC 側で作る)。
ローカル (Floci): テーブル・ユーザープール・アプリクライアント・開発用ユーザーが無ければ作る。
何度流しても同じ結果になる。
"""

import logging
from datetime import date, timedelta

from . import tasks
from .auth import ids
from .aws import cognito, dynamodb
from .config import get_settings
from .tokens import OWNER_INDEX

log = logging.getLogger("taskflow.bootstrap")

CLIENT_NAME = "taskflow-web"


def ensure_tables() -> None:
    s = get_settings()
    ddb = dynamodb()
    existing = set(ddb.meta.client.list_tables()["TableNames"])
    if s.tasks_table not in existing:
        ddb.create_table(
            TableName=s.tasks_table,
            AttributeDefinitions=[
                {"AttributeName": "owner_id", "AttributeType": "S"},
                {"AttributeName": "task_id", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "owner_id", "KeyType": "HASH"},
                {"AttributeName": "task_id", "KeyType": "RANGE"},
            ],
            BillingMode="PAY_PER_REQUEST",
        ).wait_until_exists()
        log.info("created table %s", s.tasks_table)
    if s.tokens_table not in existing:
        ddb.create_table(
            TableName=s.tokens_table,
            AttributeDefinitions=[
                {"AttributeName": "token_hash", "AttributeType": "S"},
                {"AttributeName": "owner_id", "AttributeType": "S"},
            ],
            KeySchema=[{"AttributeName": "token_hash", "KeyType": "HASH"}],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": OWNER_INDEX,
                    "KeySchema": [{"AttributeName": "owner_id", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        ).wait_until_exists()
        log.info("created table %s", s.tokens_table)


def ensure_user_pool() -> tuple[str, str]:
    s = get_settings()
    c = cognito()
    pool_id = next(
        (p["Id"] for p in c.list_user_pools(MaxResults=60)["UserPools"] if p["Name"] == s.local_pool_name),
        None,
    )
    if not pool_id:
        # 本番と同じく、メールアドレスをユーザー名にする
        pool_id = c.create_user_pool(
            PoolName=s.local_pool_name,
            UsernameAttributes=["email"],
            AutoVerifiedAttributes=["email"],
            AdminCreateUserConfig={"AllowAdminCreateUserOnly": True},
        )["UserPool"]["Id"]
        log.info("created user pool %s", pool_id)

    client_id = next(
        (
            cl["ClientId"]
            for cl in c.list_user_pool_clients(UserPoolId=pool_id, MaxResults=60)["UserPoolClients"]
            if cl["ClientName"] == CLIENT_NAME
        ),
        None,
    )
    if not client_id:
        client_id = c.create_user_pool_client(
            UserPoolId=pool_id,
            ClientName=CLIENT_NAME,
            GenerateSecret=False,
            ExplicitAuthFlows=["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
        )["UserPoolClient"]["ClientId"]
        log.info("created app client %s", client_id)
    return pool_id, client_id


def ensure_dev_admin(pool_id: str) -> str | None:
    """開発用ユーザーを用意し、作ったときは sub を返す。"""
    s = get_settings()
    c = cognito()
    try:
        c.admin_get_user(UserPoolId=pool_id, Username=s.dev_admin_email)
        return None
    except c.exceptions.UserNotFoundException:
        pass
    user = c.admin_create_user(
        UserPoolId=pool_id,
        Username=s.dev_admin_email,
        UserAttributes=[
            {"Name": "email", "Value": s.dev_admin_email},
            {"Name": "email_verified", "Value": "true"},
        ],
        MessageAction="SUPPRESS",
    )["User"]
    c.admin_set_user_password(
        UserPoolId=pool_id, Username=s.dev_admin_email, Password=s.dev_admin_password, Permanent=True
    )
    sub = next(a["Value"] for a in user["Attributes"] if a["Name"] == "sub")
    log.info("created dev user %s (login: admin / admin)", s.dev_admin_email)
    return sub


SAMPLE_TASKS = [
    tasks.TaskCreate(
        title="TaskFlow を触ってみる",
        description="カードをクリックすると編集できます。状態はドラッグか編集画面で変えられます。",
        status="in_progress",
        priority="high",
        due_date=date.today(),
        tags=["はじめに"],
    ),
    tasks.TaskCreate(
        title="Claude Code から MCP でタスクを操作する",
        description="右上のメニュー →「MCP 連携」でトークンを発行し、表示されたコマンドで登録します。",
        priority="medium",
        due_date=date.today() + timedelta(days=3),
        tags=["はじめに", "MCP"],
    ),
    tasks.TaskCreate(
        title="GitHub Copilot (VS Code) にも登録する",
        description=".vscode/mcp.json の例を「MCP 連携」画面に出しています。",
        priority="low",
        tags=["MCP"],
    ),
    tasks.TaskCreate(title="ログインできることを確かめる", status="done", tags=["はじめに"]),
]


def run() -> None:
    s = get_settings()
    if not s.is_local:
        if not (s.cognito_user_pool_id and s.cognito_client_id):
            raise RuntimeError("COGNITO_USER_POOL_ID と COGNITO_CLIENT_ID を設定してください")
        ids.user_pool_id, ids.client_id = s.cognito_user_pool_id, s.cognito_client_id
        return

    ensure_tables()
    if s.cognito_user_pool_id and s.cognito_client_id:
        ids.user_pool_id, ids.client_id = s.cognito_user_pool_id, s.cognito_client_id
    else:
        ids.user_pool_id, ids.client_id = ensure_user_pool()
    new_sub = ensure_dev_admin(ids.user_pool_id)
    if new_sub and s.seed_sample_tasks and not tasks.list_tasks(new_sub):
        for t in SAMPLE_TASKS:
            tasks.create_task(new_sub, t)
    log.info("local mode: pool=%s client=%s endpoint=%s", ids.user_pool_id, ids.client_id, s.aws_endpoint_url)
