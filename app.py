from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello from the simple bakery API!"}

@app.get("/check")
def check_item(item: str):
    bakery_items = ["bread", "cake", "croissant", "donut", "muffin", "pie"]
    item_lower = item.lower()
    
    for bakery_item in bakery_items:
        if bakery_item in item_lower:
            return {"response": f"Yes, we have {bakery_item} available in our bakery!"}
    
    return {"response": f"Sorry, we don't have '{item}' available. Our selection includes: {', '.join(bakery_items)}"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 