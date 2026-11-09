.PHONY: setup test lint format seed eval up down

setup:
	uv sync
	uv run pre-commit install
	@test -f .env || cp .env.example .env

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

up:
	docker compose up -d --wait

down:
	docker compose down

seed:
	@echo "seed: not implemented yet (Phase 1)"

eval:
	@echo "eval: not implemented yet (Phase 5)"
