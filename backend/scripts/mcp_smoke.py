"""動いているサーバの /mcp を、実際の MCP クライアントで一通り叩いて確かめる。

    uv run python scripts/mcp_smoke.py                 # admin/admin でログインしてトークンを発行して使う (ローカル)
    uv run python scripts/mcp_smoke.py --token tfp_... # 発行済みのトークンで

作ったタスクは最後に消す。
"""

import argparse
import asyncio
import json

import httpx
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


def issue_token(base: str) -> tuple[str, str, str]:
    r = httpx.post(f"{base}/api/auth/login", json={"username": "admin", "password": "admin"})
    r.raise_for_status()
    access = r.json()["access_token"]
    h = {"Authorization": f"Bearer {access}"}
    t = httpx.post(f"{base}/api/tokens", json={"name": "mcp_smoke"}, headers=h)
    t.raise_for_status()
    return t.json()["token"], t.json()["token_id"], access


def data(result):
    return result.structured_content if result.structured_content is not None else result.data


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8050")
    ap.add_argument("--token")
    args = ap.parse_args()

    token_id = access = None
    token = args.token
    if not token:
        token, token_id, access = issue_token(args.base)

    # トークンなしは 401 になること
    r = httpx.post(f"{args.base}/mcp", json={}, headers={"Accept": "application/json, text/event-stream"})
    assert r.status_code == 401, r.status_code
    print("no token -> 401 OK")

    transport = StreamableHttpTransport(f"{args.base}/mcp", auth=token)
    async with Client(transport) as c:
        names = sorted(t.name for t in await c.list_tools())
        print("tools:", names)

        created = data(
            await c.call_tool(
                "create_task",
                {"title": "MCP から作ったタスク", "priority": "high", "due_date": "2030-01-02", "tags": ["mcp"]},
            )
        )
        tid = created["task_id"]
        print("created:", tid, created["title"], created["due_date"])

        updated = data(
            await c.call_tool("update_task", {"task_id": tid, "status": "in_progress", "clear_due_date": True})
        )
        assert updated["status"] == "in_progress" and updated["due_date"] is None, updated
        print("updated:", updated["status"], updated["due_date"])

        found = data(await c.call_tool("list_tasks", {"tag": "mcp"}))
        found = found.get("result", found) if isinstance(found, dict) else found
        assert any(t["task_id"] == tid for t in found), found
        print("list_tasks(tag=mcp):", len(found))

        done = data(await c.call_tool("complete_task", {"task_id": tid}))
        assert done["status"] == "done" and done["completed_at"], done
        print("summary:", json.dumps(data(await c.call_tool("task_summary", {})), ensure_ascii=False))

        print(data(await c.call_tool("delete_task", {"task_id": tid})))
        bad = await c.call_tool("get_task", {"task_id": tid}, raise_on_error=False)
        assert bad.is_error, bad
        print("get deleted -> error OK:", bad.content[0].text)

    if token_id and access:
        httpx.delete(
            f"{args.base}/api/tokens/{token_id}", headers={"Authorization": f"Bearer {access}"}
        ).raise_for_status()
        r = httpx.post(
            f"{args.base}/mcp",
            json={},
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json, text/event-stream"},
        )
        assert r.status_code == 401, r.status_code
        print("revoked token -> 401 OK")
    print("ALL OK")


if __name__ == "__main__":
    asyncio.run(main())
