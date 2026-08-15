"""Scope + permission provider — the tenancy/authorization seam.

The library is scope-agnostic: ``Board.workspace_id`` is an opaque UUID the
host owns. A ``ScopeProvider`` (dotted path in
``STAPEL_TASKS["SCOPE_PROVIDER"]``) resolves the workspace_id from a request,
filters querysets by it, and answers permission questions
(viewer/member/admin — docs/tasks-module.md §2). The default is a single
global scope that allows everything; a stapel-workspaces-aware host swaps in
a provider that reads the active workspace and checks roles.

This is a *soft* integration: the module never imports stapel-workspaces —
the host's provider does, if it exists.
"""
from __future__ import annotations

from stapel_core.django.scope import MandateScopeMixin

# Permission actions the views ask about. Kept coarse on purpose.
READ = "read"          # view boards/cards
WRITE = "write"        # create/edit cards & comments
ADMIN = "admin"        # boards, columns, the custom-field schema


class ScopeProvider:
    """Contract for scope resolution/filtering and permission checks.
    Subclass and point ``STAPEL_TASKS["SCOPE_PROVIDER"]`` at it."""

    def resolve(self, request):
        """Return the ``workspace_id`` (UUID/str or ``None``) to stamp on
        boards created via ``request``."""
        raise NotImplementedError

    def filter(self, queryset, request):
        """Restrict ``queryset`` to the scope visible to ``request``."""
        raise NotImplementedError

    def can(self, request, action: str, board=None) -> bool:
        """Whether ``request``'s user may perform ``action`` (READ/WRITE/
        ADMIN) — optionally in the context of ``board``.

        Answer False for "no". Raise
        ``stapel_core.django.api.permissions.MandateUnavailable`` (503) for
        "could not find out" — a lookup that failed is not a permission that
        was granted.
        """
        raise NotImplementedError


class DefaultScopeProvider(MandateScopeMixin, ScopeProvider):
    """Single global scope: boards get ``workspace_id=None`` and nothing is
    filtered. Suitable for single-tenant hosts and tests.

    ``can`` used to return True unconditionally, which meant all eleven views
    asked a question with one possible answer. It now answers with the third
    principal state (``stapel_core.django.scope``): a registered account
    holding no mandate anywhere is not a member of a single global scope
    either — it is a member of nothing. In a genuinely standalone deployment,
    where nothing can answer that question and so nobody holds a mandate, the
    permissive behaviour stands and ``checks.py`` says so out loud.

    Swap for a workspace-aware provider in production: this closes the guest
    state, it does not separate one workspace's boards from another's
    (``stapel_tasks.E007``).
    """

    def resolve(self, request):
        return None

    def filter(self, queryset, request):
        return queryset if self.mandate_admits(request) else queryset.none()

    def can(self, request, action: str, board=None) -> bool:
        return self.mandate_admits(request)


def get_scope_provider() -> ScopeProvider:
    """Resolve the configured provider (already import_string'd by conf)."""
    from .conf import tasks_settings

    provider = tasks_settings.SCOPE_PROVIDER
    return provider() if isinstance(provider, type) else provider
