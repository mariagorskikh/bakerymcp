#!/usr/bin/env python3
import os
import sys
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("bakery_api_simplified:app", host="0.0.0.0", port=port) 