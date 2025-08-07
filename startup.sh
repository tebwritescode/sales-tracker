#!/bin/bash

echo "Starting Sales Tracker application..."

# Ensure directories exist
mkdir -p /app/data /app/uploads

# Start the application
echo "Starting Gunicorn..."
exec gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 app:app