"""画面用の REST API (/api)。"""

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from . import auth, tasks, tokens
from .auth import CurrentUser
from .config import get_settings

router = APIRouter(prefix="/api")


# --- 認証 -------------------------------------------------------------------


class AuthConfig(BaseModel):
    dev_login: bool  # ログイン画面に「admin / admin」のヒントを出すか
    mcp_url: str


@router.get("/auth/config", response_model=AuthConfig)
def auth_config():
    s = get_settings()
    return AuthConfig(dev_login=s.dev_login, mcp_url=f"{s.public_base_url.rstrip('/')}/mcp")


@router.post("/auth/login", response_model=auth.AuthResult)
def login(body: auth.LoginRequest):
    try:
        return auth.login(body.username, body.password)
    except auth.AuthError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from e


@router.post("/auth/refresh", response_model=auth.AuthResult)
def refresh(body: auth.RefreshRequest):
    try:
        return auth.refresh(body.refresh_token)
    except auth.AuthError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from e


@router.get("/me", response_model=auth.UserInfo)
def me(user: CurrentUser):
    return auth.UserInfo(sub=user.owner_id, email=user.resolved_email())


# --- タスク -----------------------------------------------------------------


def _not_found(task_id: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"タスク {task_id} がありません")


@router.get("/tasks", response_model=list[tasks.Task])
def list_tasks(
    user: CurrentUser,
    status: tasks.Status | None = None,
    tag: str | None = None,
    q: str | None = None,
):
    return tasks.list_tasks(user.owner_id, status=status, tag=tag, query=q)


@router.post("/tasks", response_model=tasks.Task, status_code=status.HTTP_201_CREATED)
def create_task(user: CurrentUser, body: tasks.TaskCreate):
    return tasks.create_task(user.owner_id, body)


@router.get("/tasks/{task_id}", response_model=tasks.Task)
def get_task(user: CurrentUser, task_id: str):
    try:
        return tasks.get_task(user.owner_id, task_id)
    except tasks.TaskNotFound:
        raise _not_found(task_id) from None


@router.patch("/tasks/{task_id}", response_model=tasks.Task)
def update_task(user: CurrentUser, task_id: str, body: tasks.TaskUpdate):
    try:
        return tasks.update_task(user.owner_id, task_id, body)
    except tasks.TaskNotFound:
        raise _not_found(task_id) from None


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(user: CurrentUser, task_id: str):
    try:
        tasks.delete_task(user.owner_id, task_id)
    except tasks.TaskNotFound:
        raise _not_found(task_id) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- MCP 用のトークン --------------------------------------------------------


class TokenCreate(BaseModel):
    name: str = Field(default="MCP", max_length=60)


@router.get("/tokens", response_model=list[tokens.TokenInfo])
def list_tokens(user: CurrentUser):
    return tokens.list_tokens(user.owner_id)


@router.post("/tokens", response_model=tokens.IssuedToken, status_code=status.HTTP_201_CREATED)
def issue_token(user: CurrentUser, body: TokenCreate):
    if user.via != "cognito":
        # トークンでトークンを増やせると、漏れたときに取り消しきれない
        raise HTTPException(status.HTTP_403_FORBIDDEN, "トークンの発行は画面からログインして行ってください")
    return tokens.issue(user.owner_id, user.resolved_email(), body.name)


@router.delete("/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_token(user: CurrentUser, token_id: str):
    if not tokens.revoke(user.owner_id, token_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "トークンがありません")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
