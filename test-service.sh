#!/bin/bash
# Test script to run the service manually and see errors

echo "🧪 Testing FM-Go Service"
echo "======================="
echo ""

# Check Python
echo "1️⃣  Checking Python..."
/opt/fm-go/venv/bin/python --version
echo ""

# Check Flask import
echo "2️⃣  Testing Flask import..."
/opt/fm-go/venv/bin/python -c "from flask import Flask; print('✅ Flask import OK')" 2>&1
echo ""

# Check if script exists
echo "3️⃣  Checking script file..."
if [ -f /opt/fm-go/backend/fm_receiver.py ]; then
    echo "✅ Script exists"
    ls -la /opt/fm-go/backend/fm_receiver.py
else
    echo "❌ Script NOT found!"
    exit 1
fi
echo ""

# Try to run the script as the service user
echo "4️⃣  Attempting to run script (will show errors)..."
echo "Running as fmgo user..."
sudo -u fmgo /opt/fm-go/venv/bin/python /opt/fm-go/backend/fm_receiver.py 2>&1 | head -30
