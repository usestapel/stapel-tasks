"""Every response body the contract declares is a body the views actually send.

``docs/schema.json`` is emitted from the views' ``@extend_schema``
annotations, and an annotation is a CLAIM: it says what the view returns, and
the generator has no way to check it against the method body.
``tests/test_contract.py`` compares the committed document against a FRESH
EMISSION of the same annotations — it proves the file is not stale, and
nothing else, because both sides come from the claim. stapel-alerts 0.2.0
shipped ``GET /issues`` declared as ``Issue[]`` while the wire carried
``{count, offset, limit, results}``: the drift gate was green and the
frontend pair rendered ``undefined``.

This is the gate the generator cannot be: it performs every operation the
committed schema declares with a JSON response body, and validates the body
it gets against the schema it was promised.

Rules this file holds itself to:

* an operation with a declared JSON response and no entry in ``RECIPES``
  FAILS LOUDLY — a gate that quietly covers three of four rows is the family
  of green that proves nothing;
* a path parameter the gate cannot fill fails at the point of substitution,
  naming the operation;
* the operations that genuinely cannot be driven in-process are listed by
  name in ``UNDRIVABLE`` with a one-line reason each. That list is asserted
  to be exactly current: a stale entry, or a missing reason, fails;
* a collection that comes back empty fails — an empty array validates
  against any item schema, so an empty answer is a check that looked at
  nothing;
* where a second state is cheap, a recipe drives BOTH. Every null finding
  of the first wave of this gate was on the EMPTY state (auth answered null
  for a REQUIRED integer on every account without TOTP; profiles answered a
  null ``created_at`` for every just-signed-up account), so "populated
  only" is a coverage number that hides the interesting half. The recipes
  below return a list of ``(state, response)`` pairs wherever an empty
  board, an empty page, a card with no optional field set, or a
  never-touched envelope is reachable.

Runs on every interpreter: it reads the committed schema and never emits.

The urlconf below is the EMISSION mount (``codegen_urls.py``): ``tasks/`` +
the module's own ``api/v1/``, giving the canonical ``/tasks/api/v1/…``
prefix the document is written against. ``tests/urls.py`` happens to mount
the same thing, so — unlike three of the first four libraries this gate was
written for — this module's suite was already looking where its document
points. The mount is restated here anyway, and asserted by
``test_every_declared_path_resolves_under_this_urlconf``, so that it fails
at the one moment it is cheap to fix: when somebody changes a mount.

What it found on its first run: 22 of 22 operations driven (23 declared
``(method, path, code)`` rows — ``POST /tasks/{id}/move`` declares 200 and
202 and both are driven), every one of them green, in both states where a
second state exists. ``KNOWN_MISMATCHES`` is empty and no operation is
excluded. The claim was checked, not assumed: swapping a declared schema for
``{"type": "string"}`` turns every operation red, which is the canary that
says this gate is not blind.
"""
import copy
import json
import re
import uuid
from pathlib import Path

import jsonschema
import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import include, path as url_path
from rest_framework.test import APIClient

REPO = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((REPO / "docs" / "schema.json").read_text())

#: The mount the contract is emitted at, reproduced for the test client.
urlpatterns = [
    url_path("tasks/", include("stapel_tasks.urls")),
]

pytestmark = [pytest.mark.django_db, pytest.mark.urls(__name__)]

V1 = "/tasks/api/v1"


@pytest.fixture(autouse=True)
def _media_root(tmp_path):
    """Nothing in this module writes an uploaded file today, and that is
    exactly the assumption worth pinning: ``MEDIA_ROOT`` is unset in the
    harness settings, so it defaults to the working directory and the first
    view that ever does write one would drop it into the checkout — beside a
    flat-layout package, where a stray directory also shadows a submodule."""
    with override_settings(MEDIA_ROOT=str(tmp_path)):
        yield


# ─────────────────────────────────────────────────────────────────────────────
# The contract side: what the document declares
# ─────────────────────────────────────────────────────────────────────────────


