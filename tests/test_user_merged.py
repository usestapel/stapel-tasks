"""``user.merged`` — a card started as a guest stays the person's card.

stapel-auth absorbs an anonymous guest into an existing account and then
DELETES the guest row. ``Task.creator`` and ``TaskComment.author`` are
``SET_NULL``, so the guest's authorship is not erased — it is *anonymized*,
which for a merge is exactly wrong: the person is still there, and their card
comes back authored by nobody. The M2M assignments simply cascade away and
the card stops being anyone's job. What is pinned here:

* all three user columns move — ``Task.creator``, ``Task.assignees``,
  ``TaskComment.author``;
* the ``(task, user)`` collision folds instead of raising: a card both
  accounts sat on ends with exactly one membership;
* no ``task.assigned`` fact is emitted — the same person keeps the same
  cards, and announcing it would notify them about work they already had;
* the handler is idempotent, and a no-op for ids it has never seen;
* a guest with rows to carry and a survivor this service has not projected
  yet RAISES rather than reporting success, so the outbox redelivers instead
  of silently discarding the transfer;
* a malformed id is swallowed — an escaping exception is a poison pill on an
  at-least-once bus, and no redelivery can fix a typo.
"""
import types
import uuid

import pytest

from stapel_tasks import services
from stapel_tasks.actions import MergeTargetNotReady, handle_user_merged
from stapel_tasks.models import Task, TaskComment

pytestmark = pytest.mark.django_db


@pytest.fixture
def survivor(db):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create_user(
        username="carol", email="carol@example.com", password="x"
    )


def _event(from_user_id, into_user_id, event_id="evt-merge"):
    return types.SimpleNamespace(
        payload={
            "from_user_id": str(from_user_id),
            "into_user_id": str(into_user_id),
            "reason": "anonymous_promotion",
        },
        event_id=event_id,
    )


def _merge(from_user, into_user):
    handle_user_merged(
        _event(getattr(from_user, "pk", from_user), getattr(into_user, "pk", into_user))
    )


def _seed_guest(guest):
    """Everything a guest can own in this module, in one call."""
    board = services.create_board(name="B", preset="simple")
    task = services.create_task(board=board, title="Guest card", creator=guest)
    services.set_assignees(task, [guest.pk])
    comment = services.add_comment(task, body="from the guest", author=guest)
    return task, comment


# ── the happy path ──────────────────────────────────────────────────────


def test_all_three_user_columns_move_to_the_survivor(user, survivor):
    task, comment = _seed_guest(user)

    _merge(user, survivor)

    task.refresh_from_db()
    comment.refresh_from_db()
    assert task.creator_id == survivor.pk
    assert comment.author_id == survivor.pk
    assert list(task.assignees.values_list("pk", flat=True)) == [survivor.pk]
    assert not Task.objects.filter(creator_id=user.pk).exists()
    assert not TaskComment.objects.filter(author_id=user.pk).exists()


def test_a_card_the_guest_only_commented_on_keeps_its_creator(
    user, other_user, survivor
):
    """Only what the guest owns moves; another person's card is untouched."""
    board = services.create_board(name="B", preset="simple")
    task = services.create_task(board=board, title="theirs", creator=other_user)
    comment = services.add_comment(task, body="hi", author=user)

    _merge(user, survivor)

    task.refresh_from_db()
    comment.refresh_from_db()
    assert task.creator_id == other_user.pk
    assert comment.author_id == survivor.pk


def test_second_delivery_changes_nothing(user, survivor):
    task, comment = _seed_guest(user)

    _merge(user, survivor)
    _merge(user, survivor)  # at-least-once delivery

    task.refresh_from_db()
    comment.refresh_from_db()
    assert task.creator_id == survivor.pk
    assert comment.author_id == survivor.pk
    assert task.assignees.count() == 1
    assert Task.objects.count() == 1
    assert TaskComment.objects.count() == 1


def test_guest_owning_nothing_is_a_clean_no_op(user, survivor):
    _merge(user, survivor)
    assert Task.objects.count() == 0


def test_merge_into_self_is_a_no_op(user):
    task, _comment = _seed_guest(user)
    _merge(user, user)
    task.refresh_from_db()
    assert task.creator_id == user.pk


def test_an_event_naming_users_with_nothing_here_does_nothing(user, survivor):
    task, _comment = _seed_guest(user)

    handle_user_merged(_event(uuid.uuid4(), survivor.pk))

    task.refresh_from_db()
    assert task.creator_id == user.pk


# ── the (task, user) assignment collision ───────────────────────────────


def test_a_card_both_accounts_sat_on_ends_with_one_membership(user, survivor):
    """The through table is unique on (task, user): a blind reassignment
    would violate it, so the survivor's membership stays and the guest's is
    dropped."""
    board = services.create_board(name="B", preset="simple")
    task = services.create_task(board=board, title="shared", creator=survivor)
    services.set_assignees(task, [user.pk, survivor.pk])

    _merge(user, survivor)

    assert list(task.assignees.values_list("pk", flat=True)) == [survivor.pk]
    assert task.assignees.count() == 1


