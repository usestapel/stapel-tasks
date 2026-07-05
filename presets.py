"""Board-shape presets — an open merge registry.

A preset is a zero-arg callable returning an ordered list of
:class:`ColumnSpec` (the columns a new board starts with). Built-ins live in
``BUILTIN_PRESETS``; a host merges its own OVER them via
``STAPEL_TASKS["BOARD_PRESETS"]`` or the runtime ``register_board_preset``
API (merge semantics: a host key with the same name overrides the built-in;
``None`` removes a built-in).

Only the *mechanism* (registry + category vocabulary) is open. A specific
set of pipeline states is private product semantics and is registered by the
host that owns it — it never ships here (docs/tasks-module.md §3).
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import ColumnCategory


@dataclass(frozen=True)
class ColumnSpec:
    """One column of a preset board.

    Attributes:
        key: Stable machine key (the card's status). Unique within a board.
        name: Display name.
        category: Fixed machine semantic (:class:`ColumnCategory`).
        name_key: Optional i18n key for the display name.
        wip_limit: Optional WIP limit (stored, not enforced in v1).
    """

    key: str
    name: str
    category: str
    name_key: str = ""
    wip_limit: int | None = None


def _simple() -> list[ColumnSpec]:
    return [
        ColumnSpec("todo", "To do", ColumnCategory.BACKLOG, name_key="tasks.column.todo"),
        ColumnSpec(
            "in_progress",
            "In progress",
            ColumnCategory.ACTIVE,
            name_key="tasks.column.in_progress",
        ),
        ColumnSpec("done", "Done", ColumnCategory.DONE, name_key="tasks.column.done"),
    ]


# Built-in presets (never restated by a host — merged OVER).
BUILTIN_PRESETS: dict[str, object] = {
    "simple": _simple,
}

# Runtime overrides registered via register_board_preset().
_runtime_presets: dict[str, object] = {}


def register_board_preset(key: str, factory) -> None:
    """Register/override a board preset at runtime. ``factory`` is a zero-arg
    callable returning a list of :class:`ColumnSpec`; pass ``None`` to remove
    a built-in."""
    _runtime_presets[key] = factory


def reset_presets() -> None:
    """Drop all runtime-registered presets (test hygiene)."""
    _runtime_presets.clear()


def get_board_presets() -> dict[str, object]:
    """Effective preset map: built-ins, then settings, then runtime — later
    layers override; a ``None`` value removes a key."""
    from .conf import tasks_settings

    merged: dict[str, object] = dict(BUILTIN_PRESETS)
    for layer in (tasks_settings.BOARD_PRESETS, _runtime_presets):
        for key, factory in (layer or {}).items():
            if factory is None:
                merged.pop(key, None)
            else:
                merged[key] = factory
    return merged


def get_preset_columns(key: str) -> list[ColumnSpec]:
    """Column specs for preset ``key``. Raises ``KeyError`` if unknown."""
    presets = get_board_presets()
    if key not in presets:
        raise KeyError(key)
    return list(presets[key]())
