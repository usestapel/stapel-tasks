from django.apps import AppConfig


class TasksConfig(AppConfig):
    # Canonical Django label for the generic task domain. stapel-core's
    # background-task persistence app (``stapel_core.django.taskstore``)
    # historically claimed the label ``stapel_tasks`` too — the two are
    # unrelated ("comm Task" = async background function vs. this user-facing
    # task/kanban domain). Core renames its taskstore label to
    # ``stapel_taskstore`` so this module can own ``stapel_tasks`` (see
    # MODULE.md §"stapel-core requirement").
    name = "stapel_tasks"
    label = "stapel_tasks"
    verbose_name = "Tasks and kanban boards"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        # Import-time side effects: comm functions/actions, system checks,
        # error-key registration, and the built-in board presets. Each lives
        # in its own module.
        from . import actions  # noqa: F401
        from . import checks  # noqa: F401
        from . import errors  # noqa: F401
        from . import functions  # noqa: F401
        from . import presets  # noqa: F401

        # GDPR: register the per-app data handler (monolith in-process mode).
        from stapel_core.gdpr import gdpr_registry

        from .gdpr import TasksGDPRProvider

        if not any(p.section == "tasks" for p in gdpr_registry.providers):
            gdpr_registry.register(TasksGDPRProvider())
