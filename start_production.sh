#!/bin/bash

echo "Starting TerryFox LIMS in production mode..."

# Kill any existing gunicorn processes
pkill -f gunicorn || true

# Change to project directory
cd /home/hadriengt/project/lims/terryfox-lims

# Start Gunicorn in the background
./gunicorn_start.sh &

# Wait a moment for Gunicorn to start
sleep 2

# Display access information
echo ""
echo "==========================================="
echo "TerryFox LIMS is now running!"
echo "Access it at: http://localhost:8000"
echo "               http://$(hostname -I | awk '{print $1}'):8000"
echo "==========================================="
echo ""
echo "Press Ctrl+C to stop the server"

# Keep the script running
tail -f /dev/null 