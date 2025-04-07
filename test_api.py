import requests
import json

def test_api():
    """
    Test the bakery API by sending a few sample queries
    """
    base_url = "http://localhost:8000"
    
    # Test the root endpoint
    response = requests.get(base_url)
    print(f"Root endpoint response: {response.json()}")
    
    # Test the check endpoint with a valid day and item
    query = "Can I order a croissant on Monday?"
    response = requests.post(
        f"{base_url}/check",
        json=query  # Send the query string directly, not as a dict
    )
    print(f"\nQuery: {query}")
    print(f"Response: {response.json()}")
    
    # Test with a day when bakery is closed
    query = "Can I order a cake on Tuesday?"
    response = requests.post(
        f"{base_url}/check",
        json=query  # Send the query string directly, not as a dict
    )
    print(f"\nQuery: {query}")
    print(f"Response: {response.json()}")

if __name__ == "__main__":
    test_api() 