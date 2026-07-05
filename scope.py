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
        ADMIN) — optionally in the context of ``board``."""
        raise NotImplementedError


class DefaultScopeProvider(ScopeProvider):
    """Single global scope: boards get ``workspace_id=None``, nothing is
    filtered, and every authenticated request may do anything. Suitable for
    single-tenant hosts and tests."""

    def resolve(self, request):
        return None

    def filter(self, queryset, request):
        return queryset

    def can(self, request, action: str, board=None) -> bool:
        return True


def get_scope_provider() -> ScopeProvider:
    """Resolve the configured provider (already import_string'd by conf)."""
    from .conf import tasks_settings

    provider = tasks_settings.SCOPE_PROVIDER
    return provider() if isinstance(provider, type) else provider
