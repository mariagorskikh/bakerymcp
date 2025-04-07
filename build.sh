#!/usr/bin/env bash
# This script helps resolve dependency conflicts

# Install pip-tools for dependency resolution
pip install pip-tools

# Create a requirements file that pip-tools can use to resolve dependencies
cat > requirements.in << EOF
fastapi>=0.95.0,<0.105.0
uvicorn>=0.15.0,<0.24.0
fast-agent-mcp==0.2.4
requests>=2.28.0,<2.32.0
python-dotenv>=0.19.0
typing-extensions>=4.0.0
pydantic>=1.8.0
EOF

# Use pip-compile to generate a locked requirements file
pip-compile requirements.in --output-file=requirements-lock.txt

# Install from the locked file
pip install -r requirements-lock.txt

# Echo the final requirements for debugging
echo "Final requirements installed:"
pip freeze 