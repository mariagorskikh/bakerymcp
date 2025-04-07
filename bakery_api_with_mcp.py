import asyncio
import os
import sys
import json
import traceback
from fastapi import FastAPI, Body, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from mcp_agent.core.fastagent import FastAgent
from mcp_agent.core.config import FastAgentConfig, ServerConfig  # Add this import
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

# Define request model for JSON input
class BakeryQuery(BaseModel):
    query: str

# Define the lifespan context manager for FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Simple lifespan manager that configures and initializes FastAgent"""
    logger.info("Starting application lifespan...")
    
    # Print environment info for debugging
    try:
        # Check if bakery_hours.json exists
        if os.path.exists("bakery_hours.json"):
            with open("bakery_hours.json", "r") as f:
                logger.info(f"Found bakery_hours.json: {f.read()[:100]}...")
        else:
            logger.warning("bakery_hours.json not found!")

        # Get configuration file path - but we won't rely on it
        config_path = os.path.join(os.getcwd(), "fastagent.config.yaml")
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                logger.info(f"FastAgent configuration content: {f.read()}")
        else:
            logger.warning(f"Configuration file not found at: {config_path}")
            
        # Print Python path and environment
        logger.info(f"Python path: {sys.path}")
        logger.info(f"Current directory: {os.getcwd()}")
        logger.debug(f"Directory contents: {os.listdir('.')}")
    except Exception as e:
        logger.error(f"Error during environment check: {str(e)}")
    
    # Create FastAgent with explicit configuration
    try:
        # Create explicit server configs 
        fetch_server = ServerConfig(
            server_type="subprocess",
            command="python3",
            args=["-m", "mcp.server.fetch"],
            timeout=45,
            max_restarts=3,
            restart_delay=2
        )
        
        filesystem_server = ServerConfig(
            server_type="subprocess",
            command="python3",
            args=["-m", "mcp.server.filesystem", os.getcwd()],
            timeout=30,
            max_restarts=3,
            restart_delay=2
        )
        
        # Create explicit config object
        explicit_config = FastAgentConfig(
            default_model="openai.o3-mini.high",
            mcp_servers={
                "fetch": fetch_server,
                "filesystem": filesystem_server
            }
        )
        
        # Create FastAgent with explicit config
        fast_agent = FastAgent(
            "Bakery Agent",
            config=explicit_config  # Use explicit config instead of config_path
        )
        
        logger.info("FastAgent instance created successfully with explicit config")
        
        # Define bakery agent - ensure server names match exactly with config
        @fast_agent.agent(
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
        
        logger.info("Bakery agent defined successfully")
        
        # Store FastAgent in app state
        app.state.agent_manager = fast_agent
        
    except Exception as e:
        logger.error(f"Failed to initialize FastAgent: {str(e)}")
        logger.error(traceback.format_exc())
        app.state.agent_manager = None
    
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
    
    if not hasattr(app.state, "agent_manager") or app.state.agent_manager is None:
        logger.error("FastAgent not initialized properly")
        return {
            "response": "Sorry, the bakery service is experiencing technical issues. (FastAgent not available)",
            "source": "error_fallback"
        }
    
    try:
        # Create a local FastAgent instance just for this request
        local_agent = app.state.agent_manager
        
        # Each request needs its own MCP context with a short timeout
        async with asyncio.timeout(10):
            # The key part: use the run() context manager for EACH request
            try:
                async with local_agent.run() as agent:
                    logger.info("MCP context started successfully")
                    if hasattr(agent, "bakery"):
                        logger.info("Agent has bakery method")
                        response = await agent.bakery(query)
                        logger.info("MCP query completed successfully")
                        return {"response": response, "source": "mcp_agent"}
                    else:
                        logger.error("Agent doesn't have bakery method")
                        raise AttributeError("Agent doesn't have bakery method")
            except Exception as inner_e:
                logger.error(f"Error inside MCP context: {str(inner_e)}")
                logger.error(traceback.format_exc())
                raise inner_e
    except asyncio.TimeoutError:
        logger.error("MCP query timed out")
        return {
            "response": "Sorry, the bakery service is taking too long to respond. Please try again later.",
            "source": "timeout_fallback"
        }
    except Exception as e:
        logger.error(f"Error running MCP query: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Use a simple fallback response
        return {
            "response": f"Sorry, I couldn't process your request about bakery items. Please try a simpler query or try again later.",
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
        logger.error(traceback.format_exc())
        
        # Return a user-friendly error without exposing implementation details
        return JSONResponse(
            status_code=500,
            content={
                "response": "Sorry, the bakery service is currently unavailable. Please try again later.",
                "source": "error_response"
            }
        )

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
        logger.error(traceback.format_exc())
        
        # Return a user-friendly error without exposing implementation details
        return JSONResponse(
            status_code=500,
            content={
                "response": "Sorry, the bakery service is currently unavailable. Please try again later.",
                "source": "error_response"
            }
        )

# Add a simple fallback for GET /bakery-response endpoint
@app.get("/bakery-response")
async def fallback_response(question: str = ""):
    """Provide a simple fallback response without using MCP"""
    if not question:
        return {"response": "Please provide a question about bakery items.", "source": "fallback"}
    
    items = ["bread", "cake", "croissant", "donut", "muffin", "pie"]
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    
    item_found = None
    day_found = None
    
    for item in items:
        if item in question.lower():
            item_found = item
            break
            
    for day in days:
        if day in question.lower():
            day_found = day
            break
    
    if item_found:
        if day_found and day_found == "sunday":
            return {"response": f"Sorry, we're closed on Sunday so {item_found} is not available.", "source": "fallback"}
        elif day_found:
            return {"response": f"Yes, we have {item_found} available on {day_found.title()}.", "source": "fallback"}
        else:
            return {"response": f"Yes, we have {item_found} on our menu most days. Please specify which day you want to order it.", "source": "fallback"}
    else:
        return {"response": "I couldn't determine which item you're asking about. We have bread, cake, croissants, donuts, muffins, and pies.", "source": "fallback"}

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception handler caught: {exc}")
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"response": "An unexpected error occurred with the bakery service. Please try again later."}
    )

# Add debug/status endpoint
@app.get("/status")
async def status():
    """Return system status and configuration information without initializing MCP"""
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
            "path": os.path.join(os.getcwd(), "fastagent.config.yaml"),
            "exists": os.path.exists(os.path.join(os.getcwd(), "fastagent.config.yaml"))
        },
        "bakery_hours": {
            "exists": os.path.exists("bakery_hours.json")
        },
        "mcp_info": {
            "status": "configured_in_code", 
            "note": "Using explicit ServerConfig objects instead of config file"
        }
    }
    
    # Add FastAgent configuration info without trying to initialize anything
    if hasattr(app.state, "agent_manager") and app.state.agent_manager is not None:
        agent_manager = app.state.agent_manager
        status_info["mcp_info"]["agent_manager"] = "available"
        
        if hasattr(agent_manager, "context") and hasattr(agent_manager.context, "mcp_servers"):
            try:
                status_info["mcp_info"]["configured_servers"] = list(agent_manager.context.mcp_servers.keys())
            except Exception as e:
                status_info["mcp_info"]["configured_servers_error"] = str(e)
        
        if hasattr(agent_manager, "agents"):
            try:
                status_info["mcp_info"]["configured_agents"] = list(agent_manager.agents.keys())
            except Exception as e:
                status_info["mcp_info"]["configured_agents_error"] = str(e)
    else:
        status_info["mcp_info"]["agent_manager"] = "not_available"
    
    # Provide access to fallback api
    status_info["fallback_api"] = {
        "url": "/bakery-response?question=Do you have cake on Friday?",
        "description": "Use this endpoint for a simple fallback response when MCP is not available"
    }
    
    return status_info

# Main function to run everything
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    
    # Use more reliable host binding
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="debug") 