# ---- builder ----
FROM python:3.13-slim AS builder

WORKDIR /app

RUN pip install uv --no-cache-dir

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app/ ./app/

# ---- runtime ----
FROM python:3.13-slim AS runtime

RUN useradd --system --no-create-home appuser

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app /app/app

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1
# コンテナ内では /app/db（named volume）に永続化する
ENV DB_PATH="/app/db/stocks_advisor.db"

RUN mkdir -p /app/db && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "app.servers.api:app", "--host", "0.0.0.0", "--port", "8000"]
