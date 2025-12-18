#!/bin/bash
# Start Game Store Server
# Automatically kills old processes and finds available ports

echo "=== Game Store Server Startup ==="
echo ""

# Change to server directory
cd "$(dirname "$0")"

# Check if old server is running
if pgrep -f "python3 main.py" > /dev/null; then
    echo "⚠️  Found old server process, killing..."
    pkill -f "python3 main.py"
    sleep 1
    
    # Force kill if still running
    if pgrep -f "python3 main.py" > /dev/null; then
        echo "Force killing..."
        pkill -9 -f "python3 main.py"
        sleep 1
    fi
    
    echo "✓ Old process killed"
    echo ""
fi

# Check ports
echo "Checking ports..."
if lsof -i :8888 > /dev/null 2>&1; then
    echo "⚠️  Port 8888 is in use (will auto-find alternative)"
fi
if lsof -i :8889 > /dev/null 2>&1; then
    echo "⚠️  Port 8889 is in use (will auto-find alternative)"
fi
echo ""

# Start server
echo "Starting server..."
python3 main.py

# If main.py exits, show message
echo ""
echo "Server stopped"