from datetime import date, timedelta

import pytest

from app import tasks
from app.tasks import TaskCreate, TaskUpdate


def test_create_and_get(owner):
    t = tasks.create_task(owner, TaskCreate(title="  買い物  ", tags=["家", " 家 ", ""]))
    assert t.title == "買い物"
    assert t.tags == ["家"]
    assert t.status == "todo" and t.completed_at is None
    assert tasks.get_task(owner, t.task_id) == t


def test_owner_isolation(owner):
    t = tasks.create_task(owner, TaskCreate(title="a"))
    with pytest.raises(tasks.TaskNotFound):
        tasks.get_task("someone-else", t.task_id)
    with pytest.raises(tasks.TaskNotFound):
        tasks.update_task("someone-else", t.task_id, TaskUpdate(title="x"))
    with pytest.raises(tasks.TaskNotFound):
        tasks.delete_task("someone-else", t.task_id)
    assert tasks.list_tasks("someone-else") == []


def test_update_partial_and_clear_due(owner):
    t = tasks.create_task(owner, TaskCreate(title="a", due_date=date(2030, 1, 1), priority="high"))
    u = tasks.update_task(owner, t.task_id, TaskUpdate(description="詳細"))
    assert u.description == "詳細" and u.due_date == date(2030, 1, 1) and u.priority == "high"
    u = tasks.update_task(owner, t.task_id, TaskUpdate(due_date=None))
    assert u.due_date is None


def test_completed_at_follows_status(owner):
    t = tasks.create_task(owner, TaskCreate(title="a"))
    done = tasks.update_task(owner, t.task_id, TaskUpdate(status="done"))
    assert done.completed_at is not None
    back = tasks.update_task(owner, t.task_id, TaskUpdate(status="todo"))
    assert back.completed_at is None


def test_update_missing_raises(owner):
    with pytest.raises(tasks.TaskNotFound):
        tasks.update_task(owner, "nope", TaskUpdate(title="x"))
    # 存在しないキーへの update で項目が作られていないこと
    assert tasks.list_tasks(owner) == []


def test_list_filters_and_order(owner):
    today = date.today()
    a = tasks.create_task(owner, TaskCreate(title="期限なし高", priority="high"))
    b = tasks.create_task(owner, TaskCreate(title="明日", due_date=today + timedelta(days=1), tags=["仕事"]))
    c = tasks.create_task(owner, TaskCreate(title="今日 低", due_date=today, priority="low"))
    d = tasks.create_task(owner, TaskCreate(title="完了", status="done", due_date=today - timedelta(days=9)))

    assert [t.task_id for t in tasks.list_tasks(owner)] == [c.task_id, b.task_id, a.task_id, d.task_id]
    assert [t.task_id for t in tasks.list_tasks(owner, include_done=False)] == [c.task_id, b.task_id, a.task_id]
    assert [t.task_id for t in tasks.list_tasks(owner, status="done")] == [d.task_id]
    assert [t.task_id for t in tasks.list_tasks(owner, tag="仕事")] == [b.task_id]
    assert [t.task_id for t in tasks.list_tasks(owner, query="低")] == [c.task_id]
    assert [t.task_id for t in tasks.list_tasks(owner, query="しごと")] == []


def test_summary_counts_overdue(owner):
    yesterday = date.today() - timedelta(days=1)
    tasks.create_task(owner, TaskCreate(title="遅れ", due_date=yesterday))
    tasks.create_task(owner, TaskCreate(title="遅れたが完了", due_date=yesterday, status="done"))
    s = tasks.summary(owner)
    assert s == {"counts": {"todo": 1, "in_progress": 0, "done": 1}, "total": 2, "overdue": 1}
