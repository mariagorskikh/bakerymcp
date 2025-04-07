#!/usr/bin/env bash
# Script to install dependencies with careful conflict resolution for MCP

echo "Starting dependency installation process"

# Upgrade pip first
pip install --upgrade pip

# Install MCP first (specifically 1.6.0 as required by fast-agent-mcp)
echo "Installing base MCP dependencies..."
pip install --no-cache-dir mcp==1.6.0 typing-extensions==4.12.2

# Now install the rest of the dependencies
echo "Installing remaining dependencies..."
pip install --no-cache-dir \
    fastapi==0.115.6 \
    uvicorn==0.23.2 \
    pydantic==2.10.4 \
    starlette==0.40.0 \
    httpx==0.27.0 \
    anyio==4.5.0 \
    sse-starlette==1.6.5 \
    requests==2.31.0 \
    python-dotenv==1.0.0 \
    numpy==2.2.1 \
    PyYAML==6.0.2

# Install fast-agent-mcp last to avoid overriding specific package versions
echo "Installing fast-agent-mcp..."
pip install --no-cache-dir fast-agent-mcp==0.2.4

# Echo the final requirements for debugging
echo "Final requirements installed:"
pip freeze

echo "Build process completed" 