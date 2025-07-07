#!/bin/bash

echo "Starting TerryFox LIMS React Development Server..."

# Change to frontend directory
cd frontend

# Set environment variables for React
export REACT_APP_API_URL=https://127.0.0.1:443/api
export PORT=3000
export BROWSER=none

echo "=== Configuration ==="
echo "API URL: $REACT_APP_API_URL"
echo "React Port: $PORT"
echo ""

echo "Starting React development server..."
echo "Once started, you can access the modern interface at:"
echo "http://localhost:3000"
echo ""
echo "Make sure the Django server is running with: sudo ./start_production_debug.sh"
echo ""

# Start the React development server
npm start 