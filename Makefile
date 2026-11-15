.PHONY: setup test lint format migrate seed eval eval-gate redteam dashboard judge-calibrate agent-eval api rag-index rag-eval up down

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

eval: up
	uv run python -m parley.evals.suite $(ARGS)

eval-gate: up
	uv run python -m parley.evals.suite --profile gate --repeats 3 $(ARGS)

redteam: up
	uv run python -m parley.evals.suite --profile security --repeats 3 --ablation-repeats 1 $(ARGS)

dashboard:
	uv run python -m parley.observability.dashboard $(TRACES) $(ARGS)

judge-calibrate:
	uv run python -m parley.evals.calibration $(ARGS)

agent-eval: up
	uv run python -m parley.evals.agent_eval $(ARGS)

api:
	uv run uvicorn parley.backend.api:create_app --factory --reload

rag-index: up migrate
	uv run python -m parley.rag

rag-eval: up migrate
	uv run python -m parley.rag.ablation
	uv run python -m parley.rag
