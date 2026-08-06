"""FastAPI + MCP Python SDK v2 — spec 2026-07-28 demo server.

Run:
    pip install -r requirements.txt
    uvicorn server:app --port 8765
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from mcp.server.mcpserver import MCPServer

mcp = MCPServer(name="taskflow-mcp", version="0.1.0")


@mcp.tool()
def add_task(title: str, priority: str = "medium") -> str:
    """Add a task to TaskFlow."""
    return f"Task created: {title} (priority={priority})"


@mcp.tool()
def list_tasks() -> list[str]:
    """List all tasks."""
    return ["Design review (high)", "Write docs (low)"]


# FastAPI does not run a mounted sub-app's lifespan, so the MCP session
# manager must be started from the parent app's lifespan.
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="TaskFlow API", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


# stateless_http=True enables the sessionless operation required by the
# 2026-07-28 spec; json_response=True returns plain JSON instead of SSE,
# which makes curl testing easier.
app.mount("/", mcp.streamable_http_app(stateless_http=True, json_response=True))
