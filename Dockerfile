FROM python:3.9-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose the port the app runs on
EXPOSE 8000

# Set environment variables
ENV PORT=8000

# Command to run the application
CMD ["python", "bakery_api_with_mcp.py"] 