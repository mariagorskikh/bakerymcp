import asyncio
import os
from fastapi import FastAPI, Body, Request
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

# Define the lifespan context manager for FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize MCP servers on startup
    print("Starting application lifespan...")
    
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
        
        # Try to use the agent
        try:
            # We need to manually validate if MCP servers are defined and available
            if "fetch" not in fast.context.mcp_servers or "filesystem" not in fast.context.mcp_servers:
                raise Exception(f"MCP servers not properly configured in fastagent.config.yaml. Make sure 'fetch' and 'filesystem' are properly defined")
            
            # Run the agent with a timeout to prevent hanging
            async with asyncio.timeout(10):
                async with fast.run() as agent:
                    print("Agent running for POST request")
                    response = await agent.bakery(query)
                    return {"response": response, "source": "mcp_agent"}
        except Exception as e:
            print(f"Agent error in POST method: {str(e)}")
            
            # Extract bakery item and day from query for a manual response
            items = ["bread", "cake", "croissant", "donut", "muffin", "pie"]
            days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            
            # Use simple text processing as a fallback
            query_lower = query.lower()
            
            found_item = None
            for item in items:
                if item in query_lower:
                    found_item = item
                    break
                    
            found_day = None
            for day in days:
                if day in query_lower:
                    found_day = day
                    break
                    
            if found_item and found_day:
                # Try to read bakery_hours.json manually
                try:
                    with open("bakery_hours.json", "r") as f:
                        hours = json.load(f)
                        if found_day in hours and hours[found_day]["open"]:
                            return {"response": f"Yes, we have {found_item} available on {found_day.title()}.", "source": "fallback"}
                        else:
                            return {"response": f"No, sorry. We're closed on {found_day.title()}.", "source": "fallback"}
                except:
                    return {"response": f"I believe we have {found_item} available on {found_day.title()}, but I couldn't verify our hours.", "source": "fallback"}
            elif found_item:
                return {"response": f"We have {found_item} on our menu, but please specify which day you want to order it.", "source": "fallback"}
            else:
                return {"response": "I couldn't determine what item you're asking about. Please specify the bakery item and day.", "source": "fallback"}
                
    except Exception as e:
        print(f"Error in POST method: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {"response": f"Sorry, we couldn't process your query due to a technical issue: {str(e)}", "source": "error"}

@app.get("/check")
async def check_availability_get(item: str):
    """Check if an item is available at the bakery (GET method)"""
    try:
        query = f"Can I order a {item}?"
        print(f"Processing GET request for item: {item}")
        
        # Try to use the agent
        try:
            # We need to manually validate if MCP servers are defined and available
            if "fetch" not in fast.context.mcp_servers or "filesystem" not in fast.context.mcp_servers:
                raise Exception(f"MCP servers not properly configured in fastagent.config.yaml. Make sure 'fetch' and 'filesystem' are properly defined")
            
            # Run the agent with a timeout to prevent hanging
            async with asyncio.timeout(10):
                async with fast.run() as agent:
                    print("Agent running for GET request")
                    response = await agent.bakery(query)
                    return {"response": response, "source": "mcp_agent"}
        except Exception as e:
            print(f"Agent error in GET method: {str(e)}")
            
            # Simple fallback logic
            bakery_items = ["bread", "cake", "croissant", "donut", "muffin", "pie"]
            item_lower = item.lower()
            
            for bakery_item in bakery_items:
                if bakery_item in item_lower:
                    try:
                        # Try to read bakery_hours.json to check if we're open today
                        with open("bakery_hours.json", "r") as f:
                            hours = json.load(f)
                            import datetime
                            today = datetime.datetime.now().strftime("%A").lower()
                            if today in hours and hours[today]["open"]:
                                return {"response": f"Yes, we have {bakery_item} available today ({today.title()}).", "source": "fallback"}
                            else:
                                return {"response": f"We have {bakery_item}, but we're closed today ({today.title()}).", "source": "fallback"}
                    except:
                        return {"response": f"Yes, we have {bakery_item} available in our bakery!", "source": "fallback"}
            
            return {"response": f"Sorry, we don't have '{item}' available in our bakery.", "source": "fallback"}
            
    except Exception as e:
        print(f"Error in GET method: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {"response": f"Sorry, we couldn't check availability for '{item}' due to a technical issue: {str(e)}", "source": "error"}

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
    
    # Try to safely add MCP server info
    try:
        status_info["mcp"] = {
            "servers_configured": list(fast.context.mcp_servers.keys()) if hasattr(fast, "context") and hasattr(fast.context, "mcp_servers") else [],
            "agents_configured": list(fast.agents.keys()) if hasattr(fast, "agents") else []
        }
    except Exception as e:
        status_info["mcp"] = {"error": str(e)}
    
    return status_info

# Main function to run everything
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port) 