def test_a_second_delivery_after_a_fold_is_still_one_membership(user, survivor):
    board = services.create_board(name="B", preset="simple")
    task = services.create_task(board=board, title="shared", creator=survivor)
    services.set_assignees(task, [user.pk, survivor.pk])

    _merge(user, survivor)
    _merge(user, survivor)

    assert task.assignees.count() == 1


def test_the_transfer_announces_no_assignment(user, survivor, captured_events):
    """``task.assigned`` means "this became somebody's job". The same person
    keeping the same cards under a new id is not that, and announcing it
    would notify them about work they already had."""
    _seed_guest(user)
    captured_events.clear()

    _merge(user, survivor)

    assert [e.event_type for e in captured_events] == []


# ── malformed and missing payloads ──────────────────────────────────────


def test_missing_ids_are_reported_and_ignored(user, survivor):
    task, _comment = _seed_guest(user)

    handle_user_merged(
        types.SimpleNamespace(payload={"into_user_id": str(survivor.pk)}, event_id="e1")
    )
    handle_user_merged(
        types.SimpleNamespace(payload={"from_user_id": str(user.pk)}, event_id="e2")
    )
    handle_user_merged(types.SimpleNamespace(payload={}, event_id="e3"))

    task.refresh_from_db()
    assert task.creator_id == user.pk


def test_unusable_user_ids_are_a_clean_no_op(user, survivor):
    """``not-a-uuid`` raises ``ValidationError`` — which is NOT a
    ``ValueError`` — from a UUID pk filter. Catching only ``ValueError``
    would make this a poison pill."""
    task, _comment = _seed_guest(user)

    handle_user_merged(_event("not-a-uuid", survivor.pk))
    handle_user_merged(_event(user.pk, "not-a-uuid"))

    task.refresh_from_db()
    assert task.creator_id == user.pk


# ── the survivor has not been projected here yet ────────────────────────


def test_unknown_survivor_raises_and_moves_nothing(user):
    task, comment = _seed_guest(user)
    survivor_id = uuid.uuid4()

    with pytest.raises(MergeTargetNotReady) as excinfo:
        handle_user_merged(_event(user.pk, survivor_id))

    assert str(user.pk) in str(excinfo.value)
    assert str(survivor_id) in str(excinfo.value)

    task.refresh_from_db()
    comment.refresh_from_db()
    assert task.creator_id == user.pk
    assert comment.author_id == user.pk
    assert list(task.assignees.values_list("pk", flat=True)) == [user.pk]


def test_redelivery_after_the_survivor_appears_completes_the_transfer(user):
    """The raise is a real retry path, not just a louder failure."""
    from django.contrib.auth import get_user_model

    task, comment = _seed_guest(user)
    survivor_id = uuid.uuid4()

    with pytest.raises(MergeTargetNotReady):
        handle_user_merged(_event(user.pk, survivor_id))

    late = get_user_model().objects.create(id=survivor_id, username="late")

    handle_user_merged(_event(user.pk, survivor_id))  # ...and it redelivers.

    task.refresh_from_db()
    comment.refresh_from_db()
    assert task.creator_id == late.pk
    assert comment.author_id == late.pk
    assert list(task.assignees.values_list("pk", flat=True)) == [late.pk]


def test_unknown_survivor_with_an_empty_guest_stays_quiet(user):
    """No rows to carry — a genuine no-op, and the retry loop must not start."""
    handle_user_merged(_event(user.pk, uuid.uuid4()))
    assert Task.objects.count() == 0


def test_second_delivery_after_a_completed_merge_never_raises(user, survivor):
    task, _comment = _seed_guest(user)

    _merge(user, survivor)
    _merge(user, survivor)  # must not raise MergeTargetNotReady

    task.refresh_from_db()
    assert task.creator_id == survivor.pk


# ── wiring ──────────────────────────────────────────────────────────────


def test_the_subscription_is_registered():
    from stapel_core.comm import action_registry

    assert handle_user_merged in action_registry.handlers("user.merged")


def test_the_lifecycle_pair_check_is_green():
    """``stapel_core.lifecycle.E001`` — one half of an account's life cycle
    answered and not the other is an ERROR as of core 0.52.x."""
    from stapel_core.comm.lifecycle_checks import check_lifecycle_pairs

    assert check_lifecycle_pairs() == []


def test_the_consumes_schema_is_committed():
    import json
    from pathlib import Path

    path = (
        Path(__file__).resolve().parent.parent
        / "schemas" / "consumes" / "user.merged.json"
    )
    schema = json.loads(path.read_text())
    assert schema["title"] == "user.merged"
    assert set(schema["required"]) == {"from_user_id", "into_user_id"}


def test_only_three_columns_here_name_a_user():
    """The handler moves exactly these. A fourth user column would be
    silently stranded — fail here, not in production."""
    from django.apps import apps
    from django.conf import settings as django_settings

    found = set()
    for model in apps.get_app_config("stapel_tasks").get_models():
        for field in model._meta.get_fields():
            remote = getattr(field, "related_model", None)
            if remote is not None and remote._meta.label == django_settings.AUTH_USER_MODEL:
                found.add(f"{model.__name__}.{field.name}")
    assert found == {"Task.creator", "Task.assignees", "TaskComment.author"}
