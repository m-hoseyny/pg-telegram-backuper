FROM python:3.9-slim

# Install PostgreSQL client
RUN apt-get update && \
    apt-get install -y postgresql-client && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /app/data && \
    echo '{"connections": []}' > /app/data/connections.json && \
    chmod 755 /app/data && \
    chmod 644 /app/data/connections.json

# Volume for persistent data
VOLUME ["/app/data"]

# Run the application
ENTRYPOINT ["./start.sh"]
