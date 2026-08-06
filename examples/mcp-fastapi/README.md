# MCP 2026-07-28 仕様 × FastAPI 検証サンプル

MCP の 2026-07-28 版仕様を FastAPI 上で動かす最小構成のサンプルです。
**MCP Python SDK v2（`mcp==2.0.0`）が 2026-07-28 仕様に完全対応しており、FastAPI で問題なく利用できます。**

## 2026-07-28 仕様の要点

- **プロトコルレイヤーのステートレス化**（目玉変更）: プロトコルレベルのセッションと
  `Mcp-Session-Id` ヘッダーが Streamable HTTP トランスポートから削除
- **HTTP サーフェスの標準化**: `MCP-Method` / `MCP-Name` ヘッダーで通常の HTTP
  インフラ（LB・ゲートウェイ等）が MCP トラフィックをルーティング可能に
- **リクエスト単位の `_meta` エンベロープ**: セッションが無い代わりに、各リクエストが
  `io.modelcontextprotocol/protocolVersion` と `io.modelcontextprotocol/clientCapabilities` を携行
- Tasks は `io.modelcontextprotocol/tasks` 拡張へ移動、通知は `subscriptions/listen` に一本化
- Roots / Sampling / Logging および HTTP+SSE トランスポートは非推奨（12ヶ月の猶予付き）

## 実行方法

```bash
cd examples/mcp-fastapi
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --port 8765
```

## 動作確認

### SDK クライアント（推奨 — エンベロープ等は自動処理）

```python
import asyncio
from mcp.client import Client

async def main():
    async with Client("http://localhost:8765/mcp") as client:
        tools = await client.list_tools()
        print([t.name for t in tools.tools])          # ['add_task', 'list_tasks']
        r = await client.call_tool("add_task", {"title": "hello", "priority": "high"})
        print(r.structured_content)

asyncio.run(main())
```

検証結果: ネゴシエートされたプロトコルバージョンは **`2026-07-28`**。

### curl（生プロトコル — initialize 不要・セッションレス）

```bash
curl -s -X POST localhost:8765/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'MCP-Protocol-Version: 2026-07-28' \
  -H 'MCP-Method: tools/call' \
  -H 'MCP-Name: add_task' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{
        "name":"add_task",
        "arguments":{"title":"try MCP 2026-07-28","priority":"high"},
        "_meta":{
          "io.modelcontextprotocol/protocolVersion":"2026-07-28",
          "io.modelcontextprotocol/clientCapabilities":{}
        }}}'
```

## FastAPI 組み込み時の注意点（ハマりどころ)

1. **`stateless_http=True` を指定する** — 省略すると旧来のセッションベース動作になり、
   `Mcp-Session-Id` が返り、ネゴシエーションも `2025-11-25` に留まる
2. **親アプリの lifespan でセッションマネージャを起動する** — FastAPI はマウントした
   サブアプリの lifespan を実行しないため、忘れると
   `RuntimeError: Task group is not initialized` で 500 になる
3. curl で直接叩く場合は `MCP-Method`(全リクエスト) と `MCP-Name`(tools/call) ヘッダーが
   必須。SDK クライアントを使えばすべて自動で付与される

## SDK v2 の主な破壊的変更（v1 からの移行時)

- `from mcp.server.fastmcp import FastMCP` → `from mcp.server.mcpserver import MCPServer`
  （エイリアス・deprecation shim なし）
- ワイヤ型が snake_case に: `result.isError` → `result.is_error`、
  `tool.inputSchema` → `tool.input_schema`
