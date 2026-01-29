#!/bin/bash
# Debug RTL-SDR detection issues

echo "🔍 RTL-SDR Detection Debug"
echo "=========================="
echo ""

echo "1️⃣  Testing as current user ($(whoami)):"
rtl_test -t 2>&1 | head -5
echo ""

echo "2️⃣  Testing as service user (fmgo):"
sudo -u fmgo rtl_test -t 2>&1 | head -5
echo ""

echo "3️⃣  Checking groups for fmgo user:"
groups fmgo
echo ""

echo "4️⃣  Checking USB device permissions:"
ls -la /dev/bus/usb/*/* 2>/dev/null | grep -i "0bda\|283" || echo "No RTL-SDR USB devices found"
echo ""

echo "5️⃣  Checking udev rules:"
if [ -f /etc/udev/rules.d/20-rtl-sdr.rules ]; then
    echo "✅ Udev rules file exists:"
    cat /etc/udev/rules.d/20-rtl-sdr.rules
else
    echo "❌ Udev rules file not found"
fi
echo ""

echo "6️⃣  Testing Python detection as service user:"
sudo -u fmgo /opt/fm-go/venv/bin/python3 << 'PYEOF'
import subprocess
import sys

try:
    result = subprocess.run(['rtl_test', '-t'], capture_output=True, timeout=5)
    output = result.stdout.decode('utf-8', errors='replace') + result.stderr.decode('utf-8', errors='replace')
    
    print(f"Return code: {result.returncode}")
    print(f"Output length: {len(output)}")
    print(f"First 300 chars:")
    print(output[:300])
    print()
    
    if 'Found' in output and 'device' in output.lower():
        print("✅ Python detection: RTL-SDR FOUND")
        if any(tuner in output for tuner in ['R820T', 'E4000', 'tuner', 'Supported gain']):
            print("✅ Tuner detected")
        else:
            print("⚠️  Device found but tuner unclear")
    else:
        print("❌ Python detection: RTL-SDR NOT FOUND")
        print("Full output:")
        print(output)
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
PYEOF

echo ""
echo "7️⃣  Checking service logs:"
sudo journalctl -u fm-go.service -n 20 --no-pager | grep -i "rtl\|detect" || echo "No RTL-SDR related logs found"
