"""MOVE_POLICY — the drag-and-drop / ``tasks.move`` decision seam.

A move (card -> column at a position) is validated by a ``MovePolicy``
(dotted path in ``STAPEL_TASKS["MOVE_POLICY"]``). Three outcomes
(docs/tasks-module.md §3, §6):

- ``allow`` — apply the move.
- ``deny(reason_key)`` — reject with a localizable error key (HTTP 4xx / a
  ``{"result": "denied", "reason_key": ...}`` Function result). The default
  never denies.
- ``defer`` — accept the move *as a command* but do not apply it: a managed
  card whose canonical state lives in an external orchestrator. The
  orchestrator moves the card itself (via the service API) after it acts.
  Surfaced as HTTP 202 / ``{"result": "deferred"}``.

This is the synchronous half of the managed-card contract; the async half is
the ``task.comment_added`` / ``task.checklist_item_changed`` emits an
orchestrator subscribes to.
"""
from __future__ import annotations

from dataclasses import dataclass

ALLOW = "allow"
DENY = "deny"
DEFER = "defer"


@dataclass(frozen=True)
class MoveDecision:
    """Outcome of a move policy check. Build via :meth:`allow` /
    :meth:`deny` / :meth:`defer`."""

    result: str
    reason_key: str | None = None

    @classmethod
    def allow(cls) -> "MoveDecision":
        return cls(ALLOW)

    @classmethod
    def deny(cls, reason_key: str) -> "MoveDecision":
        return cls(DENY, reason_key=reason_key)

    @classmethod
    def defer(cls) -> "MoveDecision":
        return cls(DEFER)

    @property
    def is_allowed(self) -> bool:
        return self.result == ALLOW

    @property
    def is_denied(self) -> bool:
        return self.result == DENY

    @property
    def is_deferred(self) -> bool:
        return self.result == DEFER


class MovePolicy:
    """Contract for move validation. Subclass and point
    ``STAPEL_TASKS["MOVE_POLICY"]`` at it."""

    def check(self, *, task, from_column, to_column, actor) -> MoveDecision:
        raise NotImplementedError


class AllowAllMovePolicy(MovePolicy):
    """Any move is allowed — a plain human board needs no state machine.

    Additionally honours an optional per-board ``transitions`` whitelist in
    ``Board.settings`` (``{"transitions": {"from_key": ["to_key", ...]}}``):
    a declared source key restricts its allowed targets; an undeclared source
    key is unrestricted. Absent settings = any -> any.
    """

    def check(self, *, task, from_column, to_column, actor) -> MoveDecision:
        transitions = (task.board.settings or {}).get("transitions")
        if not transitions or from_column.key == to_column.key:
            return MoveDecision.allow()
        allowed = transitions.get(from_column.key)
        if allowed is not None and to_column.key not in allowed:
            from .errors import ERR_409_TRANSITION_NOT_ALLOWED

            return MoveDecision.deny(ERR_409_TRANSITION_NOT_ALLOWED)
        return MoveDecision.allow()


def get_move_policy() -> MovePolicy:
    """Resolve the configured policy (already import_string'd by conf)."""
    from .conf import tasks_settings

    policy = tasks_settings.MOVE_POLICY
    return policy() if isinstance(policy, type) else policy
