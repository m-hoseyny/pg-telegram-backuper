FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory and initialize connections.json
RUN mkdir -p /app/data && \
    echo '{"connections": []}' > /app/data/connections.json && \
    chmod -R 755 /app/data && \
    chmod 644 /app/data/connections.json && \
    chmod +x start.sh

# Run the application
ENTRYPOINT ["./start.sh"]
