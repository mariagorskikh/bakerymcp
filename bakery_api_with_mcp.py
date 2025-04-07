import asyncio
import os
import sys
import json
import traceback
from fastapi import FastAPI, Body, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from mcp_agent.core.fastagent import FastAgent
from contextlib import asynccontextmanager

# Set up logging
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("bakery_api")

# Create FastAPI application first (no lifespan yet)
app = FastAPI(
    title="Bakery API", 
    description="Bakery availability checker with MCP servers"
)

# Create FastAgent with explicit config path
# Make sure to use absolute path for reliability
config_path = os.path.join(os.getcwd(), "fastagent.config.yaml")
logger.info(f"Creating FastAgent with config at: {config_path}")
fast = FastAgent("Bakery Agent", config_path=config_path)

# Define request model for JSON input
class BakeryQuery(BaseModel):
    query: str

# Define bakery agent - ensure server names match exactly with config
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
    servers=["fetch", "filesystem"],  # Must exactly match keys in mcp_servers config
    model="openai.o3-mini.high"  # Explicitly use OpenAI model
)
async def bakery_agent():
    pass  # Agent is defined by decorator

# Define the lifespan context manager for FastAPI - much simpler now
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Simple lifespan manager that just logs information"""
    logger.info("Starting application lifespan...")
    
    # Print environment info for debugging
    try:
        # Check if bakery_hours.json exists
        if os.path.exists("bakery_hours.json"):
            with open("bakery_hours.json", "r") as f:
                logger.info(f"Found bakery_hours.json: {f.read()[:100]}...")
        else:
            logger.warning("bakery_hours.json not found!")

        # Print the config for debugging
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                logger.info(f"FastAgent configuration content: {f.read()}")
        else:
            logger.error(f"Configuration file not found at: {config_path}")
            
        # Print Python path and environment
        logger.info(f"Python path: {sys.path}")
        logger.info(f"Current directory: {os.getcwd()}")
        logger.debug(f"Directory contents: {os.listdir('.')}")
    except Exception as e:
        logger.error(f"Error during environment check: {str(e)}")
    
    # Store agent manager in app state (but don't try to initialize it yet)
    app.state.agent_manager = fast
    
    # Yield control to FastAPI - run the application
    try:
        yield
    except Exception as e:
        if not isinstance(e, SystemExit):
            logger.error(f"Error during application execution: {str(e)}")
            traceback.print_exc()
    finally:
        logger.info("Shutting down application...")

# Apply lifespan after defining it
app.router.lifespan_context = lifespan

# Helper function to run MCP operations with proper error handling
async def run_mcp_query(query: str):
    """Run a query through MCP with proper error handling and timeouts"""
    logger.info(f"Running MCP query: {query}")
    
    try:
        # Each request needs its own MCP context
        async with asyncio.timeout(15):
            # The key part: use the run() context manager for EACH request
            async with fast.run() as agent:
                logger.info("MCP context started successfully")
                response = await agent.bakery(query)
                logger.info("MCP query completed successfully")
                return {"response": response, "source": "mcp_agent"}
    except Exception as e:
        logger.error(f"Error running MCP query: {str(e)}")
        traceback.print_exc()
        # Return a simple fallback that mentions the error
        return {
            "response": f"Sorry, I couldn't process your request due to a technical issue: {str(e)}",
            "source": "error_fallback"
        }

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
        logger.info(f"Processing POST request with query: {query}")
        
        # Use our helper function to run the MCP query
        return await run_mcp_query(query)
            
    except Exception as e:
        logger.error(f"Error in POST method: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to process request: {str(e)}")

@app.get("/check")
async def check_availability_get(item: str):
    """Check if an item is available at the bakery (GET method)"""
    try:
        query = f"Can I order a {item}?"
        logger.info(f"Processing GET request for item: {item}")
        
        # Use our helper function to run the MCP query
        return await run_mcp_query(query)
            
    except Exception as e:
        logger.error(f"Error in GET method: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to check item: {str(e)}")

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception handler caught: {exc}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"message": f"An unexpected error occurred: {str(exc)}"}
    )

# Add debug/status endpoint
@app.get("/status")
async def status():
    """Return system status and configuration information"""
    # Basic status info that doesn't try to use MCP directly
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
            "path": config_path,
            "exists": os.path.exists(config_path)
        },
        "bakery_hours": {
            "exists": os.path.exists("bakery_hours.json")
        }
    }
    
    # Try to validate MCP by running a simple test within the status endpoint
    try:
        # Test MCP within this request
        test_result = await run_mcp_query("Is the bakery open today?")
        status_info["mcp_test"] = {
            "status": "success",
            "result": test_result
        }
    except Exception as e:
        status_info["mcp_test"] = {
            "status": "error",
            "error": str(e)
        }
    
    return status_info

# Main function to run everything
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    
    # Use more reliable host binding
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="debug") 