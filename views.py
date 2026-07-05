"""DRF views for stapel-tasks.

Thin views over :mod:`services`. Scope resolution/filtering and permission
checks go through the ``SCOPE_PROVIDER`` seam; moves go through
``MOVE_POLICY`` (inside :func:`services.move_task`). Every mutation the views
trigger emits its event via the outbox (in the service layer).
"""
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.views import APIView
from stapel_core.django.api.errors import StapelErrorResponse, StapelResponse
from stapel_core.django.api.pagination import CreatedAtAnchorPagination

from . import services
from .dto import (
    BoardResponse,
    ChecklistItemResponse,
    ColumnResponse,
    CommentResponse,
    MoveResponse,
    TaskResponse,
)
from .errors import (
    ERR_400_INVALID_CHECKLIST_STATE,
    ERR_400_INVALID_COLUMN,
    ERR_400_INVALID_FEATURE_DEFS,
    ERR_400_INVALID_FEATURES,
    ERR_400_UNKNOWN_PRESET,
    ERR_403_FORBIDDEN,
    ERR_404_BOARD_NOT_FOUND,
    ERR_404_CHECKLIST_ITEM_NOT_FOUND,
    ERR_404_COLUMN_NOT_FOUND,
    ERR_404_TASK_NOT_FOUND,
)
from .features import FeatureValidationError
from .models import Board, ChecklistItem, Column, Task
from .policy import ALLOW, DEFER, DENY
from .scope import ADMIN, READ, WRITE, get_scope_provider
from .serializers import (
    BoardCreateRequestSerializer,
    BoardResponseSerializer,
    BoardUpdateRequestSerializer,
    ChecklistItemCreateRequestSerializer,
    ChecklistItemResponseSerializer,
    ChecklistItemStateRequestSerializer,
    ColumnCreateRequestSerializer,
    ColumnReorderRequestSerializer,
    ColumnResponseSerializer,
    CommentCreateRequestSerializer,
    CommentResponseSerializer,
    MoveResponseSerializer,
    TaskAssignRequestSerializer,
    TaskCreateRequestSerializer,
    TaskMoveRequestSerializer,
    TaskResponseSerializer,
    TaskUpdateRequestSerializer,
)


class SerializerSeamMixin:
    """Overridable serializer seam for every stapel-tasks APIView.

    Host projects can swap the request/response serializer of any view by
    subclassing and setting ``request_serializer_class`` /
    ``response_serializer_class`` (or overriding the getters).
    """

    request_serializer_class = None
    response_serializer_class = None

    def get_request_serializer_class(self):
        return self.request_serializer_class

    def get_response_serializer_class(self):
        return self.response_serializer_class


# ── Mappers ──────────────────────────────────────────────────────────────


def column_to_dto(column: Column) -> ColumnResponse:
    return ColumnResponse(
        id=str(column.id),
        board_id=str(column.board_id),
        key=column.key,
        name=column.name,
        name_key=column.name_key,
        order=column.order,
        category=column.category,
        wip_limit=column.wip_limit,
    )


def checklist_to_dto(item: ChecklistItem) -> ChecklistItemResponse:
    return ChecklistItemResponse(
        id=str(item.id),
        text=item.text,
        state=item.state,
        order=item.order,
        ref=item.ref,
    )


def comment_to_dto(comment) -> CommentResponse:
    return CommentResponse(
        id=str(comment.id),
        task_id=str(comment.task_id),
        author_id=str(comment.author_id) if comment.author_id else None,
        body=comment.body,
        created_at=comment.created_at,
    )


def task_to_dto(task: Task) -> TaskResponse:
    return TaskResponse(
        id=str(task.id),
        board_id=str(task.board_id),
        column=task.column.key,
        category=task.column.category,
        position=str(task.position),
        title=task.title,
        description=task.description,
        creator_id=str(task.creator_id) if task.creator_id else None,
        assignee_ids=[str(u) for u in task.assignees.values_list("pk", flat=True)],
        priority=task.priority,
        due_at=task.due_at,
        parent_id=str(task.parent_id) if task.parent_id else None,
        blocked_by_ids=[str(t) for t in task.blocked_by.values_list("pk", flat=True)],
        features=task.features or {},
        origin_type=task.origin_type,
        origin_ref=task.origin_ref or None,
        origin_meta=task.origin_meta or {},
        completed_at=task.completed_at,
        is_archived=task.is_archived,
        checklist=[checklist_to_dto(i) for i in task.checklist_items.all()],
        created_at=task.created_at,
    )