def _json_schema(node):
    """OpenAPI 3.0 → JSON Schema, for the divergences that matter here.

    OAS 3.0 spells "may be null" as ``nullable: true`` beside a ``type``;
    JSON Schema has no such keyword and would refuse the null. Everything
    else drf-spectacular emits here (``$ref``, ``allOf``, ``enum``,
    ``required``, ``readOnly``, ``additionalProperties``) is JSON Schema as
    written, or inert.
    """
    if isinstance(node, list):
        return [_json_schema(item) for item in node]
    if not isinstance(node, dict):
        return node
    rebuilt = {k: _json_schema(v) for k, v in node.items() if k != "nullable"}
    if node.get("nullable"):
        return {"anyOf": [rebuilt, {"type": "null"}]}
    return rebuilt


def _validator(response_schema):
    root = copy.deepcopy(response_schema)
    root["components"] = copy.deepcopy(SCHEMA["components"])
    return jsonschema.Draft202012Validator(_json_schema(root))


def _operations():
    """Every ``(method, path, 2xx code, JSON body schema)`` the contract declares."""
    ops = []
    for path, methods in SCHEMA["paths"].items():
        for method, op in methods.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            for code, response in op.get("responses", {}).items():
                body = (
                    response.get("content", {})
                    .get("application/json", {})
                    .get("schema")
                )
                if body is not None and code.startswith("2"):
                    ops.append((method.upper(), path, int(code), body))
    return sorted(ops, key=lambda o: (o[1], o[0], o[2]))


OPERATIONS = _operations()


# ─────────────────────────────────────────────────────────────────────────────
# The wire side: harness
# ─────────────────────────────────────────────────────────────────────────────


def _unique(prefix):
    return f"{prefix}{uuid.uuid4().hex[:10]}"


def make_user(**kwargs):
    User = get_user_model()
    defaults = dict(
        username=_unique("wire_"),
        email=f"{_unique('wire-')}@example.com",
        password="wire-contract-password-7",
    )
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


def client_for(user=None):
    """An APIClient acting as ``user`` (every view is ``IsAuthenticated``)."""
    client = APIClient()
    client.force_authenticate(user=user if user is not None else make_user())
    return client


def make_board(**kwargs):
    from stapel_tasks import services

    defaults = dict(name="Wire board", preset="simple")
    defaults.update(kwargs)
    return services.create_board(**defaults)


def make_task(board=None, **kwargs):
    from stapel_tasks import services

    board = board if board is not None else make_board()
    defaults = dict(title="Wire card")
    defaults.update(kwargs)
    return services.create_task(board=board, **defaults)


class DeferAllMovePolicy:
    """The managed-card path: every move is accepted as a command and not
    applied, which is the ONLY way ``POST /tasks/{id}/move`` answers the 202
    the contract declares beside its 200. Without it that row would be
    unreachable and the declared 202 body unproven."""

    def check(self, *, task, from_column, to_column, actor):
        from stapel_tasks.policy import MoveDecision

        return MoveDecision.defer()


def defer_moves():
    return override_settings(
        STAPEL_TASKS={
            "MOVE_POLICY": (
                "stapel_tasks.tests.test_contract_wire.DeferAllMovePolicy"
            )
        }
    )


def no_priority_scale():
    """``PRIORITY_SCALE`` is a host's list and may legitimately be empty —
    the DTO documents it as "may be empty" — so the vocabulary read is driven
    with the scale removed as well as with the shipped default."""
    return override_settings(STAPEL_TASKS={"PRIORITY_SCALE": []})


# ─────────────────────────────────────────────────────────────────────────────
# The recipe table
# ─────────────────────────────────────────────────────────────────────────────


class Call:
    """Performs one declared operation, and refuses to guess a path parameter.

    Carries the declared status ``code`` as well, because one operation here
    (``POST /tasks/{task_id}/move``) declares two of them and the recipe has
    to produce the state that yields the one under test.
    """

    def __init__(self, method, path, code):
        self.method = method
        self.path = path
        self.code = code

    def __call__(self, client, params=None, data=None, query="", **extra):
        url = self.path
        for name, value in (params or {}).items():
            url = url.replace("{%s}" % name, str(value))
        assert "{" not in url, (
            f"{self.method} {self.path}: a path parameter this gate does not "
            "know how to fill — teach its recipe, or the operation goes unchecked"
        )
        send = getattr(client, self.method.lower())
        if self.method in ("GET", "DELETE"):
            return send(url + query, **extra)
        return send(url + query, data if data is not None else {}, format="json", **extra)


