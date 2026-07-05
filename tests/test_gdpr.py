"""GDPR: user.deleted anonymizes authored cards/comments and drops
assignments (cards are shared artifacts — anonymize, not delete)."""
import pytest
from stapel_core.comm import emit

from stapel_tasks import services
from stapel_tasks.gdpr import TasksGDPRProvider
from stapel_tasks.models import Task, TaskComment


@pytest.mark.django_db
class TestGDPR:
    def test_export_shape(self, user):
        board = services.create_board(name="B", preset="simple")
        task = services.create_task(board=board, title="t", creator=user)
        services.set_assignees(task, [user.id])
        services.add_comment(task, body="hi", author=user)
        data = TasksGDPRProvider().export(user.id)
        assert data["created_tasks"] and data["assigned_tasks"] and data["comments"]

    def test_anonymize_keeps_cards(self, user):
        board = services.create_board(name="B", preset="simple")
        task = services.create_task(board=board, title="keep me", creator=user)
        services.set_assignees(task, [user.id])
        services.add_comment(task, body="secret", author=user)

        TasksGDPRProvider().anonymize(user.id)

        task.refresh_from_db()
        assert task.creator_id is None  # de-linked, not deleted
        assert Task.objects.filter(id=task.id).exists()
        assert task.assignees.count() == 0
        comment = TaskComment.objects.get(task=task)
        assert comment.author_id is None
        assert comment.body == ""

    def test_user_deleted_consumer(self, user, db):
        from django.db import transaction

        board = services.create_board(name="B", preset="simple")
        task = services.create_task(board=board, title="t", creator=user)
        with transaction.atomic():
            emit("user.deleted", {"user_id": str(user.id)})
        task.refresh_from_db()
        assert task.creator_id is None
