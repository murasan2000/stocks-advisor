# ---- dev ----
# docker compose（ローカル開発）用。dev 依存込みで入れ、ソースはバインドマウントして
# uvicorn --reload でホットリロードする。.venv はマウント領域の外（/opt/venv）に置き、
# ホスト側 api/.venv（macOS 用バイナリ）の有無に影響されないようにする。
FROM python:3.13-slim AS dev

WORKDIR /app

RUN pip install uv --no-cache-dir

ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --group dev --no-install-project

EXPOSE 8000

CMD ["uvicorn", "app.servers.api:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "app"]

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
ENV DB_PATH="/app/db/stock_advisor.db"

RUN mkdir -p /app/db && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "app.servers.api:app", "--host", "0.0.0.0", "--port", "8000"]
