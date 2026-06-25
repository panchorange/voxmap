.PHONY: setup
setup:
	uv add --dev ruff mypy pre-commit
	uv run pre-commit install

.PHONY: lint
lint:
	uv run ruff check .

.PHONY: format
format:
	uv run ruff format .

.PHONY: typecheck
typecheck:
	uv run mypy .

.PHONY: check
check: lint typecheck

.PHONY: test
test:
	uv run pytest

.PHONY: precommit-install
precommit-install:
	uv run pre-commit install

.PHONY: precommit-run
precommit-run:
	uv run pre-commit run --all-files

.PHONY: sync-check
sync-check:
	uv run python scripts/sync_check.py

# --- voxmap-studio (apps/studio) ---
# ADR 2026-06-02: フロントの品質ゲートはエンジン (make check) と分離する。
STUDIO_FE := apps/studio/frontend

.PHONY: studio-fe-setup
studio-fe-setup:
	cd $(STUDIO_FE) && bun install
	bun add --dev lefthook
	bunx lefthook install

.PHONY: studio-fe-check
studio-fe-check:
	cd $(STUDIO_FE) && bun run lint && bun run typecheck

.PHONY: studio-fe-fix
studio-fe-fix:
	cd $(STUDIO_FE) && bun run fix

.PHONY: studio-fe-dev
studio-fe-dev:
	cd $(STUDIO_FE) && bun run dev

# backend (FastAPI + voxmap)。engine の make check とは分離。
STUDIO_BE := apps/studio/backend

.PHONY: studio-be-check
studio-be-check:
	cd $(STUDIO_BE) && uv run ruff check app && uv run mypy app

.PHONY: studio-be-test
studio-be-test:
	cd $(STUDIO_BE) && uv run pytest

.PHONY: studio-be-dev
studio-be-dev:
	cd $(STUDIO_BE) && uv run uvicorn app.main:app --reload --port 8000
