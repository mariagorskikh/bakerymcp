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
from sse_starlette.sse import EventSourceResponse  # Import SSE

# Set up logging
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("bakery_api")

# API Documentation
API_DESCRIPTION = """
# Bakery API

## Overview
The Bakery API provides information about bakery products, availability, and operating hours. 
It offers a simple, reliable interface for querying bakery information through multiple endpoints.
It also provides a Server-Sent Events (SSE) endpoint for real-time updates.

## Core Features
- Check availability of specific bakery items using MCP servers
- Get information about bakery operating hours using MCP servers
- Query the menu and product offerings using MCP servers
- Server-Sent Events (SSE) endpoint for streaming updates

## API Endpoints

### 1. Root Endpoint (GET /)
Returns basic API status information.

### 2. Status Endpoint (GET /status)
Provides detailed system and MCP server status information.

### 3. Check Availability - POST (POST /check)
Check item availability using MCP via POST method with JSON payload.

### 4. Check Availability - GET (GET /check)
Check item availability using MCP via GET method with query parameter.

### 5. Direct Response (GET /bakery-response)
Get direct responses to bakery-related questions (bypasses MCP).

### 6. Server-Sent Events (GET /sse)
Stream real-time events from the server.

### 7. Resources (GET /resources)
Get static information about bakery resources.

## Query Types
The API can handle various types of questions about:
- Specific bakery items (bread, cake, etc.)
- Operating hours 
- Menu offerings
- Availability on specific days
"""

# Create FastAPI application with detailed documentation
app = FastAPI(
    title="Bakery API", 
    description=API_DESCRIPTION,
    version="1.2.0",  # Incremented version for MCP fix attempt
    docs_url="/docs",
    redoc_url="/redoc"
)

# Define request model for JSON input
class BakeryQuery(BaseModel):
    """
    Query model for checking bakery item availability
    
    Attributes:
        query: The question about bakery items or services
    
    Example:
        {"query": "Do you have chocolate cake?"}
    """
    query: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "Do you have chocolate cake?"
            }
        }

# Define the lifespan context manager for FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler for FastAPI
    Initializes FastAgent and registers the agent using its decorator.
    """
    global agent_manager
    agent_manager = None  # Initialize
    
    try:
        logger.info("Starting application lifespan...")
        
        # Check if bakery_hours.json exists
        if os.path.exists("bakery_hours.json"):
            with open("bakery_hours.json", "r") as f:
                data = f.read()
                logger.info(f"Found bakery_hours.json: {data[:100]}...")
        else:
            logger.warning("bakery_hours.json not found! MCP filesystem server might not work as expected.")
            
        # Create config file
        config_path = os.path.join(os.getcwd(), "fastagent.config.yaml")
        config_content = """# FastAgent Configuration File
default_model: openai.o3-mini.high

logger:
    level: "debug"
    type: "console"  
    progress_display: true
    show_chat: true
    show_tools: true
    truncate_tools: true

mcp_servers:
    fetch:
        server_type: subprocess
        command: python3
        args: ["-m", "mcp.server.fetch"]
        timeout: 45
        max_restarts: 3
        restart_delay: 2
    filesystem:
        server_type: subprocess
        command: python3 
        args: ["-m", "mcp.server.filesystem", "/opt/render/project/src"]
        timeout: 30
        max_restarts: 3
        restart_delay: 2