#: How to perform each operation the contract declares with a JSON response
#: body, keyed by ``(METHOD, path template)``. Each recipe receives a ``Call``
#: bound to that operation and returns either the response it produced or a
#: list of ``(state name, response)`` pairs — every one of which is validated.
RECIPES = {}


def recipe(method, path):
    def register(fn):
        key = (method, V1 + path)
        assert key not in RECIPES, f"duplicate recipe for {method} {path}"
        RECIPES[key] = fn
        return fn

    return register


#: Operations that cannot be driven in-process, by name and with the reason.
#: EMPTY: every operation this contract declares is reachable from a test
#: client. A short, visible list would be acceptable here; a silent skip is
#: not.
UNDRIVABLE: dict = {}


# ── boards ───────────────────────────────────────────────────────────────────


@recipe("GET", "/boards")
def _boards_list(call):
    """Populated only: the declared body is an ARRAY, and an empty array
    validates against any item schema — the gate asserts a non-empty list
    below, so the empty state here would prove nothing and fail loudly."""
    user = make_user()
    make_board()
    make_board(name="Second board", preset="simple")
    return call(client_for(user))


@recipe("POST", "/boards")
def _boards_create(call):
    return [
        (
            "minimal (preset default, no slug/settings/feature_defs)",
            call(client_for(), data={"name": "Wire board"}),
        ),
        (
            "full (explicit columns, slug, settings)",
            call(
                client_for(),
                data={
                    "name": "Wire board full",
                    "slug": _unique("wire-"),
                    "columns": [
                        {"key": "todo", "name": "To do", "category": "backlog"},
                        {"key": "done", "name": "Done", "category": "done",
                         "name_key": "board.done", "wip_limit": 5},
                    ],
                    "settings": {"transitions": {"todo": ["done"]}},
                },
            ),
        ),
    ]


@recipe("GET", "/boards/presets")
def _board_presets(call):
    client = client_for()
    with no_priority_scale():
        empty_scale = call(client)
    return [
        ("shipped PRIORITY_SCALE", call(client)),
        ("PRIORITY_SCALE emptied by the host", empty_scale),
    ]


@recipe("GET", "/boards/{board_id}")
def _board_get(call):
    client = client_for()
    plain = make_board()
    rich = make_board(
        name="Rich board",
        slug=_unique("wire-"),
        settings={"transitions": {"todo": ["done"]}},
    )
    return [
        ("board with no settings and no feature_defs", call(client, params={"board_id": plain.id})),
        ("board with slug and settings", call(client, params={"board_id": rich.id})),
    ]


@recipe("PATCH", "/boards/{board_id}")
def _board_patch(call):
    client = client_for()
    return [
        (
            "no-op patch (nothing supplied)",
            call(client, params={"board_id": make_board().id}, data={}),
        ),
        (
            "name and settings replaced",
            call(
                client,
                params={"board_id": make_board().id},
                data={"name": "Renamed by the wire gate",
                      "settings": {"transitions": {"todo": ["done"]}}},
            ),
        ),
    ]


@recipe("DELETE", "/boards/{board_id}")
def _board_archive(call):
    return call(client_for(), params={"board_id": make_board().id})


@recipe("GET", "/boards/{board_id}/columns")
def _columns_list(call):
    return call(client_for(), params={"board_id": make_board().id})


@recipe("POST", "/boards/{board_id}/columns")
def _columns_create(call):
    client = client_for()
    return [
        (
            "minimal (no order, no name_key, no wip_limit)",
            call(
                client,
                params={"board_id": make_board().id},
                data={"key": "review", "name": "Review", "category": "review"},
            ),
        ),
        (
            "full (order, name_key, wip_limit)",
            call(
                client,
                params={"board_id": make_board().id},
                data={"key": "waiting", "name": "Waiting", "category": "waiting",
                      "order": 1, "name_key": "board.waiting", "wip_limit": 3},
            ),
        ),
    ]


