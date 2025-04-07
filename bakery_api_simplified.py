import asyncio
from fastapi import FastAPI, Body
from mcp_agent.core.fastagent import FastAgent
import uvicorn
import random

# Create FastAPI application
app = FastAPI(title="Bakery API", description="Bakery availability checker")

# Create FastAgent
fast = FastAgent("Bakery Agent")

# Define bakery agent
@fast.agent(
    name="bakery",
    instruction="""You are a helpful bakery assistant that checks if items are available.
    
    When a customer asks about a bakery item, respond with YES or NO and a brief explanation.
    For this demo, randomly decide if items are available.""",
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
async def check_availability_post(query: str = Body(..., example="Can I order a croissant on Monday?")):
    """Check if an item is available at the bakery on a specific day (POST method)"""
    try:
        async with fast.run() as agent:
            response = await agent.bakery(query)
        return {"response": response}
    except Exception as e:
        return {"error": str(e)}

@app.get("/check")
async def check_availability_get(item: str):
    """Check if an item is available at the bakery (GET method)"""
    # Simplified implementation that doesn't use MCP servers
    bakery_items = ["bread", "cake", "croissant", "donut", "muffin", "pie"]
    days_open = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    
    item_available = item.lower() in bakery_items
    day_mentioned = any(day.lower() in item.lower() for day in days_open)
    
    if item_available:
        if day_mentioned:
            # Randomly decide availability for demonstration
            is_available = random.choice([True, False])
            if is_available:
                response = f"YES, we have {item} available today!"
            else:
                response = f"NO, unfortunately we're out of {item} today. Try again tomorrow!"
        else:
            response = f"YES, {item} is on our menu, but please specify which day you want it."
    else:
        response = f"NO, we don't carry {item} at our bakery. Would you like to try something else?"
    
    return {"response": response}

# Main function to run everything
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port) 