# PiFM Installation

## One-command install

```bash
curl -sSL https://raw.githubusercontent.com/rossingram/PiFM/main/install.sh | sudo bash
```

## Manual install (from repo)

```bash
git clone https://github.com/rossingram/PiFM.git
cd PiFM
sudo ./install.sh
```

## What the installer does

- Installs system packages: `rtl-sdr`, `sox`, `ffmpeg`, `python3`, etc.
- Blacklists DVB-T drivers that conflict with RTL-SDR
- Creates user `pifm` and adds it to `plugdev` / `dialout`
- Adds udev rules for RTL-SDR
- Installs Python deps (Flask, flask-cors) in a venv under `/opt/pifm`
- Copies backend and frontend to `/opt/pifm`
- Creates and enables `pifm.service` (systemd)

## After install

1. Plug in the RTL-SDR (after the service is running if you prefer).
2. Open the web UI: `http://<pi-ip>:8080`
3. Tap **Play** to start streaming.

## Updating

```bash
cd ~/PiFM
git pull
sudo ./install.sh
```

The installer is idempotent; safe to run again.
