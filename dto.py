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
class TaskPageResponse:
    """One keyset page of the card feed (``GET boards/{id}/tasks``).

    The envelope stapel-core's anchor pagination answers with. Note the
    order is ``-created_at`` — a feed, not the board shape; read
    ``BoardCardsResponse`` for the latter.

    Attributes:
        items: The cards on this page.
        next_anchor: Anchor to pass as ``anchor`` for the next page (null at the end).
        prev_anchor: Anchor for the previous page (null at the start).
        has_next: Whether more cards follow this page.
        has_prev: Whether cards precede this page.
        count: Number of cards on this page.
    """

    items: List[TaskResponse] = field(default_factory=list)
    next_anchor: Optional[str] = None
    prev_anchor: Optional[str] = None
    has_next: bool = False
    has_prev: bool = False
    count: int = 0


@dataclass
class ArchivedResponse:
    """Answer to an archive (soft-delete) call.

    Attributes:
        status: Always "archived" — the row is kept, not deleted.
    """

    status: str = "archived"


@dataclass
class BoardCardsResponse:
    """A whole board in one read: its columns, and its cards grouped by column.

    The paginated ``GET boards/{id}/tasks`` answers in ``-created_at`` order
    (a feed), but a card's place on a board is its fractional ``position``
    within its column. This read is the board-shaped one: every non-archived
    card, grouped by column key, each group ordered by ``position``, columns
    in board order — the same shape the ``tasks.list_board`` comm Function
    returns. Un-paginated and capped by ``BOARD_CARDS_MAX``.

    Attributes:
        board_id: The board's id.
        columns: The board's columns in display order.
        cards: Card lists keyed by column key; every column key is present.
        count: Number of cards returned.
        truncated: True when the cap cut the answer short — the client must
            narrow with filters to see the rest.
    """

    board_id: str
    columns: List[ColumnResponse] = field(default_factory=list)
    cards: Dict[str, List[TaskResponse]] = field(default_factory=dict)
    count: int = 0
    truncated: bool = False


@dataclass
class PresetColumnResponse:
    """One column of a board preset.

    Attributes:
        key: Stable machine key the created column will carry.
        name: Display name.
        category: Fixed machine semantic (backlog/active/review/waiting/done).
        name_key: Optional i18n key for the display name.
        wip_limit: Optional WIP limit.
    """

    key: str
    name: str
    category: str
    name_key: str = ""
    wip_limit: Optional[int] = None


@dataclass
class BoardPresetResponse:
    """A board-shape preset.

    Attributes:
        key: Preset key to pass as ``preset`` when creating a board.
        columns: The columns a board created from it starts with.
    """

    key: str
    columns: List[PresetColumnResponse] = field(default_factory=list)


@dataclass
class VocabularyTermResponse:
    """One term of a fixed vocabulary.

    Attributes:
        value: The machine value carried in requests and responses.
        label: The canonical English label (a client localizes by value).
    """

    value: str
    label: str


@dataclass
class PriorityLevelResponse:
    """One step of the configured priority scale.

    Attributes:
        value: The integer written to a card's ``priority``.
        label_key: i18n key a client renders for this step.
    """

    value: int
    label_key: str


@dataclass
class BoardVocabularyResponse:
    """Everything a board-creation form needs that is otherwise undiscoverable.

    Presets, the fixed column-category vocabulary, the checklist states and
    the host's configured priority scale (``priority`` itself is an
    unconstrained int in the table — this is the scale a client offers).

    Attributes:
        presets: Board-shape presets, ``key`` sorted.
        categories: The fixed column-category vocabulary.
        checklist_states: The fixed checklist-state vocabulary.
        priority_scale: The configured priority steps (may be empty).
    """

    presets: List[BoardPresetResponse] = field(default_factory=list)
    categories: List[VocabularyTermResponse] = field(default_factory=list)
    checklist_states: List[VocabularyTermResponse] = field(default_factory=list)
    priority_scale: List[PriorityLevelResponse] = field(default_factory=list)


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