@recipe("POST", "/boards/{board_id}/columns/reorder")
def _columns_reorder(call):
    board = make_board()
    return call(
        client_for(),
        params={"board_id": board.id},
        data={"keys": ["done", "todo", "in_progress"]},
    )


@recipe("GET", "/boards/{board_id}/cards")
def _board_cards(call):
    client = client_for()
    empty = make_board()
    full = make_board()
    make_task(full, title="Card one")
    make_task(full, title="Card two", description="with a body", priority=3)
    return [
        ("board with no cards at all", call(client, params={"board_id": empty.id})),
        ("board with cards in a column", call(client, params={"board_id": full.id})),
        (
            "filtered to a column that holds nothing",
            call(client, params={"board_id": full.id}, query="?column=done"),
        ),
    ]


@recipe("GET", "/boards/{board_id}/tasks")
def _tasks_feed(call):
    client = client_for()
    empty = make_board()
    full = make_board()
    for index in range(3):
        make_task(full, title=f"Card {index}")
    return [
        ("empty page (next_anchor/prev_anchor never filled)",
         call(client, params={"board_id": empty.id})),
        ("populated page", call(client, params={"board_id": full.id})),
        ("page smaller than the feed (has_next true)",
         call(client, params={"board_id": full.id}, query="?limit=1")),
    ]


@recipe("POST", "/boards/{board_id}/tasks")
def _tasks_create(call):
    client = client_for()
    user = make_user()
    return [
        (
            "minimal (title alone — no description, priority, due_at, assignees)",
            call(client, params={"board_id": make_board().id}, data={"title": "Bare card"}),
        ),
        (
            "full (column, description, priority, due date, assignee)",
            call(
                client,
                params={"board_id": make_board().id},
                data={
                    "title": "Full card",
                    "description": "A described card.",
                    "column": "in_progress",
                    "priority": 2,
                    "due_at": "2030-01-01T00:00:00Z",
                    "assignee_ids": [str(user.pk)],
                },
            ),
        ),
    ]


# ── cards ────────────────────────────────────────────────────────────────────


@recipe("GET", "/tasks/{task_id}")
def _task_get(call):
    client = client_for()
    bare = make_task()
    rich_board = make_board()
    rich = make_task(
        rich_board,
        title="Rich card",
        description="A described card.",
        priority=4,
    )
    from stapel_tasks import services

    services.add_checklist_item(rich, text="A step")
    return [
        ("card with nothing optional set", call(client, params={"task_id": bare.id})),
        ("card with priority, description and a checklist",
         call(client, params={"task_id": rich.id})),
    ]


@recipe("PATCH", "/tasks/{task_id}")
def _task_patch(call):
    client = client_for()
    return [
        ("no-op patch (nothing supplied)",
         call(client, params={"task_id": make_task().id}, data={})),
        (
            "title, description, priority and due date replaced",
            call(
                client,
                params={"task_id": make_task().id},
                data={
                    "title": "Retitled by the wire gate",
                    "description": "Rewritten.",
                    "priority": 1,
                    "due_at": "2031-06-01T12:00:00Z",
                },
            ),
        ),
    ]


@recipe("DELETE", "/tasks/{task_id}")
def _task_archive(call):
    return call(client_for(), params={"task_id": make_task().id})


@recipe("POST", "/tasks/{task_id}/move")
def _task_move(call):
    """200 applied and 202 deferred are two DECLARED bodies of one operation.

    The default ``MOVE_POLICY`` allows every move, so the 202 row only exists
    under a policy that defers — the managed-card path this module documents.
    """
    client = client_for()
    if call.code == 202:
        with defer_moves():
            return call(
                client, params={"task_id": make_task().id}, data={"to_column": "done"}
            )
    return [
        (
            "applied, appended",
            call(client, params={"task_id": make_task().id}, data={"to_column": "done"}),
        ),
        (
            "applied at an explicit index",
            call(
                client,
                params={"task_id": make_task().id},
                data={"to_column": "in_progress", "index": 0},
            ),
        ),
    ]


