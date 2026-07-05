"""Domain services for stapel-tasks — the transport-agnostic core.

Every mutation goes through ``stapel_core.comm.mutate_and_emit`` so the ORM
write and the outbox event commit as one unit (the outbox guarantee: the
event leaves iff the surrounding transaction commits). The ``emit_check`` CI
gate enforces this discipline from the first commit.

This module *is* the module's primary API (docs/library-standard.md §8.1):
the REST views and the comm Functions are thin adapters over it, and an
in-process orchestrator projects cards by calling these functions directly
(``upsert_task_by_origin`` / ``move_task`` / ``update_task``).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.db import IntegrityError
from django.utils import timezone
from stapel_core.comm import mutate_and_emit

from . import features as features_seam
from .models import (
    Board,
    ChecklistItem,
    ChecklistState,
    Column,
    ColumnCategory,
    Task,
    TaskComment,
)
from .policy import MoveDecision, get_move_policy
from .positioning import (
    needs_rebalance,
    position_between,
    rebalanced_positions,
)
from .presets import ColumnSpec, get_preset_columns


# ── Boards & columns ────────────────────────────────────────────────────


def create_board(
    *,
    name: str,
    workspace_id=None,
    preset: str | None = "simple",
    columns: list[ColumnSpec] | None = None,
    feature_defs: list | None = None,
    slug: str = "",
    settings: dict | None = None,
) -> Board:
    """Create a board and its starting columns.

    Columns come from ``columns`` if given, else from the named ``preset``
    (raises ``KeyError`` for an unknown preset). ``feature_defs`` (the
    board's custom-field schema) is validated through the attributes seam.
    """
    if feature_defs:
        features_seam.validate_feature_defs(feature_defs)
    specs = columns if columns is not None else get_preset_columns(preset or "simple")

    board = Board.objects.create(
        name=name,
        workspace_id=workspace_id,
        slug=slug or "",
        feature_defs=feature_defs or [],
        settings=settings or {},
    )
    _create_columns(board, specs)
    return board


def _create_columns(board: Board, specs: list[ColumnSpec]) -> None:
    Column.objects.bulk_create(
        [
            Column(
                board=board,
                key=spec.key,
                name=spec.name,
                name_key=spec.name_key,
                category=spec.category,
                wip_limit=spec.wip_limit,
                order=order,
            )
            for order, spec in enumerate(specs)
        ]
    )


def add_column(
    board: Board,
    *,
    key: str,
    name: str,
    category: str,
    order: int | None = None,
    name_key: str = "",
    wip_limit: int | None = None,
) -> Column:
    """Append (or insert at ``order``) a column on a board."""
    if order is None:
        order = board.columns.count()
    return Column.objects.create(
        board=board,
        key=key,
        name=name,
        name_key=name_key,
        category=category,
        order=order,
        wip_limit=wip_limit,
    )


def reorder_columns(board: Board, ordered_keys: list[str]) -> None:
    """Set column order from a list of column keys (missing keys keep their
    relative order after the listed ones)."""
    by_key = {c.key: c for c in board.columns.all()}
    order = 0
    for key in ordered_keys:
        col = by_key.pop(key, None)
        if col is not None:
            col.order = order
            order += 1
    for col in by_key.values():  # any not listed keep trailing order
        col.order = order
        order += 1
    Column.objects.bulk_update(board.columns.all(), ["order"])


def set_board_feature_defs(board: Board, feature_defs: list) -> Board:
    """Replace a board's custom-field schema (validated via the seam)."""
    features_seam.validate_feature_defs(feature_defs)
    board.feature_defs = feature_defs or []
    board.save(update_fields=["feature_defs", "updated_at"])
    return board


# ── Card creation ───────────────────────────────────────────────────────


def _default_column(board: Board) -> Column:
    col = board.columns.order_by("order").first()
    if col is None:
        raise ValueError("board has no columns")
    return col


def _append_position(column: Column) -> Decimal:
    last = (
        Task.objects.filter(column=column, is_archived=False)
        .order_by("position", "created_at", "id")
        .values_list("position", flat=True)
        .last()
    )
    return position_between(last, None)


def create_task(
    *,
    board: Board,
    title: str,
    column: Column | None = None,
    description: str = "",
    creator=None,
    features_dto: dict | None = None,
    priority: int | None = None,
    due_at: datetime | None = None,
    parent: Task | None = None,
    assignee_ids: list | None = None,
    origin_type: str = "local",
    origin_ref: str = "",
    origin_meta: dict | None = None,
) -> Task:
    """Create a card and emit ``task.created``.

    Custom-field values are validated + normalized against the board schema
    via the attributes seam. The card is appended to the end of its column.
    """
    column = column or _default_column(board)
    features_seam.validate_features(board.feature_defs, features_dto)
    dao = features_seam.normalize_features(board.feature_defs, features_dto)

    completed_at = timezone.now() if _is_done(column) else None
    with mutate_and_emit() as emit_event:
        task = Task.objects.create(
            board=board,
            column=column,
            position=_append_position(column),
            title=title,
            description=description or "",
            priority=priority,
            due_at=due_at,
            parent=parent,
            features=dao,
            origin_type=origin_type or "local",
            origin_ref=origin_ref or "",
            origin_meta=origin_meta or {},
            completed_at=completed_at,
            **_user_fk("creator", creator),
        )
        if assignee_ids:
            task.assignees.set(list(assignee_ids))
        emit_event("task.created", _created_payload(task), key=str(task.id))
        if completed_at is not None:
            emit_event("task.completed", _completed_payload(task, _actor_id(creator)),
                       key=str(task.id))
    return task


def upsert_task_by_origin(
    *,
    board: Board,
    origin_type: str,
    origin_ref: str,
    title: str,
    column: Column | None = None,
    origin_meta: dict | None = None,
    actor=None,
    **create_kwargs,
) -> tuple[Task, bool]:
    """Idempotent projection entry point: create the card for
    ``(board, origin_type, origin_ref)`` or update the existing one.

    Returns ``(task, created)``. The uniqueness constraint makes concurrent
    projections safe — the loser of a create race falls back to an update.
    """
    existing = Task.objects.filter(
        board=board, origin_type=origin_type, origin_ref=origin_ref
    ).first()
    if existing is not None:
        _apply_origin_update(existing, title=title, origin_meta=origin_meta,
                             column=column, actor=actor)
        return existing, False
    try:
        task = create_task(
            board=board,
            title=title,
            column=column,
            creator=actor,
            origin_type=origin_type,
            origin_ref=origin_ref,
            origin_meta=origin_meta,
            **create_kwargs,
        )
        return task, True
    except IntegrityError:
        # Lost the create race — the concurrent projection won. Update its row.
        task = Task.objects.get(
            board=board, origin_type=origin_type, origin_ref=origin_ref
        )
        _apply_origin_update(task, title=title, origin_meta=origin_meta,
                             column=column, actor=actor)
        return task, False


def _apply_origin_update(task, *, title, origin_meta, column, actor):
    changed = {"title": title}
    if origin_meta is not None:
        changed["origin_meta"] = origin_meta
    update_task(task, actor=actor, **changed)
    if column is not None and column.id != task.column_id:
        move_task(task, to_column=column, actor=actor)


# ── Card updates ────────────────────────────────────────────────────────


_UPDATABLE = {"title", "description", "priority", "due_at", "origin_meta"}


def update_task(task: Task, *, actor=None, features_dto=None, **fields) -> Task:
    """Patch a card's scalar fields (and/or custom-field values) and emit
    ``task.updated`` with the list of changed field names."""
    changed_fields: list[str] = []
    for name, value in fields.items():
        if name not in _UPDATABLE:
            raise ValueError(f"field {name!r} is not updatable")
        if getattr(task, name) != value:
            setattr(task, name, value)
            changed_fields.append(name)

    if features_dto is not None:
        features_seam.validate_features(task.board.feature_defs, features_dto)
        task.features = features_seam.normalize_features(
            task.board.feature_defs, features_dto
        )
        changed_fields.append("features")

    if not changed_fields:
        return task

    with mutate_and_emit() as emit_event:
        task.save(update_fields=changed_fields + ["updated_at"])
        emit_event(
            "task.updated",
            {
                "task_id": str(task.id),
                "board_id": str(task.board_id),
                "changed_fields": changed_fields,
                "actor_id": _actor_id(actor),
            },
            key=str(task.id),
        )
    return task


# ── Move (drag-and-drop) ────────────────────────────────────────────────


def move_task(
    task: Task,
    *,
    to_column: Column,
    index: int | None = None,
    actor=None,
) -> MoveDecision:
    """Move a card to ``to_column`` at ``index`` (append if ``index`` is
    None), subject to ``MOVE_POLICY``.

    Returns the :class:`MoveDecision`. ``allow`` applies the move (emitting
    ``task.moved``, plus ``task.completed`` when the card enters a DONE
    column); ``deny`` and ``defer`` leave the card untouched — a deferred
    move is a command for an external owner to apply.
    """
    from_column = task.column
    decision = get_move_policy().check(
        task=task, from_column=from_column, to_column=to_column, actor=actor
    )
    if not decision.is_allowed:
        return decision

    new_position = _target_position(to_column, index, exclude_id=task.id)
    entered_done = _is_done(to_column) and not _is_done(from_column)
    left_done = _is_done(from_column) and not _is_done(to_column)

    update_fields = ["column", "position", "updated_at"]
    task.column = to_column
    task.position = new_position
    if entered_done and task.completed_at is None:
        task.completed_at = timezone.now()
        update_fields.append("completed_at")
    elif left_done and task.completed_at is not None:
        task.completed_at = None
        update_fields.append("completed_at")

    with mutate_and_emit() as emit_event:
        task.save(update_fields=update_fields)
        emit_event(
            "task.moved",
            {
                "task_id": str(task.id),
                "board_id": str(task.board_id),
                "from_column": from_column.key,
                "to_column": to_column.key,
                "from_category": from_column.category,
                "to_category": to_column.category,
                "actor_id": _actor_id(actor),
            },
            key=str(task.id),
        )
        if entered_done:
            emit_event("task.completed", _completed_payload(task, _actor_id(actor)),
                       key=str(task.id))
    return decision


def _target_position(column: Column, index: int | None, *, exclude_id) -> Decimal:
    positions = list(
        Task.objects.filter(column=column, is_archived=False)
        .exclude(id=exclude_id)
        .order_by("position", "created_at", "id")
        .values_list("position", flat=True)
    )
    n = len(positions)
    if index is None or index >= n:
        return position_between(positions[-1] if positions else None, None)
    if index <= 0:
        return position_between(None, positions[0])
    prev, nxt = positions[index - 1], positions[index]
    if needs_rebalance(prev, nxt):
        _rebalance_column(column, exclude_id=exclude_id)
        positions = list(
            Task.objects.filter(column=column, is_archived=False)
            .exclude(id=exclude_id)
            .order_by("position", "created_at", "id")
            .values_list("position", flat=True)
        )
        prev, nxt = positions[index - 1], positions[index]
    return position_between(prev, nxt)


def _rebalance_column(column: Column, *, exclude_id=None) -> None:
    """Renumber a column's cards with evenly spaced integers (the rare
    precision-exhausted fallback). Writes only positions."""
    rows = list(
        Task.objects.filter(column=column, is_archived=False)
        .exclude(id=exclude_id)
        .order_by("position", "created_at", "id")
    )
    for row, pos in zip(rows, rebalanced_positions(len(rows))):
        row.position = pos
    Task.objects.bulk_update(rows, ["position"])


# ── Assignees ───────────────────────────────────────────────────────────


def set_assignees(task: Task, user_ids, *, actor=None) -> Task:
    """Replace a card's assignee set, emitting one ``task.assigned`` per
    added/removed user."""
    target = {str(u) for u in (user_ids or [])}
    current = {str(u) for u in task.assignees.values_list("pk", flat=True)}
    added = target - current
    removed = current - target
    if not added and not removed:
        return task
    with mutate_and_emit() as emit_event:
        if added:
            task.assignees.add(*added)
        if removed:
            task.assignees.remove(*removed)
        for uid in sorted(added):
            emit_event("task.assigned", _assigned_payload(task, uid, "assigned", actor),
                       key=str(task.id))
        for uid in sorted(removed):
            emit_event("task.assigned", _assigned_payload(task, uid, "unassigned", actor),
                       key=str(task.id))
    return task


# ── Archive ─────────────────────────────────────────────────────────────


def archive_task(task: Task, *, actor=None) -> Task:
    """Soft-delete a card and emit ``task.archived``."""
    if task.is_archived:
        return task
    with mutate_and_emit() as emit_event:
        task.is_archived = True
        task.archived_at = timezone.now()
        task.save(update_fields=["is_archived", "archived_at", "updated_at"])
        emit_event(
            "task.archived",
            {
                "task_id": str(task.id),
                "board_id": str(task.board_id),
                "actor_id": _actor_id(actor),
            },
            key=str(task.id),
        )
    return task


# ── Comments ────────────────────────────────────────────────────────────


def add_comment(task: Task, *, body: str, author=None) -> TaskComment:
    """Add a comment and emit ``task.comment_added`` (the human->orchestrator
    reply channel for a managed card)."""
    with mutate_and_emit() as emit_event:
        comment = TaskComment.objects.create(
            task=task, body=body, **_user_fk("author", author)
        )
        emit_event(
            "task.comment_added",
            {
                "task_id": str(task.id),
                "board_id": str(task.board_id),
                "comment_id": str(comment.id),
                "author_id": _actor_id(author),
            },
            key=str(task.id),
        )
    return comment


def delete_comment(comment: TaskComment) -> TaskComment:
    """Soft-delete a comment (no event — deletion is not a domain fact
    anyone subscribes to)."""
    if not comment.is_deleted:
        comment.is_deleted = True
        comment.body = ""
        comment.save(update_fields=["is_deleted", "body", "updated_at"])
    return comment


# ── Checklist ───────────────────────────────────────────────────────────


def add_checklist_item(
    task: Task, *, text: str, order: int | None = None, ref: str = ""
) -> ChecklistItem:
    """Append a checklist step to a card."""
    if order is None:
        order = task.checklist_items.count()
    return ChecklistItem.objects.create(task=task, text=text, order=order, ref=ref)


def set_checklist_item_state(
    item: ChecklistItem, state: str, *, actor=None
) -> ChecklistItem:
    """Set a checklist step's state and emit ``task.checklist_item_changed``
    (the QA channel: a FAILED step is mechanically visible to a projector)."""
    if state not in ChecklistState.values:
        raise ValueError(f"invalid checklist state {state!r}")
    if item.state == state:
        return item
    with mutate_and_emit() as emit_event:
        item.state = state
        item.save(update_fields=["state", "updated_at"])
        emit_event(
            "task.checklist_item_changed",
            {
                "task_id": str(item.task_id),
                "item_id": str(item.id),
                "ref": item.ref or None,
                "state": item.state,
                "actor_id": _actor_id(actor),
            },
            key=str(item.task_id),
        )
    return item


# ── Payload / helper builders ───────────────────────────────────────────


def _user_fk(name: str, value) -> dict:
    """FK kwargs accepting either a user instance or a raw user id — the
    service API and the comm Functions (which pass ids) share one path."""
    if value is None:
        return {name: None}
    if hasattr(value, "_meta"):  # a model instance
        return {name: value}
    return {f"{name}_id": value}


def _is_done(column: Column) -> bool:
    return column.category == ColumnCategory.DONE


def _actor_id(actor) -> str | None:
    if actor is None:
        return None
    pk = getattr(actor, "pk", actor)
    return str(pk) if pk is not None else None


def _created_payload(task: Task) -> dict:
    return {
        "workspace_id": str(task.board.workspace_id) if task.board.workspace_id else None,
        "board_id": str(task.board_id),
        "task_id": str(task.id),
        "title": task.title,
        "column": task.column.key,
        "category": task.column.category,
        "creator_id": _actor_id(task.creator_id),
        "origin_type": task.origin_type,
        "origin_ref": task.origin_ref or None,
        "parent_id": str(task.parent_id) if task.parent_id else None,
    }


def _completed_payload(task: Task, actor_id: str | None) -> dict:
    return {
        "task_id": str(task.id),
        "board_id": str(task.board_id),
        "actor_id": actor_id,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "origin_ref": task.origin_ref or None,
    }


def _assigned_payload(task: Task, uid: str, op: str, actor) -> dict:
    return {
        "task_id": str(task.id),
        "board_id": str(task.board_id),
        "assignee_id": uid,
        "op": op,
        "actor_id": _actor_id(actor),
    }
