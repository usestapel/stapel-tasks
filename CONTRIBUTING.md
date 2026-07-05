# Contributing to stapel-tasks

Thanks for helping build the Stapel framework.

## Ground rules

- **Layering.** stapel-tasks is an L2 module: it depends only on
  `stapel-core` (and, softly, `stapel-attributes`). It must never import
  another module — cross-module interaction is comm (Action/Function) by
  string name + JSON schema only.
- **Every seam has a test.** Swapping a provider, merging a registry,
  tripping a system check — extension points are covered by tests, not just
  the happy path.
- **Outbox discipline.** Every mutation that emits does so through
  `stapel_core.comm.mutate_and_emit` (or a `transaction.atomic()` block); the
  `emit-check` CI gate enforces it.
- **Errors are keys.** Responses carry `error.<status>.<slug>` keys, never
  human strings.

## Override vs. upstream

Before changing this package, decide: does the change require a monkeypatch
or an edit *inside* the package? Then it is an upstream contribution. Does a
setting, subclass, registered provider or event subscription suffice? Then it
is an app-layer override — keep it in your project. MODULE.md maps every seam.

## Local workflow

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[all]"
pip install pytest pytest-django pytest-cov ruff
./setup-hooks.sh                      # ruff pre-commit/pre-push
ruff check . --select E,F,W --ignore E501
python -m stapel_core.lint.emit_check .
pytest tests/
```

Every behavioral change needs a CHANGELOG entry and, if it touches a seam, a
MODULE.md update in the same PR.
