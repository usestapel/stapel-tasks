"""Django system checks on seam configuration."""
from stapel_tasks.checks import (
    check_board_presets,
    check_move_policy,
    check_scope_provider,
)


class TestChecks:
    def test_defaults_pass(self):
        assert check_scope_provider(None) == []
        assert check_move_policy(None) == []
        assert check_board_presets(None) == []

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
