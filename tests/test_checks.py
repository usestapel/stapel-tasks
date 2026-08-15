"""Django system checks on seam configuration."""
from stapel_tasks.checks import (
    check_board_presets,
    check_move_policy,
    check_scope_provider,
)
from stapel_tasks.scope import ScopeProvider


class HostScopeProvider(ScopeProvider):
    """What the checks want a production host to write."""

    def resolve(self, request):
        return "ws-1"

    def filter(self, queryset, request):
        return queryset.filter(workspace_id="ws-1")

    def can(self, request, action, board=None):
        return False


class TestChecks:
    def test_defaults_pass(self):
        assert check_move_policy(None) == []
        assert check_board_presets(None) == []

    def test_the_shipped_provider_warns_in_a_standalone_deployment(self):
        """No longer silent: importability and type said nothing about a
        single-scope provider carrying a whole deployment."""
        assert [m.id for m in check_scope_provider(None)] == ["stapel_tasks.W001"]

    def test_the_shipped_provider_is_an_error_where_workspaces_can_answer(self):
        """The finding the old check could not make: this deployment knows
        what a mandate is, and the shipped provider cannot name a tenant."""
        from stapel_core.comm import function_registry
        from stapel_core.django.mandate import MANDATE_FUNCTION, MANDATE_RESULT_KEY

        function_registry.register(
            MANDATE_FUNCTION, lambda payload: {MANDATE_RESULT_KEY: True}
        )
        try:
            msgs = check_scope_provider(None)
        finally:
            function_registry._providers.pop(MANDATE_FUNCTION, None)
        assert [m.id for m in msgs] == ["stapel_tasks.E007"]

    def test_a_real_swap_is_silent(self, settings):
        settings.STAPEL_TASKS = {
            "SCOPE_PROVIDER": "tests.test_checks.HostScopeProvider"
        }
        assert check_scope_provider(None) == []

    def test_bad_scope_provider_errors(self, settings):
        settings.STAPEL_TASKS = {"SCOPE_PROVIDER": "stapel_tasks.models.Board"}
        errors = check_scope_provider(None)
        assert errors and errors[0].id == "stapel_tasks.E002"

    def test_unimportable_scope_provider_errors(self, settings):
        settings.STAPEL_TASKS = {"SCOPE_PROVIDER": "nope.Missing"}
        errors = check_scope_provider(None)
        assert errors and errors[0].id == "stapel_tasks.E001"

    def test_bad_move_policy_errors(self, settings):
        settings.STAPEL_TASKS = {"MOVE_POLICY": "stapel_tasks.models.Board"}
        errors = check_move_policy(None)
        assert errors and errors[0].id == "stapel_tasks.E004"

    def test_bad_board_presets_errors(self, settings):
        settings.STAPEL_TASKS = {"BOARD_PRESETS": {"x": "not-callable"}}
        errors = check_board_presets(None)
        assert errors and errors[0].id == "stapel_tasks.E006"
