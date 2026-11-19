.PHONY: setup test lint format migrate seed eval eval-gate redteam dashboard judge-calibrate agent-eval api serve serve-sim demo stack stack-down console-install console-dev console-check rag-index rag-eval up down

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

serve: up migrate
	uv run python -m parley.service $(ARGS)

serve-sim: up migrate
	PARLEY_LLM_MODE=simulated PARLEY_SIMULATED_LATENCY_S=0.4 uv run python -m parley.service $(ARGS)

demo:
	uv run python -m parley.service.demo $(ARGS)

stack:
	docker compose --profile app up --build -d --wait

stack-down:
	docker compose --profile app down

console-install:
	cd console && npm ci

console-dev:
	cd console && npm run dev

console-check:
	cd console && npm run lint && npm run typecheck && npm test && npm run build

rag-index: up migrate
	uv run python -m parley.rag

rag-eval: up migrate
	uv run python -m parley.rag.ablation
	uv run python -m parley.rag
