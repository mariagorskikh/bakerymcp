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
- Check availability of specific bakery items
- Get information about bakery operating hours
- Query the menu and product offerings
- Reliable responses with detailed error handling
- SSE endpoint for streaming updates

## API Endpoints

### 1. Root Endpoint (GET /)
Returns basic API status information.

### 2. Status Endpoint (GET /status)
Provides detailed system status information.

### 3. Check Availability - POST (POST /check)
Check item availability using POST method with JSON payload.

### 4. Check Availability - GET (GET /check)
Check item availability using GET method with query parameter.

### 5. Direct Response (GET /bakery-response)
Get direct responses to bakery-related questions.

### 6. Server-Sent Events (GET /sse)
Stream real-time events from the server.

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
    version="1.1.0",  # Incremented version for SSE feature
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
        schema_extra = {
            "example": {
                "query": "Do you have chocolate cake?"
            }
        }

# Define the lifespan context manager for FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler for FastAPI
    This creates the FastAgent and manages its lifecycle
    """
    global agent_manager
    agent_manager = None  # Initialize to avoid UnboundLocalError
    
    try:
        logger.info("Starting application lifespan...")
        
        # Check if bakery_hours.json exists (for filesystem server)
        if os.path.exists("bakery_hours.json"):
            with open("bakery_hours.json", "r") as f:
                data = f.read()
                logger.info(f"Found bakery_hours.json: {data[:100]}...")
        else:
            logger.warning("bakery_hours.json not found!")
            
        # Create config file in the correct location
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
        logger.info(f"Created fastagent.config.yaml with explicit server definitions")
        
        # Log some debugging info
        logger.info(f"Python path: {sys.path}")
        logger.info(f"Current directory: {os.getcwd()}")
        logger.debug(f"Directory contents: {os.listdir(os.getcwd())}")
        
        # Create the bakery agent function first (without decorator)
        async def bakery_agent(agent, query: str):
            """
            MCP agent to check bakery inventory and hours
            """
            logger.info(f"Running bakery agent with query: {query}")
            
            # Check bakery hours first
            try:
                files = await agent.filesystem.list(path=".")
                logger.debug(f"Files found: {files}")
                
                if "bakery_hours.json" in files:
                    hours_data = await agent.filesystem.read_file(path="bakery_hours.json")
                    logger.debug(f"Bakery hours data: {hours_data}")
                else:
                    logger.warning("Bakery hours file not found!")
                
                # Fetch menu data
                try:
                    menu_response = await agent.fetch.fetch(url="https://example.com/bakery-menu")
                    logger.debug(f"Menu data: {menu_response}")
                except Exception as e:
                    logger.error(f"Error fetching menu: {e}")
            except Exception as e:
                logger.error(f"Error calling MCP servers: {e}")
            
            # Respond to the query (fallback to direct responses)
            response = process_bakery_query(query)  # Use the direct query processor
            return response

        # Create FastAgent instance with explicit config path and name
        agent_manager = FastAgent("BakeryAgent", config_path=config_path)
        logger.info("FastAgent instance created successfully")
        
        # Initialize the FastAgent explicitly 
        await agent_manager.initialize()
        logger.info("FastAgent initialized successfully")
        
        # Register the agent directly with FastAgent after initialization
        agent_manager.register_agent("bakery", bakery_agent)
        logger.info("Bakery agent registered successfully")
        
        # Here we yield control back to FastAPI
        yield
    
    except Exception as e:
        logger.error(f"Error during lifespan setup: {e}")
        logger.error(traceback.format_exc())
        # Allow app to start even if MCP fails
        yield
    
    finally:
        # Cleanup code for when the application is shutting down
        logger.info("Application shutdown...")
        try:
            if agent_manager is not None:
                await agent_manager.cleanup()
                logger.info("FastAgent cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

# Add the lifespan to the FastAPI app
app.router.lifespan_context = lifespan

# Global variable for the FastAgent manager
agent_manager = None

async def run_mcp_query(query: str) -> dict:
    """Run a query using MCP agent with fallback handling"""
    logger.info(f"Running MCP query: {query}")
    
    try:
        # Create a local copy of the agent manager
        global agent_manager
        
        if agent_manager is None:
            logger.error("Agent manager not initialized - falling back to direct response")
            return {
                "response": process_bakery_query(query),
                "source": "fallback"
            }
        
        # Run the bakery agent using the initialized manager
        async with agent_manager.run() as agent:
            # Agent should already be registered from lifespan
            if not hasattr(agent, "bakery"):
                 logger.error("Bakery agent not found on agent handler despite registration.")
                 raise RuntimeError("Agent not properly registered")
            
            result = await agent.invoke("bakery", query=query)
            return {"response": result, "source": "mcp"}
    
    except Exception as e:
        logger.error(f"Error running MCP query: {e}")
        logger.error(traceback.format_exc())
        
        # Provide a fallback response
        return {
            "response": process_bakery_query(query),
            "source": "fallback_after_error"
        }

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
        "version": "1.1.0" # Updated version
    }

# Status endpoint for system status
@app.get("/status", tags=["System"])
async def status():
    """
    Endpoint for checking system status
    
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
            status_info["mcp_status"] = {"status": "not_initialized", "message": "MCP agent manager not initialized"}
        elif hasattr(agent_manager, "context") and hasattr(agent_manager.context, "mcp_servers"):
            servers = agent_manager.context.mcp_servers
            status_info["mcp_status"] = {
                "status": "online", 
                "message": "MCP servers initialized",
                "servers": list(servers.keys()) if servers else []
            }
        else:
            status_info["mcp_status"] = {"status": "partial", "message": "MCP servers not fully initialized"}
        return status_info

    except Exception as e:
        logger.error(f"Global exception handler caught: {e}")
        logger.error(traceback.format_exc())
        return {
            "status": "error",
            "message": "Error checking system status",
            "error_type": str(type(e).__name__)
        }

# POST endpoint for checking item availability
@app.post("/check", tags=["Bakery Queries"])
async def check_availability_post(query_data: BakeryQuery):
    """
    POST endpoint for checking bakery item availability
    
    Accepts a JSON payload with a query string and returns information
    about bakery item availability or other requested details.
    
    Args:
        query_data: The BakeryQuery object containing the query string
        
    Returns:
        JSON object with response and source information
    
    Example:
        Request: {"query": "Do you have chocolate cake?"}
        Response: {"response": "Yes, our specialty chocolate cake is available all week!", "source": "mcp"}
    """
    logger.info(f"Processing POST request with query: {query_data.query}")
    query = query_data.query
    return await run_mcp_query(query)

# GET endpoint for checking item availability
@app.get("/check", tags=["Bakery Queries"])
async def check_availability_get(item: str = None):
    """
    GET endpoint for checking bakery item availability
    
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
        return {"response": "Please specify an item to check", "source": "error"}
    
    logger.info(f"Processing GET request for item: {item}")
    query = f"Can I order a {item}?"
    return await run_mcp_query(query)

# Backup endpoint for direct response
@app.get("/bakery-response", tags=["Bakery Queries"])
async def direct_bakery_response(question: str):
    """
    Endpoint for direct bakery responses (fallback)
    
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
        logger.error(f"Error in SSE generator: {e}")
        logger.error(traceback.format_exc())
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
    logger.error(f"Global exception handler caught: {exc}")
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={
            "response": "An unexpected error occurred with the bakery service. Please try again later.",
            "error_type": str(type(exc).__name__)
        }
    )

# Run the server directly if the script is executed
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)