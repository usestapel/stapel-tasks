"""stapel-tasks — Generic tasks and kanban boards for the Stapel framework.

A *generic* task domain: Board / Column / Task / ChecklistItem / TaskComment,
a REST surface, a workflow-as-data-lite model (columns carry a fixed
``category`` enum), custom fields via stapel-attributes (a soft seam that
works without it), and a full event surface through the transactional outbox.

The module deliberately knows nothing about any orchestrator / pipeline FSM.
External state machines *project* into it through the opaque
``origin_type``/``origin_ref``/``origin_meta`` handles and the ``MOVE_POLICY``
seam — see MODULE.md §"Projection seam".

Public API (lazily exported, PEP 562 — importing this package never pulls in
Django or requires configured settings):

- ``tasks_settings`` — resolved app settings (``stapel_tasks.conf``).
"""

__all__ = [
    "tasks_settings",
]

# name -> submodule that defines it. Resolution is deferred until first
# attribute access so that `import stapel_tasks` stays Django-free.
_LAZY_EXPORTS = {
    "tasks_settings": ".conf",
}


def __getattr__(name):
    if name in _LAZY_EXPORTS:
        from importlib import import_module

        value = getattr(import_module(_LAZY_EXPORTS[name], __name__), name)
        globals()[name] = value  # cache for subsequent lookups
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | set(__all__))
