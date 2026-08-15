"""F3 — the tenancy seam that had no "no workspace" answer.

``DefaultScopeProvider.can()`` returned True unconditionally and ``filter()``
was the identity, so all eleven views — every one of them ``IsAuthenticated``
— asked a question that could only be answered yes. A registered account
belonging to no workspace anywhere read, created and edited every board and
card in the deployment.

Compounding it: ``BoardListCreateView.post`` stamps ``workspace_id =
resolve(request)``, the contract permits ``None``, and ``NULL`` is valid
tenancy in the table — so a board could be created into a scope no membership
check can ever reach. A board in limbo is not a board with a permissive owner;
it is a board with no owner at all.

Both are closed in the provider, not in the eleven views: the views were
right to ask, they were just given a seam that always said yes.
"""
import pytest
from django.urls import reverse

from stapel_core.comm import function_registry
from stapel_core.django.mandate import MANDATE_FUNCTION, MANDATE_RESULT_KEY
from stapel_tasks.models import Board


@pytest.fixture
def mandate_seam():
    state = {"has_mandate": False, "raises": None}

    def handler(payload):
        if state["raises"]:
            raise state["raises"]
        return {MANDATE_RESULT_KEY: state["has_mandate"]}

    function_registry.register(MANDATE_FUNCTION, handler)
    yield state
    function_registry._providers.pop(MANDATE_FUNCTION, None)


@pytest.fixture(autouse=True)
def _clear_mandate_cache():
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def someone_elses_board(db):
    from stapel_tasks import services

    return services.create_board(name="Roadmap", preset="simple")


# ---------------------------------------------------------------------------
# The state nothing guarded
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_mandate_less_account_cannot_list_boards(mandate_seam, auth_client):
    assert auth_client.get(reverse("tasks-boards")).status_code == 403


@pytest.mark.django_db
def test_a_mandate_less_account_cannot_create_a_board(mandate_seam, auth_client):
    resp = auth_client.post(
        reverse("tasks-boards"), {"name": "Mine", "preset": "simple"}, format="json"
    )
    assert resp.status_code == 403, resp.content
    assert Board.objects.count() == 0


@pytest.mark.django_db
def test_a_mandate_less_account_cannot_read_a_board_by_id(
    mandate_seam, auth_client, someone_elses_board
):
    resp = auth_client.get(
        reverse("tasks-board-detail", args=[someone_elses_board.id])
    )
    assert resp.status_code in (403, 404), resp.content


@pytest.mark.django_db
def test_a_mandate_less_account_cannot_write_a_card(
    mandate_seam, auth_client, someone_elses_board
):
    column = someone_elses_board.columns.first()
    resp = auth_client.post(
        reverse("tasks-tasks", args=[someone_elses_board.id]),
        {"title": "planted", "column_id": str(column.id)},
        format="json",
    )
    assert resp.status_code in (403, 404), resp.content


# ---------------------------------------------------------------------------
# The compounding half: NULL tenancy
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_scoped_deployment_refuses_to_create_a_board_with_no_workspace(
    mandate_seam, auth_client
):
    """A mandated caller, a provider that cannot name a workspace: the board
    would land on NULL tenancy, which no membership check can reach. Refuse
    the write instead of manufacturing a scope nobody owns."""
    mandate_seam["has_mandate"] = True
    resp = auth_client.post(
        reverse("tasks-boards"), {"name": "Limbo", "preset": "simple"}, format="json"
    )
    assert resp.status_code == 503, resp.content
    assert Board.objects.count() == 0


@pytest.mark.django_db
def test_a_standalone_deployment_still_creates_single_scope_boards(auth_client):
    """NULL tenancy is legitimate in a host with exactly one tenant — that is
    what the shipped provider is documented for. Only a deployment that KNOWS
    about workspaces is refused it."""
    resp = auth_client.post(
        reverse("tasks-boards"), {"name": "Ours", "preset": "simple"}, format="json"
    )
    assert resp.status_code == 201, resp.content
    assert Board.objects.get().workspace_id is None


# ---------------------------------------------------------------------------
# The three states stay three
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_mandated_account_still_reads(mandate_seam, auth_client, someone_elses_board):
    mandate_seam["has_mandate"] = True
    assert auth_client.get(reverse("tasks-boards")).status_code == 200


@pytest.mark.django_db
def test_could_not_ask_refuses_with_503_never_403(mandate_seam, auth_client):
    mandate_seam["raises"] = RuntimeError("workspaces is down")
    assert auth_client.get(reverse("tasks-boards")).status_code == 503


@pytest.mark.django_db
def test_a_standalone_deployment_keeps_working(auth_client, someone_elses_board):
    assert auth_client.get(reverse("tasks-boards")).status_code == 200
