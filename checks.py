"""Django system checks for stapel-tasks configuration.

Policy (docs/library-standard.md §3.7): E-level for configuration the
service cannot run with; W-level for entries that only degrade lazily.

- SCOPE_PROVIDER unimportable / not a ScopeProvider -> E (every request
  needs it to resolve/filter scope and check permissions).
- MOVE_POLICY unimportable / not a MovePolicy -> E (every move needs it).
- BOARD_PRESETS entries must be callable or None -> E (board creation from a
  broken preset would crash).
"""
from django.core import checks


@checks.register(checks.Tags.compatibility)
def check_scope_provider(app_configs, **kwargs):
    from .conf import tasks_settings
    from .scope import ScopeProvider

    try:
        provider = tasks_settings.SCOPE_PROVIDER
    except Exception as exc:
        return [
            checks.Error(
                f"STAPEL_TASKS['SCOPE_PROVIDER'] could not be imported: {exc}",
                id="stapel_tasks.E001",
            )
        ]
    target = provider if isinstance(provider, type) else type(provider)
    if not issubclass(target, ScopeProvider):
        return [
            checks.Error(
                "STAPEL_TASKS['SCOPE_PROVIDER'] must be a ScopeProvider subclass",
                id="stapel_tasks.E002",
            )
        ]
    return []


@checks.register(checks.Tags.compatibility)
def check_move_policy(app_configs, **kwargs):
    from .conf import tasks_settings
    from .policy import MovePolicy

    try:
        policy = tasks_settings.MOVE_POLICY
    except Exception as exc:
        return [
            checks.Error(
                f"STAPEL_TASKS['MOVE_POLICY'] could not be imported: {exc}",
                id="stapel_tasks.E003",
            )
        ]
    target = policy if isinstance(policy, type) else type(policy)
    if not issubclass(target, MovePolicy):
        return [
            checks.Error(
                "STAPEL_TASKS['MOVE_POLICY'] must be a MovePolicy subclass",
                id="stapel_tasks.E004",
            )
        ]
    return []


@checks.register(checks.Tags.compatibility)
def check_board_presets(app_configs, **kwargs):
    from .conf import tasks_settings

    presets = tasks_settings.BOARD_PRESETS
    if not isinstance(presets, dict):
        return [
            checks.Error(
                "STAPEL_TASKS['BOARD_PRESETS'] must be a dict of "
                "{key: callable|None}.",
                id="stapel_tasks.E005",
            )
        ]
    bad = [k for k, v in presets.items() if v is not None and not callable(v)]
    if bad:
        return [
            checks.Error(
                f"STAPEL_TASKS['BOARD_PRESETS'] values must be callable or None; "
                f"offending keys: {bad}",
                id="stapel_tasks.E006",
            )
        ]
    return []
