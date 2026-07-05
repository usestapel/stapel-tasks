"""Custom fields — the soft stapel-attributes seam.

A board owns a custom-field *schema* (``Board.feature_defs`` — a list of
stapel-attributes FeatureDef configs); a card stores *values*
(``Task.features`` — a DAO JSON with display metadata, so a client renders
badges/titles for free). Validation and DTO->DAO normalization are delegated
to stapel-attributes — the same engine categories->listings use — so this
module invents no type system of its own.

**Soft integration.** stapel-attributes is an optional dependency: the import
happens inside these functions, and if it is absent the seam degrades to a
pass-through (``STORE_UNKNOWN_FEATURES`` decides whether the raw submitted
DTO is kept on the card or dropped). A board with no ``feature_defs`` also
short-circuits. This keeps custom fields a genuine seam — the module is
useful without stapel-attributes installed.
"""
from __future__ import annotations

from typing import Any


def attributes_available() -> bool:
    """Whether stapel-attributes is importable in this environment."""
    try:
        import stapel_attributes  # noqa: F401
    except ImportError:
        return False
    return True


class FeatureValidationError(Exception):
    """Raised when a submitted custom-field DTO is invalid for the board's
    schema. ``messages`` carries one human-oriented string per bad field
    (the view maps this to a 400 error key)."""

    def __init__(self, messages):
        self.messages = list(messages)
        super().__init__("; ".join(self.messages))


def validate_features(feature_defs: list, features_dto: dict | None) -> None:
    """Validate a submitted custom-field DTO against the board's schema.

    No-op when the board declares no schema or stapel-attributes is absent
    (there is nothing to validate against). Raises
    :class:`FeatureValidationError` on invalid input.
    """
    if not feature_defs or not features_dto:
        return
    if not attributes_available():
        return
    from django.core.exceptions import ValidationError
    from stapel_attributes import validate_dto

    try:
        validate_dto(feature_defs, features_dto)
    except ValidationError as exc:
        messages = getattr(exc, "messages", None) or [str(exc)]
        raise FeatureValidationError(messages) from exc


def normalize_features(feature_defs: list, features_dto: dict | None) -> dict[str, Any]:
    """Turn a submitted DTO into the DAO stored on ``Task.features``.

    With stapel-attributes present and a schema declared, this is the real
    DTO->DAO pipeline (display metadata injected). Without it, the seam falls
    back to keeping the raw DTO (``STORE_UNKNOWN_FEATURES=True``, default) or
    dropping it — so cards still round-trip their custom fields on a host that
    has not installed the attributes engine.
    """
    if not feature_defs or not attributes_available():
        return _passthrough(features_dto)

    from stapel_attributes import normalize_to_dao

    return normalize_to_dao(feature_defs, features_dto or {})


def validate_feature_defs(feature_defs: list) -> None:
    """Validate a board's custom-field *schema* (used when a board's
    ``feature_defs`` is set/edited). No-op without stapel-attributes.

    Raises :class:`FeatureValidationError` if the schema is structurally
    invalid.
    """
    if not feature_defs or not attributes_available():
        return
    from stapel_attributes import validate_configs_structured

    result = validate_configs_structured(feature_defs)
    if not getattr(result, "valid", True):
        messages = [
            f"{r.slug}: {r.message or r.error}"
            for r in getattr(result, "results", [])
            if getattr(r, "status", None) == "validation_failed"
        ] or ["invalid feature schema"]
        raise FeatureValidationError(messages)


def _passthrough(features_dto: dict | None) -> dict[str, Any]:
    from .conf import tasks_settings

    if not features_dto:
        return {}
    if tasks_settings.STORE_UNKNOWN_FEATURES:
        return dict(features_dto)
    return {}
