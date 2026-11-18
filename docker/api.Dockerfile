FROM python:3.12-slim AS api

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH"
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY docs/PROJECT.md docs/PROJECT.md
RUN uv sync --locked --no-install-project --no-dev

COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
COPY data ./data
COPY docker/api-entrypoint.sh /usr/local/bin/api-entrypoint
RUN uv sync --locked --no-dev && chmod +x /usr/local/bin/api-entrypoint \
    && useradd --create-home app && mkdir -p /app/.cache && chown -R app /app/.cache
USER app

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=10 \
    CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/health')"
ENTRYPOINT ["api-entrypoint"]
CMD ["python", "-m", "parley.service", "--host", "0.0.0.0", "--port", "8000"]
