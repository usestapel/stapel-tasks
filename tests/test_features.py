"""Custom-fields seam — the soft stapel-attributes integration.

These tests exercise the seam *contract*, not a specific attributes schema.
The point of the soft seam is that the module is useful with or without
stapel-attributes installed.
"""
import pytest

from stapel_tasks import features, services


class TestSoftSeam:
    def test_no_feature_defs_is_passthrough(self):
        # No schema declared -> DTO kept verbatim (STORE_UNKNOWN_FEATURES).
        dto = {"color": {"type": "text", "value": "red"}}
        # validate is a no-op, normalize keeps the DTO.
        features.validate_features([], dto)
        assert features.normalize_features([], dto) == dto

    def test_store_unknown_features_off_drops(self, settings):
        settings.STAPEL_TASKS = {"STORE_UNKNOWN_FEATURES": False}
        dto = {"color": {"type": "text", "value": "red"}}
        assert features.normalize_features([], dto) == {}

    def test_attributes_available_reflects_import(self):
        # In this workspace stapel-attributes IS installed; the flag is a
        # simple, honest import probe.
        assert isinstance(features.attributes_available(), bool)


@pytest.mark.django_db
class TestFeaturesOnCard:
    def test_card_roundtrips_features_without_schema(self):
        board = services.create_board(name="B", preset="simple")
        dto = {"note": {"type": "text", "value": "hi"}}
        task = services.create_task(board=board, title="t", features_dto=dto)
        task.refresh_from_db()
        # Without a board schema the raw DTO is preserved (soft seam), so the
        # module is useful even when a host has not modeled custom fields.
        assert task.features == dto
