"""Action subscriptions of stapel-tasks.

Handlers must be idempotent: delivery is at-least-once (outbox retries,
broker redelivery). Consumes contracts live in ``schemas/consumes/``.

- ``user.deleted`` (from stapel-auth/gdpr) — de-link the account from the
  cards and comments it authored and drop its assignments.
- ``user.merged`` (from stapel-auth) — an anonymous guest was absorbed into
  an existing account; carry the guest's authorship and assignments over.
"""
import logging

from stapel_core.comm import on_action

logger = logging.getLogger(__name__)


class MergeTargetNotReady(RuntimeError):
    """A ``user.merged`` arrived before the surviving account exists here.

    Transient, not a bug: the guest has cards to carry over but there is no
    local user row to point their FKs at yet. Raising is the comm layer's
    retry signal — ``deliver()`` wraps a failing handler in
    ``ActionDeliveryError`` and the outbox redelivers — so the transfer
    completes once the survivor's user projection lands. An operator seeing
    this in a redelivery loop is looking at an ordering lag, not a defect.
    """


@on_action("user.deleted")
def handle_user_deleted(event):
    """Erase this module's PII when an account deletion is executed: drop the
    user's card assignments and anonymize the cards/comments they authored."""
    from .gdpr import TasksGDPRProvider

    user_id = event.payload.get("user_id")
    if not user_id:
        logger.error("user.deleted event without user_id: %s", event.event_id)
        return
    TasksGDPRProvider().delete(user_id)
    logger.info("tasks data anonymized for deleted user %s", user_id)


@on_action("user.merged")
def handle_user_merged(event):
    """Carry a merged-away account's cards, assignments and comments over.

    stapel-auth absorbs an anonymous guest into an existing account and then
    DELETES the guest row. The two FK columns here are ``SET_NULL``, so the
    guest's authorship is not erased by that — it is *anonymized*, which for
    a merge is exactly wrong: the person is still there, and a card they
    created minutes ago as a guest comes back authored by nobody. The
    assignments are worse: ``assignees`` is a plain M2M, its rows cascade
    with the user, and the card simply stops being anyone's job.

    Three columns carry a user here and all three move:

    * ``Task.creator`` — the card's author;
    * ``Task.assignees`` (M2M) — who the card is on;
    * ``TaskComment.author`` — the note's author.

    ``Board`` carries no owner (its tenancy is the opaque ``workspace_id``,
    resolved by the host's scope seam), and ``Column``/``ChecklistItem`` hang
    off a board or a card, so they follow by id.

    **The assignment collision.** The M2M's through table is unique on
    ``(task, user)``, so a blind reassignment of a card BOTH accounts are
    assigned to would violate it. The survivor's membership is the one that
    stays and the guest's is dropped — the set is a set, and the person ends
    up on the card exactly once.

    No ``task.assigned`` fact is emitted for the transfer. That fact means
    "this card became somebody's job"; here the same person keeps the same
    cards under a different id, and announcing it would fire an assignment
    notification for every card the person already had.

    Two different "unknown id" situations, and conflating them loses data:

    * the guest owns nothing here (never touched a board, or a previous
      delivery already moved it all) — a genuine no-op, returned quietly;
    * the guest owns rows but the survivor has no user row here yet — NOT a
      no-op. :class:`MergeTargetNotReady` is raised so the event is
      redelivered, because returning success would let the outbox mark it
      delivered and leave the cards authored by nobody.
    """
    from django.contrib.auth import get_user_model
    from django.core.exceptions import ValidationError
    from django.db import transaction

    from .models import Task, TaskComment

    payload = event.payload or {}
    from_user_id = payload.get("from_user_id")
    into_user_id = payload.get("into_user_id")
    if not from_user_id or not into_user_id:
        logger.error("user.merged without from/into user id: %s", event.event_id)
        return
    if str(from_user_id) == str(into_user_id):
        return

    with transaction.atomic():
        # Every read, and the decision they feed, happens inside the
        # transaction and before the first write, so the "not yet" path below
        # can never leave half the rows moved.
        try:
            assigned_ids = list(
                Task.objects.filter(assignees__pk=from_user_id)
                .distinct()
                .values_list("pk", flat=True)
            )
            owns_something = bool(assigned_ids) or (
                Task.objects.filter(creator_id=from_user_id).exists()
                or TaskComment.objects.filter(author_id=from_user_id).exists()
            )
            # The survivor probe is read here, under the same guard, because a
            # malformed *into* id must not escape as a poison pill either.
            survivor = get_user_model().objects.filter(pk=into_user_id).first()
        except (ValidationError, ValueError, TypeError):
            # Django raises ValidationError (not ValueError) for a malformed
            # UUID; an id that cannot address a row here names nothing.
            logger.warning("user.merged with unusable user ids: %s", event.event_id)
            return
        if not owns_something:
            # Nothing to carry: the guest never reached a board here, or a
            # previous delivery already moved everything. Quiet by design —
            # this is also the at-least-once idempotency path.
            return
        if survivor is None:
            raise MergeTargetNotReady(
                f"user.merged {from_user_id} -> {into_user_id}: the surviving "
                f"account has no user row in stapel-tasks yet; redeliver once "
                f"its projection has landed"
            )

        moved_cards = Task.objects.filter(creator_id=from_user_id).update(
            creator_id=survivor.pk
        )
        moved_comments = TaskComment.objects.filter(author_id=from_user_id).update(
            author_id=survivor.pk
        )
        for task in Task.objects.filter(pk__in=assigned_ids):
            # ``add`` before ``remove``, and ``add`` is idempotent — that is
            # what folds the (task, user) collision instead of colliding on it.
            task.assignees.add(survivor)
            task.assignees.remove(from_user_id)

    logger.info(
        "user.merged %s -> %s: %s cards, %s comments, %s assignment(s) "
        "carried over",
        from_user_id,
        into_user_id,
        moved_cards,
        moved_comments,
        len(assigned_ids),
    )
