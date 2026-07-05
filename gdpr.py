"""GDPR data handler for stapel-tasks.

This module holds user PII in three places: ``Task.creator``,
``Task.assignees`` and ``TaskComment.author``. A card, unlike a calendar
event, is *shared* work — hard-deleting the cards a user created would
destroy a whole team's board. So the policy is **anonymize, not delete**:

- authored cards and comments are kept but de-linked from the user
  (``creator``/``author`` set null, comment bodies scrubbed);
- the user is removed from every card's assignee set (their assignment is
  their PII);
- nothing another user owns is destroyed.
"""
from stapel_core.gdpr import GDPRProvider


class TasksGDPRProvider(GDPRProvider):
    section = "tasks"

    def export(self, user_id) -> dict:
        from .models import Task, TaskComment

        created = list(
            Task.objects.filter(creator_id=user_id).values(
                "id", "board_id", "title", "created_at"
            )
        )
        assigned = list(
            Task.objects.filter(assignees__pk=user_id).values("id", "board_id", "title")
        )
        comments = list(
            TaskComment.objects.filter(author_id=user_id, is_deleted=False).values(
                "id", "task_id", "body", "created_at"
            )
        )
        return {
            "created_tasks": _serialize(created),
            "assigned_tasks": _serialize(assigned),
            "comments": _serialize(comments),
        }

    def delete(self, user_id) -> None:
        # A user.deleted consumer maps to anonymize for this module (cards are
        # shared team artifacts, not solely the user's data).
        self.anonymize(user_id)

    def anonymize(self, user_id) -> None:
        from django.contrib.auth import get_user_model

        from .models import Task, TaskComment

        Task.objects.filter(creator_id=user_id).update(creator=None)
        TaskComment.objects.filter(author_id=user_id).update(author=None, body="")

        User = get_user_model()
        user = User.objects.filter(pk=user_id).first()
        if user is not None:
            for task in Task.objects.filter(assignees__pk=user_id):
                task.assignees.remove(user)


def _serialize(rows: list[dict]) -> list[dict]:
    return [
        {k: v.isoformat() if hasattr(v, "isoformat") else str(v) for k, v in row.items()}
        for row in rows
    ]
