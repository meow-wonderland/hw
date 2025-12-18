#!/bin/bash
# Stop Game Store Server

echo "=== Stopping Game Store Server ==="

# Check if server is running
if pgrep -f "python3 main.py" > /dev/null; then
    echo "Killing server processes..."
    pkill -f "python3 main.py"
    sleep 1
    
    # Force kill if still running
    if pgrep -f "python3 main.py" > /dev/null; then
        echo "Force killing..."
        pkill -9 -f "python3 main.py"
        sleep 1
    fi
    
    echo "✓ Server stopped"
else
    echo "⚠️  Server is not running"
fi

# Check if ports are freed
echo ""
echo "Checking ports..."
if lsof -i :8888 > /dev/null 2>&1; then
    echo "⚠️  Port 8888 is still in use"
    lsof -i :8888
else
    echo "✓ Port 8888 is free"
fi

if lsof -i :8889 > /dev/null 2>&1; then
    echo "⚠️  Port 8889 is still in use"
    lsof -i :8889
else
    echo "✓ Port 8889 is free"
fi