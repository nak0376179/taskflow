"""Multi-tenant MCP server PoC — spec 2026-07-28, FastAPI, mock Cognito auth.

Tenancy model (mirrors production):
- A "group" is a tenant; data is fully isolated per group.
- Users may belong to many groups. Anyone can create a group (becoming its
  owner); joining any other group is invite-only (owner invites).
- Permission checks happen inside every tool, against the verified token —
  never trusting anything the LLM put in the arguments.

Run:
    uvicorn server:app --port 8766
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer

import db
from mock_auth import MockCognitoVerifier

mcp = MCPServer(
    name="taskflow-multitenant",
    version="0.1.0",
    token_verifier=MockCognitoVerifier(),
    auth=AuthSettings(
        issuer_url="http://localhost:8766/fake-cognito",
        resource_server_url="http://localhost:8766/mcp",
        required_scopes=["taskflow/api"],
    ),
)


# ---- authorization helpers -------------------------------------------------

def current_user() -> str:
    token = get_access_token()
    assert token is not None  # bearer middleware already rejected anonymous calls
    return token.claims["username"]


def require_member(group_id: str) -> tuple[str, str]:
    """Return (username, role); raise if the caller is not in the group."""
    user = current_user()
    role = db.member_role(group_id, user)
    if role is None:
        # Same message whether the group is missing or merely not yours:
        # don't leak other tenants' group existence.
        raise PermissionError(f"group {group_id} not found or you are not a member")
    return user, role


def require_owner(group_id: str) -> str:
    user, role = require_member(group_id)
    if role != "owner":
        raise PermissionError(f"only the owner of group {group_id} may do this")
    return user


# ---- tools -----------------------------------------------------------------

@mcp.tool()
def create_group(name: str) -> dict:
    """Create a new group (tenant). The caller becomes its owner."""
    user = current_user()
    gid = db.create_group(name, owner=user)
    return {"group_id": gid, "name": name, "owner": user}


@mcp.tool()
def list_my_groups() -> list[dict]:
    """List the groups the caller belongs to, with their role in each."""
    return db.groups_of(current_user())


@mcp.tool()
def invite_user(group_id: str, username: str) -> str:
    """Invite a user into a group. Owner only."""
    require_owner(group_id)
    db.add_member(group_id, username, role="member")
    return f"{username} is now a member of group {group_id}"


@mcp.tool()
def add_task(group_id: str, title: str, priority: str = "medium") -> dict:
    """Add a task to a group's board. Members only."""
    user, _ = require_member(group_id)
    return db.add_task(group_id, title, priority, created_by=user)


@mcp.tool()
def list_tasks(group_id: str) -> list[dict]:
    """List a group's tasks. Members only."""
    require_member(group_id)
    return db.list_tasks(group_id)


@mcp.tool()
def update_task(group_id: str, task_id: str, title: str | None = None, priority: str | None = None) -> dict:
    """Update a task's title and/or priority. Members only."""
    require_member(group_id)
    task = db.get_task(group_id, task_id)
    if task is None:
        raise ValueError(f"task {task_id} not found in group {group_id}")
    if title is not None:
        task["title"] = title
    if priority is not None:
        task["priority"] = priority
    return {k: v for k, v in task.items() if k not in ("pk", "sk")}


@mcp.tool()
def delete_task(group_id: str, task_id: str) -> str:
    """Delete a task. Owner only."""
    require_owner(group_id)
    if db.get_task(group_id, task_id) is None:
        raise ValueError(f"task {task_id} not found in group {group_id}")
    db.delete_task(group_id, task_id)
    return f"task {task_id} deleted from group {group_id}"


# ---- FastAPI wiring --------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="TaskFlow multi-tenant PoC", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def playground():
    """Browser playground for trying the tenancy/permission model by hand."""
    return FileResponse(Path(__file__).parent / "static" / "index.html")


app.mount("/", mcp.streamable_http_app(stateless_http=True, json_response=True))
