"""Models for stapel-tasks — the generic task/kanban domain.

Three ideas kept strictly separate (docs/tasks-module.md §1): this module
owns the *user-facing* representation of work (boards, columns, cards,
comments, checklists). It does not own — and never imports — any pipeline
FSM; an external state machine only *projects* into a card through the
opaque ``origin_*`` handles.

House rules (docs/library-standard.md §3.8):
- primary keys are UUIDs — a card/board/column id is a stable cross-service
  handle (comm payloads and the ``origin`` idempotency key rely on it);
- the only user model is ``settings.AUTH_USER_MODEL``;
- tenancy is the opaque ``workspace_id`` (nullable — the module works
  without stapel-workspaces); there is **no FK** to a Workspace model.
"""
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models


class ColumnCategory(models.TextChoices):
    """Fixed machine-semantic category of a column (docs/tasks-module.md §3).

    Column *keys* and names are workflow-as-data (per board); the category
    is the fixed vocabulary that carries meaning no configuration may own:
    when to emit ``task.completed`` (a card entering a ``DONE`` column),
    what counts as "awaiting your response" (``WAITING`` — the visually
    primary column), and how to group columns in a business/summary view.

    Members:
        BACKLOG: Not started; ideas / triage.
        ACTIVE: In progress.
        REVIEW: Done by the doer, awaiting a check.
        WAITING: Blocked on someone/something (the "awaiting you" column).
        DONE: Finished — entering a DONE column completes the card.
    """

    BACKLOG = "backlog", "Backlog"
    ACTIVE = "active", "Active"
    REVIEW = "review", "Review"
    WAITING = "waiting", "Waiting"
    DONE = "done", "Done"


class ChecklistState(models.TextChoices):
    """Three-valued checklist step state (docs/tasks-module.md §2).

    ``FAILED`` is a real state, not a missing ``DONE``: a manual-QA step that
    fails is ready-made steps-to-reproduce for a bug card, and the
    ``task.checklist_item_changed`` emit lets a projector react mechanically.
    Generic consumers that only need done/pending simply never use FAILED.
    """

    PENDING = "pending", "Pending"
    DONE = "done", "Done"
    FAILED = "failed", "Failed"


class Board(models.Model):
    """A kanban board: an ordered set of columns and the cards on them.

    ``feature_defs`` holds the board's custom-field *schema* (a list of
    stapel-attributes FeatureDef configs); cards store the *values*. The two
    have different owners and lifecycles — do not confuse ``feature_defs``
    (what the board's users define) with ``Task.origin_meta`` (what a
    projecting system writes).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Opaque host-supplied tenancy (workspace/org/tenant). Null = un-scoped;
    # the SCOPE_PROVIDER seam resolves & filters. The library never reads it.
    workspace_id = models.UUIDField(null=True, blank=True, db_index=True)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, blank=True, default="")
    # Custom-field schema: a list of stapel-attributes FeatureDef configs.
    feature_defs = models.JSONField(blank=True, default=list)
    settings = models.JSONField(blank=True, default=dict)

    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["workspace_id"], name="tsk_board_ws"),
        ]

    def __str__(self):
        return self.name


class Column(models.Model):
    """A column on a board. Its ``key`` is the card's status; its
    ``category`` is the fixed machine semantic (see :class:`ColumnCategory`).
    Columns are workflow-as-data — a board's set/order of columns is edited
    per board.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    board = models.ForeignKey(
        Board, on_delete=models.CASCADE, related_name="columns"
    )
    # Stable machine key = the card's status. Unique within a board.
    key = models.SlugField(max_length=64)
    name = models.CharField(max_length=255)
    # Optional i18n key for preset columns (name is the fallback display).
    name_key = models.CharField(max_length=255, blank=True, default="")
    order = models.PositiveIntegerField(default=0)
    category = models.CharField(
        max_length=16,
        choices=ColumnCategory.choices,
        default=ColumnCategory.BACKLOG,
    )
    # Stored, not enforced in v1 (docs/tasks-module.md §9).
    wip_limit = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["board", "order"]
        constraints = [
            models.UniqueConstraint(
                fields=["board", "key"], name="tsk_column_uniq_key"
            ),
        ]
        indexes = [
            models.Index(fields=["board", "order"], name="tsk_column_board_order"),
        ]

    def __str__(self):
        return f"{self.key} ({self.category})"


