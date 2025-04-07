#!/bin/bash
# Start script to use the correct uvicorn

# Use Python's module system to run the correct uvicorn
python -m uvicorn bakery_api_simplified:app --host 0.0.0.0 --port $PORT 