#!/bin/bash
set -e

# FM-Go Installer
# One-command installation for Raspberry Pi FM radio receiver

echo "🎧 FM-Go Installer"
echo "=================="
echo ""

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ] || ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    echo "⚠️  Warning: This installer is designed for Raspberry Pi"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check for root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root (use sudo)"
    exit 1
fi

INSTALL_DIR="/opt/fm-go"
SERVICE_USER="fmgo"
SERVICE_NAME="fm-go.service"
PORT=8080
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "📦 Installing system dependencies..."

# Update package list
apt-get update -qq

# Install required packages
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    rtl-sdr \
    sox \
    libsox-fmt-mp3 \
    ffmpeg \
    git \
    || {
    echo "❌ Failed to install system dependencies"
    exit 1
}

# Blacklist DVB-T drivers to prevent conflicts with RTL-SDR
if [ ! -f /etc/modprobe.d/blacklist-rtl.conf ]; then
    echo "📝 Blacklisting DVB-T drivers..."
    cat > /etc/modprobe.d/blacklist-rtl.conf <<EOF
blacklist dvb_usb_rtl28xxu
blacklist rtl2832
blacklist rtl2830
EOF
fi

# Create service user
if ! id "$SERVICE_USER" &>/dev/null; then
    echo "👤 Creating service user..."
    useradd -r -s /bin/false "$SERVICE_USER" || true
fi

# Create installation directory
echo "📁 Creating installation directory..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"/{backend,frontend,config}

# Copy files
echo "📋 Copying files..."
if [ -d "$SCRIPT_DIR/backend" ]; then
    cp -r "$SCRIPT_DIR/backend"/* "$INSTALL_DIR/backend/" 2>/dev/null || true
fi
if [ -d "$SCRIPT_DIR/frontend" ]; then
    cp -r "$SCRIPT_DIR/frontend"/* "$INSTALL_DIR/frontend/" 2>/dev/null || true
fi

# Create Python virtual environment
echo "🐍 Setting up Python environment..."
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    "$INSTALL_DIR/venv/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
else
    # Fallback: install only what we actually need
    "$INSTALL_DIR/venv/bin/pip" install flask flask-cors
fi

# Create default configuration
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

# Create default presets
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

# Set ownership
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

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

# Reload systemd and enable service
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

echo ""
echo "✅ Installation complete!"
echo ""
echo "🔍 Checking for RTL-SDR hardware..."
if rtl_test -t 2>/dev/null | grep -q "Found"; then
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
else
    echo "⚠️  Service may have issues. Check status with: sudo systemctl status $SERVICE_NAME"
fi

echo ""
echo "🌐 Web interface will be available at:"
echo "   http://$(hostname -I | awk '{print $1}'):$PORT"
echo ""
echo "📊 Check service status: sudo systemctl status $SERVICE_NAME"
echo "📝 View logs: sudo journalctl -u $SERVICE_NAME -f"
