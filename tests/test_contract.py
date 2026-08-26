"""Contract drift gates — the triad, llms.txt and README.md.

Since 0.3.0 this module emits its OWN contract triad (``_codegen.py`` /
``make contract``): ``docs/schema.json`` + ``docs/flows.json`` +
``docs/errors.json``, from a single-module {tasks + core} Django instance
mounted at the canonical ``/tasks/api/v1/`` prefix. ``@stapel/tasks-react``'s
``gen:api`` / ``gen:flows`` / ``gen:errors`` read exactly these files, so a
view whose serializer changed and whose docs did not is a red test here, not
a surprise in the frontend's generated types.

``docs/capabilities.json`` stays HAND-AUTHORED apart from ``module``/
``version``/``surface`` (there is no ``_capabilities.py`` emitter) — that
half is gated in ``test_capabilities_surface.py``.

``docs/llms.txt`` is rendered from the triad plus that capabilities.json;
README.md is assembled from ``docs/readme.md`` plus everything above.

Regenerate after any change to a view, serializer, flow or error key:

    make contract
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"

# The Makefile raises the llms.txt ceiling deliberately; the gate has to run
# the SAME budget it does, or it measures a different artifact.
LLMS_BUDGET = "7000"

TRIAD = ("schema.json", "flows.json", "errors.json")


def _emit(out_dir: Path) -> None:
    subprocess.run(
        [sys.executable, "-m", "stapel_tools.llms_txt", str(REPO),
         "--out", str(out_dir), "--budget", LLMS_BUDGET],
        check=True,
        capture_output=True,
    )


def _emit_triad(out_dir: Path) -> None:
    """Run the module's own contract harness into ``out_dir``."""
    subprocess.run(
        [sys.executable, "-m", "stapel_tasks._codegen", "--out", str(out_dir)],
        check=True,
        capture_output=True,
        cwd=str(REPO),
    )


@pytest.mark.parametrize("name", TRIAD)
def test_triad_artifact_is_committed(name):
    assert (DOCS / name).is_file(), f"missing docs/{name} — run `make contract`"


@pytest.mark.skipif(
    sys.version_info[:2] != (3, 12),
    reason="the triad is emitted on the pinned 3.12 interpreter only "
    "(_codegen aborts elsewhere); the drift gate runs on the 3.12 leg",
)
@pytest.mark.parametrize("name", TRIAD)
def test_triad_has_no_drift(tmp_path, name):
    """Regenerate the triad; each committed file must match byte-for-byte.

    Emission is pinned to 3.12 (``_codegen._require_pinned_interpreter``), so
    on the matrix's other legs this test could only ever assert that the pin
    still refuses to run — which it does, by exiting non-zero. It skips there.
    """
    _emit_triad(tmp_path)
    assert (DOCS / name).read_bytes() == (tmp_path / name).read_bytes(), (
        f"docs/{name} drifted — run `make contract` and commit it"
    )


def test_schema_carries_the_board_shaped_read():
    """The pair binds `GET boards/{id}/cards`; the schema must describe it.

    A schema that merely *has* the path is not enough — drf-spectacular
    silently falls back to an untyped body when an APIView carries no
    `responses=`, which is exactly how a generated client ends up with
    `unknown` where the board should be.
    """
    schema = json.loads((DOCS / "schema.json").read_text())
    op = schema["paths"]["/tasks/api/v1/boards/{board_id}/cards"]["get"]
    ref = op["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("/BoardCardsResponse")
    cards = schema["components"]["schemas"]["BoardCardsResponse"]
    assert set(cards["properties"]) >= {"board_id", "columns", "cards", "truncated"}


def test_errors_registry_carries_the_column_conflict_key():
    codes = {e["code"] for e in json.loads((DOCS / "errors.json").read_text())}
    assert "error.409.tasks_column_exists" in codes


@pytest.mark.parametrize("lang", ["ru", "es"])
def test_locale_catalog_covers_every_owned_key(lang):
    """gen:errors demands a catalog entry for every key this module OWNS.

    A missing one is a raw i18n key rendered at a user, so the gate lives
    here rather than in the frontend's generator.
    """
    from stapel_tasks.errors import STAPEL_TASKS_ERRORS

    catalog = json.loads((REPO / "translations" / f"errors.{lang}.json").read_text())
    missing = sorted(set(STAPEL_TASKS_ERRORS) - set(catalog))
    assert not missing, f"translations/errors.{lang}.json is missing: {missing}"
    extra = sorted(set(catalog) - set(STAPEL_TASKS_ERRORS))
    assert not extra, f"translations/errors.{lang}.json carries foreign keys: {extra}"


def test_llms_txt_committed():
    assert (DOCS / "llms.txt").is_file(), "missing docs/llms.txt — run `make contract`"


def test_llms_txt_has_no_drift(tmp_path):
    """Regenerate into a temp dir; the committed file must match byte-for-byte."""
    _emit(tmp_path)
    committed = (DOCS / "llms.txt").read_bytes()
    regenerated = (tmp_path / "llms.txt").read_bytes()
    assert committed == regenerated, (
        "docs/llms.txt drifted — run `make contract` and commit docs/llms.txt"
    )


def test_llms_txt_emission_is_deterministic(tmp_path):
    """Two independent emissions are byte-identical (the drift gate above is
    only meaningful if this holds)."""
    a, b = tmp_path / "a", tmp_path / "b"
    _emit(a)
    _emit(b)
    assert (a / "llms.txt").read_bytes() == (b / "llms.txt").read_bytes()


# --- README.md — the sixth artifact (tracker #257) ---------------------------
#
# README.md is assembled by ``stapel_tools.readme`` from docs/readme.md (the
# human half: what this module is and how to think about it) plus the contract
# documents above (badges, version, surface counts, doc links). Everything a
# hand-written README used to restate — and therefore used to get wrong one
# release later — is generated here and gated below.

def test_readme_is_assembled_and_has_no_drift():
    from stapel_tools.readme import load_inputs, render, static_languages

    inputs = load_inputs(REPO)
    languages = static_languages(REPO)
    assert languages == ["en"], "expected exactly the English static body docs/readme.md"
    committed = (REPO / "README.md").read_text()
    assert committed == render(REPO, inputs, "en", languages), (
        "README.md drifted — run `make contract` and commit README.md "
        "(edit prose in docs/readme.md, never README.md itself)"
    )


def test_readme_version_matches_the_package():
    """The #226 gate, at the point where the number is published."""
    import tomllib

    from stapel_tools.readme import load_inputs, resolve_version

    pyproject = tomllib.loads((REPO / "pyproject.toml").read_text())
    assert resolve_version(load_inputs(REPO)) == pyproject["project"]["version"]
