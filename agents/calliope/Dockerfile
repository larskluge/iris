# Hermetic Calliope agent image (§7.6): only the pinned package + deps, no host
# config. The dispatcher launches one ephemeral container per async task.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev
ENTRYPOINT ["/app/.venv/bin/calliope"]
