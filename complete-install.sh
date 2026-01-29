#!/bin/bash
# Complete installation script - finishes setup after pip install failure

set -e

if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root (use sudo)"
    exit 1
fi

INSTALL_DIR="/opt/fm-go"
SERVICE_USER="fmgo"
SERVICE_NAME="fm-go.service"
PORT=8080

echo "🔧 Completing FM-Go installation..."
echo ""

# Check if install directory exists
if [ ! -d "$INSTALL_DIR" ]; then
    echo "❌ Installation directory not found. Please run install.sh first."
    exit 1
fi

# Install Flask dependencies
echo "📦 Installing Python dependencies..."
if [ -d "$INSTALL_DIR/venv" ]; then
    "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
    "$INSTALL_DIR/venv/bin/pip" install flask flask-cors
else
    echo "❌ Virtual environment not found. Please run install.sh first."
    exit 1
fi

# Ensure config directory exists
mkdir -p "$INSTALL_DIR/config"

# Create default configuration if it doesn't exist
if [ ! -f "$INSTALL_DIR/config/config.json" ]; then
    echo "⚙️  Creating default configuration..."
    cat > "$INSTALL_DIR/config/config.json" <<EOF
{
    "port": $PORT,
    "sample_rate": 240000,
    "frequency": 101500000,
    "gain": "auto",
    "audio_format": "mp3",
    "audio_bitrate": 128
}
EOF
fi

# Create default presets if they don't exist
if [ ! -f "$INSTALL_DIR/config/presets.json" ]; then
    echo "📻 Creating default presets..."
    cat > "$INSTALL_DIR/config/presets.json" <<EOF
{
    "presets": [
        {
            "id": 1,
            "name": "Default Station",
            "frequency": 101500000
        }
    ]
}
EOF
fi

# Set ownership
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR" 2>/dev/null || {
    echo "⚠️  Could not set ownership. Service user may not exist."
}

# Create systemd service
echo "🔧 Creating systemd service..."
cat > "/etc/systemd/system/$SERVICE_NAME" <<EOF
[Unit]
Description=FM-Go Radio Receiver
After=network.target sound.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR/backend
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/backend/fm_receiver.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

echo ""
echo "✅ Installation complete!"
echo ""
echo "🔍 Checking for RTL-SDR hardware..."
if command -v rtl_test >/dev/null 2>&1 && rtl_test -t 2>/dev/null | grep -q "Found"; then
    echo "✅ RTL-SDR detected!"
else
    echo "⚠️  RTL-SDR not detected. Please plug in your RTL-SDR dongle."
fi

echo ""
echo "🚀 Starting FM-Go service..."
systemctl start "$SERVICE_NAME"

sleep 2

if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "✅ Service started successfully!"
    echo ""
    PI_IP=$(hostname -I | awk '{print $1}')
    echo "🌐 Web interface available at:"
    echo "   http://${PI_IP}:${PORT}"
else
    echo "⚠️  Service failed to start. Check status with:"
    echo "   sudo systemctl status $SERVICE_NAME"
    echo "   sudo journalctl -u $SERVICE_NAME -f"
fi
