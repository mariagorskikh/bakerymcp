FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies with specific versions
# Using --no-deps for fast-agent-mcp to avoid pulling in conflicting dependencies
# Then installing mcp explicitly at the correct version
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Set environment variables
ENV PORT=8000
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Set permissions for bakery_hours.json to ensure it's readable
RUN chmod 644 bakery_hours.json

# Create a directory for any potential file access
RUN mkdir -p /app/data && chmod 777 /app/data

# Expose port
EXPOSE 8000

# Command to run the application
CMD ["python", "bakery_api_with_mcp.py"] 