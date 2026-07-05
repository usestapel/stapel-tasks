"""URL patterns — no global prefix here, the host project mounts them:

    path("tasks/", include("stapel_tasks.urls"))
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
    path("api/boards", BoardListCreateView.as_view(), name="tasks-boards"),
    path(
        "api/boards/<uuid:board_id>",
        BoardDetailView.as_view(),
        name="tasks-board-detail",
    ),
    path(
        "api/boards/<uuid:board_id>/columns",
        ColumnListCreateView.as_view(),
        name="tasks-columns",
    ),
    path(
        "api/boards/<uuid:board_id>/columns/reorder",
        ColumnReorderView.as_view(),
        name="tasks-columns-reorder",
    ),
    path(
        "api/boards/<uuid:board_id>/tasks",
        TaskListCreateView.as_view(),
        name="tasks-tasks",
    ),
    path(
        "api/tasks/<uuid:task_id>",
        TaskDetailView.as_view(),
        name="tasks-task-detail",
    ),
    path(
        "api/tasks/<uuid:task_id>/move",
        TaskMoveView.as_view(),
        name="tasks-task-move",
    ),
    path(
        "api/tasks/<uuid:task_id>/assign",
        TaskAssignView.as_view(),
        name="tasks-task-assign",
    ),
    path(
        "api/tasks/<uuid:task_id>/comments",
        CommentListCreateView.as_view(),
        name="tasks-task-comments",
    ),
    path(
        "api/tasks/<uuid:task_id>/checklist",
        ChecklistListCreateView.as_view(),
        name="tasks-task-checklist",
    ),
    path(
        "api/tasks/<uuid:task_id>/checklist/<uuid:item_id>/state",
        ChecklistItemStateView.as_view(),
        name="tasks-checklist-item-state",
    ),
]
