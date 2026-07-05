# Changelog

All notable changes to stapel-tasks are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Pre-1.0 semver: **minor = breaking**, patch = compatible.

## [0.1.0] — 2026-07-06

Initial release. A *generic* task/kanban domain for the Stapel framework —
useful to any project on its own, and the substrate Stapel Studio's kanban
(system-design §7.17) projects onto without inheriting a private pipeline
FSM. Design: `docs/tasks-module.md` in the stapel workspace.

### Added
- **Board / Column / Task / ChecklistItem / TaskComment** models. A card's
  status *is* its column; the fixed `ColumnCategory` enum
  (`backlog/active/review/waiting/done`) carries the machine semantics no
  configuration may own (when to complete a card, what "awaiting you" means).
  UUID primary keys throughout; opaque nullable `workspace_id` tenancy (no FK
  to any Workspace model).
- **Workflow-as-data lite** — columns are per-board data; an optional
  `Board.settings["transitions"]` whitelist plus the `MOVE_POLICY` seam gate
  moves (`allow` / `deny(reason_key)` / `defer`). No FSM engine in the module.
- **Fractional-index positioning** (`positioning.py`) — drag-and-drop is a
  `move` writing a single row (midpoint between neighbours); a rare
  precision-exhausted gap triggers an O(n) column rebalance. `position` is
  not unique — concurrent drags never contend on the same row.
- **Projection seam (managed cards)** — opaque `origin_type`/`origin_ref`/
  `origin_meta` with a `(board, origin_type, origin_ref)` uniqueness
  constraint make an external orchestrator's projection idempotent
  (`services.upsert_task_by_origin`). The module knows nothing about any
  pipeline.
- **Custom fields via stapel-attributes — a *soft* seam** (`features.py`):
  a board owns the schema (`feature_defs`), a card stores DAO values
  (`features`); validation/normalization delegate to stapel-attributes when
  installed and degrade to a documented pass-through when it is not.
- **Event surface** through the transactional outbox (`mutate_and_emit` from
  the first commit; `emit-check` CI gate): `task.created`, `task.updated`,
  `task.moved`, `task.assigned`, `task.completed`, `task.comment_added`,
  `task.checklist_item_changed`, `task.archived`. Categories travel in
  move/completed payloads so subscribers react to semantics, not column names.
- **comm Functions** — `tasks.get`, `tasks.list_board`, `tasks.create`,
  `tasks.move`, `tasks.comment` (schemas in `schemas/functions/`) — the
  transport-agnostic mirror of `services` and the natural MCP-tool candidates.
- **REST API** — boards CRUD, columns CRUD + reorder, tasks CRUD + move +
  assign, comments, checklist items. DTO/serializer seams
  (`SerializerSeamMixin`), scope+permission seam (`SCOPE_PROVIDER`), anchor
  pagination on the card list, OpenAPI (drf-spectacular).
- **Board preset registry** — an open merge registry (`register_board_preset`
  + `STAPEL_TASKS["BOARD_PRESETS"]`) with a built-in `simple` preset.
- **GDPR** — a `user.deleted` consumer + `TasksGDPRProvider` that
  *anonymizes* (cards are shared team artifacts): authored cards/comments are
  de-linked, assignments dropped, nothing another user owns is destroyed.
- **System checks** on every seam config (E: SCOPE_PROVIDER / MOVE_POLICY /
  BOARD_PRESETS).

### Requires
- **stapel-core with the renamed taskstore label.** stapel-core's background
  `taskstore` app historically used the Django label `stapel_tasks`; this
  module owns that label for the generic task domain, so it must be installed
  alongside a stapel-core whose taskstore label is `stapel_taskstore`. See
  MODULE.md §"stapel-core requirement".

[0.1.0]: https://github.com/usestapel/stapel-tasks/releases/tag/v0.1.0
