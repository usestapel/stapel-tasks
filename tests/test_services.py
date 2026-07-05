"""Domain services: boards, cards, moves, positioning, assignees, checklist."""
import pytest

from stapel_tasks import services
from stapel_tasks.models import ColumnCategory, Task


@pytest.fixture
def board(db):
    return services.create_board(name="Team", preset="simple")


@pytest.mark.django_db
class TestBoards:
    def test_preset_creates_columns(self, board):
        keys = list(board.columns.order_by("order").values_list("key", flat=True))
        assert keys == ["todo", "in_progress", "done"]
        assert board.columns.get(key="done").category == ColumnCategory.DONE

    def test_unknown_preset_raises(self, db):
        with pytest.raises(KeyError):
            services.create_board(name="X", preset="nope")

    def test_explicit_columns(self, db):
        from stapel_tasks.presets import ColumnSpec

        b = services.create_board(
            name="Custom",
            columns=[
                ColumnSpec("a", "A", ColumnCategory.BACKLOG),
                ColumnSpec("b", "B", ColumnCategory.DONE),
            ],
        )
        assert b.columns.count() == 2


@pytest.mark.django_db
class TestCards:
    def test_create_emits_created(self, board, captured_events):
        task = services.create_task(board=board, title="Do it")
        assert task.column.key == "todo"
        created = [e for e in captured_events if e.event_type == "task.created"]
        assert len(created) == 1
        assert created[0].payload["title"] == "Do it"
        assert created[0].payload["category"] == ColumnCategory.BACKLOG

    def test_create_in_done_column_completes(self, board, captured_events):
        done = board.columns.get(key="done")
        task = services.create_task(board=board, title="Already done", column=done)
        assert task.completed_at is not None
        assert any(e.event_type == "task.completed" for e in captured_events)

    def test_update_emits_changed_fields(self, board, captured_events):
        task = services.create_task(board=board, title="t")
        services.update_task(task, title="new", description="d")
        updated = [e for e in captured_events if e.event_type == "task.updated"]
        assert updated
        assert set(updated[-1].payload["changed_fields"]) == {"title", "description"}

    def test_update_noop_no_event(self, board, captured_events):
        task = services.create_task(board=board, title="t")
        captured_events.clear()
        services.update_task(task, title="t")  # unchanged
        assert not [e for e in captured_events if e.event_type == "task.updated"]


@pytest.mark.django_db
class TestMove:
    def test_move_emits_moved_and_completed(self, board, captured_events):
        task = services.create_task(board=board, title="t")
        done = board.columns.get(key="done")
        decision = services.move_task(task, to_column=done)
        assert decision.is_allowed
        task.refresh_from_db()
        assert task.column_id == done.id
        assert task.completed_at is not None
        assert any(e.event_type == "task.moved" for e in captured_events)
        assert any(e.event_type == "task.completed" for e in captured_events)

    def test_move_out_of_done_clears_completed(self, board):
        done = board.columns.get(key="done")
        todo = board.columns.get(key="todo")
        task = services.create_task(board=board, title="t", column=done)
        assert task.completed_at is not None
        services.move_task(task, to_column=todo)
        task.refresh_from_db()
        assert task.completed_at is None

    def test_transitions_whitelist_denies(self, db, captured_events):
        b = services.create_board(
            name="Strict",
            preset="simple",
            settings={"transitions": {"todo": ["in_progress"]}},
        )
        task = services.create_task(board=b, title="t")  # in todo
        done = b.columns.get(key="done")
        decision = services.move_task(task, to_column=done)
        assert decision.is_denied
        task.refresh_from_db()
        assert task.column.key == "todo"  # unchanged

    def test_move_ordering_by_index(self, board):
        col = board.columns.get(key="todo")
        services.create_task(board=board, title="a")
        services.create_task(board=board, title="b")
        c = services.create_task(board=board, title="c")
        # move c to the front of the same column
        services.move_task(c, to_column=col, index=0)
        order = list(
            Task.objects.filter(column=col)
            .order_by("position", "created_at", "id")
            .values_list("title", flat=True)
        )
        assert order == ["c", "a", "b"]


@pytest.mark.django_db
class TestAssignees:
    def test_set_assignees_emits(self, board, user, other_user, captured_events):
        task = services.create_task(board=board, title="t")
        services.set_assignees(task, [user.id, other_user.id])
        assigned = [e for e in captured_events if e.event_type == "task.assigned"]
        assert len(assigned) == 2
        assert all(e.payload["op"] == "assigned" for e in assigned)
        captured_events.clear()
        services.set_assignees(task, [user.id])  # drop other_user
        assigned = [e for e in captured_events if e.event_type == "task.assigned"]
        assert len(assigned) == 1
        assert assigned[0].payload["op"] == "unassigned"


@pytest.mark.django_db
class TestChecklistAndComments:
    def test_checklist_state_emits(self, board, captured_events):
        task = services.create_task(board=board, title="t")
        item = services.add_checklist_item(task, text="step", ref="s1")
        services.set_checklist_item_state(item, "failed")
        ev = [e for e in captured_events if e.event_type == "task.checklist_item_changed"]
        assert ev and ev[-1].payload["state"] == "failed"
        assert ev[-1].payload["ref"] == "s1"

    def test_comment_emits(self, board, user, captured_events):
        task = services.create_task(board=board, title="t")
        services.add_comment(task, body="hello", author=user)
        assert any(e.event_type == "task.comment_added" for e in captured_events)


@pytest.mark.django_db
class TestArchiveAndOrigin:
    def test_archive_emits(self, board, captured_events):
        task = services.create_task(board=board, title="t")
        services.archive_task(task)
        assert any(e.event_type == "task.archived" for e in captured_events)
        task.refresh_from_db()
        assert task.is_archived

    def test_upsert_by_origin_idempotent(self, board):
        t1, created1 = services.upsert_task_by_origin(
            board=board, origin_type="studio", origin_ref="spec-1", title="First"
        )
        assert created1
        t2, created2 = services.upsert_task_by_origin(
            board=board, origin_type="studio", origin_ref="spec-1", title="Updated"
        )
        assert not created2
        assert t1.id == t2.id
        t2.refresh_from_db()
        assert t2.title == "Updated"
