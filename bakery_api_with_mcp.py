import asyncio
import os
from fastapi import FastAPI, Body
from pydantic import BaseModel
from mcp_agent.core.fastagent import FastAgent
import uvicorn

# Create FastAPI application
app = FastAPI(title="Bakery API", description="Bakery availability checker with MCP servers")

# Create FastAgent with explicit config path
fast = FastAgent("Bakery Agent", config_path="fastagent.config.yaml")

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
    return {"message": "Bakery API is running with MCP support. Use /check endpoint to check item availability."}

@app.post("/check")
async def check_availability_post(query_data: BakeryQuery):
    """Check if an item is available at the bakery on a specific day (POST method)"""
    try:
        # Print agent and context information for debugging
        print(f"Agent context: {fast.context}")
        print(f"Available agents: {fast.agents}")
        print(f"Server config: {fast.context.mcp_servers}")
        
        async with fast.run() as agent:
            response = await agent.bakery(query_data.query)
        return {"response": response}
    except Exception as e:
        print(f"Error in POST method: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

@app.get("/check")
async def check_availability_get(item: str):
    """Check if an item is available at the bakery (GET method)"""
    try:
        query = f"Can I order a {item}?"
        print(f"Processing GET request for item: {item}")
        print(f"Agent context: {fast.context}")
        print(f"Available agents: {fast.agents}")
        print(f"Server config: {fast.context.mcp_servers}")
        
        # First try a simple approach in case MCP servers are not working
        bakery_items = ["bread", "cake", "croissant", "donut", "muffin", "pie"]
        
        # Check if the item is in our predefined list
        for bakery_item in bakery_items:
            if bakery_item in item.lower():
                return {"response": f"Yes, we have {bakery_item} available in our bakery!"}
        
        # If we got here, try using the agent
        async with fast.run() as agent:
            response = await agent.bakery(query)
        return {"response": response}
    except Exception as e:
        print(f"Error in GET method: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Fallback response if agent fails
        return {"response": f"Sorry, we couldn't check availability for '{item}' due to a technical issue. Please try again later."}

# Main function to run everything
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port) 