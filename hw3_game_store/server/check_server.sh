#!/bin/bash
# Check Game Store Server Status

echo "=== Game Store Server Status ==="
echo ""

# Check processes
echo "1. Process Status:"
if pgrep -f "python3 main.py" > /dev/null; then
    echo "   ✓ Server is running"
    ps aux | grep "python3 main.py" | grep -v grep
else
    echo "   ✗ Server is not running"
fi

echo ""
echo "2. Port Status:"

# Check port 8888
if lsof -i :8888 > /dev/null 2>&1; then
    echo "   Port 8888: IN USE"
    lsof -i :8888 | grep LISTEN
else
    echo "   Port 8888: FREE"
fi

# Check port 8889
if lsof -i :8889 > /dev/null 2>&1; then
    echo "   Port 8889: IN USE"
    lsof -i :8889 | grep LISTEN
else
    echo "   Port 8889: FREE"
fi

# Check game server ports (9000-9010)
echo ""
echo "3. Game Server Ports (9000-9010):"
used_ports=0
for port in {9000..9010}; do
    if lsof -i :$port > /dev/null 2>&1; then
        echo "   Port $port: IN USE"
        ((used_ports++))
    fi
done
if [ $used_ports -eq 0 ]; then
    echo "   All ports free"
fi

echo ""
echo "4. Log Files:"
if [ -f "logs/server.log" ]; then
    echo "   Last 5 lines of server.log:"
    tail -5 logs/server.log | sed 's/^/   /'
else
    echo "   No log file found"
fi