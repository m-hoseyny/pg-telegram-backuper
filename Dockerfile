FROM python:3.9-slim

# Add PostgreSQL repository and install system dependencies
RUN apt-get update \
    && apt-get install -y curl gnupg2 lsb-release gcc python3-dev \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/postgresql-keyring.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/postgresql-keyring.gpg] http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/postgresql.list \
    && apt-get update \
    && apt-get install -y postgresql-client-16 \
    && rm -rf /var/lib/apt/lists/* \
    && pg_dump --version

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
