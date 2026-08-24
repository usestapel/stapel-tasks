# CONFIG.MD — stapel-tasks

Config registry for **stapel-tasks** (`static-scaffold-and-config.md` §2). One
row per configuration key the module reads, its **source** (`env` = the process
environment / the `STAPEL_TASKS` settings dict), what it is for, whether it is
required, and its default.

Every key is read through `tasks_settings` (`stapel_tasks.conf.AppSettings`,
namespace `STAPEL_TASKS`). Resolution order per key: `settings.STAPEL_TASKS`
dict → a flat Django setting of the same name → environment variable → the
default below.

stapel-tasks integrates **stapel-attributes** as a *soft* seam (guarded import,
degrades to pass-through when absent — see `STORE_UNKNOWN_FEATURES`), so
attributes is an optional dependency, NOT wired in automatically by the
scaffolder.

## stapel-tasks

| Key | Source | Purpose | Required | Default |
|-----|--------|---------|----------|---------|
| SCOPE_PROVIDER | env | dotted path to a ScopeProvider (resolve/filter/permission seam). Default is a single global allow-all scope. | no | stapel_tasks.scope.DefaultScopeProvider |
| MOVE_POLICY | env | dotted path to a MovePolicy (allow/deny/defer a card move). Default allows any move. | no | stapel_tasks.policy.AllowAllMovePolicy |
| BOARD_PRESETS | env | board-shape presets merged OVER the built-ins (callable → list[ColumnSpec]); None removes. | no | {} |
| DEFAULT_PAGE_SIZE | env | default page size for the paginated board/task listing. | no | 100 |
| BOARD_CARDS_MAX | env | cap on the un-paginated whole-board read (`GET boards/{id}/cards`); past it the answer carries `truncated: true`. | no | 2000 |
| PRIORITY_SCALE | env | priority steps served by `GET boards/presets` (`[{value, label_key}]`); the stored `priority` itself stays an unconstrained int. | no | low/normal/high/urgent (1-4) |
| STORE_UNKNOWN_FEATURES | env | when stapel-attributes is absent (or a board declares no feature_defs), keep the raw custom-field DTO on the card rather than dropping it. | no | true |
