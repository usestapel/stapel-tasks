"""i18n error keys of stapel-tasks.

Only ``error.<status>.<slug>`` keys leave this package — human-readable
strings are translations, never literals in responses.
"""
from stapel_core.django.api.errors import register_service_errors

ERR_400_INVALID_FEATURES = "error.400.tasks_invalid_features"
ERR_400_INVALID_FEATURE_DEFS = "error.400.tasks_invalid_feature_defs"
ERR_400_UNKNOWN_PRESET = "error.400.tasks_unknown_preset"
ERR_400_INVALID_MOVE = "error.400.tasks_invalid_move"
ERR_400_INVALID_COLUMN = "error.400.tasks_invalid_column"
ERR_400_INVALID_CHECKLIST_STATE = "error.400.tasks_invalid_checklist_state"
ERR_403_FORBIDDEN = "error.403.tasks_forbidden"
ERR_404_BOARD_NOT_FOUND = "error.404.tasks_board_not_found"
ERR_404_COLUMN_NOT_FOUND = "error.404.tasks_column_not_found"
ERR_404_TASK_NOT_FOUND = "error.404.tasks_task_not_found"
ERR_404_COMMENT_NOT_FOUND = "error.404.tasks_comment_not_found"
ERR_404_CHECKLIST_ITEM_NOT_FOUND = "error.404.tasks_checklist_item_not_found"
ERR_409_TRANSITION_NOT_ALLOWED = "error.409.tasks_transition_not_allowed"

STAPEL_TASKS_ERRORS = {
    ERR_400_INVALID_FEATURES: "Invalid custom-field values for this board",
    ERR_400_INVALID_FEATURE_DEFS: "Invalid custom-field schema",
    ERR_400_UNKNOWN_PRESET: "Unknown board preset",
    ERR_400_INVALID_MOVE: "Invalid move: unknown target column or position",
    ERR_400_INVALID_COLUMN: "Invalid column",
    ERR_400_INVALID_CHECKLIST_STATE: "Checklist state must be one of: pending, done, failed",
    ERR_403_FORBIDDEN: "You do not have permission to perform this action",
    ERR_404_BOARD_NOT_FOUND: "Board not found",
    ERR_404_COLUMN_NOT_FOUND: "Column not found",
    ERR_404_TASK_NOT_FOUND: "Task not found",
    ERR_404_COMMENT_NOT_FOUND: "Comment not found",
    ERR_404_CHECKLIST_ITEM_NOT_FOUND: "Checklist item not found",
    ERR_409_TRANSITION_NOT_ALLOWED: "This move is not allowed by the board workflow",
}

register_service_errors(STAPEL_TASKS_ERRORS)

__all__ = [
    "STAPEL_TASKS_ERRORS",
    "ERR_400_INVALID_FEATURES",
    "ERR_400_INVALID_FEATURE_DEFS",
    "ERR_400_UNKNOWN_PRESET",
    "ERR_400_INVALID_MOVE",
    "ERR_400_INVALID_COLUMN",
    "ERR_400_INVALID_CHECKLIST_STATE",
    "ERR_403_FORBIDDEN",
    "ERR_404_BOARD_NOT_FOUND",
    "ERR_404_COLUMN_NOT_FOUND",
    "ERR_404_TASK_NOT_FOUND",
    "ERR_404_COMMENT_NOT_FOUND",
    "ERR_404_CHECKLIST_ITEM_NOT_FOUND",
    "ERR_409_TRANSITION_NOT_ALLOWED",
]
