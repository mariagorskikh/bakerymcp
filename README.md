# Bakery API

A simple API that checks if bakery items are available on specific days.

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