@recipe("POST", "/tasks/{task_id}/assign")
def _task_assign(call):
    client = client_for()
    return [
        (
            "assignee set emptied",
            call(client, params={"task_id": make_task().id}, data={"assignee_ids": []}),
        ),
        (
            "two assignees",
            call(
                client,
                params={"task_id": make_task().id},
                data={"assignee_ids": [str(make_user().pk), str(make_user().pk)]},
            ),
        ),
    ]


# ── comments & checklist ─────────────────────────────────────────────────────


@recipe("GET", "/tasks/{task_id}/comments")
def _comments_list(call):
    from stapel_tasks import services

    user = make_user()
    task = make_task()
    services.add_comment(task, body="A comment from the wire gate", author=user)
    services.add_comment(task, body="A comment with no author", author=None)
    return call(client_for(user), params={"task_id": task.id})


@recipe("POST", "/tasks/{task_id}/comments")
def _comments_create(call):
    return call(
        client_for(),
        params={"task_id": make_task().id},
        data={"body": "Posted by the wire gate"},
    )


@recipe("GET", "/tasks/{task_id}/checklist")
def _checklist_list(call):
    from stapel_tasks import services

    task = make_task()
    services.add_checklist_item(task, text="Step with no ref")
    services.add_checklist_item(task, text="Step mirroring an external step", ref="ext-1")
    return call(client_for(), params={"task_id": task.id})


@recipe("POST", "/tasks/{task_id}/checklist")
def _checklist_create(call):
    client = client_for()
    return [
        (
            "minimal (no ref, no order)",
            call(client, params={"task_id": make_task().id}, data={"text": "A step"}),
        ),
        (
            "full (ref and order)",
            call(
                client,
                params={"task_id": make_task().id},
                data={"text": "A mirrored step", "ref": "ext-7", "order": 0},
            ),
        ),
    ]


@recipe("POST", "/tasks/{task_id}/checklist/{item_id}/state")
def _checklist_state(call):
    from stapel_tasks import services

    client = client_for()
    outcomes = []
    for state in ("done", "failed", "pending"):
        task = make_task()
        item = services.add_checklist_item(task, text="A step")
        outcomes.append(
            (
                f"state -> {state}",
                call(
                    client,
                    params={"task_id": task.id, "item_id": item.id},
                    data={"state": state},
                ),
            )
        )
    return outcomes


# ─────────────────────────────────────────────────────────────────────────────
# The gate
# ─────────────────────────────────────────────────────────────────────────────


#: Operations whose declared body the wire does not send, with the defect and
#: its owner. ``strict=True``: a fixed entry fails until it is deleted, so a
#: finding can be neither forgotten nor quietly kept.
#:
#: EMPTY, and that is a finding rather than an omission: all 22 operations
#: answer bodies their declared schemas describe, in every state this file
#: reaches. The mechanism stays because the next change will need it.
KNOWN_MISMATCHES: dict = {}


def test_the_contract_declares_something_to_check():
    assert OPERATIONS, "docs/schema.json declares no JSON responses at all"


def test_every_declared_path_resolves_under_this_urlconf():
    """The suite must be looking where the document describes.

    Three of the first four libraries this gate was written for had a
    committed contract that nothing had ever driven, because the test urlconf
    mounted somewhere the document does not describe: one mounted a different
    prefix AND one segment short, one mounted the paths bare, and one mounted
    less than the emission did. In every case the operations were "covered"
    by a file that could not have reached a single one of them.

    That is the same family as a gate nobody asks: the recipes can all be
    written, the run can be green, and not one request went where the contract
    says it goes. A missing recipe already fails loudly; this fails when the
    MOUNT is wrong, which no per-operation check can see, because when the
    mount is wrong every operation is equally and silently unreachable.

    Asserted against the urlconf this module declares, so it fails at the one
    moment it is cheap to fix: when somebody changes a mount.
    """
    from django.urls import Resolver404, resolve

    # Resolution cares about the SHAPE of a segment, and a urlconf may use
    # several converters — uuid, int, slug. A path counts as reachable if any
    # one shape resolves: the question here is whether the mount exists, not
    # whether a particular id does.
    candidates = (
        "00000000-0000-4000-8000-000000000000",
        "1",
        "a-slug",
    )

    unreachable = []
    for _method, path, _code, _schema in OPERATIONS:
        for value in candidates:
            try:
                resolve(re.sub(r"\{[^}]+\}", value, path))
                break
            except Resolver404:
                continue
        else:
            unreachable.append(path)

    assert not unreachable, (
        "these declared paths do not resolve under this module's urlconf, so "
        "nothing here can be driving them — the mount is wrong, not the "
        "recipes:\n  " + "\n  ".join(sorted(set(unreachable)))
    )


