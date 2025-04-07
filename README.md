# Bakery API with MCP Support

This API demonstrates integrating Model Context Protocol (MCP) with a FastAPI application for a bakery availability checker.

## Features

- Checks if bakery items are available
- Uses MCP Fetch server for API calls
- Uses MCP Filesystem server for local file access
- Provides fallback responses when MCP servers are unavailable

## Deployment Options

### Option 1: Direct Deployment (Render)

1. Deploy to Render using the render.yaml configuration
2. Ensure the build.sh script installs all required dependencies
3. The API will run using the updated bakery_api_with_mcp.py file with proper MCP initialization

### Option 2: Docker Deployment

1. Build and run with Docker:
   ```
   docker build -t bakery-api .
   docker run -p 8000:8000 bakery-api
   ```

2. Or use Docker Compose:
   ```
   docker-compose up
   ```

## Troubleshooting MCP Server Issues

If you encounter MCP initialization errors:

1. Check that MCP module paths in fastagent.config.yaml are correct
2. Ensure you have the latest MCP package versions
3. Try running in a local environment first to validate configuration
4. Use the Docker approach for more consistent environment isolation

## API Usage

- `GET /`: Check API status
- `GET /check?item=bread`: Check item availability (GET method)
- `POST /check`: Check item availability with JSON request body:
  ```json
  {
    "query": "Can I order a cake for Saturday?"
  }
  ```

## Endpoints

- `GET /` - Returns basic API info
- `POST /check` - Checks if an item is available on a specific day

## How to Use

Send a POST request to `/check` with a query string like:

```
"Can I order a croissant on Monday?"
```

The API will check:
1. If the bakery is open on that day
2. If the item is on the menu

## Deployment

This API is deployed on Render. 