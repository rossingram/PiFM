# FM-Go Troubleshooting

## RTL-SDR not detected

- **Plug in the SDR** and wait a few seconds. The web UI shows "RTL-SDR ✅ Detected" when the device is present (USB only; we don’t open the device for status).
- **Reinstall** so udev rules and user groups are applied:
  ```bash
  cd ~/FM-Go && sudo ./install.sh
  ```
- **Unload conflicting drivers** (if you use TV tuner software):
  ```bash
  sudo modprobe -r dvb_usb_rtl28xxu rtl2832 rtl2830
  sudo reboot
  ```

## RTL-SDR drops offline when you tap Play

If the SDR shows **✅ Detected** but **disconnects as soon as you hit Play**, the device is dropping when we open it for streaming. Software already keeps load low (one open, gain 0, 170k sample rate); the cause is usually **hardware or USB**.

Try in order:

1. **Powered USB 2.0 hub** – Put a *powered* USB 2.0 hub between the Pi and the RTL-SDR.
2. **Different RTL-SDR dongle** – Some units are unstable on Pi; try another.
3. **Different USB port** – Prefer USB 2.0 if available; try each port.
4. **Official Pi power supply** – Undervoltage causes USB dropouts. Use 5V 2.5A+ (Pi 3B+) or 5V 3A+ (Pi 4/5).

**Quick test without FM-Go** (on the Pi, SDR plugged in):

```bash
rtl_fm -f 101500000 -s 170000 -M wfm -r 48000 -g 0 - 2>/dev/null | head -c 5000000 > /dev/null
```

If the SDR disappears from `lsusb` during this, the problem is hardware/USB.

## No audio (stream plays but no sound)

- **Volume** – Check the volume slider in the UI and system/browser volume. Ensure the tab isn’t muted.
- **Pipeline errors** – Check logs: `sudo journalctl -u fm-go.service -n 100 | grep -E "rtl_fm|sox|ffmpeg"`
- **Frequency** – Try a known local FM frequency (e.g. 101.5 MHz = 101500000). You should hear at least static.
- **Gain** – Try raising RF gain in the UI (e.g. 20 or Auto AGC).

## Service won’t start

```bash
sudo systemctl status fm-go.service
sudo journalctl -u fm-go.service -n 50
```

Ensure Python dependencies are installed:

```bash
sudo /opt/fm-go/venv/bin/pip install flask flask-cors
```

## Web interface not loading

- Confirm the service is running: `sudo systemctl status fm-go.service`
- Open `http://<pi-ip>:8080` (replace with your Pi’s IP).
- Check firewall: port 8080 must be allowed.

## Reinstall from scratch

```bash
cd ~/FM-Go
sudo ./install.sh
```

Or one-command:

```bash
curl -sSL https://raw.githubusercontent.com/rossingram/FM-Go/main/install.sh | sudo bash
```
