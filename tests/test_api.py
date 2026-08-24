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


@pytest.mark.django_db
class TestBoardVocabularyApi:
    """`GET boards/presets` — T-2/T-7: preset keys, categories and the
    priority scale were undiscoverable from the API alone."""

    def test_serves_presets_with_their_columns(self, auth_client):
        resp = auth_client.get(reverse("tasks-board-presets"))
        assert resp.status_code == 200
        by_key = {p["key"]: p for p in resp.data["presets"]}
        assert "simple" in by_key
        assert [c["key"] for c in by_key["simple"]["columns"]] == [
            "todo",
            "in_progress",
            "done",
        ]
        assert by_key["simple"]["columns"][0]["name_key"] == "tasks.column.todo"

    def test_serves_the_fixed_vocabularies(self, auth_client):
        resp = auth_client.get(reverse("tasks-board-presets"))
        assert [c["value"] for c in resp.data["categories"]] == [
            "backlog",
            "active",
            "review",
            "waiting",
            "done",
        ]
        assert [s["value"] for s in resp.data["checklist_states"]] == [
            "pending",
            "done",
            "failed",
        ]

    def test_serves_the_configured_priority_scale(self, auth_client, settings):
        settings.STAPEL_TASKS = {
            "PRIORITY_SCALE": [{"value": 7, "label_key": "custom.seven"}]
        }
        resp = auth_client.get(reverse("tasks-board-presets"))
        assert resp.data["priority_scale"] == [
            {"value": 7, "label_key": "custom.seven"}
        ]

    def test_a_host_preset_is_discoverable(self, auth_client):
        from stapel_tasks.presets import ColumnSpec, register_board_preset

        register_board_preset(
            "triage", lambda: [ColumnSpec("new", "New", "backlog")]
        )
        resp = auth_client.get(reverse("tasks-board-presets"))
        assert "triage" in {p["key"] for p in resp.data["presets"]}


@pytest.mark.django_db
class TestDuplicateColumnKey:
    """T-8: the (board, key) constraint used to surface as a 500."""

    def test_duplicate_key_is_409_not_500(self, auth_client, board):
        body = {"key": "todo", "name": "Todo again", "category": "backlog"}
        resp = auth_client.post(
            reverse("tasks-columns", args=[board.id]), body, format="json"
        )
        assert resp.status_code == 409
        assert resp.data["localizable_error"] == "error.409.tasks_column_exists"

    def test_the_board_is_unchanged_after_the_conflict(self, auth_client, board):
        auth_client.post(
            reverse("tasks-columns", args=[board.id]),
            {"key": "todo", "name": "Dup", "category": "backlog"},
            format="json",
        )
        assert board.columns.count() == 3

    def test_the_service_raises_a_domain_error(self, board):
        with pytest.raises(services.ColumnExists):
            services.add_column(board, key="todo", name="Dup", category="backlog")


@pytest.mark.django_db
class TestBoardCardsApi:
    """T-4: the board-shaped read — grouped by column, ordered by position."""

    def test_groups_by_column_key_and_keeps_every_column(self, auth_client, board):
        services.create_task(board=board, title="A")
        resp = auth_client.get(reverse("tasks-board-cards", args=[board.id]))
        assert resp.status_code == 200
        assert set(resp.data["cards"]) == {"todo", "in_progress", "done"}
        assert [c["title"] for c in resp.data["cards"]["todo"]] == ["A"]
        assert resp.data["cards"]["done"] == []
        assert [c["key"] for c in resp.data["columns"]] == [
            "todo",
            "in_progress",
            "done",
        ]

    def test_orders_by_position_not_by_creation(self, auth_client, board):
        todo = board.columns.get(key="todo")
        first = services.create_task(board=board, title="first")
        second = services.create_task(board=board, title="second")
        # Move the newest card to the head of the column: a -created_at feed
        # would answer ["second", "first"] for the wrong reason, so make the
        # position order disagree with the creation order.
        services.move_task(second, to_column=todo, index=0)
        resp = auth_client.get(reverse("tasks-board-cards", args=[board.id]))
        titles = [c["title"] for c in resp.data["cards"]["todo"]]
        assert titles == ["second", "first"]
        positions = [c["position"] for c in resp.data["cards"]["todo"]]
        assert positions == sorted(positions, key=float)
        assert first.title == "first"

    def test_archived_cards_are_out_unless_asked_for(self, auth_client, board):
        task = services.create_task(board=board, title="gone")
        services.archive_task(task)
        resp = auth_client.get(reverse("tasks-board-cards", args=[board.id]))
        assert resp.data["count"] == 0
        resp = auth_client.get(
            reverse("tasks-board-cards", args=[board.id]) + "?include_archived=true"
        )
        assert resp.data["count"] == 1

    def test_filters_narrow_the_answer(self, auth_client, board):
        services.create_task(board=board, title="A")
        services.create_task(
            board=board, title="B", column=board.columns.get(key="done")
        )
        resp = auth_client.get(
            reverse("tasks-board-cards", args=[board.id]) + "?category=done"
        )
        assert resp.data["count"] == 1
        assert [c["title"] for c in resp.data["cards"]["done"]] == ["B"]

    def test_the_cap_truncates_and_says_so(self, auth_client, board, settings):
        settings.STAPEL_TASKS = {"BOARD_CARDS_MAX": 2}
        for i in range(3):
            services.create_task(board=board, title=f"T{i}")
        resp = auth_client.get(reverse("tasks-board-cards", args=[board.id]))
        assert resp.data["truncated"] is True
        assert resp.data["count"] == 2

    def test_not_truncated_when_exactly_at_the_cap(self, auth_client, board, settings):
        settings.STAPEL_TASKS = {"BOARD_CARDS_MAX": 2}
        for i in range(2):
            services.create_task(board=board, title=f"T{i}")
        resp = auth_client.get(reverse("tasks-board-cards", args=[board.id]))
        assert resp.data["truncated"] is False
        assert resp.data["count"] == 2

    def test_unknown_board_is_404(self, auth_client):
        import uuid

        resp = auth_client.get(reverse("tasks-board-cards", args=[uuid.uuid4()]))
        assert resp.status_code == 404

    def test_requires_auth(self, api_client, board):
        resp = api_client.get(reverse("tasks-board-cards", args=[board.id]))
        assert resp.status_code in (401, 403)

    def test_matches_the_comm_functions_grouping(self, auth_client, board):
        """The HTTP read and `tasks.list_board` must not disagree — they are
        one implementation (services.board_cards) precisely so they cannot."""
        from stapel_core.comm import call

        services.create_task(board=board, title="A")
        services.create_task(board=board, title="B")
        http = auth_client.get(reverse("tasks-board-cards", args=[board.id])).data
        comm = call("tasks.list_board", {"board_id": str(board.id)})
        assert [c["key"] for c in http["columns"]] == [
            c["key"] for c in comm["columns"]
        ]
        for key in comm["cards"]:
            assert [c["title"] for c in http["cards"][key]] == [
                c["title"] for c in comm["cards"][key]
            ]
