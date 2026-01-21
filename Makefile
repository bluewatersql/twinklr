.PHONY: help install install-dev sync clean lint format type-check test test-cov test-watch run-demo build verify-install check-all pre-commit validate

# Default target
.DEFAULT_GOAL := help

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

#############################################################################
# Help
#############################################################################

help: ## Show this help message
	@echo "$(BLUE)BlinkB0t - AI-powered lighting sequencer$(NC)"
	@echo ""
	@echo "$(GREEN)Available targets:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)Quick start:$(NC)"
	@echo "  make install        # First time setup"
	@echo "  make check-all      # Run all quality checks"
	@echo "  make run-demo       # Run demo pipeline"

#############################################################################
# Installation & Setup
#############################################################################

install: ## Install project for development (first time setup)
	@echo "$(GREEN)Installing BlinkB0t for development...$(NC)"
	@command -v uv >/dev/null 2>&1 || { echo "$(RED)Error: uv is not installed. Install from https://github.com/astral-sh/uv$(NC)"; exit 1; }
	@echo "$(BLUE)→ Syncing workspace and installing all packages with dependencies...$(NC)"
	uv sync --extra dev --all-packages
	@echo "$(BLUE)→ Verifying installation...$(NC)"
	@$(MAKE) verify-install
	@echo "$(GREEN)✓ Installation complete!$(NC)"

install-dev: install ## Alias for install (for muscle memory)

sync: ## Sync dependencies (update after pyproject.toml changes)
	@echo "$(BLUE)→ Syncing all dependencies (including dev)...$(NC)"
	uv sync --extra dev --all-packages
	@echo "$(GREEN)✓ Dependencies synced$(NC)"

#############################################################################
# Development
#############################################################################

lint: ## Run linter (ruff check)
	@echo "$(BLUE)→ Running ruff check...$(NC)"
	uv run ruff check .
	@echo "$(GREEN)✓ Linting complete$(NC)"

lint-fix: ## Run linter with auto-fix
	@echo "$(BLUE)→ Running ruff check with auto-fix...$(NC)"
	uv run ruff check . --fix
	@echo "$(GREEN)✓ Linting complete$(NC)"

lint-fix-unsafe: ## Run linter with unsafe fixes (preview only - shows diff)
	@echo "$(YELLOW)→ Previewing unsafe fixes (no changes applied)...$(NC)"
	@echo "$(YELLOW)→ Use 'make lint-fix-unsafe-apply' to actually apply changes$(NC)"
	@uv run ruff check . --fix --unsafe-fixes --diff

lint-fix-unsafe-apply: ## Apply unsafe fixes with git checkpoint (undo with: git restore .)
	@echo "$(YELLOW)→ Creating git checkpoint...$(NC)"
	@git diff --quiet && git diff --cached --quiet || { \
		echo "$(RED)Error: You have uncommitted changes. Commit or stash first.$(NC)"; \
		exit 1; \
	}
	@echo "$(BLUE)→ Applying unsafe fixes...$(NC)"
	@uv run ruff check . --fix --unsafe-fixes
	@echo "$(GREEN)✓ Unsafe fixes applied$(NC)"
	@echo "$(YELLOW)→ To undo: git restore .$(NC)"

format: ## Format code with ruff
	@echo "$(BLUE)→ Formatting code...$(NC)"
	uv run ruff format .
	@echo "$(GREEN)✓ Code formatted$(NC)"

type-check: ## Run type checker (mypy)
	@echo "$(BLUE)→ Running mypy...$(NC)"
	uv run mypy .
	@echo "$(GREEN)✓ Type checking complete$(NC)"

#############################################################################
# Testing
#############################################################################

test: ## Run all tests
	@echo "$(BLUE)→ Running tests...$(NC)"
	uv run pytest tests/ -v
	@echo "$(GREEN)✓ Tests complete$(NC)"

test-cov: ## Run tests with coverage report
	@echo "$(BLUE)→ Running tests with coverage...$(NC)"
	uv run pytest tests/ --cov=blinkb0t.core --cov-report=term-missing --cov-report=html
	@echo "$(GREEN)✓ Tests complete$(NC)"
	@echo "$(YELLOW)→ Coverage report: htmlcov/index.html$(NC)"

test-watch: ## Run tests in watch mode (requires pytest-watch)
	@echo "$(BLUE)→ Running tests in watch mode...$(NC)"
	@command -v ptw >/dev/null 2>&1 || { echo "$(YELLOW)Installing pytest-watch...$(NC)"; uv pip install pytest-watch; }
	uv run ptw tests/ -- -v

test-unit: ## Run unit tests only
	@echo "$(BLUE)→ Running unit tests...$(NC)"
	uv run pytest tests/test_value_curves.py tests/test_phase1_integration.py -v