class Task(models.Model):
    """A card. Its status is the ``column`` it sits in; its order within the
    column is the fractional ``position`` (see ``positioning.py``).

    ``origin_type``/``origin_ref``/``origin_meta`` are the projection handles
    (docs/tasks-module.md §6): an external system upserts a card by
    ``(board, origin_type, origin_ref)`` (idempotent) and owns ``origin_meta``
    — the module treats all three as opaque and never interprets them.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    board = models.ForeignKey(
        Board, on_delete=models.CASCADE, related_name="tasks"
    )
    column = models.ForeignKey(
        Column, on_delete=models.PROTECT, related_name="tasks"
    )
    # Fractional index within the column (see positioning.py). Ties are
    # broken by (created_at, id); position is deliberately NOT unique so a
    # move writes only the moved row (concurrency-friendly).
    position = models.DecimalField(max_digits=40, decimal_places=20, default=Decimal(0))

    title = models.CharField(max_length=512)
    description = models.TextField(blank=True, default="")

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_tasks",
    )
    assignees = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="assigned_tasks"
    )
    priority = models.IntegerField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)

    # Sub-tasks / epic swimlanes.
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
    )
    # Dependencies ("this card is blocked by those cards").
    blocked_by = models.ManyToManyField(
        "self", symmetrical=False, blank=True, related_name="blocks"
    )

    # Custom-field VALUES (DAO JSON with display metadata) — schema lives on
    # the board's feature_defs, validated/normalized via the attributes seam.
    features = models.JSONField(blank=True, default=dict)

    # Projection handles (opaque to this module).
    origin_type = models.CharField(max_length=64, default="local", db_index=True)
    origin_ref = models.CharField(max_length=255, blank=True, default="")
    origin_meta = models.JSONField(blank=True, default=dict)

    completed_at = models.DateTimeField(null=True, blank=True)
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "created_at", "id"]
        constraints = [
            # Idempotent projection: a given origin maps to at most one card
            # per board. Applies only to real origin refs (local cards leave
            # origin_ref empty and are exempt).
            models.UniqueConstraint(
                fields=["board", "origin_type", "origin_ref"],
                condition=models.Q(origin_ref__gt=""),
                name="tsk_task_uniq_origin",
            ),
        ]
        indexes = [
            models.Index(fields=["board", "column"], name="tsk_task_board_col"),
            models.Index(fields=["column", "position"], name="tsk_task_col_pos"),
            models.Index(
                fields=["origin_type", "origin_ref"], name="tsk_task_origin"
            ),
        ]

    def __str__(self):
        return self.title


class ChecklistItem(models.Model):
    """A checklist step on a card (three-valued state; see
    :class:`ChecklistState`). ``ref`` is an opaque id of an external step
    (e.g. a scenario step) the item mirrors."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(
        Task, on_delete=models.CASCADE, related_name="checklist_items"
    )
    text = models.CharField(max_length=512)
    state = models.CharField(
        max_length=8, choices=ChecklistState.choices, default=ChecklistState.PENDING
    )
    order = models.PositiveIntegerField(default=0)
    ref = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["task", "order"]
        indexes = [
            models.Index(fields=["task", "order"], name="tsk_checkitem_task_order"),
        ]

    def __str__(self):
        return f"{self.text} ({self.state})"


class TaskComment(models.Model):
    """A lightweight anchored note on a card (not a chat thread). For a
    managed card it doubles as the human's reply channel (a comment on a
    WAITING card = an answer to a projected question)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(
        Task, on_delete=models.CASCADE, related_name="comments"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="task_comments",
    )
    body = models.TextField()

    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["task", "created_at"], name="tsk_comment_task_ct"),
        ]

    def __str__(self):
        return f"comment on {self.task_id}"
