#!/bin/bash
# Fix script for Pi installation - skip pyaudio and complete setup

set -e

INSTALL_DIR="/opt/fm-go"

if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root (use sudo)"
    exit 1
fi

echo "🔧 Fixing FM-Go installation..."
echo ""

# Install only Flask dependencies (skip pyaudio)
echo "📦 Installing Python dependencies (Flask only)..."
"$INSTALL_DIR/venv/bin/pip" install flask flask-cors --no-deps || {
    echo "⚠️  Trying with dependencies..."
    "$INSTALL_DIR/venv/bin/pip" install flask flask-cors
}

echo ""
echo "✅ Python dependencies installed!"
echo ""
echo "🚀 Starting FM-Go service..."
systemctl start fm-go.service || true

sleep 2

if systemctl is-active --quiet fm-go.service; then
    echo "✅ Service started successfully!"
    echo ""
    echo "🌐 Web interface available at:"
    echo "   http://$(hostname -I | awk '{print $1}'):8080"
else
    echo "⚠️  Service may have issues. Check status with:"
    echo "   sudo systemctl status fm-go.service"
    echo "   sudo journalctl -u fm-go.service -f"
fi