test-integration: ## Run integration tests only
	@echo "$(BLUE)→ Running integration tests...$(NC)"
	uv run pytest tests/test_e2e_value_curves.py tests/test_phase4_sequencer.py -v

#############################################################################
# Quality Checks (Run all before committing)
#############################################################################

check-all: lint format type-check test-cov ## Run all quality checks (recommended before commit)
	@echo ""
	@echo "$(GREEN)========================================$(NC)"
	@echo "$(GREEN)✓ All quality checks passed!$(NC)"
	@echo "$(GREEN)========================================$(NC)"

pre-commit: check-all ## Alias for check-all

validate: ## Run format, lint-fix, type-check, and test (shows all errors/warnings)
	@echo "$(BLUE)========================================$(NC)"
	@echo "$(BLUE)Running all validation checks...$(NC)"
	@echo "$(BLUE)========================================$(NC)"
	@echo ""
	@EXIT_CODE=0; \
	echo "$(YELLOW)[1/4] Formatting code...$(NC)"; \
	uv run ruff format . || EXIT_CODE=$$?; \
	echo ""; \
	echo "$(YELLOW)[2/4] Running linter with auto-fix...$(NC)"; \
	uv run ruff check . --fix || EXIT_CODE=$$?; \
	echo ""; \
	echo "$(YELLOW)[3/4] Running type checker...$(NC)"; \
	uv run mypy . || EXIT_CODE=$$?; \
	echo ""; \
	echo "$(YELLOW)[4/4] Running tests...$(NC)"; \
	uv run pytest tests/ -v || EXIT_CODE=$$?; \
	echo ""; \
	if [ $$EXIT_CODE -ne 0 ]; then \
		echo "$(RED)========================================$(NC)"; \
		echo "$(RED)✗ Validation failed (see errors above)$(NC)"; \
		echo "$(RED)========================================$(NC)"; \
		exit $$EXIT_CODE; \
	else \
		echo "$(GREEN)========================================$(NC)"; \
		echo "$(GREEN)✓ All validation checks passed!$(NC)"; \
		echo "$(GREEN)========================================$(NC)"; \
	fi

#############################################################################
# Running
#############################################################################

run-demo: ## Run demo pipeline (requires audio/xsq files in data/)
	@echo "$(BLUE)→ Running demo pipeline...$(NC)"
	@if [ ! -f "data/11 - Need A Favor.mp3" ]; then \
		echo "$(RED)Error: Demo audio file not found$(NC)"; \
		echo "Place audio file at: data/11 - Need A Favor.mp3"; \
		exit 1; \
	fi
	@if [ ! -f "data/Need A Favor.xsq" ]; then \
		echo "$(RED)Error: Demo sequence file not found$(NC)"; \
		echo "Place sequence file at: data/Need A Favor.xsq"; \
		exit 1; \
	fi
	@if [ ! -f ".env" ] || ! grep -q "OPENAI_API_KEY" .env; then \
		echo "$(YELLOW)Warning: OPENAI_API_KEY not set in .env$(NC)"; \
		echo "Create .env file with: OPENAI_API_KEY=your_key_here"; \
		exit 1; \
	fi
	uv run blinkb0t run \
		--audio "data/11 - Need A Favor.mp3" \
		--xsq "data/Need A Favor.xsq" \
		--config job_config.json \
		--out demo_output
	@echo "$(GREEN)✓ Demo complete! Check demo_output/ for results$(NC)"

#############################################################################
# Building
#############################################################################

build: ## Build distribution packages
	@echo "$(BLUE)→ Building packages...$(NC)"
	@cd packages/core && uv build
	@cd packages/cli && uv build
	@echo "$(GREEN)✓ Packages built$(NC)"
	@echo "$(YELLOW)→ Core package: packages/core/dist/$(NC)"
	@echo "$(YELLOW)→ CLI package: packages/cli/dist/$(NC)"

#############################################################################
# Cleanup
#############################################################################

clean: ## Clean build artifacts and caches
	@echo "$(BLUE)→ Cleaning build artifacts...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "build" -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

