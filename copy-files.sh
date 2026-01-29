#!/bin/bash
# Copy FM-Go files to installation directory

set -e

if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root (use sudo)"
    exit 1
fi

INSTALL_DIR="/opt/fm-go"
SERVICE_USER="fmgo"

echo "📋 Copying FM-Go files..."
echo ""

# Create directories
mkdir -p "$INSTALL_DIR"/{backend,frontend,config}

# Check if we're in the repo directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$SCRIPT_DIR/backend/fm_receiver.py" ]; then
    echo "✅ Found files in $SCRIPT_DIR"
    REPO_DIR="$SCRIPT_DIR"
else
    echo "⚠️  Files not found in current directory."
    echo "Please run this from the FM-Go repository directory, or"
    echo "we'll download files from GitHub..."
    REPO_DIR=""
fi

if [ -n "$REPO_DIR" ]; then
    # Copy from local repo
    echo "📁 Copying backend files..."
    cp -v "$REPO_DIR/backend/"*.py "$INSTALL_DIR/backend/" 2>/dev/null || echo "No backend files found"
    
    echo "📁 Copying frontend files..."
    cp -v "$REPO_DIR/frontend/"*.html "$INSTALL_DIR/frontend/" 2>/dev/null || echo "No frontend files found"
else
    # Download from GitHub
    echo "📥 Downloading files from GitHub..."
    
    echo "Downloading backend..."
    curl -sSL -o "$INSTALL_DIR/backend/fm_receiver.py" \
        https://raw.githubusercontent.com/rossingram/FM-Go/main/backend/fm_receiver.py
    
    echo "Downloading frontend..."
    curl -sSL -o "$INSTALL_DIR/frontend/index.html" \
        https://raw.githubusercontent.com/rossingram/FM-Go/main/frontend/index.html
fi

# Set ownership
echo ""
echo "👤 Setting ownership..."
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

# Verify files
echo ""
echo "✅ Verification:"
ls -la "$INSTALL_DIR/backend/"
ls -la "$INSTALL_DIR/frontend/"

echo ""
echo "✅ Files copied successfully!"
echo ""
echo "🚀 Restarting service..."
systemctl restart fm-go.service
sleep 2
systemctl status fm-go.service --no-pager -l | head -20
