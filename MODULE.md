# stapel-tasks — MODULE.md

> Agent-facing map of this module: what it provides, where to extend it
> without forking, and what not to do. Kept in the same PR as any change to a
> seam. See also README.md and CHANGELOG.md. Design of record:
> `docs/tasks-module.md` in the stapel workspace.

## What this module provides

- **Board / Column / Task / ChecklistItem / TaskComment** — the generic
  task/kanban domain. A card's **status is its column** (no separate status
  field); a column's `category` (`backlog/active/review/waiting/done`) is a
  fixed machine vocabulary that owns the semantics configuration must not
  (when to emit `task.completed`, what "awaiting you" means, how to group
  columns in a summary view). All PKs are UUIDs; tenancy is an opaque nullable
  `workspace_id` — **no FK** to any Workspace model.
- **Workflow-as-data lite** — columns are per-board data; moves default to
  any→any. An optional `Board.settings["transitions"]` whitelist and the
  `MOVE_POLICY` seam constrain moves. There is deliberately no FSM engine.
- **Fractional-index positioning** — drag-and-drop is a `move` that writes a
  single row (the moved card's `position` = midpoint of its neighbours); a
  rare precision-exhausted gap triggers an O(n) column rebalance. `position`
  is not unique, so concurrent drags never contend on one row.
- **Projection seam (managed cards)** — opaque `origin_type` / `origin_ref` /
  `origin_meta`, uniquely keyed `(board, origin_type, origin_ref)`, let an
  external orchestrator project idempotently. The module never interprets
  these and knows nothing of any pipeline. `origin_meta` (written by the
  projector) is distinct from `features` (defined by the board's users).
- **Custom fields via stapel-attributes (a soft seam)** — the board owns the
  schema (`feature_defs`), the card stores DAO values (`features`);
  validation/normalization delegate to stapel-attributes when installed and
  degrade to a pass-through when it is not.
- **Event surface + comm Functions** — all mutations emit through the outbox;
  Functions mirror the service layer for microservice topologies / MCP tools.
- **REST API** — boards/columns/tasks/comments/checklist, DTO + serializer
  seams, scope+permission seam, anchor pagination, OpenAPI.
- **GDPR** — a `user.deleted` consumer that *anonymizes* (cards are shared
  team artifacts).

## stapel-core requirement (label ownership)

stapel-core's background-task persistence app
(`stapel_core.django.taskstore`) historically claimed the Django label
`stapel_tasks` — an **unrelated** concept (a comm "Task" is an async
background function). This module owns the label `stapel_tasks` for the
generic task domain, so it must run against a **stapel-core whose taskstore
label is `stapel_taskstore`** (renamed upstream; a pre-1.0 minor). If a host's
`INSTALLED_APPS` includes both `stapel_core.django.taskstore` (old label) and
`stapel_tasks`, Django will raise a duplicate-label error. The test harness
here deliberately does **not** install `taskstore` (see `conftest.py`).

## Extension points (fork-free)

### 1. `SCOPE_PROVIDER` — tenancy + permissions (dotted path, REPLACE)

`STAPEL_TASKS["SCOPE_PROVIDER"]` points at a `stapel_tasks.scope.ScopeProvider`
subclass with three methods:

- `resolve(request) -> workspace_id | None` — the scope stamped on boards
  created via the request;
- `filter(queryset, request)` — restrict a queryset to the visible scope;
- `can(request, action, board=None) -> bool` — permission check for
  `READ` / `WRITE` / `ADMIN` (the constants in `stapel_tasks.scope`).

The default `DefaultScopeProvider` is a single global scope that allows
everything. A stapel-workspaces-aware host swaps in a provider that reads the
active `workspace_id` and checks roles (viewer→READ, member→WRITE,
admin→ADMIN). This module never imports stapel-workspaces — the host's
provider does. Guarded by system checks `E001`/`E002`.

### 2. `MOVE_POLICY` — drag-and-drop authorization (dotted path, REPLACE)

`STAPEL_TASKS["MOVE_POLICY"]` points at a `stapel_tasks.policy.MovePolicy`
subclass. `check(task, from_column, to_column, actor)` returns a
`MoveDecision`: `allow()` (apply), `deny(reason_key)` (reject with a
localizable key → HTTP 409 / `{"result":"denied"}`), or `defer()` (accept as
a command but do not apply → HTTP 202 / `{"result":"deferred"}` — the managed
card is moved later by its external owner).

The default `AllowAllMovePolicy` allows any move but honours a per-board
`transitions` whitelist. A Studio-style host registers a policy that permits
human input only where its automaton allows it. Guarded by `E003`/`E004`.

### 3. `BOARD_PRESETS` — board-shape presets (open registry, MERGE)

`STAPEL_TASKS["BOARD_PRESETS"]` and `register_board_preset(key, factory)`
merge **over** the built-in `simple` preset (a `factory` is a zero-arg
callable returning `list[ColumnSpec]`; `None` removes a built-in). Only the
mechanism (registry + category vocabulary) is open — a specific set of
pipeline states is private product semantics registered by the host that owns
it, never shipped here. Guarded by `E005`/`E006`.

### 4. Custom-field seam (`features.py`, soft attributes integration)

`Board.feature_defs` is a stapel-attributes FeatureDef config list;
`Task.features` holds the normalized DAO. `services.create_task` /
`update_task` call `features.validate_features` + `normalize_features`. With
stapel-attributes installed these run the real DTO→DAO pipeline; without it
the seam is a pass-through governed by `STORE_UNKNOWN_FEATURES` (keep raw DTO
vs. drop). Add vertical field types with attributes' own
`register_feature_type` — no change here.

### 5. Serializer seams (per view)

Every APIView mixes in `SerializerSeamMixin` with
`request_serializer_class` / `response_serializer_class` (+ `get_*` methods).
Subclass a view and set these to reshape a contract without rewriting the
method body. The DTOs (`dto.py`) are the API models — never ORM instances.

### 6. Event surface (comm — subscribe, don't fork)

| Kind | Name | Payload (essentials) |
|---|---|---|
| Emit | `task.created` | `board_id, task_id, title, column, category, creator_id, origin_*` |
| Emit | `task.updated` | `task_id, board_id, changed_fields[], actor_id` |
| Emit | `task.moved` | `task_id, board_id, from/to_column, from/to_category, actor_id` |
| Emit | `task.assigned` | `task_id, board_id, assignee_id, op(assigned/unassigned)` |
| Emit | `task.completed` | `task_id, board_id, completed_at, origin_ref` (entered a DONE column) |
| Emit | `task.comment_added` | `task_id, board_id, comment_id, author_id` (human→projector reply channel) |
| Emit | `task.checklist_item_changed` | `task_id, item_id, ref, state` (QA channel — a FAILED step) |
| Emit | `task.archived` | `task_id, board_id, actor_id` |
| Consume | `user.deleted` | GDPR anonymization |
| Function | `tasks.get` | `{task_id}` → `{task}` |
| Function | `tasks.list_board` | `{board_id, column?, category?, assignee_id?}` → columns + cards-by-column |
| Function | `tasks.create` | `{board_id, title, column?, features?, origin?}` → `{task_id}` |
| Function | `tasks.move` | `{task_id, to_column, index?}` → `{result: applied/deferred/denied, reason_key?}` |
| Function | `tasks.comment` | `{task_id, body}` → `{comment_id}` |

Reactions to these events (webhooks, notifications) are a subscription-layer
concern, not this module's — subscribe `@on_action` in-process until
stapel-webhooks arrives.

### 7. Service layer is the primary API

An in-process orchestrator projects cards by calling `stapel_tasks.services`
directly (`upsert_task_by_origin` / `move_task` / `update_task` /
`set_checklist_item_state`), which is the transport-agnostic core; the comm
Functions are the same operations for a microservice topology. There is no
special "orchestrator API" — origin handles + `MOVE_POLICY` + events suffice.

## Anti-patterns

- **Do not add a status field** — the column is the status; the category is
  the machine semantic. Splitting them re-introduces Jira-class drift.
- **Do not model pipeline states as categories** — categories are a fixed
  generic vocabulary. Private state machines belong in a private preset +
  `MOVE_POLICY`, projected via `origin_*`.
- **Do not make `position` unique** — it is a fractional index; uniqueness
  would turn every drag into an O(n) contended renumber.
- **Do not write `origin_meta` from a normal user path** — it is owned by the
  projecting system (service API / Function), read-only over REST.
- **Do not emit outside `mutate_and_emit`/`transaction.atomic`** — the
  `emit-check` gate fails the build; the outbox guarantee depends on it.
- **Do not import another module** — cross-module interaction is comm by
  string name only.

## App-layer override vs. upstream contribution

Litmus: **needs a monkeypatch or an edit inside the package → upstream**;
**a setting, subclass, registered provider or event subscription suffices →
app-layer.** Custom workflow rules (`MOVE_POLICY`), tenancy/permissions
(`SCOPE_PROVIDER`), board shapes (`BOARD_PRESETS`), field types (attributes'
`register_feature_type`), reshaped contracts (serializer seams) and reactions
to events are all app-layer. A missing seam ("should be configurable but only
a fork works") is an upstream bug — file it in
`docs/module-extension-gaps.md`.
