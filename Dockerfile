FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies with specific versions
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Set environment variables
ENV PORT=8000
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Set permissions for bakery_hours.json to ensure it's readable
RUN chmod 644 bakery_hours.json

# Expose port
EXPOSE 8000

# Command to run the application
CMD ["python", "bakery_api_with_mcp.py"] 