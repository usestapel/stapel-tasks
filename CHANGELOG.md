# Changelog

All notable changes to stapel-tasks are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Pre-1.0 semver: **minor = breaking**, patch = compatible.

## [0.2.0] — 2026-08-16

### Security — the tenancy seam has a third answer

`DefaultScopeProvider.can` returned `True` unconditionally, so all eleven views
asked a question with exactly one possible answer. It now answers with the
third principal state (`stapel_core.django.scope`): a registered account
holding no mandate anywhere is not a member of one global scope, it is a member
of nothing. Where nothing can answer the question — a genuinely standalone
deployment — the permissive behaviour stands, and `checks.py` says so out loud
instead of leaving it implied.

- `error.503.tasks_scope_unresolved` (`ERR_503_SCOPE_UNRESOLVED`): a lookup
  that failed is not a permission that was granted. `ScopeProvider.can`
  documents `MandateUnavailable` as the way to say "could not find out".
- Board creation with NULL tenancy is refused where a workspace is expected —
  a board belonging to no workspace is visible to everyone who can list.
- New system checks for the shipped single-scope default carrying a
  multi-tenant host.

**Breaking** (pre-1.0: minor = breaking): a custom provider that answered
`can` with a bare `False` on lookup failure now hides a fault as a denial;
raise `MandateUnavailable` instead. Deployments where guests could reach
boards will see them refused.

### Changed — `stapel-core` floor raised to 0.27.0

The floor had been `>=0.10` since long before this module used any of core's
tenancy machinery. `django/scope.py` exists only in 0.27.0.

## [0.1.8] — 2026-08-02

Fix-up: 0.1.7's `publish.yml` test gate never installed `stapel-tools`,
unlike `ci.yml` — the new `docs/llms.txt` drift/determinism tests in
`tests/test_contract.py` failed at the tag-triggered publish workflow
(0.1.7 never reached PyPI). `publish.yml` now installs `stapel-tools`
the same way `ci.yml` does. No other change.

## [0.1.7] — 2026-08-02

Packaging/docs catch-up, no behavior change:

- Badge canon + Python 3.14 classifier; migration-lint enabled in CI.
- `docs/llms.txt` — the fifth contract artifact (badge-canon §3),
  rendered from the curated (hand-authored) `docs/capabilities.json` by
  `stapel_tools.llms_txt`; `capabilities.json`'s `version` field brought
  in sync with `pyproject.toml` (0.1.5 → 0.1.7), no other change to its
  hand-authored content.

## [0.1.5] — 2026-07-17

Fleet follow-up to stapel-core 0.12.0 (legacy shim sweep). No source
changes needed. Full suite green against core 0.12.0.

### Changed
- `stapel-core` dependency ceiling `<0.12` → `<0.13`.

## [0.1.4] — 2026-07-17

### Changed
- `stapel-core` ceiling raised `>=0.10,<0.11` → `>=0.10,<0.12` (core 0.11
  fleet re-pin: default bus, nav, config-checks, error params/language —
  additive for modules). Suite green as-is.

## [0.1.2] — 2026-07-11

Patch release: HEAD had advanced past the `v0.1.1` tag without a release;
`0.1.2` publishes the accumulated non-code housekeeping and fixes the core
pin. No behavior changes.

### Fixed
- Repinned `stapel-core` to the `>=0.10,<0.11` window — the published
  `0.10.0`; the old `>=0.8,<0.9` pin no longer resolved against PyPI.

### Added
- `CONFIG.MD` registry (static-scaffold-and-config.md §2): every key
  stapel-tasks reads through its AppSettings namespace, with source,
  purpose, required flag and default — aggregated into a scaffolded
  project's root CONFIG.MD by `assemble_scaffold`.
- `make migration-lint` + CI step (release-management.md §3; the CI step
  ships commented-out until module CI can install stapel-tools).

### Changed
- MODULE.md: AS-5 access-category review documented — all models stay on
  the implicit `@access.standard` (business/domain objects; none match the
  ops/secret shape).
- README: CI/coverage/PyPI badges.

## [0.1.1] — 2026-07-06

### Changed
- Pinned `stapel-core` to the `>=0.8,<0.9` window (library-standard §7.1: one
  minor window; floor `0.8.0` is published on PyPI — no pin into the void).
- Pinned `stapel-attributes` to the `>=0.3,<0.4` window (was `>=0.1,<0.2` —
  a stale sibling pin predating attributes 0.3.x; same §7.1 rule).

- CI: added the release-track job (library-standard §7.4) — installs the package
  the way an end user does (`pip install .`, dependencies resolved from PyPI
  strictly by the declared pins, no git-main core, no editable siblings), asserts
  `stapel-core` resolves inside the `0.8` window, and runs an import smoke.
  Advisory (continue-on-error) until the whole stapel graph is on PyPI; becomes
  the blocking precondition for a `vX.Y.Z` tag once it is.


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

[0.1.2]: https://github.com/usestapel/stapel-tasks/releases/tag/v0.1.2
[0.1.1]: https://github.com/usestapel/stapel-tasks/releases/tag/v0.1.1
[0.1.0]: https://github.com/usestapel/stapel-tasks/releases/tag/v0.1.0
