import asyncio
import os
from fastapi import FastAPI, Body, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from mcp_agent.core.fastagent import FastAgent
from contextlib import asynccontextmanager
from typing import Dict, Any
import uvicorn
import sys
import json

# Create FastAgent with explicit config path
fast = FastAgent("Bakery Agent", config_path="fastagent.config.yaml")

# Global variable to track agent initialization status
agent_initialized = False

# Define the lifespan context manager for FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting application lifespan...")
    print("Initializing MCP servers...")
    
    # Check if bakery_hours.json exists
    try:
        with open("bakery_hours.json", "r") as f:
            print(f"Found bakery_hours.json: {f.read()[:100]}...")
    except Exception as e:
        print(f"Warning: Could not read bakery_hours.json: {str(e)}")

    # Validate configuration for debugging
    try:
        # Print the full config for debugging
        print(f"FastAgent configuration at path: fastagent.config.yaml")
        with open("fastagent.config.yaml", "r") as f:
            print(f"Configuration content: {f.read()}")
            
        # Print Python path and environment for debugging
        print(f"Python path: {sys.path}")
        print(f"Current directory: {os.getcwd()}")
        print(f"Listing current directory:")
        for item in os.listdir('.'):
            print(f"  - {item}")
    except Exception as e:
        print(f"Warning during config validation: {str(e)}")
    
    # Test initialization by running the agent once
    try:
        # Store the agent manager in the app state
        app.state.agent_manager = fast
        
        # Verify that MCP servers work by running a minimal test
        async with fast.run() as agent:
            if hasattr(agent, "bakery"):
                print("✅ Agent initialization test successful")
                print(f"✅ Found 'bakery' agent")
            else:
                print("⚠️ Agent initialized but bakery agent is not defined")
            
            # Mark initialization as successful
            app.state.agent_initialized = True
            
            # Log available MCP servers
            if hasattr(fast, "context") and hasattr(fast.context, "mcp_servers"):
                print(f"✅ MCP servers configured: {list(fast.context.mcp_servers.keys())}")
                
        print("✅ MCP servers initialized and ready")
    except Exception as e:
        print(f"❌ Error during MCP initialization test: {str(e)}")
        import traceback
        traceback.print_exc()
        app.state.agent_initialized = False
    
    # Yield control to FastAPI
    yield
    
    # Cleanup on shutdown
    print("Shutting down application...")

# Create FastAPI application with lifespan
app = FastAPI(
    title="Bakery API", 
    description="Bakery availability checker with MCP servers",
    lifespan=lifespan
)

# Define request model for JSON input
class BakeryQuery(BaseModel):
    query: str

# Define bakery agent
@fast.agent(
    name="bakery",
    instruction="""You are a helpful bakery assistant that checks if items are available.
    
    When a customer asks about ordering an item on a specific day, you need to:
    1. Check if the bakery is open on that day using the filesystem tool to read bakery_hours.json
    2. Check if the requested item is on the menu using the fetch tool to access https://www.flourbakery.com/menu
    
    Only say YES if both conditions are met:
    - The bakery is open on the requested day
    - The requested item is on the menu
    
    Otherwise say NO and explain why (either bakery closed or item not available).
    Be concise in your responses.""",
    servers=["fetch", "filesystem"],  # Using both fetch and filesystem MCP tools
    model="openai.o3-mini.high"  # Explicitly use OpenAI model
)
async def bakery_agent():
    pass  # Agent is defined by decorator

# Define API endpoints
@app.get("/")
async def root():
    """Root endpoint that returns basic API info"""
    return {
        "message": "Bakery API is running with MCP support. Use /check endpoint to check item availability.",
        "status": "online",
        "version": "1.0.0"
    }

@app.post("/check")
async def check_availability_post(query_data: BakeryQuery):
    """Check if an item is available at the bakery on a specific day (POST method)"""
    try:
        query = query_data.query
        print(f"Processing POST request with query: {query}")
        
        # Access the pre-initialized FastAgent from app state
        if not hasattr(app.state, "agent_manager"):
            raise Exception("Agent manager not found in application state")
            
        agent_manager = app.state.agent_manager
        
        # Use a timeout to prevent hanging
        async with asyncio.timeout(30):
            async with agent_manager.run() as agent:
                print("Agent running for POST request")
                response = await agent.bakery(query)
                return {"response": response, "source": "mcp_agent"}
    except Exception as e:
        print(f"Error in POST method: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to process request: {str(e)}")

@app.get("/check")
async def check_availability_get(item: str):
    """Check if an item is available at the bakery (GET method)"""
    try:
        query = f"Can I order a {item}?"
        print(f"Processing GET request for item: {item}")
        
        # Access the pre-initialized FastAgent from app state
        if not hasattr(app.state, "agent_manager"):
            raise Exception("Agent manager not found in application state")
            
        agent_manager = app.state.agent_manager
        
        # Use a timeout to prevent hanging
        async with asyncio.timeout(30):
            async with agent_manager.run() as agent:
                print("Agent running for GET request")
                response = await agent.bakery(query)
                return {"response": response, "source": "mcp_agent"}
    except Exception as e:
        print(f"Error in GET method: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to check item: {str(e)}")

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"Global exception handler caught: {exc}")
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"message": f"An unexpected error occurred: {str(exc)}"}
    )

# Add debug/status endpoint
@app.get("/status")
async def status():
    """Return system status and configuration information"""
    status_info = {
        "app": {
            "name": "Bakery API",
            "version": "1.0.0",
            "status": "running"
        },
        "environment": {
            "python_version": sys.version,
            "directory": os.getcwd(),
            "files": os.listdir('.')[:10],  # List first 10 files for security
        },
        "config": {
            "path": "fastagent.config.yaml",
            "exists": os.path.exists("fastagent.config.yaml")
        },
        "bakery_hours": {
            "exists": os.path.exists("bakery_hours.json")
        }
    }
    
    # Add MCP server info from the pre-initialized agent
    if hasattr(app.state, "agent_manager"):
        agent_manager = app.state.agent_manager
        initialized = getattr(app.state, "agent_initialized", False)
        
        status_info["mcp"] = {
            "status": "initialized" if initialized else "error_during_initialization",
            "agent_manager_available": True
        }
        
        if hasattr(agent_manager, "context") and hasattr(agent_manager.context, "mcp_servers"):
            status_info["mcp"]["servers_configured"] = list(agent_manager.context.mcp_servers.keys())
        
        if hasattr(agent_manager, "agents"):
            status_info["mcp"]["agents_configured"] = list(agent_manager.agents.keys())
    else:
        status_info["mcp"] = {"status": "not_initialized", "error": "Agent manager not found in application state"}
    
    return status_info

# Main function to run everything
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port) 