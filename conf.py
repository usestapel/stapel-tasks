"""Settings namespace for stapel-tasks.

All configuration is read through ``tasks_settings`` (lazily, at call time)
— never via module-level ``os.getenv`` (values would freeze at import).
Resolution order per key: ``settings.STAPEL_TASKS`` dict -> flat Django
setting of the same name -> environment variable -> default below.

Dotted-path keys listed in ``import_strings`` are resolved with
``import_string`` — the fork-free escape hatch for swappable behavior.

The extension seams (see MODULE.md):

- ``SCOPE_PROVIDER`` — resolves the opaque ``workspace_id`` from a request,
  filters querysets by it, and answers permission questions
  (viewer/member/admin). The default is a single-global-scope allow-all
  provider; a workspaces-aware host swaps it. The library never interprets
  the scope itself.
- ``MOVE_POLICY`` — decides whether a card may move from one column to
  another (drag-and-drop / ``tasks.move``): ``allow`` / ``deny(reason_key)``
  / ``defer``. ``defer`` is the managed-card path — the move is accepted for
  processing but not applied (an external orchestrator will move it). The
  default allows any move.
- ``BOARD_PRESETS`` — board-shape presets merged OVER the built-ins
  (``simple``). A value is a callable ``() -> list[ColumnSpec]``; ``None``
  removes a built-in. Register at runtime with ``register_board_preset``.
- ``STORE_UNKNOWN_FEATURES`` — when stapel-attributes is not installed (or a
  board declares no ``feature_defs``), whether the feature seam stores the
  submitted custom-field DTO verbatim (``True``) or drops it (``False``).
- ``PRIORITY_SCALE`` — the priority vocabulary served by
  ``GET boards/presets``. The stored ``priority`` stays an unconstrained
  int; this is the list a generic client offers.
- ``BOARD_CARDS_MAX`` — cap on the un-paginated whole-board read.
"""
from stapel_core.conf import AppSettings

tasks_settings = AppSettings(
    "STAPEL_TASKS",
    defaults={
        # Dotted path to a ScopeProvider (resolve/filter/permission seam).
        # The default is a no-op single global scope that allows everything.
        "SCOPE_PROVIDER": "stapel_tasks.scope.DefaultScopeProvider",
        # Dotted path to a MovePolicy. The default allows any move.
        "MOVE_POLICY": "stapel_tasks.policy.AllowAllMovePolicy",
        # Board presets merged OVER presets.BUILTIN_PRESETS. A value is a
        # zero-arg callable returning a list of ColumnSpec; None removes a
        # built-in.
        "BOARD_PRESETS": {},
        # Default page size for the paginated board/task listing.
        "DEFAULT_PAGE_SIZE": 100,
        # Hard cap on the un-paginated whole-board read
        # (GET boards/{id}/cards). A board past the cap answers with the
        # newest BOARD_CARDS_MAX cards and `truncated: true` — a kanban view
        # is a bounded surface, and a client that must show more filters.
        "BOARD_CARDS_MAX": 2000,
        # The priority vocabulary served by GET boards/presets. `priority`
        # is an unconstrained int in the table on purpose (a host may run a
        # 1..10 scale); this is what a generic client renders as a picker.
        # Each entry is {"value": int, "label_key": str}.
        "PRIORITY_SCALE": [
            {"value": 1, "label_key": "tasks.priority.low"},
            {"value": 2, "label_key": "tasks.priority.normal"},
            {"value": 3, "label_key": "tasks.priority.high"},
            {"value": 4, "label_key": "tasks.priority.urgent"},
        ],
        # When attributes is absent, keep the raw custom-field DTO on the
        # card (soft seam) rather than dropping it.
        "STORE_UNKNOWN_FEATURES": True,
    },
    import_strings=("SCOPE_PROVIDER", "MOVE_POLICY"),
)

__all__ = ["tasks_settings"]
