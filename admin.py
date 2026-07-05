"""Admin registrations for stapel-tasks (observability; kept minimal)."""
from django.contrib import admin

from .models import Board, ChecklistItem, Column, Task, TaskComment


class ColumnInline(admin.TabularInline):
    model = Column
    extra = 0
    fields = ("key", "name", "category", "order", "wip_limit")


@admin.register(Board)
class BoardAdmin(admin.ModelAdmin):
    list_display = ("name", "workspace_id", "is_archived", "created_at")
    list_filter = ("is_archived",)
    search_fields = ("name", "slug")
    inlines = [ColumnInline]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "board",
        "column",
        "origin_type",
        "is_archived",
        "created_at",
    )
    list_filter = ("origin_type", "is_archived")
    search_fields = ("title", "origin_ref")
    raw_id_fields = ("board", "column", "creator", "parent")


@admin.register(ChecklistItem)
class ChecklistItemAdmin(admin.ModelAdmin):
    list_display = ("text", "task", "state", "order")
    list_filter = ("state",)


@admin.register(TaskComment)
class TaskCommentAdmin(admin.ModelAdmin):
    list_display = ("task", "author", "is_deleted", "created_at")
    list_filter = ("is_deleted",)
