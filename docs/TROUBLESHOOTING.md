# PiFM Troubleshooting

## RTL-SDR not detected

- **Plug in the SDR** and wait a few seconds. The web UI shows "RTL-SDR ✅ Detected" when the device is present (USB only; we don't open the device for status).
- **Reinstall** so udev rules and user groups are applied:
  ```bash
  cd ~/PiFM && sudo ./install.sh
  ```
- **Unload conflicting drivers** (if you use TV tuner software):
  ```bash
  sudo modprobe -r dvb_usb_rtl28xxu rtl2832 rtl2830
  sudo reboot
  ```

## "usb_claim_interface error -6" / "Failed to open rtlsdr device"

This usually means the device is still held by a previous process or the kernel. The service now **retries once** after a short delay. If it still fails:

- **Wait 5–10 seconds** after stopping the stream, then try Play again.
- **Restart the service** to release the device: `sudo systemctl restart pifm.service`
- **Unplug and replug** the RTL-SDR, then try again.
- Ensure no other program is using the SDR (e.g. GQRX, SDR#, or another `rtl_fm`/`rtl_test` process).

## RTL-SDR drops offline when you tap Play

If the SDR shows **✅ Detected** but **disconnects as soon as you hit Play**, the device is dropping when we open it for streaming. Software already keeps load low (one open, gain 0, 170k sample rate); the cause is usually **hardware or USB**.

Try in order:

1. **Powered USB 2.0 hub** – Put a *powered* USB 2.0 hub between the Pi and the RTL-SDR.
2. **Different RTL-SDR dongle** – Some units are unstable on Pi; try another.
3. **Different USB port** – Prefer USB 2.0 if available; try each port.
4. **Official Pi power supply** – Undervoltage causes USB dropouts. Use 5V 2.5A+ (Pi 3B+) or 5V 3A+ (Pi 4/5).

**Quick test without PiFM** (on the Pi, SDR plugged in):

```bash
rtl_fm -f 101500000 -s 170000 -M wfm -r 48000 -g 0 - 2>/dev/null | head -c 5000000 > /dev/null
```

If the SDR disappears from `lsusb` during this, the problem is hardware/USB.

## No audio (stream plays but no sound)

- **Volume** – Check the volume slider in the UI and system/browser volume. Ensure the tab isn't muted.
- **Pipeline errors** – Check logs: `sudo journalctl -u pifm.service -n 100 | grep -E "rtl_fm|sox|ffmpeg"`
- **Frequency** – Try a known local FM frequency (e.g. 101.5 MHz = 101500000). You should hear at least static.
- **Gain** – Try raising RF gain in the UI (e.g. 20 or Auto AGC).

## iOS Safari garbled/distorted audio

**Status:** Under investigation (as of Feb 2025)

Audio plays fine on desktop browsers but is garbled/distorted on iOS Safari (iPhone/iPad). This is a known iOS Safari compatibility issue with MP3 live streaming.

**What we've tried:**
1. ✅ Switched from 48kHz to 44.1kHz sample rate (standard MP3 rate)
2. ✅ Lowered bitrate from 128k to 64k
3. ✅ Disabled MP3 bit reservoir (`-reservoir 0`) for consistent frame sizes
4. ✅ Disabled XING header (`-write_xing 0`)
5. ✅ Increased chunk size for streaming (32KB)
6. ✅ Added proper HTTP headers (`Accept-Ranges`, `Transfer-Encoding: chunked`)
7. ✅ Added frontend logging and audio event listeners for debugging
8. ❌ Tried AAC/MP4 fragmented format (still garbled)
9. ❌ Tried ADTS AAC format (not supported by HTML5 audio)

**Current implementation:**
- MP3 encoding: 44.1kHz, mono, 64k CBR, bit reservoir disabled
- Stream chunks: 32KB
- Headers: Proper cache control and chunked encoding

**Next steps to investigate:**
1. **HLS (HTTP Live Streaming)** – Apple's preferred format, requires segmenting the stream
2. **Web Audio API** – Use `fetch()` + `AudioContext` instead of HTML5 `<audio>` element for more control
3. **Check actual MP3 data** – Verify stream isn't corrupted earlier in pipeline
4. **Network/proxy issues** – Check if something between server and iOS Safari is affecting the stream

**Debugging:**
- Check browser console (F12 on desktop, Safari Web Inspector on iOS) for audio events
- Check backend logs: `sudo journalctl -u pifm.service -f` and look for "Stream endpoint requested"
- Frontend logs show when `updateAudioSource()` is called and audio element events

## Service won't start

```bash
sudo systemctl status pifm.service
sudo journalctl -u pifm.service -n 50
```

Ensure Python dependencies are installed:

```bash
sudo /opt/pifm/venv/bin/pip install flask flask-cors
```

## Web interface not loading

- Confirm the service is running: `sudo systemctl status pifm.service`
- Open `http://<pi-ip>:8080` (replace with your Pi's IP).
- Check firewall: port 8080 must be allowed.

## Reinstall from scratch

```bash
cd ~/PiFM
sudo ./install.sh
```

Or one-command:

```bash
curl -sSL https://raw.githubusercontent.com/rossingram/PiFM/main/install.sh | sudo bash
```
