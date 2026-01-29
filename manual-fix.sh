#!/bin/bash
# Manual fix to download and install files

set -e

if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root (use sudo)"
    exit 1
fi

INSTALL_DIR="/opt/fm-go"
SERVICE_USER="fmgo"

echo "🔧 Manual Fix: Downloading FM-Go files"
echo "======================================"
echo ""

# Stop service
systemctl stop fm-go.service 2>/dev/null || true

# Create directories
mkdir -p "$INSTALL_DIR"/{backend,frontend,config}

# Download backend
echo "📥 Downloading backend..."
if curl -sSL -f -o "$INSTALL_DIR/backend/fm_receiver.py" \
    https://raw.githubusercontent.com/rossingram/FM-Go/main/backend/fm_receiver.py; then
    echo "✅ Backend downloaded"
    chmod +x "$INSTALL_DIR/backend/fm_receiver.py"
else
    echo "❌ Failed to download backend"
    exit 1
fi

# Download frontend
echo "📥 Downloading frontend..."
if curl -sSL -f -o "$INSTALL_DIR/frontend/index.html" \
    https://raw.githubusercontent.com/rossingram/FM-Go/main/frontend/index.html; then
    echo "✅ Frontend downloaded"
else
    echo "❌ Failed to download frontend"
    exit 1
fi

# Set ownership
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

# Verify
echo ""
echo "✅ Verification:"
ls -la "$INSTALL_DIR/backend/fm_receiver.py"
ls -la "$INSTALL_DIR/frontend/index.html"

# Start service
echo ""
echo "🚀 Starting service..."
systemctl start fm-go.service
sleep 2
systemctl status fm-go.service --no-pager -l | head -15
