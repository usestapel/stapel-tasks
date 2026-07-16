"""v1 URL set for stapel-tasks (api-versioning.md §2, §6).

No global prefix here — the root ``urls.py`` mounts this module under
``api/v1/`` and the host mounts that under ``tasks/``:

    path("tasks/", include("stapel_tasks.urls"))   # -> /tasks/api/v1/...
"""
from django.urls import path

from .views import (
    BoardDetailView,
    BoardListCreateView,
    ChecklistItemStateView,
    ChecklistListCreateView,
    ColumnListCreateView,
    ColumnReorderView,
    CommentListCreateView,
    TaskAssignView,
    TaskDetailView,
    TaskListCreateView,
    TaskMoveView,
)

urlpatterns = [
    path("boards", BoardListCreateView.as_view(), name="tasks-boards"),
    path(
        "boards/<uuid:board_id>",
        BoardDetailView.as_view(),
        name="tasks-board-detail",
    ),
    path(
        "boards/<uuid:board_id>/columns",
        ColumnListCreateView.as_view(),
        name="tasks-columns",
    ),
    path(
        "boards/<uuid:board_id>/columns/reorder",
        ColumnReorderView.as_view(),
        name="tasks-columns-reorder",
    ),
    path(
        "boards/<uuid:board_id>/tasks",
        TaskListCreateView.as_view(),
        name="tasks-tasks",
    ),
    path(
        "tasks/<uuid:task_id>",
        TaskDetailView.as_view(),
        name="tasks-task-detail",
    ),
    path(
        "tasks/<uuid:task_id>/move",
        TaskMoveView.as_view(),
        name="tasks-task-move",
    ),
    path(
        "tasks/<uuid:task_id>/assign",
        TaskAssignView.as_view(),
        name="tasks-task-assign",
    ),
    path(
        "tasks/<uuid:task_id>/comments",
        CommentListCreateView.as_view(),
        name="tasks-task-comments",
    ),
    path(
        "tasks/<uuid:task_id>/checklist",
        ChecklistListCreateView.as_view(),
        name="tasks-task-checklist",
    ),
    path(
        "tasks/<uuid:task_id>/checklist/<uuid:item_id>/state",
        ChecklistItemStateView.as_view(),
        name="tasks-checklist-item-state",
    ),
]
