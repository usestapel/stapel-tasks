def pytest_configure(config):
    from django.conf import settings

    if not settings.configured:
        settings.configure(
            SECRET_KEY="test-secret-key-not-for-production",
            INSTALLED_APPS=[
                "django.contrib.contenttypes",
                "django.contrib.auth",
                "django.contrib.sessions",
                "django.contrib.admin",
                "django.contrib.messages",
                "stapel_core.django.users",
                "rest_framework",
                "stapel_tasks",
            ],
            # NOTE: stapel_core.django.taskstore is deliberately NOT installed.
            # It historically claimed the Django label `stapel_tasks` (an
            # unrelated background-task persistence app); this module owns that
            # label. See MODULE.md §"stapel-core requirement".
            AUTH_USER_MODEL="users.User",
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": ":memory:",
                }
            },
            DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
            USE_TZ=True,
            ROOT_URLCONF="stapel_tasks.tests.urls",
            CACHES={
                "default": {
                    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                }
            },
            # Synchronous in-process comm with schema validation ON, so the
            # committed contracts in schemas/ are enforced by the tests.
            STAPEL_BUS_BACKEND="stapel_core.bus.backends.memory.MemoryBus",
            STAPEL_COMM={
                "OUTBOX_ENABLED": False,
                "ACTION_TRANSPORT": "inprocess",
                "VALIDATE_SCHEMAS": True,
            },
            MIGRATION_MODULES={
                "users": None,
                "stapel_tasks": None,
            },
        )
        import django

        django.setup()

        from stapel_core.comm.schemas import autoload_schemas

        autoload_schemas()


import pytest  # noqa: E402


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def user(db):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create_user(
        username="alice", email="alice@example.com", password="x"
    )


@pytest.fixture
def other_user(db):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create_user(
        username="bob", email="bob@example.com", password="x"
    )


@pytest.fixture
def auth_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture(autouse=True)
def _reset_board_presets():
    """Keep the board preset registry clean between tests."""
    from stapel_tasks.presets import reset_presets

    reset_presets()
    yield
    reset_presets()


@pytest.fixture
def captured_events():
    """Subscribe to task emits (in-process) and collect Event envelopes.
    Delivery is synchronous with OUTBOX disabled, so the list is populated by
    the time emit() returns."""
    from stapel_core.comm import action_registry, subscribe_action

    collected = []

    def _handler(event):
        collected.append(event)

    names = [
        "task.created",
        "task.updated",
        "task.moved",
        "task.assigned",
        "task.completed",
        "task.comment_added",
        "task.checklist_item_changed",
        "task.archived",
    ]
    for name in names:
        subscribe_action(name, _handler)
    try:
        yield collected
    finally:
        for name in names:
            handlers = action_registry._subscribers.get(name, [])
            if _handler in handlers:
                handlers.remove(_handler)
