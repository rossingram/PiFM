#!/bin/bash
# Debug script to check service status and logs

echo "🔍 FM-Go Service Debug Information"
echo "==================================="
echo ""

echo "1️⃣  Service Status:"
sudo systemctl status fm-go.service --no-pager -l
echo ""

echo "2️⃣  Recent Service Logs:"
sudo journalctl -u fm-go.service -n 50 --no-pager
echo ""

echo "3️⃣  Checking if service file exists:"
if [ -f /etc/systemd/system/fm-go.service ]; then
    echo "✅ Service file exists"
    echo ""
    echo "Service file contents:"
    cat /etc/systemd/system/fm-go.service
else
    echo "❌ Service file NOT found!"
fi
echo ""

echo "4️⃣  Checking installation directory:"
if [ -d /opt/fm-go ]; then
    echo "✅ Installation directory exists"
    ls -la /opt/fm-go/
    echo ""
    echo "Backend files:"
    ls -la /opt/fm-go/backend/ 2>/dev/null || echo "Backend directory not found"
    echo ""
    echo "Frontend files:"
    ls -la /opt/fm-go/frontend/ 2>/dev/null || echo "Frontend directory not found"
else
    echo "❌ Installation directory NOT found!"
fi
echo ""

echo "5️⃣  Checking Python virtual environment:"
if [ -d /opt/fm-go/venv ]; then
    echo "✅ Virtual environment exists"
    echo ""
    echo "Installed packages:"
    /opt/fm-go/venv/bin/pip list 2>/dev/null || echo "Could not list packages"
else
    echo "❌ Virtual environment NOT found!"
fi
echo ""

echo "6️⃣  Testing Python script directly:"
if [ -f /opt/fm-go/backend/fm_receiver.py ]; then
    echo "Attempting to run Python script (will show import errors):"
    sudo -u fmgo /opt/fm-go/venv/bin/python /opt/fm-go/backend/fm_receiver.py --help 2>&1 | head -20 || \
    /opt/fm-go/venv/bin/python /opt/fm-go/backend/fm_receiver.py --help 2>&1 | head -20 || \
    echo "Could not run script"
else
    echo "❌ Python script NOT found!"
fi
echo ""

echo "7️⃣  Checking port 8080:"
if command -v netstat >/dev/null 2>&1; then
    netstat -tuln | grep 8080 || echo "Port 8080 not in use"
elif command -v ss >/dev/null 2>&1; then
    ss -tuln | grep 8080 || echo "Port 8080 not in use"
else
    echo "Could not check port"
fi
