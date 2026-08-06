"""In-memory store laid out like a DynamoDB single-table design.

PK / SK layout (swap for real DynamoDB later):
    GROUP#<gid>  META            group metadata (name, owner)
    GROUP#<gid>  MEMBER#<user>   membership (role: owner | member)
    GROUP#<gid>  TASK#<tid>      task item
    USER#<user>  GROUP#<gid>     reverse index: user's groups (GSI equivalent)
"""
import itertools

_TABLE: dict[tuple[str, str], dict] = {}
_seq = itertools.count(1)


def put(pk: str, sk: str, item: dict) -> None:
    _TABLE[(pk, sk)] = {**item, "pk": pk, "sk": sk}


def get(pk: str, sk: str) -> dict | None:
    return _TABLE.get((pk, sk))


def delete(pk: str, sk: str) -> None:
    _TABLE.pop((pk, sk), None)


def query(pk: str, sk_prefix: str = "") -> list[dict]:
    return [v for (p, s), v in _TABLE.items() if p == pk and s.startswith(sk_prefix)]


def next_id() -> str:
    return str(next(_seq))


# ---- domain operations (all take an explicit group scope) ----

def create_group(name: str, owner: str) -> str:
    gid = next_id()
    put(f"GROUP#{gid}", "META", {"group_id": gid, "name": name, "owner": owner})
    add_member(gid, owner, role="owner")
    return gid


def add_member(gid: str, username: str, role: str = "member") -> None:
    put(f"GROUP#{gid}", f"MEMBER#{username}", {"username": username, "role": role})
    put(f"USER#{username}", f"GROUP#{gid}", {"group_id": gid, "role": role})


def member_role(gid: str, username: str) -> str | None:
    item = get(f"GROUP#{gid}", f"MEMBER#{username}")
    return item["role"] if item else None


def groups_of(username: str) -> list[dict]:
    out = []
    for link in query(f"USER#{username}", "GROUP#"):
        meta = get(f"GROUP#{link['group_id']}", "META")
        if meta:
            out.append({"group_id": link["group_id"], "name": meta["name"], "role": link["role"]})
    return out


def add_task(gid: str, title: str, priority: str, created_by: str) -> dict:
    tid = next_id()
    item = {"task_id": tid, "title": title, "priority": priority, "created_by": created_by}
    put(f"GROUP#{gid}", f"TASK#{tid}", item)
    return item


def list_tasks(gid: str) -> list[dict]:
    return [
        {k: v for k, v in t.items() if not k in ("pk", "sk")}
        for t in query(f"GROUP#{gid}", "TASK#")
    ]


def get_task(gid: str, tid: str) -> dict | None:
    return get(f"GROUP#{gid}", f"TASK#{tid}")


def delete_task(gid: str, tid: str) -> None:
    delete(f"GROUP#{gid}", f"TASK#{tid}")
