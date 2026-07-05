"""Dataclass DTOs — the API models of stapel-tasks (never ORM instances)."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


# ── Response DTOs ───────────────────────────────────────────────────────


@dataclass
class ColumnResponse:
    """A board column.

    Attributes:
        id: Column id (UUID).
        board_id: Owning board id.
        key: Stable machine key = the card's status.
        name: Display name.
        name_key: Optional i18n key for the display name.
        order: Position of the column on the board.
        category: Fixed machine semantic (backlog/active/review/waiting/done).
        wip_limit: Optional WIP limit (stored, not enforced in v1).
    """

    id: str
    board_id: str
    key: str
    name: str
    name_key: str
    order: int
    category: str
    wip_limit: Optional[int] = None


@dataclass
class ChecklistItemResponse:
    """A checklist step.

    Attributes:
        id: Item id (UUID).
        text: Step text.
        state: pending/done/failed.
        order: Order within the card's checklist.
        ref: Opaque id of an external step this item mirrors.
    """

    id: str
    text: str
    state: str
    order: int
    ref: str = ""


@dataclass
class CommentResponse:
    """A comment on a card.

    Attributes:
        id: Comment id (UUID).
        task_id: Card id.
        author_id: Author's user id (null if anonymized).
        body: Comment text.
        created_at: Creation time.
    """

    id: str
    task_id: str
    author_id: Optional[str]
    body: str
    created_at: datetime


@dataclass
class TaskResponse:
    """A card.

    Attributes:
        id: Card id (UUID).
        board_id: Owning board id.
        column: The card's column key (= its status).
        category: The card's column category.
        position: Fractional position within the column (stringified Decimal).
        title: Card title.
        description: Free-text description.
        creator_id: Creator's user id (null if anonymized).
        assignee_ids: Assigned users.
        priority: Optional priority.
        due_at: Optional due date.
        parent_id: Parent card id (sub-tasks/epics).
        blocked_by_ids: Cards this card is blocked by.
        features: Custom-field values (DAO with display metadata).
        origin_type: Projection namespace ("local" for user-created cards).
        origin_ref: Opaque id of the projected source (null for local).
        origin_meta: Projection metadata (owned by the projecting system).
        completed_at: Set when the card entered a DONE column.
        is_archived: Soft-delete flag.
        checklist: Checklist steps.
        created_at: Creation time.
    """

    id: str
    board_id: str
    column: str
    category: str
    position: str
    title: str
    description: str
    creator_id: Optional[str]
    assignee_ids: List[str] = field(default_factory=list)
    priority: Optional[int] = None
    due_at: Optional[datetime] = None
    parent_id: Optional[str] = None
    blocked_by_ids: List[str] = field(default_factory=list)
    features: Dict[str, Any] = field(default_factory=dict)
    origin_type: str = "local"
    origin_ref: Optional[str] = None
    origin_meta: Dict[str, Any] = field(default_factory=dict)
    completed_at: Optional[datetime] = None
    is_archived: bool = False
    checklist: List[ChecklistItemResponse] = field(default_factory=list)
    created_at: Optional[datetime] = None


@dataclass
class BoardResponse:
    """A board with its columns.

    Attributes:
        id: Board id (UUID).
        workspace_id: Opaque tenancy (null if un-scoped).
        name: Board name.
        slug: Board slug.
        feature_defs: Custom-field schema (stapel-attributes FeatureDef list).
        settings: Board settings (may hold a `transitions` whitelist).
        columns: The board's columns.
        is_archived: Soft-delete flag.
        created_at: Creation time.
    """

    id: str
    workspace_id: Optional[str]
    name: str
    slug: str
    feature_defs: List[Any] = field(default_factory=list)
    settings: Dict[str, Any] = field(default_factory=dict)
    columns: List[ColumnResponse] = field(default_factory=list)
    is_archived: bool = False
    created_at: Optional[datetime] = None


@dataclass
class MoveResponse:
    """Outcome of a move.

    Attributes:
        result: applied/deferred/denied.
        reason_key: Localizable reason key when denied (else null).
    """

    result: str
    reason_key: Optional[str] = None


# ── Request DTOs ────────────────────────────────────────────────────────


@dataclass
class BoardCreateRequest:
    """Create a board.

    Attributes:
        name: Board name.
        preset: Board preset key (default "simple"); ignored if columns given.
        columns: Explicit column specs (key/name/category/...) — overrides preset.
        feature_defs: Custom-field schema.
        slug: Optional slug.
        settings: Optional board settings.
    """

    name: str
    preset: str = "simple"
    columns: Optional[List[Dict[str, Any]]] = None
    feature_defs: List[Any] = field(default_factory=list)
    slug: str = ""
    settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BoardUpdateRequest:
    """Patch a board (only provided fields change).

    Attributes:
        name: New name.
        feature_defs: New custom-field schema.
        settings: New settings.
    """

    name: Optional[str] = None
    feature_defs: Optional[List[Any]] = None
    settings: Optional[Dict[str, Any]] = None


@dataclass
class ColumnCreateRequest:
    """Add a column to a board.

    Attributes:
        key: Stable machine key.
        name: Display name.
        category: backlog/active/review/waiting/done.
        order: Optional position (append if omitted).
        name_key: Optional i18n key.
        wip_limit: Optional WIP limit.
    """

    key: str
    name: str
    category: str
    order: Optional[int] = None
    name_key: str = ""
    wip_limit: Optional[int] = None


@dataclass
class ColumnReorderRequest:
    """Reorder a board's columns.

    Attributes:
        keys: Column keys in the desired order.
    """

    keys: List[str] = field(default_factory=list)


@dataclass
class TaskCreateRequest:
    """Create a card.

    Attributes:
        title: Card title.
        description: Optional description.
        column: Target column key (defaults to the first column).
        features: Custom-field values DTO.
        priority: Optional priority.
        due_at: Optional due date.
        parent_id: Parent card id.
        assignee_ids: Users to assign.
    """

    title: str
    description: str = ""
    column: Optional[str] = None
    features: Optional[Dict[str, Any]] = None
    priority: Optional[int] = None
    due_at: Optional[datetime] = None
    parent_id: Optional[str] = None
    assignee_ids: List[str] = field(default_factory=list)


@dataclass
class TaskUpdateRequest:
    """Patch a card (only provided fields change).

    Attributes:
        title: New title.
        description: New description.
        priority: New priority.
        due_at: New due date.
        features: New custom-field values DTO.
    """

    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[int] = None
    due_at: Optional[datetime] = None
    features: Optional[Dict[str, Any]] = None


@dataclass
class TaskMoveRequest:
    """Move a card (drag-and-drop).

    Attributes:
        to_column: Target column key.
        index: Target index within the column (append if omitted).
    """

    to_column: str
    index: Optional[int] = None


@dataclass
class TaskAssignRequest:
    """Replace a card's assignee set.

    Attributes:
        assignee_ids: The new full set of assignee user ids.
    """

    assignee_ids: List[str] = field(default_factory=list)


@dataclass
class CommentCreateRequest:
    """Add a comment.

    Attributes:
        body: Comment text.
    """

    body: str


@dataclass
class ChecklistItemCreateRequest:
    """Add a checklist step.

    Attributes:
        text: Step text.
        ref: Opaque external-step id.
        order: Optional order.
    """

    text: str
    ref: str = ""
    order: Optional[int] = None


@dataclass
class ChecklistItemStateRequest:
    """Set a checklist step's state.

    Attributes:
        state: pending/done/failed.
    """

    state: str
