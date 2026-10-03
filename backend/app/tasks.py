"""タスクの保存と取得。REST API と MCP のツールはどちらもここを通す。

テーブル TaskflowTasks: PK owner_id (Cognito の sub) / SK task_id。
1 人あたりのタスク数は多くない前提で、絞り込みは owner_id で引いた後に Python で行う。
"""

import secrets
import time
from datetime import UTC, date, datetime
from typing import Literal

from boto3.dynamodb.conditions import Attr, Key
from pydantic import BaseModel, Field, field_validator

from .aws import table
from .config import get_settings

Status = Literal["todo", "in_progress", "done"]
Priority = Literal["low", "medium", "high"]

STATUSES: tuple[Status, ...] = ("todo", "in_progress", "done")
PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}


class TaskNotFound(Exception):
    pass


def _clean_tags(v: list[str] | None) -> list[str] | None:
    if v is None:
        return None
    seen: list[str] = []
    for t in v:
        t = t.strip()
        if t and t not in seen:
            seen.append(t)
    return seen


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10000)
    status: Status = "todo"
    priority: Priority = "medium"
    due_date: date | None = None
    tags: list[str] = Field(default_factory=list, max_length=20)

    _tags = field_validator("tags")(_clean_tags)


class TaskUpdate(BaseModel):
    """指定した項目だけ書き換える。due_date を消すときは null を明示する。"""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    status: Status | None = None
    priority: Priority | None = None
    due_date: date | None = None
    tags: list[str] | None = Field(default=None, max_length=20)

    _tags = field_validator("tags")(_clean_tags)


class Task(BaseModel):
    task_id: str
    title: str
    description: str
    status: Status
    priority: Priority
    due_date: date | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _new_id() -> str:
    # 時刻順に並ぶ ID (ミリ秒の 16 進 + 乱数)
    return f"{int(time.time() * 1000):012x}{secrets.token_hex(4)}"


def _tbl():
    return table(get_settings().tasks_table)


def _to_task(item: dict) -> Task:
    return Task(
        task_id=item["task_id"],
        title=item["title"],
        description=item.get("description", ""),
        status=item["status"],
        priority=item.get("priority", "medium"),
        due_date=item.get("due_date") or None,
        tags=list(item.get("tags") or []),
        created_at=item["created_at"],
        updated_at=item["updated_at"],
        completed_at=item.get("completed_at") or None,
    )


def sort_key(t: Task):
    """未完了 → 完了。その中で期限の近い順 (期限なしは後)、優先度、作成順。"""
    return (
        t.status == "done",
        t.due_date is None,
        t.due_date or date.max,
        PRIORITY_RANK[t.priority],
        t.created_at,
    )


def list_tasks(
    owner_id: str,
    *,
    status: Status | None = None,
    tag: str | None = None,
    query: str | None = None,
    include_done: bool = True,
) -> list[Task]:
    items: list[dict] = []
    kw: dict = {"KeyConditionExpression": Key("owner_id").eq(owner_id)}
    while True:
        res = _tbl().query(**kw)
        items.extend(res["Items"])
        if "LastEvaluatedKey" not in res:
            break
        kw["ExclusiveStartKey"] = res["LastEvaluatedKey"]

    tasks = [_to_task(i) for i in items]
    if status:
        tasks = [t for t in tasks if t.status == status]
    elif not include_done:
        tasks = [t for t in tasks if t.status != "done"]
    if tag:
        tasks = [t for t in tasks if tag in t.tags]
    if query:
        q = query.casefold()
        tasks = [
            t
            for t in tasks
            if q in t.title.casefold() or q in t.description.casefold() or any(q in tg.casefold() for tg in t.tags)
        ]
    return sorted(tasks, key=sort_key)


def get_task(owner_id: str, task_id: str) -> Task:
    item = _tbl().get_item(Key={"owner_id": owner_id, "task_id": task_id}).get("Item")
    if not item:
        raise TaskNotFound(task_id)
    return _to_task(item)


def create_task(owner_id: str, data: TaskCreate) -> Task:
    now = _now()
    item = {
        "owner_id": owner_id,
        "task_id": _new_id(),
        "title": data.title.strip(),
        "description": data.description,
        "status": data.status,
        "priority": data.priority,
        "due_date": data.due_date.isoformat() if data.due_date else None,
        "tags": data.tags,
        "created_at": now,
        "updated_at": now,
        "completed_at": now if data.status == "done" else None,
    }
    _tbl().put_item(Item=item)
    return _to_task(item)


def update_task(owner_id: str, task_id: str, data: TaskUpdate) -> Task:
    fields = data.model_dump(exclude_unset=True)
    if not fields:
        return get_task(owner_id, task_id)

    now = _now()
    values: dict = {}
    for k, v in fields.items():
        if k == "due_date":
            v = v.isoformat() if v else None
        elif k == "title":
            v = v.strip()
        values[k] = v
    values["updated_at"] = now
    if "status" in values:
        values["completed_at"] = now if values["status"] == "done" else None

    names = {f"#{k}": k for k in values}
    expr_values = {f":{k}": v for k, v in values.items()}
    try:
        res = _tbl().update_item(
            Key={"owner_id": owner_id, "task_id": task_id},
            UpdateExpression="SET " + ", ".join(f"#{k} = :{k}" for k in values),
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=expr_values,
            ConditionExpression=Attr("task_id").exists(),
            ReturnValues="ALL_NEW",
        )
    except _tbl().meta.client.exceptions.ConditionalCheckFailedException:
        raise TaskNotFound(task_id) from None
    return _to_task(res["Attributes"])


def delete_task(owner_id: str, task_id: str) -> None:
    try:
        _tbl().delete_item(
            Key={"owner_id": owner_id, "task_id": task_id},
            ConditionExpression=Attr("task_id").exists(),
        )
    except _tbl().meta.client.exceptions.ConditionalCheckFailedException:
        raise TaskNotFound(task_id) from None


def summary(owner_id: str) -> dict:
    tasks = list_tasks(owner_id)
    today = date.today()
    counts = {s: 0 for s in STATUSES}
    for t in tasks:
        counts[t.status] += 1
    overdue = [t for t in tasks if t.status != "done" and t.due_date and t.due_date < today]
    return {"counts": counts, "total": len(tasks), "overdue": len(overdue)}
