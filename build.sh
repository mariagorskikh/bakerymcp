#!/usr/bin/env bash
# Script to install dependencies with careful conflict resolution

echo "Starting dependency installation process"

# Ensure pip is updated
pip install --upgrade pip

# Create the default config file if it doesn't exist
mkdir -p $(pwd)
if [ ! -f $(pwd)/fastagent.config.yaml ]; then
  echo "Creating default fastagent.config.yaml file"
  cat > $(pwd)/fastagent.config.yaml << EOL
# FastAgent Configuration File
default_model: openai.o3-mini.high

# Logging and Console Configuration:
logger:
    level: "debug"
    type: "console"  
    progress_display: true
    show_chat: true
    show_tools: true
    truncate_tools: true

# MCP Servers with exact server names matching those used in the agent definition
mcp_servers:
    "fetch":
        server_type: "subprocess"
        command: "python3"
        args: ["-m", "mcp.server.fetch"]
        timeout: 30
    "filesystem":
        server_type: "subprocess"
        command: "python3" 
        args: ["-m", "mcp.server.filesystem", "$(pwd)"]
        timeout: 30
EOL
fi

# Create the bakery_hours.json file if it doesn't exist
if [ ! -f $(pwd)/bakery_hours.json ]; then
  echo "Creating default bakery_hours.json file"
  cat > $(pwd)/bakery_hours.json << EOL
{
  "monday": {
    "open": true,
    "hours": "7:00 AM - 6:00 PM"
  },
  "tuesday": {
    "open": true,
    "hours": "7:00 AM - 6:00 PM"
  },
  "wednesday": {
    "open": true,
    "hours": "7:00 AM - 6:00 PM"
  },
  "thursday": {
    "open": true,
    "hours": "7:00 AM - 6:00 PM"
  },
  "friday": {
    "open": true,
    "hours": "7:00 AM - 6:00 PM"
  },
  "saturday": {
    "open": true,
    "hours": "8:00 AM - 4:00 PM"
  },
  "sunday": {
    "open": false,
    "hours": "Closed"
  }
}
EOL
fi

# Clean any previous installations
pip uninstall -y fast-agent-mcp mcp

# Install core dependencies first with exact versions
echo "Installing core dependencies..."
pip install --no-cache-dir \
  typing-extensions==4.12.2 \
  fastapi==0.115.6 \
  uvicorn==0.23.2 \
  pydantic==2.10.4 \
  starlette==0.40.0 \
  httpx==0.27.0 \
  anyio==4.5.0 \
  sse-starlette==1.6.5 \
  requests==2.31.0 \
  python-dotenv==1.0.0 \
  PyYAML==6.0.2 \
  numpy==2.2.1

# Install MCP with specific version
echo "Installing MCP 1.6.0..."
pip install --no-cache-dir mcp==1.6.0

# Install fast-agent-mcp last to avoid dependency conflicts
echo "Installing fast-agent-mcp..."
pip install --no-cache-dir fast-agent-mcp==0.2.4

# List all installed packages for debugging
echo "Installed packages:"
pip list

echo "Configuration and dependency installation complete!" 