"""REST API — boards/columns/tasks/move/assign/comments/checklist."""
import pytest
from django.urls import reverse

from stapel_tasks import services


@pytest.fixture
def board(db):
    return services.create_board(name="Team", preset="simple")


@pytest.mark.django_db
class TestBoardApi:
    def test_create_board(self, auth_client):
        resp = auth_client.post(
            reverse("tasks-boards"), {"name": "New", "preset": "simple"}, format="json"
        )
        assert resp.status_code == 201
        assert [c["key"] for c in resp.data["columns"]] == ["todo", "in_progress", "done"]

    def test_unknown_preset_400(self, auth_client):
        resp = auth_client.post(
            reverse("tasks-boards"), {"name": "X", "preset": "nope"}, format="json"
        )
        assert resp.status_code == 400

    def test_list_boards(self, auth_client, board):
        resp = auth_client.get(reverse("tasks-boards"))
        assert resp.status_code == 200
        assert any(b["id"] == str(board.id) for b in resp.data)

    def test_get_board(self, auth_client, board):
        resp = auth_client.get(
            reverse("tasks-board-detail", args=[board.id])
        )
        assert resp.status_code == 200
        assert resp.data["name"] == "Team"

    def test_archive_board(self, auth_client, board):
        resp = auth_client.delete(reverse("tasks-board-detail", args=[board.id]))
        assert resp.status_code == 200
        board.refresh_from_db()
        assert board.is_archived

    def test_requires_auth(self, api_client, board):
        resp = api_client.get(reverse("tasks-boards"))
        assert resp.status_code in (401, 403)


@pytest.mark.django_db
class TestColumnApi:
    def test_add_and_reorder_columns(self, auth_client, board):
        resp = auth_client.post(
            reverse("tasks-columns", args=[board.id]),
            {"key": "review", "name": "Review", "category": "review"},
            format="json",
        )
        assert resp.status_code == 201
        resp = auth_client.post(
            reverse("tasks-columns-reorder", args=[board.id]),
            {"keys": ["done", "todo", "in_progress", "review"]},
            format="json",
        )
        assert resp.status_code == 200
        assert [c["key"] for c in resp.data][0] == "done"


@pytest.mark.django_db
class TestTaskApi:
    def test_create_and_get_task(self, auth_client, board):
        resp = auth_client.post(
            reverse("tasks-tasks", args=[board.id]),
            {"title": "Card", "description": "d"},
            format="json",
        )
        assert resp.status_code == 201
        task_id = resp.data["id"]
        assert resp.data["creator_id"] is not None
        resp = auth_client.get(reverse("tasks-task-detail", args=[task_id]))
        assert resp.status_code == 200
        assert resp.data["title"] == "Card"

    def test_list_tasks_paginated(self, auth_client, board):
        for i in range(3):
            services.create_task(board=board, title=f"t{i}")
        resp = auth_client.get(reverse("tasks-tasks", args=[board.id]))
        assert resp.status_code == 200
        assert "items" in resp.data
        assert len(resp.data["items"]) == 3

    def test_patch_task(self, auth_client, board):
        task = services.create_task(board=board, title="t")
        resp = auth_client.patch(
            reverse("tasks-task-detail", args=[task.id]),
            {"title": "renamed", "priority": 5},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["title"] == "renamed"
        assert resp.data["priority"] == 5

    def test_move_applied(self, auth_client, board):
        task = services.create_task(board=board, title="t")
        resp = auth_client.post(
            reverse("tasks-task-move", args=[task.id]),
            {"to_column": "in_progress"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["result"] == "applied"

    def test_move_unknown_column_404(self, auth_client, board):
        task = services.create_task(board=board, title="t")
        resp = auth_client.post(
            reverse("tasks-task-move", args=[task.id]),
            {"to_column": "ghost"},
            format="json",
        )
        assert resp.status_code == 404

    def test_move_denied_409(self, auth_client, db):
        b = services.create_board(
            name="S", preset="simple", settings={"transitions": {"todo": ["in_progress"]}}
        )
        task = services.create_task(board=b, title="t")
        resp = auth_client.post(
            reverse("tasks-task-move", args=[task.id]),
            {"to_column": "done"},
            format="json",
        )
        assert resp.status_code == 409
        assert resp.data["result"] == "denied"

    def test_assign(self, auth_client, board, other_user):
        task = services.create_task(board=board, title="t")
        resp = auth_client.post(
            reverse("tasks-task-assign", args=[task.id]),
            {"assignee_ids": [str(other_user.id)]},
            format="json",
        )
        assert resp.status_code == 200
        assert str(other_user.id) in resp.data["assignee_ids"]

    def test_archive_task(self, auth_client, board):
        task = services.create_task(board=board, title="t")
        resp = auth_client.delete(reverse("tasks-task-detail", args=[task.id]))
        assert resp.status_code == 200
        task.refresh_from_db()
        assert task.is_archived


@pytest.mark.django_db
class TestCommentChecklistApi:
    def test_comment_flow(self, auth_client, board):
        task = services.create_task(board=board, title="t")
        resp = auth_client.post(
            reverse("tasks-task-comments", args=[task.id]),
            {"body": "note"},
            format="json",
        )
        assert resp.status_code == 201
        resp = auth_client.get(reverse("tasks-task-comments", args=[task.id]))
        assert len(resp.data) == 1

    def test_checklist_flow(self, auth_client, board):
        task = services.create_task(board=board, title="t")
        resp = auth_client.post(
            reverse("tasks-task-checklist", args=[task.id]),
            {"text": "step", "ref": "s1"},
            format="json",
        )
        assert resp.status_code == 201
        item_id = resp.data["id"]
        resp = auth_client.post(
            reverse("tasks-checklist-item-state", args=[task.id, item_id]),
            {"state": "done"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["state"] == "done"

    def test_checklist_bad_state_400(self, auth_client, board):
        task = services.create_task(board=board, title="t")
        item = services.add_checklist_item(task, text="x")
        resp = auth_client.post(
            reverse("tasks-checklist-item-state", args=[task.id, item.id]),
            {"state": "bogus"},
            format="json",
        )
        assert resp.status_code == 400
