# stapel-tasks

[![CI](https://github.com/usestapel/stapel-tasks/actions/workflows/ci.yml/badge.svg)](https://github.com/usestapel/stapel-tasks/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/usestapel/stapel-tasks/graph/badge.svg)](https://codecov.io/gh/usestapel/stapel-tasks)

Generic tasks and kanban boards for the [Stapel framework](https://github.com/usestapel) —
composable Django apps that deploy as a monolith or as microservices without
changing module code.

A **generic task domain** — Board / Column / Task / ChecklistItem /
TaskComment, a REST surface, a full outbox event surface, and custom fields
via stapel-attributes. It is useful to any project by itself (a team runs a
board by hand), and it is the substrate an orchestrator *projects* onto: an
external state machine drives cards through opaque `origin_*` handles and the
`MOVE_POLICY` seam — the module knows nothing about the machine.

## Install

```bash
pip install stapel-tasks              # core
pip install "stapel-tasks[attributes]"  # + typed custom-field validation
```

```python
INSTALLED_APPS = [
    # ...
    "stapel_tasks",
]

# urls.py
path("tasks/", include("stapel_tasks.urls"))
```

> **Requires** a stapel-core whose background `taskstore` app uses the label
> `stapel_taskstore` — this module owns the Django label `stapel_tasks`. See
> MODULE.md.

## Concepts

- **Board** — an ordered set of columns and the cards on them. Owns the
  custom-field *schema* (`feature_defs`) and optional workflow `settings`.
- **Column** — a status. Its `key` is the card's status; its `category`
  (`backlog/active/review/waiting/done`) is the fixed machine semantic.
- **Task (card)** — status = its column; order within the column is a
  fractional `position` (drag-and-drop moves write one row). Custom-field
  values live in `features`; a projecting system writes `origin_meta`.
- **Move** — drag-and-drop is a `move` validated by `MOVE_POLICY`:
  `allow` / `deny(reason_key)` / `defer` (the managed-card path).

```python
from stapel_tasks import services

board = services.create_board(name="Team", preset="simple")
card = services.create_task(board=board, title="Ship it")
services.move_task(card, to_column=board.columns.get(key="done"))  # emits task.completed
```

## comm surface

| Kind | Name | Purpose |
|---|---|---|
| Emit | `task.created` / `task.updated` / `task.moved` / `task.assigned` / `task.completed` / `task.comment_added` / `task.checklist_item_changed` / `task.archived` | Card lifecycle facts (via the outbox) |
| Consume | `user.deleted` | GDPR anonymization |
| Function | `tasks.get` / `tasks.list_board` / `tasks.create` / `tasks.move` / `tasks.comment` | Machine interface / MCP-tool candidates |

## Settings (`STAPEL_TASKS`)

| Key | Default | What it customizes |
|---|---|---|
| `SCOPE_PROVIDER` | single global scope, allow-all | Tenancy resolution/filtering + permissions |
| `MOVE_POLICY` | allow any move (honours `transitions`) | Drag-and-drop authorization |
| `BOARD_PRESETS` | `{}` (merged over built-in `simple`) | Board-shape presets |
| `STORE_UNKNOWN_FEATURES` | `True` | Keep raw custom fields when attributes is absent |
| `DEFAULT_PAGE_SIZE` | `100` | Card-list page size |

See **MODULE.md** for the full seam map (providers, registries, serializer
seams, comm tables, anti-patterns, override-vs-upstream).

## License

MIT
