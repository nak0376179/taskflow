"""MCP サーバ (FastMCP、Streamable HTTP で /mcp)。

Claude Code や GitHub Copilot から、画面と同じタスクを操作する。
認証は Bearer トークン (画面の「MCP 連携」で発行する tfp_...、または Cognito のアクセストークン)。
"""

import asyncio
from datetime import date
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AccessToken, TokenVerifier
from fastmcp.server.dependencies import get_access_token
from pydantic import Field

from . import auth, tasks
from .config import get_settings


class TaskflowTokenVerifier(TokenVerifier):
    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            p = await asyncio.to_thread(auth.principal_from_bearer, token)
        except auth.AuthError:
            return None
        return AccessToken(
            token=token,
            client_id=p.via,
            scopes=[],
            subject=p.owner_id,
            claims={"sub": p.owner_id, "email": p.email, "via": p.via},
        )


def current_owner() -> str:
    tok = get_access_token()
    if not tok or not tok.claims.get("sub"):
        raise ToolError("認証されていません")
    return tok.claims["sub"]


INSTRUCTIONS = """\
TaskFlow はログインしたユーザー個人のタスク管理です。ツールはすべてトークンの持ち主のタスクだけを扱います。
- 状態 status: todo (未着手) / in_progress (進行中) / done (完了)
- 優先度 priority: low / medium / high
- 期限 due_date: YYYY-MM-DD
タスクを指すときは task_id を使ってください。分からなければ list_tasks で探します。
"""


def build() -> FastMCP:
    s = get_settings()
    mcp = FastMCP(
        "taskflow",
        instructions=INSTRUCTIONS,
        auth=TaskflowTokenVerifier(base_url=s.public_base_url),
    )

    StatusArg = Annotated[tasks.Status | None, Field(description="状態で絞る")]

    @mcp.tool(annotations={"readOnlyHint": True})
    def list_tasks(
        status: StatusArg = None,
        tag: Annotated[str | None, Field(description="このタグが付いたものだけ")] = None,
        query: Annotated[str | None, Field(description="タイトル・説明・タグの部分一致")] = None,
        include_done: Annotated[bool, Field(description="status 未指定のとき完了済みも含めるか")] = False,
    ) -> list[tasks.Task]:
        """タスクを一覧する。未完了 → 期限の近い順 → 優先度の高い順に並ぶ。"""
        return tasks.list_tasks(current_owner(), status=status, tag=tag, query=query, include_done=include_done)

    @mcp.tool(annotations={"readOnlyHint": True})
    def get_task(task_id: str) -> tasks.Task:
        """タスクを 1 件、説明まで含めて取得する。"""
        try:
            return tasks.get_task(current_owner(), task_id)
        except tasks.TaskNotFound:
            raise ToolError(f"タスク {task_id} がありません") from None

    @mcp.tool
    def create_task(
        title: Annotated[str, Field(min_length=1, max_length=200)],
        description: str = "",
        priority: tasks.Priority = "medium",
        due_date: Annotated[date | None, Field(description="期限 (YYYY-MM-DD)")] = None,
        tags: list[str] | None = None,
        status: tasks.Status = "todo",
    ) -> tasks.Task:
        """タスクを作る。"""
        data = tasks.TaskCreate(
            title=title,
            description=description,
            priority=priority,
            due_date=due_date,
            tags=tags or [],
            status=status,
        )
        return tasks.create_task(current_owner(), data)

    @mcp.tool(annotations={"idempotentHint": True})
    def update_task(
        task_id: str,
        title: str | None = None,
        description: str | None = None,
        status: tasks.Status | None = None,
        priority: tasks.Priority | None = None,
        due_date: Annotated[date | None, Field(description="期限 (YYYY-MM-DD)")] = None,
        clear_due_date: Annotated[bool, Field(description="true で期限を消す")] = False,
        tags: Annotated[list[str] | None, Field(description="指定するとタグを丸ごと置き換える")] = None,
    ) -> tasks.Task:
        """タスクを書き換える。指定した項目だけが変わる。"""
        fields = {
            k: v
            for k, v in {
                "title": title,
                "description": description,
                "status": status,
                "priority": priority,
                "due_date": due_date,
                "tags": tags,
            }.items()
            if v is not None
        }
        if clear_due_date:
            fields["due_date"] = None
        try:
            return tasks.update_task(current_owner(), task_id, tasks.TaskUpdate(**fields))
        except tasks.TaskNotFound:
            raise ToolError(f"タスク {task_id} がありません") from None

    @mcp.tool(annotations={"idempotentHint": True})
    def complete_task(task_id: str) -> tasks.Task:
        """タスクを完了にする。"""
        try:
            return tasks.update_task(current_owner(), task_id, tasks.TaskUpdate(status="done"))
        except tasks.TaskNotFound:
            raise ToolError(f"タスク {task_id} がありません") from None

    @mcp.tool(annotations={"destructiveHint": True})
    def delete_task(task_id: str) -> str:
        """タスクを削除する。元に戻せない。"""
        try:
            tasks.delete_task(current_owner(), task_id)
        except tasks.TaskNotFound:
            raise ToolError(f"タスク {task_id} がありません") from None
        return f"削除しました: {task_id}"

    @mcp.tool(annotations={"readOnlyHint": True})
    def task_summary() -> dict:
        """状態ごとの件数と、期限切れの件数。"""
        tok = get_access_token()
        return {"email": tok.claims.get("email", "") if tok else "", **tasks.summary(current_owner())}

    return mcp
