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
    pydantic==1.10.13 \
    typing-extensions==4.9.0 \
    starlette==0.40.0 \
    httpx==0.24.1 \
    anyio==3.7.1 \
    sse-starlette==1.6.5 \
    numpy==1.24.4 \
    PyYAML==6.0.1

# Echo the final requirements for debugging
echo "Final requirements installed:"
pip freeze 