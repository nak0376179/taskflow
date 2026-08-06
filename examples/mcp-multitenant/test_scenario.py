"""End-to-end scenario against the multi-tenant MCP server.

Run the server first (uvicorn server:app --port 8766), then:
    python test_scenario.py
"""
import asyncio
import json

import httpx2
from mcp.client import Client
from mcp.client.streamable_http import streamable_http_client

URL = "http://localhost:8766/mcp"


def client_as(token: str) -> Client:
    http = httpx2.AsyncClient(headers={"Authorization": f"Bearer {token}"})
    return Client(streamable_http_client(URL, http_client=http))


async def call(client: Client, tool: str, args: dict | None = None):
    r = await client.call_tool(tool, args or {})
    if r.is_error:
        return f"DENIED: {r.content[0].text}"
    sc = r.structured_content
    if sc is None:
        # plain-dict returns have no output schema; the payload is JSON text
        texts = [c.text for c in r.content]
        try:
            return json.loads(texts[0]) if len(texts) == 1 else texts
        except (json.JSONDecodeError, IndexError):
            return texts
    # scalar/list returns are wrapped as {"result": ...}; dict returns are not
    if isinstance(sc, dict) and set(sc.keys()) == {"result"}:
        return sc["result"]
    return sc


async def main():
    ok = 0

    async with client_as("token-alice") as alice, \
               client_as("token-bob") as bob, \
               client_as("token-carol") as carol:

        print("== 1. alice がグループ(テナント)を作成 → 自動的に owner ==")
        g = await call(alice, "create_group", {"name": "設計チーム"})
        gid = g["group_id"]
        print("  ", g)

        print("== 2. alice がタスクを追加 ==")
        print("  ", await call(alice, "add_task", {"group_id": gid, "title": "API設計レビュー", "priority": "high"}))

        print("== 3. bob(未招待)は同じ group_id を指定しても見えない ==")
        r = await call(bob, "list_tasks", {"group_id": gid})
        print("  ", r)
        assert str(r).startswith("DENIED"); ok += 1

        print("== 4. bob(member ではない)は招待もできない ==")
        r = await call(bob, "invite_user", {"group_id": gid, "username": "carol"})
        print("  ", r)
        assert str(r).startswith("DENIED"); ok += 1

        print("== 5. owner の alice が bob を招待 ==")
        print("  ", await call(alice, "invite_user", {"group_id": gid, "username": "bob"}))

        print("== 6. 招待後の bob はタスクが見える・追加できる ==")
        print("  ", await call(bob, "list_tasks", {"group_id": gid}))
        print("  ", await call(bob, "add_task", {"group_id": gid, "title": "実装タスク"}))

        print("== 7. member の bob は削除(owner 限定)はできない ==")
        r = await call(bob, "delete_task", {"group_id": gid, "task_id": "2"})
        print("  ", r)
        assert str(r).startswith("DENIED"); ok += 1

        print("== 8. owner の alice は削除できる ==")
        print("  ", await call(alice, "delete_task", {"group_id": gid, "task_id": "2"}))

        print("== 9. carol は自分のグループを持てる(完全分離) ==")
        g2 = await call(carol, "create_group", {"name": "carol の個人スペース"})
        print("  ", g2)
        print("   carol の所属:", await call(carol, "list_my_groups"))
        r = await call(carol, "list_tasks", {"group_id": gid})
        print("   carol から alice のグループ:", r)
        assert str(r).startswith("DENIED"); ok += 1

    print("== 10. トークン無し / 不正トークンは HTTP レイヤーで 401 ==")
    async with httpx2.AsyncClient() as raw:
        r1 = await raw.post(URL, json={}, headers={"MCP-Method": "tools/list"})
        r2 = await raw.post(URL, json={}, headers={"MCP-Method": "tools/list", "Authorization": "Bearer bogus"})
        print(f"   no token: {r1.status_code}, bad token: {r2.status_code}")
        assert r1.status_code == 401 and r2.status_code == 401; ok += 2

    print(f"\nAll {ok} permission checks behaved as expected ✔")


asyncio.run(main())
