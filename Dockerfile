# Remote MCP server (Streamable HTTP on :8000/mcp). Dependencies come from
# uv.lock, so every build of a given commit installs the same versions.
FROM docker.io/library/python:3.14-slim-trixie

COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    SYSTEMBOLAGET_MCP_TRANSPORT=streamable-http \
    SYSTEMBOLAGET_MCP_HOST=0.0.0.0 \
    SYSTEMBOLAGET_MCP_PORT=8000

WORKDIR /src
COPY pyproject.toml uv.lock README.md LICENSE systembolaget_mcp.py ./
RUN uv sync --frozen --no-dev --no-editable && rm -rf /root/.cache

USER 65532:65532
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD ["systembolaget-mcp", "--healthcheck"]
CMD ["systembolaget-mcp"]
