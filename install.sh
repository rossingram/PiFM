#!/bin/bash
set -e

# PiFM Installer
# One-command installation for Raspberry Pi FM radio receiver

echo "🎧 PiFM Installer"
echo "================="
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

INSTALL_DIR="/opt/pifm"
SERVICE_USER="pifm"
SERVICE_NAME="pifm.service"
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

# Add service user to groups for USB device access
echo "👤 Configuring USB permissions..."
usermod -a -G plugdev "$SERVICE_USER" 2>/dev/null || true
usermod -a -G dialout "$SERVICE_USER" 2>/dev/null || true

# Create udev rules for RTL-SDR
echo "📝 Creating udev rules for RTL-SDR..."
cat > /etc/udev/rules.d/20-rtl-sdr.rules <<'UDEVEOF'
# RTL-SDR dongles
SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2838", GROUP="plugdev", MODE="0666", SYMLINK+="rtl_sdr"
SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2832", GROUP="plugdev", MODE="0666", SYMLINK+="rtl_sdr"
UDEVEOF
udevadm control --reload-rules 2>/dev/null || true
udevadm trigger 2>/dev/null || true

# Create installation directory
echo "📁 Creating installation directory..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"/{backend,frontend,config}

# Check if this is a reinstallation
if [ -d "$INSTALL_DIR/backend" ] && [ -f "$INSTALL_DIR/backend/fm_receiver.py" ]; then
    echo "ℹ️  Detected existing installation. Reinstalling..."
fi

# Copy files
echo "📋 Copying files..."
if [ -d "$SCRIPT_DIR/backend" ] && [ -f "$SCRIPT_DIR/backend/fm_receiver.py" ]; then
    # Local installation - copy from repo
    echo "📁 Copying from local repository..."
    cp -r "$SCRIPT_DIR/backend"/* "$INSTALL_DIR/backend/" 2>/dev/null || true
    cp -r "$SCRIPT_DIR/frontend"/* "$INSTALL_DIR/frontend/" 2>/dev/null || true
else
    # Remote installation via curl - download from GitHub
    echo "📥 Downloading files from GitHub..."
    if curl -sSL -f -o "$INSTALL_DIR/backend/fm_receiver.py" \
        https://raw.githubusercontent.com/rossingram/PiFM/main/backend/fm_receiver.py; then
        echo "✅ Downloaded backend/fm_receiver.py"
        chmod +x "$INSTALL_DIR/backend/fm_receiver.py"
    else
        echo "❌ Failed to download backend file"
        exit 1
    fi
    
    if curl -sSL -f -o "$INSTALL_DIR/frontend/index.html" \
        https://raw.githubusercontent.com/rossingram/PiFM/main/frontend/index.html; then
        echo "✅ Downloaded frontend/index.html"
    else
        echo "❌ Failed to download frontend file"
        exit 1
    fi
fi

# Verify files were copied
if [ ! -f "$INSTALL_DIR/backend/fm_receiver.py" ]; then
    echo "❌ Error: Backend file not found after copy/download!"
    exit 1
fi
if [ ! -f "$INSTALL_DIR/frontend/index.html" ]; then
    echo "⚠️  Warning: Frontend file not found, but continuing..."
fi

# Create Python virtual environment
echo "🐍 Setting up Python environment..."
if [ -d "$INSTALL_DIR/venv" ]; then
    echo "ℹ️  Virtual environment already exists. Updating..."
else
    python3 -m venv "$INSTALL_DIR/venv"
fi
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip --quiet
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    "$INSTALL_DIR/venv/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" --quiet
else
    # Fallback: install only what we actually need
    echo "📦 Installing Flask dependencies..."
    "$INSTALL_DIR/venv/bin/pip" install flask flask-cors --quiet
fi

# Create default configuration
echo "⚙️  Creating default configuration..."
cat > "$INSTALL_DIR/config/config.json" <<EOF
{
    "port": $PORT,
    "sample_rate": 170000,
    "frequency": 101500000,
    "gain": 0,
    "audio_format": "mp3",
    "audio_bitrate": 128
}
EOF

# Create default presets
cat > "$INSTALL_DIR/config/presets.json" <<EOF
{
    "presets": [
        {"id": 1, "name": "570 AM", "frequency": 570000},
        {"id": 2, "name": "710 AM", "frequency": 710000},
        {"id": 3, "name": "1150 AM", "frequency": 1150000},
        {"id": 4, "name": "98.7 FM HD2", "frequency": 98700000},
        {"id": 5, "name": "102.7 FM", "frequency": 102700000},
        {"id": 6, "name": "106.7 FM", "frequency": 106700000}
    ]
}
EOF

# Set ownership
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

# Create systemd service
echo "🔧 Creating systemd service..."
cat > "/etc/systemd/system/$SERVICE_NAME" <<EOF
[Unit]
Description=PiFM Radio Receiver
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

# Stop service if it exists (for reinstallation)
if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    echo "🛑 Stopping existing service..."
    systemctl stop "$SERVICE_NAME" || true
fi

# Reload systemd and enable service
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

echo ""
echo "✅ Installation complete!"
echo ""
echo "🔍 Checking for RTL-SDR hardware..."
# Test as current user first
if command -v rtl_test >/dev/null 2>&1; then
    if rtl_test -t 2>&1 | grep -q "Found"; then
        echo "✅ RTL-SDR detected (as root)!"
    elif sudo -u "$SERVICE_USER" rtl_test -t 2>&1 | grep -q "Found"; then
        echo "✅ RTL-SDR detected (as service user)!"
    else
        echo "⚠️  RTL-SDR not detected by installer check."
        echo "   This may be a permissions issue. The service will check on startup."
        echo "   If RTL-SDR is plugged in, check the web interface status page."
    fi
else
    echo "⚠️  rtl_test command not found"
fi

echo ""
echo "🚀 Starting PiFM service..."
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
