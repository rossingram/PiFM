# PiFM Development

## Project layout

```
PiFM/
├── backend/
│   └── fm_receiver.py    # Python service (Flask API + rtl_fm pipeline)
├── frontend/
│   └── index.html       # Web UI
├── docs/                 # Documentation
├── install.sh            # Main installer
├── requirements.txt
├── README.md
├── LICENSE
└── CONTRIBUTING.md
```

## Local run (no Pi)

```bash
pip install -r requirements.txt
python backend/fm_receiver.py
```

Open http://localhost:8080. RTL-SDR won’t work without the device and `rtl_fm`/`sox`/`ffmpeg` on PATH.

## Pushing to GitHub

```bash
git add .
git commit -m "Your message"
git remote add origin git@github.com:rossingram/PiFM.git   # if not already
git branch -M main
git push -u origin main
```

Install from repo:

```bash
curl -sSL https://raw.githubusercontent.com/rossingram/PiFM/main/install.sh | sudo bash
```
