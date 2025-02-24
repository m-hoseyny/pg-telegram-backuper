#!/bin/bash

# Create directory
./init.sh
# Start the Gunicorn server
gunicorn -b 0.0.0.0:9001 app:app

