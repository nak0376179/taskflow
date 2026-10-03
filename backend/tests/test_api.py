"""REST API。Cognito の JWT は moto では検証できないので、個人アクセストークンで叩く。"""

import pytest
from fastapi.testclient import TestClient

from app import auth, tokens
from app.main import app


@pytest.fixture
def client():
    # lifespan (bootstrap) は走らせない。テーブルは conftest で作ってある
    return TestClient(app)


@pytest.fixture
def token(owner):
    return tokens.issue(owner, "me@example.com", "test").token


def h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def test_requires_auth(client):
    assert client.get("/api/tasks").status_code == 401
    assert client.get("/api/tasks", headers=h("tfp_unknown")).status_code == 401
    assert client.get("/api/tasks", headers=h("not-a-jwt")).status_code == 401


def test_task_crud(client, token):
    r = client.post("/api/tasks", json={"title": "書類", "due_date": "2030-05-01", "tags": ["a"]}, headers=h(token))
    assert r.status_code == 201
    tid = r.json()["task_id"]

    r = client.patch(f"/api/tasks/{tid}", json={"status": "done"}, headers=h(token))
    assert r.json()["status"] == "done" and r.json()["completed_at"]

    r = client.patch(f"/api/tasks/{tid}", json={"due_date": None}, headers=h(token))
    assert r.json()["due_date"] is None

    assert [t["task_id"] for t in client.get("/api/tasks?status=done", headers=h(token)).json()] == [tid]
    assert client.get("/api/tasks?status=todo", headers=h(token)).json() == []

    assert client.delete(f"/api/tasks/{tid}", headers=h(token)).status_code == 204
    assert client.get(f"/api/tasks/{tid}", headers=h(token)).status_code == 404
    assert client.delete(f"/api/tasks/{tid}", headers=h(token)).status_code == 404


def test_validation(client, token):
    assert client.post("/api/tasks", json={"title": ""}, headers=h(token)).status_code == 422
    assert client.post("/api/tasks", json={"title": "a", "status": "doing"}, headers=h(token)).status_code == 422


def test_other_users_tasks_invisible(client, token):
    tid = client.post("/api/tasks", json={"title": "秘密"}, headers=h(token)).json()["task_id"]
    other = tokens.issue("user-2", "b@example.com", "x").token
    assert client.get("/api/tasks", headers=h(other)).json() == []
    assert client.get(f"/api/tasks/{tid}", headers=h(other)).status_code == 404
    assert client.patch(f"/api/tasks/{tid}", json={"title": "x"}, headers=h(other)).status_code == 404


def test_tokens(client, owner, token):
    # 個人アクセストークンでは新しいトークンを発行できない
    assert client.post("/api/tokens", json={"name": "x"}, headers=h(token)).status_code == 403

    listed = client.get("/api/tokens", headers=h(token)).json()
    assert len(listed) == 1 and "token" not in listed[0] and listed[0]["last_used_at"]

    tid = listed[0]["token_id"]
    assert client.delete("/api/tokens/nope", headers=h(token)).status_code == 404
    assert client.delete(f"/api/tokens/{tid}", headers=h(token)).status_code == 204
    assert client.get("/api/tasks", headers=h(token)).status_code == 401


def test_token_is_stored_hashed(owner):
    issued = tokens.issue(owner, "me@example.com", "x")
    from app.aws import table
    from app.config import get_settings

    items = table(get_settings().tokens_table).scan()["Items"]
    assert all(issued.token not in str(i) for i in items)


def test_dev_login_only_local(monkeypatch):
    from app.config import get_settings

    s = get_settings()
    assert auth.resolve_dev_login("admin", "admin") == ("admin", "admin")  # 本番相当 (endpoint なし)
    monkeypatch.setattr(s, "aws_endpoint_url", "http://localhost:4568")
    assert auth.resolve_dev_login("admin", "admin") == (s.dev_admin_email, s.dev_admin_password)
    assert auth.resolve_dev_login("admin", "x") == ("admin", "x")
