.PHONY: setup test lint format migrate seed eval api rag-index rag-eval up down

setup:
	uv sync
	uv run pre-commit install
	@test -f .env || cp .env.example .env

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy

format:
	uv run ruff check --fix .
	uv run ruff format .

up:
	docker compose up -d --wait

down:
	docker compose down

migrate:
	uv run alembic upgrade head

seed: up migrate
	uv run python -m parley.seed

eval:
	@echo "eval: not implemented yet (Phase 5)"

api:
	uv run uvicorn parley.backend.api:create_app --factory --reload

rag-index: up migrate
	uv run python -m parley.rag

rag-eval: up migrate
	uv run python -m parley.rag.ablation
	uv run python -m parley.rag
