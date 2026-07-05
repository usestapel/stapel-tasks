"""comm surface — Function calls + emit schema validation (VALIDATE_SCHEMAS on)."""
import pytest
from stapel_core.comm import call

from stapel_tasks import services


@pytest.fixture
def board(db):
    return services.create_board(name="B", preset="simple")


@pytest.mark.django_db
class TestFunctions:
    def test_create_get_roundtrip(self, board):
        res = call("tasks.create", {"board_id": str(board.id), "title": "Hi"})
        task_id = res["task_id"]
        got = call("tasks.get", {"task_id": task_id})
        assert got["task"]["title"] == "Hi"
        assert got["task"]["column"] == "todo"

    def test_get_missing_returns_null(self, board):
        import uuid

        got = call("tasks.get", {"task_id": str(uuid.uuid4())})
        assert got["task"] is None

    def test_list_board_groups_by_column(self, board):
        call("tasks.create", {"board_id": str(board.id), "title": "a"})
        call("tasks.create", {"board_id": str(board.id), "title": "b", "column": "done"})
        res = call("tasks.list_board", {"board_id": str(board.id)})
        assert [c["key"] for c in res["columns"]] == ["todo", "in_progress", "done"]
        assert len(res["cards"]["todo"]) == 1
        assert len(res["cards"]["done"]) == 1

    def test_move_result(self, board):
        res = call("tasks.create", {"board_id": str(board.id), "title": "a"})
        out = call(
            "tasks.move", {"task_id": res["task_id"], "to_column": "in_progress"}
        )
        assert out["result"] == "applied"
        assert out["reason_key"] is None

    def test_move_denied_by_transitions(self, db):
        b = services.create_board(
            name="Strict",
            preset="simple",
            settings={"transitions": {"todo": ["in_progress"]}},
        )
        res = call("tasks.create", {"board_id": str(b.id), "title": "a"})
        out = call("tasks.move", {"task_id": res["task_id"], "to_column": "done"})
        assert out["result"] == "denied"
        assert out["reason_key"] is not None

    def test_comment_function(self, board):
        res = call("tasks.create", {"board_id": str(board.id), "title": "a"})
        out = call("tasks.comment", {"task_id": res["task_id"], "body": "yo"})
        assert out["comment_id"]

    def test_bad_payload_rejected_by_schema(self, board):
        with pytest.raises(Exception):
            call("tasks.create", {"board_id": str(board.id)})  # title missing


@pytest.mark.django_db
class TestEmitSchemas:
    def test_all_emits_pass_schema(self, board, captured_events):
        # If any payload drifted from schemas/emits/, emit() would raise.
        task = services.create_task(board=board, title="t")
        done = board.columns.get(key="done")
        services.move_task(task, to_column=done)
        services.update_task(task, title="t2")
        item = services.add_checklist_item(task, text="s")
        services.set_checklist_item_state(item, "done")
        services.add_comment(task, body="c")
        services.archive_task(task)
        kinds = {e.event_type for e in captured_events}
        assert {
            "task.created",
            "task.moved",
            "task.completed",
            "task.updated",
            "task.checklist_item_changed",
            "task.comment_added",
            "task.archived",
        } <= kinds
