"""MCP クライアント (Claude Code / GitHub Copilot) 用の個人アクセストークン。

Cognito のトークンは 1 時間で切れるので、MCP の設定ファイルに書いておく長期の鍵を別に発行する。
平文は発行時に 1 回だけ返し、テーブルには SHA-256 だけを置く。

テーブル TaskflowTokens: PK token_hash / GSI owner_index (owner_id)。
"""

import hashlib
import secrets
from datetime import UTC, datetime

from boto3.dynamodb.conditions import Key
from pydantic import BaseModel

from .aws import table
from .config import get_settings

PREFIX = "tfp_"
OWNER_INDEX = "owner_index"


class TokenInfo(BaseModel):
    token_id: str
    name: str
    hint: str  # 見分け用に平文の先頭だけ
    created_at: datetime
    last_used_at: datetime | None = None


class IssuedToken(TokenInfo):
    token: str


class TokenOwner(BaseModel):
    owner_id: str
    email: str
    token_id: str


def _tbl():
    return table(get_settings().tokens_table)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _info(item: dict) -> TokenInfo:
    return TokenInfo(
        token_id=item["token_id"],
        name=item["name"],
        hint=item["hint"],
        created_at=item["created_at"],
        last_used_at=item.get("last_used_at") or None,
    )


def issue(owner_id: str, email: str, name: str) -> IssuedToken:
    token = PREFIX + secrets.token_urlsafe(32)
    item = {
        "token_hash": _hash(token),
        "token_id": secrets.token_hex(8),
        "owner_id": owner_id,
        "email": email,
        "name": name.strip() or "MCP",
        "hint": token[: len(PREFIX) + 6],
        "created_at": _now(),
    }
    _tbl().put_item(Item=item)
    return IssuedToken(**_info(item).model_dump(), token=token)


def _owned(owner_id: str) -> list[dict]:
    res = _tbl().query(IndexName=OWNER_INDEX, KeyConditionExpression=Key("owner_id").eq(owner_id))
    return res["Items"]


def list_tokens(owner_id: str) -> list[TokenInfo]:
    return sorted((_info(i) for i in _owned(owner_id)), key=lambda t: t.created_at, reverse=True)


def revoke(owner_id: str, token_id: str) -> bool:
    for item in _owned(owner_id):
        if item["token_id"] == token_id:
            _tbl().delete_item(Key={"token_hash": item["token_hash"]})
            return True
    return False


def verify(token: str) -> TokenOwner | None:
    if not token.startswith(PREFIX):
        return None
    h = _hash(token)
    item = _tbl().get_item(Key={"token_hash": h}).get("Item")
    if not item:
        return None
    _tbl().update_item(
        Key={"token_hash": h},
        UpdateExpression="SET last_used_at = :t",
        ExpressionAttributeValues={":t": _now()},
    )
    return TokenOwner(owner_id=item["owner_id"], email=item.get("email", ""), token_id=item["token_id"])
