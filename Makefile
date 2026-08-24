# stapel-tasks — contract emission + drift gate (contract-pipeline.md §2-3).
#
# This module emits its OWN contract triad (schema.json + flows.json +
# errors.json) from a single-module {tasks + core} Django instance mounted at
# the canonical /tasks/api/v1/ prefix (see _codegen.py / _codegen_settings.py /
# codegen_urls.py). PYTHON must have the module + its deps importable (the
# workspace venv, or a CI venv) and be a 3.12 interpreter (emission pin).
#
# docs/capabilities.json is otherwise HAND-AUTHORED here (git log: "docs:
# author capabilities.json for the stapel-catalog sweep") — this module has no
# _capabilities.py emitter, so provides/axes/extension_points/requires stay
# curated prose, never regenerated.
#
# What IS derived: the `surface` section — the symbols a product is meant to
# CALL (discoverability-design.md §1.2), plus module/version. AST-derived from
# the roots in docs/capabilities.meta.json; a selected export with no curated
# intent line fails `contract` naming the symbol. `--patch` touches only those
# two things and leaves the rest of the document verbatim.
#
# Then docs/llms.txt, the fifth contract artifact (stapel_tools.llms_txt),
# rendered from the freshly emitted triad PLUS the patched capabilities.json.
# The budget is raised to 7000 tokens DELIBERATELY (the stapel-moderation
# precedent): the triad added the errors/operations/flows sections on top of a
# 28-entry surface, and a silently cut context file reads exactly like a
# complete one.
#
# README.md is the SIXTH artifact (tracker #257): assembled by
# stapel_tools.readme from docs/readme.md (the human half — what this module
# is, how to think about it) plus everything emitted above. Badges, version,
# surface counts and doc links are generated, so a release cannot leave them
# behind. Edit docs/readme.md; never README.md.
PYTHON ?= python3

.PHONY: contract contract-check migration-lint

contract:
	$(PYTHON) -m stapel_tasks._codegen --out docs
	$(PYTHON) -m stapel_tools.surface . --patch
	$(PYTHON) -m stapel_tools.llms_txt . --budget 7000
	$(PYTHON) -m stapel_tools.readme .

# Drift gate. `stapel_tools.surface . --patch --check` runs against the real
# repo (it AST-scans the actual source files named by surface_roots, so it
# cannot run against a docs/-only temp dir) and compares the freshly patched
# capabilities.json to the committed one in memory, byte for byte. The triad
# (schema/flows/errors) regenerates into a temp dir and is diffed there;
# llms.txt and README.md keep their own --check.
contract-check:
	@$(PYTHON) -m stapel_tools.surface . --patch --check || exit 1; \
	tmp=$$(mktemp -d); \
	mkdir -p "$$tmp/docs"; \
	$(PYTHON) -m stapel_tasks._codegen --out "$$tmp/docs" || { rm -rf "$$tmp"; exit 1; }; \
	rc=0; \
	for f in schema.json flows.json errors.json; do \
		if ! cmp -s "docs/$$f" "$$tmp/docs/$$f"; then \
			echo "DRIFT: docs/$$f is stale — run 'make contract' and commit it"; \
			diff "docs/$$f" "$$tmp/docs/$$f" | head -20; rc=1; \
		fi; \
	done; \
	rm -rf "$$tmp"; \
	$(PYTHON) -m stapel_tools.llms_txt . --budget 7000 --check || rc=1; \
	$(PYTHON) -m stapel_tools.readme . --check || rc=1; \
	if [ $$rc -eq 0 ]; then echo "contract-check: docs/{capabilities,schema,flows,errors,llms.txt} + README.md up to date"; fi; \
	exit $$rc

# Expand/contract gate for Django migrations (release-management.md §3;
# stapel_tools.migration_lint). Requires stapel-tools importable (the
# workspace venv, or `pip install stapel-tools` once published).
migration-lint:
	$(PYTHON) -m stapel_tools.migration_lint . --strict