def board_to_dto(board: Board) -> BoardResponse:
    return BoardResponse(
        id=str(board.id),
        workspace_id=str(board.workspace_id) if board.workspace_id else None,
        name=board.name,
        slug=board.slug,
        feature_defs=board.feature_defs or [],
        settings=board.settings or {},
        columns=[column_to_dto(c) for c in board.columns.all()],
        is_archived=board.is_archived,
        created_at=board.created_at,
    )


# ── Access helpers ───────────────────────────────────────────────────────


def _forbidden(request, action, board=None):
    """Return a 403 error response if the scope provider denies ``action``,
    else None."""
    if not get_scope_provider().can(request, action, board):
        return StapelErrorResponse(403, ERR_403_FORBIDDEN)
    return None


def _get_board(request, board_id):
    qs = get_scope_provider().filter(Board.objects.all(), request)
    return qs.prefetch_related("columns").filter(id=board_id).first()


def _get_task(request, task_id):
    qs = get_scope_provider().filter(
        Task.objects.select_related("board", "column"), request
    )
    return (
        qs.prefetch_related("assignees", "blocked_by", "checklist_items")
        .filter(id=task_id)
        .first()
    )


class TaskPagination(CreatedAtAnchorPagination):
    page_size = 100
    max_page_size = 500


# ── Board views ──────────────────────────────────────────────────────────


