"""Business flows of stapel-tasks (stapel_core.flows).

Autodiscovered via INSTALLED_APPS by ``autodiscover_flows()``. The Flow
objects live here; the HTTP steps are attached in ``views.py`` by stacking
``@flow_step(FLOW, ...)`` on the endpoint methods (views import this module
— the dependency points one way, no cycle).

The literals below are the canonical English source texts; every flow/step
derives an implicit i18n key (``flow.<id>.title`` /
``flow.<id>.description`` / ``flow.<id>.step.<order>.note``).
"""
from stapel_core.flows import Flow

# ─────────────────────────────────────────────────────────────────────────────
# tasks.board_setup — shaping the board before any card exists
# ─────────────────────────────────────────────────────────────────────────────

BOARD_SETUP = Flow(
    "tasks.board_setup",
    title="Set up a board",
    description=(
        "An admin of a workspace creates a board — from a named preset or "
        "from an explicit column list — and then shapes its columns: adds "
        "one, reorders them. Columns are workflow-as-data (key = the card's "
        "status, category = the fixed machine semantic), so this is the "
        "whole configuration surface of a board."
    ),
    actors=["Workspace admin"],
)
BOARD_SETUP.human(order=0, note="The admin opens the boards pane and asks for a new board")

# ─────────────────────────────────────────────────────────────────────────────
# tasks.card_lifecycle — a card from creation to archive
# ─────────────────────────────────────────────────────────────────────────────

CARD_LIFECYCLE = Flow(
    "tasks.card_lifecycle",
    title="Work a card from creation to archive",
    description=(
        "A member reads the board, adds a card, opens it, edits its fields, "
        "assigns it, discusses it in comments, ticks its checklist off and "
        "finally archives it. Entering a DONE-category column is what "
        "completes a card — the module emits task.completed there, never on "
        "an explicit 'close' action."
    ),
    actors=["Workspace member"],
)
CARD_LIFECYCLE.action(
    "task.created", order=20, note="Emitted when a card is created (projectors subscribe)"
)
CARD_LIFECYCLE.action(
    "task.completed", order=21, note="Emitted when a card enters a DONE-category column"
)

# ─────────────────────────────────────────────────────────────────────────────
# tasks.card_move — drag-and-drop through MOVE_POLICY
# ─────────────────────────────────────────────────────────────────────────────

CARD_MOVE = Flow(
    "tasks.card_move",
    title="Move a card across the board",
    description=(
        "A member drags a card to another column. The MOVE_POLICY seam has "
        "three answers, and the HTTP status carries which one: 200 applied, "
        "202 deferred (an external orchestrator owns the card and will move "
        "it), 409 denied with a localizable reason_key. A client renders the "
        "move optimistically and reconciles on the answer."
    ),
    actors=["Workspace member", "External orchestrator (MOVE_POLICY)"],
)
CARD_MOVE.human(order=0, note="The member drags a card into another column")
CARD_MOVE.function(
    "tasks.move", order=2, note="The same decision reached in-process over comm"
)
CARD_MOVE.action("task.moved", order=3, note="Emitted only when the move was applied")

__all__ = ["BOARD_SETUP", "CARD_LIFECYCLE", "CARD_MOVE"]