"""
        
        # Write the config file
        with open(config_path, "w") as f:
            f.write(config_content)
        logger.info(f"Created {config_path}")
        
        # Log environment info
        logger.info(f"Python path: {sys.path}")
        logger.info(f"Current directory: {os.getcwd()}")
        logger.debug(f"Directory contents: {os.listdir(os.getcwd())}")
        
        # --- MCP Initialization ---
        # 1. Create FastAgent instance
        agent_manager = FastAgent("BakeryAgent", config_path=config_path)
        logger.info("FastAgent instance created successfully")
        
        # 2. Initialize FastAgent (starts servers, loads config)
        await agent_manager.initialize()
        logger.info("FastAgent initialized successfully")
        
        # 3. Define and register the agent using the decorator
        # This links the agent function to the manager and declares server needs
        @agent_manager.agent(name="bakery", servers=["fetch", "filesystem"])
        async def bakery_agent_impl(agent, query: str):
            """
            MCP agent to check bakery inventory and hours using fetch and filesystem.
            Uses hardcoded logic after potentially interacting with servers.
            """
            logger.info(f"Running bakery agent implementation with query: {query}")
            hours_data_str = "Bakery hours file not found."
            menu_data_str = "Could not fetch menu."
            files = []

            # Interact with MCP servers (filesystem and fetch)
            try:
                logger.info("Attempting to list files via MCP filesystem server...")
                files = await agent.filesystem.list(path=".")
                logger.debug(f"Files found via MCP: {files}")
                if "bakery_hours.json" in files:
                    logger.info("Attempting to read bakery_hours.json via MCP...")
                    hours_data = await agent.filesystem.read_file(path="bakery_hours.json")
                    hours_data_str = hours_data.get("content", "Error reading hours file content.")
                    logger.debug(f"Bakery hours data read via MCP: {hours_data_str[:100]}...")
                else:
                    logger.warning("bakery_hours.json not found in listed files.")
            except Exception as e_fs:
                logger.error(f"Error interacting with MCP filesystem server: {e_fs}", exc_info=True)
                hours_data_str = f"Error accessing filesystem: {e_fs}"

            # Fetch menu data (using placeholder URL)
            # try:
            #     logger.info("Attempting to fetch menu via MCP fetch server...")
            #     # Using a placeholder URL as example.com won't work
            #     # Replace with a real URL if available, e.g., a pastebin link with menu text
            #     menu_url = "https://httpbin.org/get" # Simple test URL
            #     menu_response = await agent.fetch.fetch(url=menu_url)
            #     menu_data_str = menu_response.get("content", "Error reading menu response content.")
            #     logger.debug(f"Menu data fetched via MCP: {menu_data_str[:100]}...")
            # except Exception as e_fetch:
            #     logger.error(f"Error interacting with MCP fetch server: {e_fetch}", exc_info=True)
            #     menu_data_str = f"Error fetching menu: {e_fetch}"

            # Use the direct query processor logic for the actual response generation
            # In a real scenario, you might pass hours_data_str and menu_data_str
            # to an LLM or use them in more complex logic.
            response = process_bakery_query(query)
            logger.info(f"Bakery agent generated response: {response}")
            return response

        logger.info("Bakery agent defined and registered via decorator.")
        # --- End MCP Initialization ---
        
        # Yield control back to FastAPI
        yield
    
    except Exception as e:
        logger.error("--- CRITICAL ERROR DURING LIFESPAN SETUP ---")
        logger.error(f"Error: {e}", exc_info=True)
        # Ensure agent_manager is None if setup fails critically before yield
        agent_manager = None
        # We still yield to allow FastAPI to start, but MCP endpoints will fail.
        yield
    
    finally:
        # Cleanup
        logger.info("Application shutdown sequence starting...")
        try:
            if agent_manager is not None:
                logger.info("Attempting FastAgent cleanup...")
                await agent_manager.cleanup()
                logger.info("FastAgent cleanup completed.")
            else:
                 logger.info("Agent manager was None, skipping cleanup.")
        except Exception as e:
            logger.error(f"Error during FastAgent cleanup: {e}", exc_info=True)
        logger.info("Application shutdown sequence finished.")

# Add the lifespan to the FastAPI app
app.router.lifespan_context = lifespan

# Global variable for the FastAgent manager
agent_manager = None

async def run_mcp_query(query: str) -> dict:
    """
    Run a query using the initialized MCP agent.
    Propagates errors instead of using fallbacks.
    """
    logger.info(f"Attempting to run MCP query: {query}")
    global agent_manager

    if agent_manager is None:
        logger.error("MCP Agent manager is None. Lifespan setup likely failed.")
        # Raise an exception as fallbacks are removed
        raise HTTPException(status_code=503, detail="Bakery MCP service is not available due to initialization error.")

    try:
        # Use the agent_manager initialized during lifespan
        # The agent ('bakery') should already be registered via the decorator
        async with agent_manager.run() as agent:
            logger.info(f"MCP run context entered. Invoking 'bakery' agent for query: {query}")
            result = await agent.invoke("bakery", query=query)
            logger.info(f"MCP agent 'bakery' invoked successfully. Result: {result}")
            return {"response": result, "source": "mcp"}

    except Exception as e:
        logger.error(f"--- ERROR RUNNING MCP QUERY ---")
        logger.error(f"Query: {query}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error details: {e}", exc_info=True) # Log traceback
        # Propagate the error as an HTTP exception
        raise HTTPException(status_code=500, detail=f"Error processing MCP query: {e}")

def process_bakery_query(question: str) -> str:
    """
    Process bakery questions and return appropriate responses.
    
    This function analyzes the query text and returns information about
    bakery products, availability, hours, or other requested information.
    
    Args:
        question: The bakery-related question from the user
        
    Returns:
        A string response addressing the user's query
    """
    query = question.lower()
    
    # Check for bread-related queries
    if "bread" in query:
        if "whole wheat" in query or "wheat" in query:
            return "Yes, we have whole wheat bread available daily until 5 PM."
        elif "sourdough" in query:
            return "Our signature sourdough bread is available Tuesday through Saturday, fresh-baked each morning."
        elif "gluten" in query:
            return "We offer gluten-free bread options on Mondays, Wednesdays, and Fridays."
        else:
            return "Yes, we have fresh bread available daily until 5 PM."
    
    # Check for cake-related queries
    elif "cake" in query:
        if "chocolate" in query:
            return "Yes, our specialty chocolate cake is available all week!"
        elif "birthday" in query:
            return "We offer custom birthday cakes with 48 hours advance notice. Please call to place an order."
        elif "cheesecake" in query:
            return "Our New York style cheesecake is available Thursday through Sunday."
        elif "friday" in query or "weekend" in query:
            return "Yes, we have cake available on Friday and the weekend."
        else:
            return "We have various cakes available. Please specify what type you're looking for."
    
    # Check for pastry-related queries
    elif "pastry" in query or "pastries" in query:
        if "croissant" in query:
            return "Our butter croissants are baked fresh every morning and typically sell out by noon."
        else:
            return "We offer a variety of pastries including croissants, danishes, and pain au chocolat."
    
    # Check for coffee-related queries
    elif "coffee" in query:
        return "We serve freshly brewed coffee all day, with espresso drinks available until 30 minutes before closing."
    
    # Check for hours-related queries
    elif "hours" in query or "open" in query or "close" in query or "closing" in query:
        if "weekend" in query or "saturday" in query or "sunday" in query:
            return "Our weekend hours are 8 AM to 4 PM on both Saturday and Sunday."
        else:
            return "Our bakery is open Monday to Friday from 7 AM to 6 PM, and on weekends from 8 AM to 4 PM."
    
    # Check for menu-related queries
    elif "menu" in query or "offer" in query or "have" in query:
        return "We offer a variety of breads, cakes, pastries, and coffee. Our most popular items are sourdough bread, chocolate cake, and croissants."
    
    # Check for ordering-related queries
    elif "order" in query or "delivery" in query or "pickup" in query:
        return "You can place orders in person, by phone, or through our website. We offer pickup and local delivery within 5 miles."
    
    # Default response for other queries
    else:
        return "Please ask about a specific bakery item, our hours, or ordering options, and I'll be happy to help!"

# Root endpoint for API status
@app.get("/", tags=["System"])
async def root():
    """
    Root endpoint for checking API status
    
    Returns basic information about the API status and version.
    
    Returns:
        JSON object with message, status, and version
    """
    return {
        "message": "Bakery API is running.",
        "status": "online",
        "version": "1.2.0" # Match version in app definition
    }

# Status endpoint for system status
@app.get("/status", tags=["System"])
async def status():
    """
    Endpoint for checking system and MCP server status
    
    Provides detailed information about the system's operational status,
    including environment details and current timestamp.
    
    Returns:
        JSON object with status information
    """
    try:
        global agent_manager
        status_info = {
            "status": "online",
            "message": "System is operational",
            "timestamp": str(asyncio.get_event_loop().time()),
            "environment": {
                "python_version": sys.version,
                "cwd": os.getcwd()
            },
            "mcp_status": {}
        }
        if agent_manager is None:
            status_info["mcp_status"] = {"status": "not_initialized", "message": "MCP agent manager failed during lifespan setup."}
        elif hasattr(agent_manager, "context") and agent_manager.context and agent_manager.context.mcp_servers:
             servers = agent_manager.context.mcp_servers
             # Check if servers are actually running/connected? (Might require more complex check)
             server_status = {name: "configured" for name in servers.keys()} # Basic status
             status_info["mcp_status"] = {
                 "status": "initialized",
                 "message": "MCP agent manager initialized.",
                 "configured_servers": server_status
             }
             # Add check for registered agents
             if hasattr(agent_manager, "agents") and agent_manager.agents:
                 status_info["mcp_status"]["registered_agents"] = list(agent_manager.agents.keys())
             else:
                 status_info["mcp_status"]["registered_agents"] = []

        else:
            status_info["mcp_status"] = {"status": "initialization_incomplete", "message": "MCP agent manager context or servers missing."}
        return status_info

    except Exception as e:
        logger.error(f"Error in /status endpoint: {e}", exc_info=True)
        # Return error status but don't crash the endpoint
        return {
            "status": "error",
            "message": "Error checking system status",
            "error_details": str(e),
            "error_type": str(type(e).__name__)
        }

# POST endpoint for checking item availability
@app.post("/check", tags=["Bakery Queries (MCP)"])
async def check_availability_post(query_data: BakeryQuery):
    """
    POST endpoint for checking bakery item availability using MCP.
    Will raise errors if MCP is not functional.
    
    Args:
        query_data: The BakeryQuery object containing the query string
        
    Returns:
        JSON object with response and source information
    
    Example:
        Request: {"query": "Do you have chocolate cake?"}
        Response: {"response": "Yes, our specialty chocolate cake is available all week!", "source": "mcp"}
    """
    logger.info(f"Processing POST /check request with query: {query_data.query}")
    # This will now raise an HTTPException if MCP fails
    return await run_mcp_query(query_data.query)

# GET endpoint for checking item availability
@app.get("/check", tags=["Bakery Queries (MCP)"])
async def check_availability_get(item: str = None):
    """
    GET endpoint for checking bakery item availability using MCP.
    Will raise errors if MCP is not functional.
    
    Accepts an item parameter in the query string and returns information
    about that item's availability.
    
    Args:
        item: The bakery item to check (query parameter)
        
    Returns:
        JSON object with response and source information
    
    Example:
        Request: /check?item=bread
        Response: {"response": "Yes, we have fresh bread available daily until 5 PM.", "source": "mcp"}
    """
    if not item:
        raise HTTPException(status_code=400, detail="Missing 'item' query parameter")

    logger.info(f"Processing GET /check request for item: {item}")
    query = f"Can I order a {item}?"
    # This will now raise an HTTPException if MCP fails
    return await run_mcp_query(query)

# Backup endpoint for direct response
@app.get("/bakery-response", tags=["Bakery Queries (Direct)"])
async def direct_bakery_response(question: str):
    """
    Endpoint for direct bakery responses (bypasses MCP).
    
    Accepts a question parameter in the query string and returns a direct
    response to the bakery-related question, bypassing MCP.
    
    Args:
        question: The bakery-related question (query parameter)
        
    Returns:
        JSON object with response and source information
    
    Example:
        Request: /bakery-response?question=When are you open on weekends?
        Response: {"response": "Our bakery is open Monday to Friday from 7 AM to 6 PM, and on weekends from 8 AM to 4 PM.", "source": "direct"}
    """
    response = process_bakery_query(question)
    return {"response": response, "source": "direct"}

# Resources available in the bakery
BAKERY_RESOURCES = {
    "bread": {
        "types": ["white", "whole wheat", "sourdough", "rye", "baguette", "gluten-free"],
        "availability": "Daily, fresh-baked each morning by 7 AM",
        "best_sellers": ["sourdough", "baguette"]
    },
    "cakes": {
        "types": ["chocolate", "vanilla", "red velvet", "carrot", "cheesecake", "birthday"],
        "availability": "All week, custom orders available with 48-hour notice",
        "best_sellers": ["chocolate", "cheesecake"]
    },
    "pastries": {
        "types": ["croissant", "danish", "pain au chocolat", "muffin", "scone"],
        "availability": "Daily until sold out, usually by noon",
        "best_sellers": ["butter croissant", "blueberry muffin"]
    },
    "coffee": {
        "types": ["drip coffee", "espresso", "latte", "cappuccino", "americano"],
        "availability": "All day during operating hours",
        "best_sellers": ["latte", "drip coffee"]
    },
    "operating_hours": {
        "weekdays": "7 AM - 6 PM (Monday to Friday)",
        "weekends": "8 AM - 4 PM (Saturday and Sunday)",
        "holidays": "Check our website for holiday hours"
    }
}

# Additional endpoint to get the bakery resources
@app.get("/resources", tags=["Resources"])
async def get_resources():
    """
    Endpoint to get information about bakery resources
    
    Returns detailed information about the bakery's product offerings,
    availability, and operating hours.
    
    Returns:
        JSON object with bakery resources information
    """
    return BAKERY_RESOURCES

# SSE Endpoint
async def event_generator(request: Request):
    """Generator for SSE events"""
    count = 0
    try:
        while True:
            # Check if the client disconnected
            if await request.is_disconnected():
                logger.info("Client disconnected from SSE stream.")
                break
            
            # Simulate sending an event every 2 seconds
            count += 1
            timestamp = str(asyncio.get_event_loop().time())
            event_data = {"count": count, "timestamp": timestamp}
            
            # Yield event data in SSE format
            yield {
                "event": "message", 
                "id": str(count), 
                "retry": 15000,  # Tell client to retry connection after 15 seconds if disconnected
                "data": json.dumps(event_data)
            }
            
            await asyncio.sleep(2)
            
    except asyncio.CancelledError:
        logger.info("SSE generator cancelled.")
    except Exception as e:
        logger.error(f"Error in SSE generator: {e}", exc_info=True)
        # Optionally yield an error event to the client
        yield {
            "event": "error",
            "data": json.dumps({"message": "An error occurred on the server"})
        }

@app.get("/sse", tags=["Streaming"])
async def sse_endpoint(request: Request):
    """
    Server-Sent Events endpoint
    
    Streams real-time server events to connected clients.
    
    Events:
        - message: Contains a count and timestamp, sent every 2 seconds.
        - error: Sent if an unexpected error occurs in the stream.
    """
    return EventSourceResponse(event_generator(request))

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for all unhandled exceptions
    
    Catches any unhandled exceptions, logs them, and returns a user-friendly
    error message.
    
    Args:
        request: The request that caused the exception
        exc: The exception that was raised
        
    Returns:
        JSONResponse with error information
    """
    # Avoid logging HTTPException details handled by run_mcp_query
    if not isinstance(exc, HTTPException):
        logger.error(f"Unhandled exception caught by global handler: {exc}", exc_info=True)
    else:
        # Log HTTPExceptions raised intentionally (like from run_mcp_query) less verbosely
        logger.warning(f"HTTPException caught: Status={exc.status_code}, Detail='{exc.detail}'")

    # For HTTPExceptions, return their status code and detail
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail}
        )
    # For other exceptions, return a generic 500 error
    else:
        return JSONResponse(
            status_code=500,
            content={
                "detail": "An unexpected internal server error occurred.",
                "error_type": str(type(exc).__name__)
            }
        )

# Run the server directly if the script is executed
if __name__ == "__main__":
    import uvicorn
    # Ensure the port is set correctly, matching Render's expectations if necessary
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"Starting Uvicorn server on host 0.0.0.0 port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)