def test_every_declared_operation_is_driven_or_named_undrivable():
    """No operation is covered by silence, and no entry outlives its operation."""
    declared = {(method, path) for method, path, _code, _schema in OPERATIONS}
    covered = set(RECIPES) | set(UNDRIVABLE)

    missing = sorted(declared - covered)
    assert not missing, (
        "operations with a declared JSON response body and no recipe:\n"
        + "\n".join(f"  {m} {p}" for m, p in missing)
    )
    stale = sorted(covered - declared)
    assert not stale, (
        "recipes/exclusions for operations the contract no longer declares:\n"
        + "\n".join(f"  {m} {p}" for m, p in stale)
    )
    both = sorted(set(RECIPES) & set(UNDRIVABLE))
    assert not both, f"driven AND excluded: {both}"
    for key, reason in UNDRIVABLE.items():
        assert reason and reason.strip(), f"{key} is excluded with no reason"


def test_every_known_mismatch_is_still_declared_and_explained():
    """A recorded defect must name a live operation and carry its reason.

    Without this, an operation that is renamed or removed leaves an entry that
    silences nothing and reads like a known problem forever.
    """
    declared = {(method, path) for method, path, _code, _schema in OPERATIONS}
    for key, reason in KNOWN_MISMATCHES.items():
        assert key in declared, (
            f"{key} is recorded as a known mismatch but the contract no longer "
            "declares it — delete the entry"
        )
        assert reason and reason.strip(), f"{key} is recorded with no reason"


def _states(produced):
    """A recipe answers with one response, or with ``(state, response)`` pairs."""
    if isinstance(produced, list):
        return produced
    return [("the only state", produced)]


@pytest.mark.parametrize(
    "method,path,code,body_schema",
    OPERATIONS,
    ids=[f"{m} {p} {c}" for m, p, c, _ in OPERATIONS],
)
def test_the_wire_matches_the_declared_response(method, path, code, body_schema, request):
    if (method, path) in UNDRIVABLE:
        pytest.skip(f"excluded by name: {UNDRIVABLE[(method, path)]}")

    if (method, path) in KNOWN_MISMATCHES:
        request.node.add_marker(
            pytest.mark.xfail(
                strict=True,
                reason=f"{method} {path}: {KNOWN_MISMATCHES[(method, path)]}",
            )
        )

    perform = RECIPES.get((method, path))
    assert perform is not None, (
        f"{method} {path} declares a response body and has no recipe — an "
        "unchecked operation is a schema nobody proves. Teach RECIPES, or "
        "name it in UNDRIVABLE with a reason."
    )

    validator = _validator(body_schema)
    for state, response in _states(perform(Call(method, path, code))):
        assert response.status_code == code, (
            f"{method} {path} [{state}]: expected the declared {code}, got "
            f"{response.status_code}: {response.content[:400]}"
        )

        body = response.json()
        errors = sorted(validator.iter_errors(body), key=lambda e: list(e.path))
        assert not errors, (
            f"{method} {path} [{state}] answers a body the contract does not "
            "describe:\n"
            + "\n".join(f"  at {list(e.path) or '<root>'}: {e.message}" for e in errors[:10])
            + f"\n  body: {json.dumps(body)[:600]}"
        )
        # An empty collection validates against any item schema, so a
        # collection response must actually carry a row for the check to have
        # looked at anything — except where the recipe named the state EMPTY
        # on purpose, which is the state the first wave's null findings all
        # lived in.
        if "empty" not in state and "nothing" not in state:
            if isinstance(body, list):
                assert body, f"{method} {path} [{state}]: the declared list came back empty"
            if isinstance(body, dict) and isinstance(body.get("items"), list):
                assert body["items"], (
                    f"{method} {path} [{state}]: the declared page came back empty"
                )
