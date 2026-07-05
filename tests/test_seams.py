"""Extension-point tests: scope/permission seam, MOVE_POLICY seam, board
preset registry merge."""
import pytest

from stapel_tasks import services
from stapel_tasks.models import ColumnCategory


# ── Scope / permission seam ─────────────────────────────────────────────


class DenyWritesProvider:
    """A provider that permits reads but denies writes/admin — proves the
    permission seam is honoured by the views without forking them."""

    def resolve(self, request):
        return None

    def filter(self, queryset, request):
        return queryset

    def can(self, request, action, board=None):
        from stapel_tasks.scope import READ

        return action == READ


@pytest.mark.django_db
class TestScopeSeam:
    def test_permission_seam_blocks_create(self, auth_client, settings):
        from django.urls import reverse

        settings.STAPEL_TASKS = {
            "SCOPE_PROVIDER": "stapel_tasks.tests.test_seams.DenyWritesProvider"
        }
        resp = auth_client.post(
            reverse("tasks-boards"), {"name": "X", "preset": "simple"}, format="json"
        )
        assert resp.status_code == 403


# ── MOVE_POLICY seam ────────────────────────────────────────────────────


class DeferAllPolicy:
    """A policy that defers every move (the managed-card path)."""

    def check(self, *, task, from_column, to_column, actor):
        from stapel_tasks.policy import MoveDecision

        return MoveDecision.defer()


@pytest.mark.django_db
class TestMovePolicySeam:
    def test_defer_leaves_card_untouched(self, db, settings):
        settings.STAPEL_TASKS = {
            "MOVE_POLICY": "stapel_tasks.tests.test_seams.DeferAllPolicy"
        }
        board = services.create_board(name="B", preset="simple")
        task = services.create_task(board=board, title="t")
        done = board.columns.get(key="done")
        decision = services.move_task(task, to_column=done)
        assert decision.is_deferred
        task.refresh_from_db()
        assert task.column.key == "todo"  # not applied

    def test_defer_api_returns_202(self, auth_client, settings):
        from django.urls import reverse

        settings.STAPEL_TASKS = {
            "MOVE_POLICY": "stapel_tasks.tests.test_seams.DeferAllPolicy"
        }
        board = services.create_board(name="B", preset="simple")
        task = services.create_task(board=board, title="t")
        resp = auth_client.post(
            reverse("tasks-task-move", args=[task.id]),
            {"to_column": "done"},
            format="json",
        )
        assert resp.status_code == 202
        assert resp.data["result"] == "deferred"


# ── Board preset registry ───────────────────────────────────────────────


class TestPresetRegistry:
    def test_register_merges_over_builtins(self):
        from stapel_tasks.presets import (
            ColumnSpec,
            get_board_presets,
            register_board_preset,
        )

        def _kanban():
            return [ColumnSpec("k", "K", ColumnCategory.ACTIVE)]

        register_board_preset("kanban", _kanban)
        presets = get_board_presets()
        assert "simple" in presets  # built-in preserved
        assert "kanban" in presets

    def test_none_removes_builtin(self, settings):
        from stapel_tasks.presets import get_board_presets

        settings.STAPEL_TASKS = {"BOARD_PRESETS": {"simple": None}}
        assert "simple" not in get_board_presets()