@extend_schema(tags=["Tasks"])
class BoardListCreateView(SerializerSeamMixin, APIView):
    """List boards in scope, or create one from a preset."""

    permission_classes = [permissions.IsAuthenticated]
    request_serializer_class = BoardCreateRequestSerializer
    response_serializer_class = BoardResponseSerializer

    def get(self, request):
        if (resp := _forbidden(request, READ)) is not None:
            return resp
        qs = get_scope_provider().filter(
            Board.objects.filter(is_archived=False), request
        ).prefetch_related("columns")
        response_cls = self.get_response_serializer_class()
        return StapelResponse(
            response_cls([board_to_dto(b) for b in qs], many=True)
        )

    def post(self, request):
        if (resp := _forbidden(request, ADMIN)) is not None:
            return resp
        ser = self.get_request_serializer_class()(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        columns = None
        if data.columns:
            columns = _column_specs(data.columns)
            if columns is None:
                return StapelErrorResponse(400, ERR_400_INVALID_COLUMN)
        workspace_id = get_scope_provider().resolve(request)
        try:
            board = services.create_board(
                name=data.name,
                workspace_id=workspace_id,
                preset=data.preset,
                columns=columns,
                feature_defs=data.feature_defs,
                slug=data.slug,
                settings=data.settings,
            )
        except KeyError:
            return StapelErrorResponse(400, ERR_400_UNKNOWN_PRESET)
        except FeatureValidationError:
            return StapelErrorResponse(400, ERR_400_INVALID_FEATURE_DEFS)
        response_cls = self.get_response_serializer_class()
        return StapelResponse(
            response_cls(board_to_dto(board)), status=status.HTTP_201_CREATED
        )


def _column_specs(raw):
    from .presets import ColumnSpec

    specs = []
    for c in raw:
        try:
            specs.append(
                ColumnSpec(
                    key=c["key"],
                    name=c["name"],
                    category=c["category"],
                    name_key=c.get("name_key", ""),
                    wip_limit=c.get("wip_limit"),
                )
            )
        except (KeyError, TypeError):
            return None
    return specs


@extend_schema(tags=["Tasks"])
class BoardDetailView(SerializerSeamMixin, APIView):
    """Retrieve, patch (name/feature_defs/settings) or archive a board."""

    permission_classes = [permissions.IsAuthenticated]
    request_serializer_class = BoardUpdateRequestSerializer
    response_serializer_class = BoardResponseSerializer

    def get(self, request, board_id):
        board = _get_board(request, board_id)
        if board is None:
            return StapelErrorResponse(404, ERR_404_BOARD_NOT_FOUND)
        if (resp := _forbidden(request, READ, board)) is not None:
            return resp
        return StapelResponse(self.get_response_serializer_class()(board_to_dto(board)))

    def patch(self, request, board_id):
        board = _get_board(request, board_id)
        if board is None:
            return StapelErrorResponse(404, ERR_404_BOARD_NOT_FOUND)
        if (resp := _forbidden(request, ADMIN, board)) is not None:
            return resp
        ser = self.get_request_serializer_class()(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        update_fields = []
        if data.name is not None:
            board.name = data.name
            update_fields.append("name")
        if data.settings is not None:
            board.settings = data.settings
            update_fields.append("settings")
        if update_fields:
            board.save(update_fields=update_fields + ["updated_at"])
        if data.feature_defs is not None:
            try:
                services.set_board_feature_defs(board, data.feature_defs)
            except FeatureValidationError:
                return StapelErrorResponse(400, ERR_400_INVALID_FEATURE_DEFS)
        return StapelResponse(self.get_response_serializer_class()(board_to_dto(board)))

    def delete(self, request, board_id):
        board = _get_board(request, board_id)
        if board is None:
            return StapelErrorResponse(404, ERR_404_BOARD_NOT_FOUND)
        if (resp := _forbidden(request, ADMIN, board)) is not None:
            return resp
        board.is_archived = True
        from django.utils import timezone

        board.archived_at = timezone.now()
        board.save(update_fields=["is_archived", "archived_at", "updated_at"])
        return StapelResponse({"status": "archived"})


# ── Column views ─────────────────────────────────────────────────────────


@extend_schema(tags=["Tasks"])
class ColumnListCreateView(SerializerSeamMixin, APIView):
    """List a board's columns or add one."""

    permission_classes = [permissions.IsAuthenticated]
    request_serializer_class = ColumnCreateRequestSerializer
    response_serializer_class = ColumnResponseSerializer

    def get(self, request, board_id):
        board = _get_board(request, board_id)
        if board is None:
            return StapelErrorResponse(404, ERR_404_BOARD_NOT_FOUND)
        if (resp := _forbidden(request, READ, board)) is not None:
            return resp
        response_cls = self.get_response_serializer_class()
        return StapelResponse(
            response_cls(
                [column_to_dto(c) for c in board.columns.order_by("order")], many=True
            )
        )

    def post(self, request, board_id):
        board = _get_board(request, board_id)
        if board is None:
            return StapelErrorResponse(404, ERR_404_BOARD_NOT_FOUND)
        if (resp := _forbidden(request, ADMIN, board)) is not None:
            return resp
        ser = self.get_request_serializer_class()(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        column = services.add_column(
            board,
            key=data.key,
            name=data.name,
            category=data.category,
            order=data.order,
            name_key=data.name_key,
            wip_limit=data.wip_limit,
        )
        return StapelResponse(
            self.get_response_serializer_class()(column_to_dto(column)),
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Tasks"])
class ColumnReorderView(SerializerSeamMixin, APIView):
    """Reorder a board's columns by key."""

    permission_classes = [permissions.IsAuthenticated]
    request_serializer_class = ColumnReorderRequestSerializer
    response_serializer_class = ColumnResponseSerializer

    def post(self, request, board_id):
        board = _get_board(request, board_id)
        if board is None:
            return StapelErrorResponse(404, ERR_404_BOARD_NOT_FOUND)
        if (resp := _forbidden(request, ADMIN, board)) is not None:
            return resp
        ser = self.get_request_serializer_class()(data=request.data)
        ser.is_valid(raise_exception=True)
        services.reorder_columns(board, ser.validated_data.keys)
        response_cls = self.get_response_serializer_class()
        return StapelResponse(
            response_cls(
                [column_to_dto(c) for c in board.columns.order_by("order")], many=True
            )
        )


# ── Task views ───────────────────────────────────────────────────────────


@extend_schema(tags=["Tasks"])
class TaskListCreateView(SerializerSeamMixin, APIView):
    """List a board's cards (paginated) or create one."""

    permission_classes = [permissions.IsAuthenticated]
    request_serializer_class = TaskCreateRequestSerializer
    response_serializer_class = TaskResponseSerializer
    pagination_class = TaskPagination

    def get(self, request, board_id):
        board = _get_board(request, board_id)
        if board is None:
            return StapelErrorResponse(404, ERR_404_BOARD_NOT_FOUND)
        if (resp := _forbidden(request, READ, board)) is not None:
            return resp
        qs = (
            Task.objects.select_related("column")
            .prefetch_related("assignees", "blocked_by", "checklist_items")
            .filter(board=board, is_archived=False)
        )
        column_key = request.query_params.get("column")
        category = request.query_params.get("category")
        assignee_id = request.query_params.get("assignee_id")
        if column_key:
            qs = qs.filter(column__key=column_key)
        if category:
            qs = qs.filter(column__category=category)
        if assignee_id:
            qs = qs.filter(assignees__pk=assignee_id)
        qs = qs.distinct()

        paginator = TaskPagination()
        page = paginator.paginate_queryset(qs, request)
        response_cls = self.get_response_serializer_class()
        items = [response_cls(task_to_dto(t)).data for t in page]
        return paginator.get_paginated_response(items)

    def post(self, request, board_id):
        board = _get_board(request, board_id)
        if board is None:
            return StapelErrorResponse(404, ERR_404_BOARD_NOT_FOUND)
        if (resp := _forbidden(request, WRITE, board)) is not None:
            return resp
        ser = self.get_request_serializer_class()(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        column = None
        if data.column:
            column = board.columns.filter(key=data.column).first()
            if column is None:
                return StapelErrorResponse(404, ERR_404_COLUMN_NOT_FOUND)
        parent = None
        if data.parent_id:
            parent = Task.objects.filter(board=board, id=data.parent_id).first()
        try:
            task = services.create_task(
                board=board,
                title=data.title,
                description=data.description,
                column=column,
                creator=request.user,
                features_dto=data.features,
                priority=data.priority,
                due_at=data.due_at,
                parent=parent,
                assignee_ids=data.assignee_ids,
            )
        except FeatureValidationError:
            return StapelErrorResponse(400, ERR_400_INVALID_FEATURES)
        task = _get_task(request, task.id)
        return StapelResponse(
            self.get_response_serializer_class()(task_to_dto(task)),
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Tasks"])
class TaskDetailView(SerializerSeamMixin, APIView):
    """Retrieve, patch or archive a card."""

    permission_classes = [permissions.IsAuthenticated]
    request_serializer_class = TaskUpdateRequestSerializer
    response_serializer_class = TaskResponseSerializer

    def get(self, request, task_id):
        task = _get_task(request, task_id)
        if task is None:
            return StapelErrorResponse(404, ERR_404_TASK_NOT_FOUND)
        if (resp := _forbidden(request, READ, task.board)) is not None:
            return resp
        return StapelResponse(self.get_response_serializer_class()(task_to_dto(task)))

    def patch(self, request, task_id):
        task = _get_task(request, task_id)
        if task is None:
            return StapelErrorResponse(404, ERR_404_TASK_NOT_FOUND)
        if (resp := _forbidden(request, WRITE, task.board)) is not None:
            return resp
        ser = self.get_request_serializer_class()(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        fields = {}
        for name in ("title", "description", "priority", "due_at"):
            value = getattr(data, name)
            if value is not None:
                fields[name] = value
        try:
            services.update_task(
                task, actor=request.user, features_dto=data.features, **fields
            )
        except FeatureValidationError:
            return StapelErrorResponse(400, ERR_400_INVALID_FEATURES)
        task = _get_task(request, task_id)
        return StapelResponse(self.get_response_serializer_class()(task_to_dto(task)))

    def delete(self, request, task_id):
        task = _get_task(request, task_id)
        if task is None:
            return StapelErrorResponse(404, ERR_404_TASK_NOT_FOUND)
        if (resp := _forbidden(request, WRITE, task.board)) is not None:
            return resp
        services.archive_task(task, actor=request.user)
        return StapelResponse({"status": "archived"})


@extend_schema(tags=["Tasks"])
class TaskMoveView(SerializerSeamMixin, APIView):
    """Move a card (drag-and-drop) subject to MOVE_POLICY."""

    permission_classes = [permissions.IsAuthenticated]
    request_serializer_class = TaskMoveRequestSerializer
    response_serializer_class = MoveResponseSerializer

    def post(self, request, task_id):
        task = _get_task(request, task_id)
        if task is None:
            return StapelErrorResponse(404, ERR_404_TASK_NOT_FOUND)
        if (resp := _forbidden(request, WRITE, task.board)) is not None:
            return resp
        ser = self.get_request_serializer_class()(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        to_column = task.board.columns.filter(key=data.to_column).first()
        if to_column is None:
            return StapelErrorResponse(404, ERR_404_COLUMN_NOT_FOUND)
        decision = services.move_task(
            task, to_column=to_column, index=data.index, actor=request.user
        )
        result = {ALLOW: "applied", DEFER: "deferred", DENY: "denied"}[decision.result]
        http = {
            "applied": status.HTTP_200_OK,
            "deferred": status.HTTP_202_ACCEPTED,
            "denied": status.HTTP_409_CONFLICT,
        }[result]
        response_cls = self.get_response_serializer_class()
        return StapelResponse(
            response_cls(MoveResponse(result=result, reason_key=decision.reason_key)),
            status=http,
        )


@extend_schema(tags=["Tasks"])
class TaskAssignView(SerializerSeamMixin, APIView):
    """Replace a card's assignee set."""

    permission_classes = [permissions.IsAuthenticated]
    request_serializer_class = TaskAssignRequestSerializer
    response_serializer_class = TaskResponseSerializer

    def post(self, request, task_id):
        task = _get_task(request, task_id)
        if task is None:
            return StapelErrorResponse(404, ERR_404_TASK_NOT_FOUND)
        if (resp := _forbidden(request, WRITE, task.board)) is not None:
            return resp
        ser = self.get_request_serializer_class()(data=request.data)
        ser.is_valid(raise_exception=True)
        services.set_assignees(
            task, ser.validated_data.assignee_ids, actor=request.user
        )
        task = _get_task(request, task_id)
        return StapelResponse(self.get_response_serializer_class()(task_to_dto(task)))


# ── Comment & checklist views ────────────────────────────────────────────


@extend_schema(tags=["Tasks"])
class CommentListCreateView(SerializerSeamMixin, APIView):
    """List a card's comments or add one."""

    permission_classes = [permissions.IsAuthenticated]
    request_serializer_class = CommentCreateRequestSerializer
    response_serializer_class = CommentResponseSerializer

    def get(self, request, task_id):
        task = _get_task(request, task_id)
        if task is None:
            return StapelErrorResponse(404, ERR_404_TASK_NOT_FOUND)
        if (resp := _forbidden(request, READ, task.board)) is not None:
            return resp
        comments = task.comments.filter(is_deleted=False)
        response_cls = self.get_response_serializer_class()
        return StapelResponse(
            response_cls([comment_to_dto(c) for c in comments], many=True)
        )

    def post(self, request, task_id):
        task = _get_task(request, task_id)
        if task is None:
            return StapelErrorResponse(404, ERR_404_TASK_NOT_FOUND)
        if (resp := _forbidden(request, WRITE, task.board)) is not None:
            return resp
        ser = self.get_request_serializer_class()(data=request.data)
        ser.is_valid(raise_exception=True)
        comment = services.add_comment(
            task, body=ser.validated_data.body, author=request.user
        )
        return StapelResponse(
            self.get_response_serializer_class()(comment_to_dto(comment)),
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Tasks"])
class ChecklistListCreateView(SerializerSeamMixin, APIView):
    """List a card's checklist or add a step."""

    permission_classes = [permissions.IsAuthenticated]
    request_serializer_class = ChecklistItemCreateRequestSerializer
    response_serializer_class = ChecklistItemResponseSerializer

    def get(self, request, task_id):
        task = _get_task(request, task_id)
        if task is None:
            return StapelErrorResponse(404, ERR_404_TASK_NOT_FOUND)
        if (resp := _forbidden(request, READ, task.board)) is not None:
            return resp
        response_cls = self.get_response_serializer_class()
        return StapelResponse(
            response_cls(
                [checklist_to_dto(i) for i in task.checklist_items.all()], many=True
            )
        )

    def post(self, request, task_id):
        task = _get_task(request, task_id)
        if task is None:
            return StapelErrorResponse(404, ERR_404_TASK_NOT_FOUND)
        if (resp := _forbidden(request, WRITE, task.board)) is not None:
            return resp
        ser = self.get_request_serializer_class()(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        item = services.add_checklist_item(
            task, text=data.text, ref=data.ref, order=data.order
        )
        return StapelResponse(
            self.get_response_serializer_class()(checklist_to_dto(item)),
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Tasks"])
class ChecklistItemStateView(SerializerSeamMixin, APIView):
    """Set a checklist step's state (pending/done/failed)."""

    permission_classes = [permissions.IsAuthenticated]
    request_serializer_class = ChecklistItemStateRequestSerializer
    response_serializer_class = ChecklistItemResponseSerializer

    def post(self, request, task_id, item_id):
        task = _get_task(request, task_id)
        if task is None:
            return StapelErrorResponse(404, ERR_404_TASK_NOT_FOUND)
        if (resp := _forbidden(request, WRITE, task.board)) is not None:
            return resp
        item = ChecklistItem.objects.filter(task=task, id=item_id).first()
        if item is None:
            return StapelErrorResponse(404, ERR_404_CHECKLIST_ITEM_NOT_FOUND)
        ser = self.get_request_serializer_class()(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            services.set_checklist_item_state(
                item, ser.validated_data.state, actor=request.user
            )
        except ValueError:
            return StapelErrorResponse(400, ERR_400_INVALID_CHECKLIST_STATE)
        return StapelResponse(
            self.get_response_serializer_class()(checklist_to_dto(item))
        )
