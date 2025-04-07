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

# Define the lifespan context manager for FastAPI - AFTER agent definitions
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize MCP servers and clean up on shutdown"""
    logger.info("Starting application lifespan...")
    logger.info("Initializing MCP environment...")
    
    # Check config file exists
    if not os.path.exists(config_path):
        logger.error(f"Config file not found at: {config_path}")
        with open(config_path, "w") as f:
            f.write("# FastAgent Configuration File created during runtime\n")
            f.write("default_model: openai.o3-mini.high\n")
            f.write("mcp_servers:\n")
            f.write('  "fetch":\n')
            f.write("    server_type: subprocess\n")
            f.write("    command: python3\n")
            f.write('    args: ["-m", "mcp.server.fetch"]\n')
            f.write("    timeout: 30\n")
            f.write('  "filesystem":\n') 
            f.write("    server_type: subprocess\n")
            f.write("    command: python3\n") 
            f.write(f'    args: ["-m", "mcp.server.filesystem", "{os.getcwd()}"]\n')
            f.write("    timeout: 30\n")
        logger.info(f"Created default config file at: {config_path}")
    
    # Print environment info for debugging
    try:
        # Check if bakery_hours.json exists
        if os.path.exists("bakery_hours.json"):
            with open("bakery_hours.json", "r") as f:
                logger.info(f"Found bakery_hours.json: {f.read()[:100]}...")
        else:
            logger.warning("bakery_hours.json not found!")

        # Print the config for debugging
        with open(config_path, "r") as f:
            logger.info(f"FastAgent configuration content: {f.read()}")
            
        # Print Python path and environment
        logger.info(f"Python path: {sys.path}")
        logger.info(f"Current directory: {os.getcwd()}")
        logger.debug(f"Directory contents: {os.listdir('.')}")
    except Exception as e:
        logger.error(f"Error during environment check: {str(e)}")
    
    # Store agent manager in app state 
    app.state.agent_manager = fast
    app.state.agent_initialized = False
    
    # Set up flag for proper exception handling
    app.state.shutdown_requested = False
    
    # Yield control to FastAPI - run the application
    try:
        yield
    except Exception as e:
        if not isinstance(e, SystemExit):
            logger.error(f"Error during application execution: {str(e)}")
            traceback.print_exc()
    finally:
        logger.info("Shutting down application...")
        app.state.shutdown_requested = True

# Apply lifespan after defining it
app.router.lifespan_context = lifespan

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
        
        # Access the FastAgent from app state
        if not hasattr(app.state, "agent_manager"):
            raise Exception("Agent manager not available")
            
        agent_manager = app.state.agent_manager
        
        # Use a timeout to prevent hanging
        try:
            async with asyncio.timeout(15):
                async with agent_manager.run() as agent:
                    logger.info("Agent running for POST request")
                    response = await agent.bakery(query)
                    app.state.agent_initialized = True
                    return {"response": response, "source": "mcp_agent"}
        except Exception as e:
            logger.error(f"Error running agent: {str(e)}")
            
            # Simple fallback for MCP errors
            items = ["bread", "cake", "croissant", "donut", "muffin", "pie"]
            days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            
            item_found = None
            day_found = None
            
            for item in items:
                if item in query.lower():
                    item_found = item
                    break
                    
            for day in days:
                if day in query.lower():
                    day_found = day
                    break
            
            if item_found:
                if day_found:
                    return {"response": f"We likely have {item_found} available on {day_found.title()}. (API using fallback due to MCP error)", "source": "fallback"}
                else:
                    return {"response": f"We have {item_found} on our menu. Please specify which day you want to order it. (API using fallback due to MCP error)", "source": "fallback"}
            else:
                return {"response": "I couldn't determine which item you're asking about. Please specify the bakery item. (API using fallback due to MCP error)", "source": "fallback"}
            
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
        
        # Access the FastAgent from app state
        if not hasattr(app.state, "agent_manager"):
            raise Exception("Agent manager not available")
            
        agent_manager = app.state.agent_manager
        
        # Use a timeout to prevent hanging
        try:
            async with asyncio.timeout(15):
                async with agent_manager.run() as agent:
                    logger.info("Agent running for GET request")
                    response = await agent.bakery(query)
                    app.state.agent_initialized = True
                    return {"response": response, "source": "mcp_agent"}
        except Exception as e:
            logger.error(f"Error running agent: {str(e)}")
            
            # Simple fallback for MCP errors
            bakery_items = ["bread", "cake", "croissant", "donut", "muffin", "pie"]
            item_lower = item.lower()
            
            for bakery_item in bakery_items:
                if bakery_item in item_lower:
                    return {"response": f"Yes, we have {bakery_item} available in our bakery! (API using fallback due to MCP error)", "source": "fallback"}
                    
            return {"response": f"Sorry, we don't have '{item}' available in our bakery. (API using fallback due to MCP error)", "source": "fallback"}
            
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
    
    # Add MCP status information
    if hasattr(app.state, "agent_manager"):
        agent_manager = app.state.agent_manager
        initialized = getattr(app.state, "agent_initialized", False)
        
        status_info["mcp"] = {
            "status": "initialized" if initialized else "not_fully_initialized",
            "agent_manager_available": True
        }
        
        if hasattr(agent_manager, "context") and hasattr(agent_manager.context, "mcp_servers"):
            try:
                status_info["mcp"]["servers_configured"] = list(agent_manager.context.mcp_servers.keys())
            except:
                status_info["mcp"]["servers_configured"] = "Error accessing server keys"
        
        if hasattr(agent_manager, "agents"):
            try:
                status_info["mcp"]["agents_configured"] = list(agent_manager.agents.keys())
            except:
                status_info["mcp"]["agents_configured"] = "Error accessing agent keys"
    else:
        status_info["mcp"] = {"status": "not_initialized", "error": "Agent manager not found in application state"}
    
    return status_info

# Main function to run everything
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    
    # Use more reliable host binding
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="debug") 