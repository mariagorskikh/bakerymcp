import asyncio
import json
import random
from fastapi import FastAPI, Body
from pydantic import BaseModel
import uvicorn

# Create FastAPI application
app = FastAPI(title="Bakery API", description="Bakery availability checker")

# Define request model for JSON input
class BakeryQuery(BaseModel):
    query: str

# Load bakery hours from file
def get_bakery_hours():
    try:
        with open("bakery_hours.json", "r") as f:
            return json.load(f)
    except Exception:
        # Fallback data if file can't be read
        return {
            "Monday": {"open": True, "hours": "7:00 AM - 7:00 PM"},
            "Tuesday": {"open": True, "hours": "7:00 AM - 7:00 PM"},
            "Wednesday": {"open": True, "hours": "7:00 AM - 7:00 PM"},
            "Thursday": {"open": True, "hours": "7:00 AM - 7:00 PM"},
            "Friday": {"open": True, "hours": "7:00 AM - 9:00 PM"},
            "Saturday": {"open": True, "hours": "8:00 AM - 9:00 PM"},
            "Sunday": {"open": False, "hours": "Closed"}
        }

# Check menu items
def check_menu_items():
    # Simulate menu items
    return ["bread", "cake", "croissant", "donut", "muffin", "pie", "cookie"]

# Helper function to extract day from query
def extract_day_from_query(query):
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    for day in days:
        if day.lower() in query.lower():
            return day
    return None

# Helper function to extract item from query
def extract_item_from_query(query):
    menu_items = check_menu_items()
    for item in menu_items:
        if item.lower() in query.lower():
            return item
    return None

# Define API endpoints
@app.get("/")
async def root():
    """Root endpoint that returns basic API info"""
    return {"message": "Bakery API is running. Use /check endpoint to check item availability."}

@app.post("/check")
async def check_availability_post(query_data: BakeryQuery):
    """Check if an item is available at the bakery on a specific day (POST method)"""
    try:
        query = query_data.query
        day = extract_day_from_query(query)
        item = extract_item_from_query(query)
        
        response = check_availability(item, day)
        return {"response": response}
    except Exception as e:
        return {"error": str(e)}

@app.get("/check")
async def check_availability_get(item: str):
    """Check if an item is available at the bakery (GET method)"""
    try:
        # Extract day if it's in the item parameter
        day = extract_day_from_query(item)
        # Clean up item string
        clean_item = extract_item_from_query(item) or item.split()[0]
        
        response = check_availability(clean_item, day)
        return {"response": response}
    except Exception as e:
        return {"error": str(e)}

def check_availability(item, day=None):
    bakery_hours = get_bakery_hours()
    menu_items = check_menu_items()
    
    # Check if item is on menu
    item_on_menu = any(menu_item.lower() == item.lower() for menu_item in menu_items)
    
    if not item_on_menu:
        return f"NO, we don't carry {item} at our bakery. Would you like to try something else?"
    
    # If no day specified
    if not day:
        return f"YES, {item} is on our menu. Please specify which day you want it."
    
    # Check if bakery is open on that day
    if day in bakery_hours and bakery_hours[day]["open"]:
        return f"YES, we have {item} available on {day}! Our hours are {bakery_hours[day]['hours']}."
    elif day in bakery_hours:
        return f"NO, our bakery is closed on {day}. We're open {', '.join([d for d in bakery_hours if bakery_hours[d]['open']])}."
    else:
        return f"I'm not sure about that day, but {item} is on our menu. We're open Monday through Saturday."

# Main function to run everything
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port) 