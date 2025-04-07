import asyncio
import os
import sys
from fastapi import FastAPI, Body
from pydantic import BaseModel
from mcp_agent.core.fastagent import FastAgent
import uvicorn

# Create FastAPI application
app = FastAPI(title="Bakery API", description="Bakery availability checker")

# Print debug information
print(f"Current working directory: {os.getcwd()}")
print(f"Files in current directory: {os.listdir('.')}")
if os.path.exists("fastagent.config.yaml"):
    print("Config file exists!")
    with open("fastagent.config.yaml", "r") as f:
        print(f"Config file contents: {f.read()}")
else:
    print("Config file does not exist!")

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
    return {"message": "Bakery API is running. Use /check endpoint to check item availability."}

@app.post("/check")
async def check_availability_post(query_data: BakeryQuery):
    """Check if an item is available at the bakery on a specific day (POST method)"""
    try:
        async with fast.run() as agent:
            response = await agent.bakery(query_data.query)
        return {"response": response}
    except Exception as e:
        return {"error": str(e)}

@app.get("/check")
async def check_availability_get(item: str):
    """Check if an item is available at the bakery (GET method)"""
    try:
        query = f"Can I order a {item}?"
        async with fast.run() as agent:
            response = await agent.bakery(query)
        return {"response": response}
    except Exception as e:
        print(f"Error in check_availability_get: {str(e)}")
        print(f"Agent configuration: {fast.context.to_dict()}")
        return {"error": str(e)}

# Main function to run everything
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port) 