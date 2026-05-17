.PHONY: help install format fmt format-check lint fix typecheck test cov frontmatter validate-schemas plugin-path-validate plugin-validate coverage-floor validate-health check clean ci plugin-refresh

# `make` with no target prints the help table.
.DEFAULT_GOAL := help

VENV   := .venv
PY     ?= $(VENV)/bin/python
PIP    := $(PY) -m pip
RUFF   ?= $(VENV)/bin/ruff
MYPY   ?= $(VENV)/bin/mypy
PYTEST ?= $(VENV)/bin/pytest
COVERAGE_XML ?= coverage.xml
COVERAGE_FLOOR ?= 85
FRONTMATTER_FILES := $(wildcard skills/*/SKILL.md commands/*.md)

# PyPI override — corp default index requires auth; use public PyPI.
PIP_INDEX := --index-url https://pypi.org/simple/

help: ## Show this help (auto-generated from doc-comment annotations)
	@awk 'BEGIN { FS = ":.*##"; printf "Usage: make <target>\n\nTargets:\n" } \
	      /^[a-zA-Z][a-zA-Z0-9_-]*:.*##/ { printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2 }' \
	      $(MAKEFILE_LIST)

install: ## Create venv (if missing) and install forge-tools with dev extras
	@test -d $(VENV) || python3.12 -m venv $(VENV) || python3 -m venv $(VENV)
	@$(PIP) install --upgrade pip $(PIP_INDEX)
	@$(PIP) install -e ".[dev]" $(PIP_INDEX)

format: ## Apply ruff formatter
	@$(RUFF) format tools tests hooks

fmt: format ## Alias for `format`

format-check: ## Verify formatting (no writes); fails if `make format` would change anything
	@$(RUFF) format --check tools tests hooks

lint: ## Run ruff lint (no fixes)
	@$(RUFF) check tools tests hooks

fix: ## Run ruff lint with --fix
	@$(RUFF) check --fix tools tests hooks

typecheck: ## Run mypy strict
	@$(MYPY) tools tests hooks

test: ## Run pytest
	@$(PYTEST) -v

cov: ## Run pytest with coverage
	@$(PYTEST) --cov=tools --cov=hooks --cov-report=term-missing

frontmatter: ## Lint skill and command frontmatter
	@if [ -z "$(FRONTMATTER_FILES)" ]; then \
		echo "No skills/commands found; failing."; \
		exit 1; \
	fi
	@$(PY) -m tools.lint_frontmatter --schema schemas/frontmatter.schema.json $(FRONTMATTER_FILES)

validate-schemas: ## Validate JSON schemas and templates
	@$(PY) -m tools.check_schemas

plugin-path-validate: ## Validate plugin manifest paths exist
	@test -f .claude-plugin/plugin.json
	@test -d skills
	@test -d commands
	@test -f hooks/hooks.json
	@test -f hooks/check_budget.py
	@test -f hooks/check_state_writer.py

plugin-validate: ## Run claude plugin validate when the CLI is available
	@if command -v claude >/dev/null 2>&1; then \
		claude plugin validate .; \
	else \
		echo "claude CLI not installed; relying on path-validate fallback"; \
	fi

coverage-floor: ## Enforce per-file coverage floor
	@$(PYTEST) --cov=tools --cov=hooks --cov-report=xml:$(COVERAGE_XML) -q
	@$(PY) -m tools.check_coverage_floor $(COVERAGE_XML) --absolute-floor $(COVERAGE_FLOOR)

validate-health: ## Run /forge:validate --target health on the current repo
	@$(PY) -m tools.validate --target health

check: format-check lint typecheck test validate-health ## Full local quality gate — run before every commit

ci: frontmatter validate-schemas plugin-path-validate plugin-validate check coverage-floor ## Full CI gate mirrored by GitHub Actions

clean: ## Remove caches (ruff, mypy, pytest, pyc, coverage)
	@rm -rf .ruff_cache .mypy_cache .pytest_cache htmlcov .coverage
	@find . -type d -name __pycache__ -prune -exec rm -rf {} +
	@find . -type d -name "*.egg-info" -prune -exec rm -rf {} +

plugin-refresh: ## Rebuild the local Claude Code plugin cache from this repo (no version bump needed)
	@claude plugin uninstall forge >/dev/null 2>&1 || true
	@claude plugin marketplace update forge-marketplace >/dev/null 2>&1 || true
	@claude plugin install forge@forge-marketplace
	@echo "Plugin cache rebuilt from current HEAD. Restart your Claude Code session to pick up the new code."
