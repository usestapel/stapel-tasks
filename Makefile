PYTHON ?= python3

# docs/capabilities.json is otherwise HAND-AUTHORED here (git log: "docs:
# author capabilities.json for the stapel-catalog sweep") — this module has no
# _capabilities.py / _codegen.py codegen pipeline, so provides/axes/
# extension_points/requires stay curated prose, never regenerated.
#
# What IS derived: the `surface` section — the symbols a product is meant to
# CALL (discoverability-design.md §1.2), plus module/version. AST-derived from
# the roots in docs/capabilities.meta.json; a selected export with no curated
# intent line fails `contract` naming the symbol. `--patch` touches only those
# two things and leaves the rest of the document verbatim.
#
# Then docs/llms.txt, the fifth contract artifact (stapel_tools.llms_txt),
# rendered straight from the docs/capabilities.json the step above produces.
#
# README.md is the SIXTH artifact (tracker #257): assembled by
# stapel_tools.readme from docs/readme.md (the human half — what this module
# is, how to think about it) plus everything emitted above. Badges, version,
# surface counts and doc links are generated, so a release cannot leave them
# behind. Edit docs/readme.md; never README.md.
.PHONY: contract contract-check migration-lint

contract:
	$(PYTHON) -m stapel_tools.surface . --patch
	$(PYTHON) -m stapel_tools.llms_txt .
	$(PYTHON) -m stapel_tools.readme .

contract-check:
	$(PYTHON) -m stapel_tools.surface . --patch --check
	$(PYTHON) -m stapel_tools.llms_txt . --check
	$(PYTHON) -m stapel_tools.readme . --check

# Expand/contract gate for Django migrations (release-management.md §3;
# stapel_tools.migration_lint). Requires stapel-tools importable (the
# workspace venv, or `pip install stapel-tools` once published).
migration-lint:
	$(PYTHON) -m stapel_tools.migration_lint . --strict
