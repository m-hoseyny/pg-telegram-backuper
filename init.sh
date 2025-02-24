#!/bin/bash

# Create data directory
mkdir -p data

# Create empty connections.json if it doesn't exist
if [ ! -f data/connections.json ]; then
    echo '{"connections": []}' > data/connections.json
fi

# Set proper permissions
chmod 755 data
chmod 644 data/connections.json
