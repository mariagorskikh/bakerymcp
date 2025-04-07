from fastapi import FastAPI, Body
from pydantic import BaseModel
import uvicorn

# Create FastAPI application
app = FastAPI(title="Bakery API", description="Bakery availability checker")

# Define request model for JSON input
class BakeryQuery(BaseModel):
    query: str

# Define API endpoints
@app.get("/")
async def root():
    """Root endpoint that returns basic API info"""
    return {"message": "Bakery API is running. Use /check endpoint to check item availability."}

@app.post("/check")
async def check_availability_post(query_data: BakeryQuery):
    """Check if an item is available at the bakery (POST method)"""
    return {"response": f"We received your query: '{query_data.query}'. Our bakery is open Monday-Saturday and closed on Sunday."}

@app.get("/check")
async def check_availability_get(item: str):
    """Check if an item is available at the bakery (GET method)"""
    bakery_items = ["bread", "cake", "croissant", "donut", "muffin", "pie"]
    
    # Simple check if the item is in our predefined list
    item_lower = item.lower()
    for bakery_item in bakery_items:
        if bakery_item in item_lower:
            return {"response": f"Yes, we have {bakery_item} available in our bakery!"}
    
    # If no matches, return a generic message
    return {"response": f"Sorry, we don't have '{item}' available. Our selection includes: {', '.join(bakery_items)}"}

# Main function to run everything
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port) 