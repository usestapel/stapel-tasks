"""comm surface of stapel-tasks (Functions).

Every Function carries a JSON schema in ``schemas/functions/`` — tests run
with ``VALIDATE_SCHEMAS`` on, so a payload drifting from its schema fails
loudly. Registration happens on import from ``apps.py:ready()``.

These Functions are the transport-agnostic, transport-independent mirror of
``services`` — the same operations an in-process orchestrator reaches by
calling ``services`` directly. They are the natural MCP-tool candidates
(docs/tasks-module.md §7): ``tasks.list_board`` / ``tasks.get`` /
``tasks.create`` / ``tasks.comment`` / ``tasks.move``.
"""
from stapel_core.comm import function


def _card(task) -> dict:
    """Compact machine projection of a card (Function result shape)."""
    return {
        "task_id": str(task.id),
        "board_id": str(task.board_id),
        "column": task.column.key,
        "category": task.column.category,
        "position": str(task.position),
        "title": task.title,
        "description": task.description,
        "creator_id": str(task.creator_id) if task.creator_id else None,
        "assignee_ids": [str(u) for u in task.assignees.values_list("pk", flat=True)],
        "priority": task.priority,
        "due_at": task.due_at.isoformat() if task.due_at else None,
        "parent_id": str(task.parent_id) if task.parent_id else None,
        "features": task.features or {},
        "origin_type": task.origin_type,
        "origin_ref": task.origin_ref or None,
        "origin_meta": task.origin_meta or {},
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "is_archived": task.is_archived,
    }


@function("tasks.get")
def get(payload):
    """Fetch a single card by id. Output: ``{"task": <card>}`` or
    ``{"task": null}`` if not found."""
    from .models import Task

    task = (
        Task.objects.select_related("board", "column")
        .prefetch_related("assignees")
        .filter(id=payload["task_id"])
        .first()
    )
    return {"task": _card(task) if task is not None else None}


@function("tasks.list_board")
def list_board(payload):
    """List a board's columns and cards (grouped by column key).

    Output: ``{"board_id", "columns": [{"key","name","category","order"}],
    "cards": {column_key: [<card>, ...]}}``.
    """
    from .models import Board, Task

    board = Board.objects.filter(id=payload["board_id"]).first()
    if board is None:
        return {"board_id": payload["board_id"], "columns": [], "cards": {}}

    columns = list(board.columns.order_by("order"))
    qs = (
        Task.objects.select_related("column")
        .prefetch_related("assignees")
        .filter(board=board)
        .order_by("position", "created_at", "id")
    )
    if not payload.get("include_archived"):
        qs = qs.filter(is_archived=False)
    if payload.get("column"):
        qs = qs.filter(column__key=payload["column"])
    if payload.get("category"):
        qs = qs.filter(column__category=payload["category"])
    if payload.get("assignee_id"):
        qs = qs.filter(assignees__pk=payload["assignee_id"])
    if payload.get("origin_ref"):
        qs = qs.filter(origin_ref=payload["origin_ref"])

    cards: dict[str, list] = {c.key: [] for c in columns}
    for task in qs.distinct():
        cards.setdefault(task.column.key, []).append(_card(task))
    return {
        "board_id": str(board.id),
        "columns": [
            {"key": c.key, "name": c.name, "category": c.category, "order": c.order}
            for c in columns
        ],
        "cards": cards,
    }


@function("tasks.create")
def create(payload):
    """Create a card on a board. Output: ``{"task_id": str}``."""
    from .models import Board, Column
    from . import services

    board = Board.objects.get(id=payload["board_id"])
    column = None
    if payload.get("column"):
        column = Column.objects.get(board=board, key=payload["column"])
    parent = None
    if payload.get("parent_id"):
        from .models import Task

        parent = Task.objects.get(id=payload["parent_id"])
    origin = payload.get("origin") or {}
    task = services.create_task(
        board=board,
        title=payload["title"],
        description=payload.get("description", ""),
        column=column,
        creator=payload.get("creator_id"),
        features_dto=payload.get("features"),
        priority=payload.get("priority"),
        parent=parent,
        origin_type=origin.get("type", "local"),
        origin_ref=origin.get("ref", ""),
        origin_meta=origin.get("meta") or {},
    )
    return {"task_id": str(task.id)}


@function("tasks.move")
def move(payload):
    """Move a card. Output: ``{"result": "applied"|"deferred"|"denied",
    "reason_key": str|null}``."""
    from .models import Column, Task
    from . import services
    from .policy import ALLOW, DEFER, DENY

    task = Task.objects.select_related("board", "column").get(id=payload["task_id"])
    to_column = Column.objects.get(board=task.board, key=payload["to_column"])
    decision = services.move_task(
        task,
        to_column=to_column,
        index=payload.get("index"),
        actor=payload.get("actor_id"),
    )
    result = {ALLOW: "applied", DEFER: "deferred", DENY: "denied"}[decision.result]
    return {"result": result, "reason_key": decision.reason_key}


@function("tasks.comment")
def comment(payload):
    """Add a comment to a card. Output: ``{"comment_id": str}``."""
    from .models import Task
    from . import services

    task = Task.objects.get(id=payload["task_id"])
    c = services.add_comment(
        task, body=payload["body"], author=payload.get("author_id")
    )
    return {"comment_id": str(c.id)}
