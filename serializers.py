"""Serializers for the stapel-tasks API (dataclass-DTO backed).

Every view exposes request/response serializer seams (SerializerSeamMixin);
these are the defaults.
"""
from stapel_core.django.api.serializers import StapelDataclassSerializer

from .dto import (
    ArchivedResponse,
    BoardCardsResponse,
    BoardCreateRequest,
    BoardResponse,
    BoardUpdateRequest,
    ChecklistItemCreateRequest,
    ChecklistItemResponse,
    ChecklistItemStateRequest,
    ColumnCreateRequest,
    BoardVocabularyResponse,
    ColumnReorderRequest,
    ColumnResponse,
    CommentCreateRequest,
    CommentResponse,
    MoveResponse,
    TaskAssignRequest,
    TaskCreateRequest,
    TaskMoveRequest,
    TaskPageResponse,
    TaskResponse,
    TaskUpdateRequest,
)


class ColumnResponseSerializer(StapelDataclassSerializer):
    class Meta:
        dataclass = ColumnResponse


class ChecklistItemResponseSerializer(StapelDataclassSerializer):
    class Meta:
        dataclass = ChecklistItemResponse


class CommentResponseSerializer(StapelDataclassSerializer):
    class Meta:
        dataclass = CommentResponse


class TaskResponseSerializer(StapelDataclassSerializer):
    class Meta:
        dataclass = TaskResponse


class BoardResponseSerializer(StapelDataclassSerializer):
    class Meta:
        dataclass = BoardResponse


class ArchivedResponseSerializer(StapelDataclassSerializer):
    class Meta:
        dataclass = ArchivedResponse


class TaskPageResponseSerializer(StapelDataclassSerializer):
    class Meta:
        dataclass = TaskPageResponse


class BoardCardsResponseSerializer(StapelDataclassSerializer):
    class Meta:
        dataclass = BoardCardsResponse


class BoardVocabularyResponseSerializer(StapelDataclassSerializer):
    class Meta:
        dataclass = BoardVocabularyResponse


class MoveResponseSerializer(StapelDataclassSerializer):
    class Meta:
        dataclass = MoveResponse


class BoardCreateRequestSerializer(StapelDataclassSerializer):
    class Meta:
        dataclass = BoardCreateRequest


class BoardUpdateRequestSerializer(StapelDataclassSerializer):
    class Meta:
        dataclass = BoardUpdateRequest


class ColumnCreateRequestSerializer(StapelDataclassSerializer):
    class Meta:
        dataclass = ColumnCreateRequest


class ColumnReorderRequestSerializer(StapelDataclassSerializer):
    class Meta:
        dataclass = ColumnReorderRequest


class TaskCreateRequestSerializer(StapelDataclassSerializer):
    class Meta:
        dataclass = TaskCreateRequest


class TaskUpdateRequestSerializer(StapelDataclassSerializer):
    class Meta:
        dataclass = TaskUpdateRequest


class TaskMoveRequestSerializer(StapelDataclassSerializer):
    class Meta:
        dataclass = TaskMoveRequest


class TaskAssignRequestSerializer(StapelDataclassSerializer):
    class Meta:
        dataclass = TaskAssignRequest


class CommentCreateRequestSerializer(StapelDataclassSerializer):
    class Meta:
        dataclass = CommentCreateRequest


class ChecklistItemCreateRequestSerializer(StapelDataclassSerializer):
    class Meta:
        dataclass = ChecklistItemCreateRequest


class ChecklistItemStateRequestSerializer(StapelDataclassSerializer):
    class Meta:
        dataclass = ChecklistItemStateRequest
