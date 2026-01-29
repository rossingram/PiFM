#!/bin/bash
# Check USB power and connection issues

echo "🔌 USB Power & Connection Diagnostics"
echo "======================================"
echo ""

echo "1️⃣  Checking USB devices:"
lsusb | grep -i "rtl\|283\|0bda" || echo "No RTL-SDR found"
echo ""

echo "2️⃣  Checking USB power management:"
if [ -d /sys/module/usbcore/parameters ]; then
    echo "USB autosuspend settings:"
    cat /sys/module/usbcore/parameters/autosuspend 2>/dev/null || echo "Not available"
else
    echo "USB power management info not available"
fi
echo ""

echo "3️⃣  Checking dmesg for USB events:"
dmesg | tail -30 | grep -i "usb\|rtl\|283" || echo "No recent USB events"
echo ""

echo "4️⃣  Testing device stability:"
echo "Running rtl_test multiple times to check for disconnects..."
for i in {1..3}; do
    echo "Test $i:"
    timeout 3 rtl_test -t 2>&1 | head -3
    sleep 1
done
echo ""

echo "5️⃣  Checking USB port power:"
if command -v uhubctl >/dev/null 2>&1; then
    echo "USB hub control available"
    uhubctl 2>/dev/null | head -10 || echo "Could not read USB hub info"
else
    echo "uhubctl not installed (optional tool for USB power control)"
fi
echo ""

echo "💡 Troubleshooting tips:"
echo "- Try a different USB port (preferably USB 2.0)"
echo "- Use a powered USB hub if available"
echo "- Check USB cable quality"
echo "- Try: echo 'on' | sudo tee /sys/bus/usb/devices/*/power/control"
echo "- Disable USB autosuspend if enabled"