clean-cache: ## Clean audio cache
	@echo "$(BLUE)→ Cleaning audio cache...$(NC)"
	rm -rf data/audio_cache/*
	@echo "$(GREEN)✓ Cache cleaned$(NC)"

clean-all: clean clean-cache ## Clean everything including caches
	@echo "$(GREEN)✓ Full cleanup complete$(NC)"

clean-venv: ## Remove virtual environment (for complete rebuild)
	@echo "$(YELLOW)⚠ Removing virtual environment...$(NC)"
	rm -rf .venv
	@echo "$(GREEN)✓ Virtual environment removed$(NC)"

clean-install: clean-venv install ## Complete clean reinstall (removes .venv and reinstalls everything)
	@echo "$(GREEN)✓ Clean installation complete!$(NC)"

#############################################################################
# Installation Verification
#############################################################################

verify-install: ## Verify installation is working correctly
	@echo "$(BLUE)→ Verifying blinkb0t installation...$(NC)"
	@echo "$(YELLOW)  Checking packages installed...$(NC)"
	@uv pip list | grep blinkb0t || { echo "$(RED)✗ BlinkB0t packages not found$(NC)"; exit 1; }
	@echo "$(YELLOW)  Testing core import...$(NC)"
	@uv run python -c "import blinkb0t.core" || { echo "$(RED)✗ Cannot import blinkb0t.core$(NC)"; exit 1; }
	@echo "$(YELLOW)  Testing CLI...$(NC)"
	@uv run blinkb0t --help >/dev/null || { echo "$(RED)✗ CLI not working$(NC)"; exit 1; }
	@echo "$(GREEN)✓ Installation verified$(NC)"

#############################################################################
# Documentation
#############################################################################

docs: ## Open documentation in browser
	@echo "$(BLUE)→ Opening documentation...$(NC)"
	@command -v open >/dev/null 2>&1 && open README.md || echo "README.md"

quickstart: ## Show developer quick start guide
	@cat QUICKSTART_DEV.md

#############################################################################
# Development Utilities
#############################################################################

shell: ## Open Python shell with project imports
	@echo "$(BLUE)→ Opening Python shell...$(NC)"
	uv run python

repl: shell ## Alias for shell

info: ## Show project information
	@echo "$(BLUE)BlinkB0t Project Information$(NC)"
	@echo ""
	@echo "$(YELLOW)Packages:$(NC)"
	@echo "  Core:    blinkb0t-core (packages/core/)"
	@echo "  CLI:     blinkb0t-cli (packages/cli/)"
	@echo ""
	@echo "$(YELLOW)Python Version:$(NC)"
	@uv run python --version
	@echo ""
	@echo "$(YELLOW)Installed Packages:$(NC)"
	@uv pip list | grep blinkb0t || echo "  (not installed yet - run 'make install')"
	@echo ""
	@echo "$(YELLOW)Test Coverage Target:$(NC) 80%"
	@echo "$(YELLOW)Line Length:$(NC) 100 characters"
	@echo "$(YELLOW)Type Checker:$(NC) MyPy"
	@echo "$(YELLOW)Linter:$(NC) Ruff"

env-check: ## Check environment setup
	@echo "$(BLUE)Checking environment...$(NC)"
	@echo ""
	@echo "$(YELLOW)UV:$(NC)"
	@command -v uv >/dev/null 2>&1 && echo "  ✓ uv installed ($(shell uv --version))" || echo "  $(RED)✗ uv not installed$(NC)"
	@echo ""
	@echo "$(YELLOW)Python:$(NC)"
	@uv run python --version 2>/dev/null && echo "  ✓ Python available" || echo "  $(RED)✗ Python not available$(NC)"
	@echo ""
	@echo "$(YELLOW)Environment File:$(NC)"
	@if [ -f ".env" ]; then \
		echo "  ✓ .env exists"; \
		if grep -q "OPENAI_API_KEY" .env; then \
			echo "  ✓ OPENAI_API_KEY is set"; \
		else \
			echo "  $(YELLOW)⚠ OPENAI_API_KEY not found in .env$(NC)"; \
		fi \
	else \
		echo "  $(YELLOW)⚠ .env not found (copy from .env.example)$(NC)"; \
	fi
	@echo ""
	@echo "$(YELLOW)Data Files:$(NC)"
	@[ -d "data" ] && echo "  ✓ data/ directory exists" || echo "  $(YELLOW)⚠ data/ directory not found$(NC)"
	@[ -f "data/11 - Need A Favor.mp3" ] && echo "  ✓ Demo audio file exists" || echo "  $(YELLOW)⚠ Demo audio file not found$(NC)"
	@[ -f "data/Need A Favor.xsq" ] && echo "  ✓ Demo sequence file exists" || echo "  $(YELLOW)⚠ Demo sequence file not found$(NC)"

#############################################################################
# Git Helpers
#############################################################################

git-status: ## Show git status with colored output
	@git status

git-clean: ## Remove untracked files (interactive)
	@git clean -i

#############################################################################
# Advanced
#############################################################################

update-deps: ## Update all dependencies to latest versions
	@echo "$(BLUE)→ Updating dependencies (including dev)...$(NC)"
	uv sync --upgrade --extra dev
	@echo "$(GREEN)✓ Dependencies updated$(NC)"

lock: ## Update lock file without installing
	@echo "$(BLUE)→ Updating lock file...$(NC)"
	uv lock
	@echo "$(GREEN)✓ Lock file updated$(NC)"

