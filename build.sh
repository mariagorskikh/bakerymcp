#!/usr/bin/env bash
# This script helps resolve dependency conflicts

# Install pip directly (avoid pip-tools)
pip install --no-cache-dir \
    fastapi==0.115.6 \
    uvicorn==0.23.2 \
    fast-agent-mcp==0.2.4 \
    requests==2.31.0 \
    python-dotenv==1.0.0 \
    mcp==1.6.0 \
    pydantic==2.10.4 \
    typing-extensions==4.12.2 \
    starlette==0.40.0 \
    httpx==0.27.0 \
    anyio==4.5.0 \
    sse-starlette==1.6.5 \
    numpy==2.2.1 \
    PyYAML==6.0.2 \
    mcp-server-fetch==0.1.0 \
    mcp-server-filesystem==0.1.0

# Echo the final requirements for debugging
echo "Final requirements installed:"
pip freeze 