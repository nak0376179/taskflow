"""MCP のツール。メモリ内のクライアントで呼ぶ (HTTP の認証は scripts/mcp_smoke.py で確かめる)。"""

import pytest
from fastmcp import Client

from app import mcp_server, tasks


@pytest.fixture
def mcp(monkeypatch, owner):
    monkeypatch.setattr(mcp_server, "current_owner", lambda: owner)
    return mcp_server.build()


async def test_tools_roundtrip(mcp, owner):
    async with Client(mcp) as c:
        names = {t.name for t in await c.list_tools()}
        assert names == {
            "list_tasks",
            "get_task",
            "create_task",
            "update_task",
            "complete_task",
            "delete_task",
            "task_summary",
        }

        created = (
            await c.call_tool("create_task", {"title": "MCP", "due_date": "2030-01-01", "tags": ["x"]})
        ).structured_content
        tid = created["task_id"]
        assert tasks.get_task(owner, tid).title == "MCP"

        u = (
            await c.call_tool("update_task", {"task_id": tid, "clear_due_date": True, "priority": "high"})
        ).structured_content
        assert u["due_date"] is None and u["priority"] == "high"

        await c.call_tool("complete_task", {"task_id": tid})
        open_tasks = (await c.call_tool("list_tasks", {})).structured_content["result"]
        assert open_tasks == []
        all_tasks = (await c.call_tool("list_tasks", {"include_done": True})).structured_content["result"]
        assert [t["task_id"] for t in all_tasks] == [tid]

        await c.call_tool("delete_task", {"task_id": tid})
        r = await c.call_tool("get_task", {"task_id": tid}, raise_on_error=False)
        assert r.is_error


async def test_invalid_args_are_errors(mcp):
    async with Client(mcp) as c:
        r = await c.call_tool("create_task", {"title": "x", "status": "doing"}, raise_on_error=False)
        assert r.is_error
        r = await c.call_tool("update_task", {"task_id": "nope", "title": "x"}, raise_on_error=False)
        assert r.is_error
