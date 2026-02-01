#!/usr/bin/env python3
"""
PiFM Backend Service
FM radio receiver using RTL-SDR with HTTP streaming
"""

import os
import sys
import json
import subprocess
import signal
import threading
import time
import logging
from pathlib import Path

# Setup logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import Flask after logging is set up
try:
    from flask import Flask, Response, jsonify, request, send_from_directory
    from flask_cors import CORS
except ImportError as e:
    logger.error(f"Failed to import Flask: {e}")
    logger.error("Please install Flask: pip install flask flask-cors")
    sys.exit(1)

# Determine paths
if os.path.exists('/opt/pifm'):
    BASE_DIR = Path('/opt/pifm')
else:
    BASE_DIR = Path(__file__).parent.parent

CONFIG_DIR = BASE_DIR / 'config'
CONFIG_FILE = CONFIG_DIR / 'config.json'
PRESETS_FILE = CONFIG_DIR / 'presets.json'
FRONTEND_DIR = BASE_DIR / 'frontend'

# Ensure config directory exists
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
FRONTEND_DIR.mkdir(parents=True, exist_ok=True)

# Check if frontend directory has files
if not list(FRONTEND_DIR.glob('*.html')):
    logger.warning(f"Frontend directory {FRONTEND_DIR} appears empty. Web interface may not work.")

try:
    app = Flask(__name__, static_folder=str(FRONTEND_DIR))
    CORS(app)
except Exception as e:
    logger.error(f"Failed to initialize Flask app: {e}")
    raise

# Global state
current_frequency = None
rtl_process = None
audio_process = None
is_playing = False
config = {}
presets = {"presets": []}
# Intercept: first stream after SDR is used gets conservative gain to prevent overload (e.g. high-gain antenna)
_first_stream_this_session = True


def load_config():
    """Load configuration from file"""
    global config
    default_config = {
        "port": 8080,
        "sample_rate": 170000,  # Standard for FM; lower USB load than 240k
        "frequency": 101500000,
        "gain": 0,  # Low gain by default to prevent overload (e.g. with high-gain antenna)
        "audio_format": "mp3",
        "audio_bitrate": 64  # Lower bitrate (64k) for better iOS Safari compatibility - reduces garbling
    }
    
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
            # Merge with defaults
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            config = default_config
    else:
        config = default_config
        save_config()
    
    return config


def save_config():
    """Save configuration to file"""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving config: {e}")


def load_presets():
    """Load presets from file"""
    global presets
    default_presets = {
        "presets": [
            {"id": 1, "name": "570 AM", "frequency": 570000},
            {"id": 2, "name": "710 AM", "frequency": 710000},
            {"id": 3, "name": "1150 AM", "frequency": 1150000},
            {"id": 4, "name": "98.7 FM HD2", "frequency": 98700000},
            {"id": 5, "name": "102.7 FM", "frequency": 102700000},
            {"id": 6, "name": "106.7 FM", "frequency": 106700000}
        ]
    }
    
    if PRESETS_FILE.exists():
        try:
            with open(PRESETS_FILE, 'r') as f:
                presets = json.load(f)
        except Exception as e:
            logger.error(f"Error loading presets: {e}")
            presets = default_presets
    else:
        presets = default_presets
        save_presets()
    
    return presets


def save_presets():
    """Save presets to file"""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(PRESETS_FILE, 'w') as f:
            json.dump(presets, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving presets: {e}")


def is_rtl_sdr_present():
    """Lightweight check: is RTL-SDR plugged in? (lsusb only - does NOT open the device.)
    Use this for status display. Opening the device (rtl_test) can overload/unstick it."""
    try:
        result = subprocess.run(
            ['lsusb'],
            capture_output=True,
            timeout=1,
            text=True
        )
        out = (result.stdout or '') + (result.stderr or '')
        return '0bda:283' in out or 'RTL283' in out or 'RTL2838' in out
    except Exception:
        return False


def detect_rtl_sdr():
    """Full check: is RTL-SDR present AND can we open it? (Runs rtl_test - use sparingly.)
    Only call this when about to start streaming. Do NOT call every few seconds for status
    or the device can overload/disconnect."""
    try:
        if not is_rtl_sdr_present():
            return False
        result = subprocess.run(
            ['rtl_test', '-t'],
            capture_output=True,
            timeout=3
        )
        try:
            output = result.stdout.decode('utf-8', errors='replace') + result.stderr.decode('utf-8', errors='replace')
        except (UnicodeDecodeError, AttributeError):
            output = result.stdout.decode('latin-1', errors='replace') + result.stderr.decode('latin-1', errors='replace')
        if 'Found' in output and 'device' in output.lower():
            if any(t in output for t in ['R820T', 'E4000', 'Supported gain']):
                return True
            if 'No supported tuner' in output:
                return True
            return True
        return False
    except FileNotFoundError:
        logger.error("rtl_test command not found. Is rtl-sdr package installed?")
        return False
    except subprocess.TimeoutExpired:
        logger.warning("RTL-SDR detection timed out")
        return False
    except Exception as e:
        logger.error(f"RTL-SDR detection error: {e}")
        return False


def stop_streaming(timeout=5):
    """Stop the current audio stream. timeout: seconds to wait for processes to exit."""
    global rtl_process, audio_process, is_playing
    
    is_playing = False
    
    if audio_process:
        try:
            audio_process.terminate()
            audio_process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                audio_process.kill()
                audio_process.wait(timeout=1)
            except Exception:
                pass
        except Exception:
            pass
        audio_process = None
    
    if rtl_process:
        try:
            rtl_process.terminate()
            rtl_process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                rtl_process.kill()
                rtl_process.wait(timeout=1)
            except Exception:
                pass
        except Exception:
            pass
        rtl_process = None
    
    logger.info("Streaming stopped")


def start_streaming(frequency=None, gain_override=None, is_retune=False):
    """Start FM streaming at the given frequency.
    gain_override: use this gain (number or 'auto') instead of config.
    is_retune: True when changing frequency while already playing (skip long delay, use shorter stop timeout)."""
    global rtl_process, audio_process, is_playing, current_frequency
    
    if frequency is None:
        frequency = config.get('frequency', 101500000)
    
    # Validate frequency range: FM 87.5-108 MHz, AM 530-1700 kHz
    if not (530000 <= frequency <= 1700000 or 87500000 <= frequency <= 108000000):
        logger.error(f"Frequency {frequency} out of valid range (AM 530-1700 kHz, FM 87.5-108 MHz)")
        return False
    
    current_frequency = frequency
    is_am = 530000 <= frequency <= 1700000
    
    if is_playing:
        stop_streaming(timeout=2 if is_retune else 5)
        time.sleep(0.3 if is_retune else 0.5)
    
    # Use lsusb-only check so we don't open the device with rtl_test before rtl_fm (one open = less chance of dropout)
    if not is_rtl_sdr_present():
        logger.error("RTL-SDR not present (USB). Plug in the device.")
        return False
    
    # Brief delay only on first start; skip when retuning to avoid request hang
    if not is_retune:
        time.sleep(1.5)
    
    try:
        global _first_stream_this_session
        # 170k is standard for FM; lower can reduce USB load but may hurt audio
        sample_rate = config.get('sample_rate', 170000)
        gain = gain_override if gain_override is not None else config.get('gain', 0)
        audio_bitrate = config.get('audio_bitrate', 128)
        
        # Intercept: first stream after SDR is plugged in / service start - force low gain to prevent overload
        if _first_stream_this_session:
            if gain == 'auto' or gain is None or (isinstance(gain, (int, float)) and gain > 20):
                logger.info("First stream this session: using gain 0 to prevent SDR overload (e.g. high-gain antenna). Adjust in UI if needed.")
                gain = 0
            _first_stream_this_session = False
        
        # Build rtl_fm command (FM 87.5-108 MHz or AM 530-1700 kHz)
        if is_am:
            # AM broadcast: direct sampling. Use valid RTL-SDR device rate (24k default);
            # -s 48000 is not a supported hardware rate and can produce no audio.
            # rtl_fm adds an offset in direct+edge mode (capture_rate/4 + rate_in/2 ≈ 264 kHz),
            # so we request (freq - offset) so the actual tuned frequency is correct.
            AM_DIRECT_OFFSET_HZ = 264000
            rtl_freq = max(0, frequency - AM_DIRECT_OFFSET_HZ)
            rtl_output_rate = '24000'  # rtl_fm output; sox will resample to 48k for pipeline
            rtl_cmd = [
                'rtl_fm',
                '-f', str(rtl_freq),
                '-s', '24000',   # Device sample rate (must be supported; 24k is default/valid)
                '-M', 'am',
                '-r', rtl_output_rate,
                '-E', 'direct',  # Tune AM band (530-1700 kHz)
                '-E', 'edge',    # Lower edge tuning for direct sampling
                '-E', 'dc',      # DC blocking filter (often needed for AM to avoid silent/muted audio)
                '-A', 'fast',
            ]
            logger.info(f"Starting AM stream at {frequency} Hz ({frequency/1000:.0f} kHz) (rtl_fm -f {rtl_freq})")
        else:
            rtl_output_rate = '48000'
            # FM broadcast
            rtl_cmd = [
                'rtl_fm',
                '-f', str(frequency),
                '-s', str(sample_rate),
                '-M', 'wfm',
                '-r', rtl_output_rate,
                '-A', 'fast',
            ]
        
        if gain == 'auto' or gain is None:
            rtl_cmd.append('-T')  # Enable AGC
        else:
            rtl_cmd.extend(['-g', str(gain)])
        
        # Use 44.1kHz for MP3 (standard CD rate, better iOS Safari compatibility than 48k)
        # AM uses 24k from rtl_fm, so sox resamples 24k->44.1k
        pipeline_rate = '44100'
        # Build audio encoding pipeline: rtl_fm -> sox (raw to WAV, optionally resample) -> ffmpeg (MP3)
        # SoX order: input [opts] output [opts] [effect ...] (effects come after output file)
        sox_cmd = [
            'sox',
            '-t', 'raw',
            '-r', rtl_output_rate,
            '-c', '1',
            '-b', '16',
            '-e', 'signed-integer',
            '-',  # stdin
            '-t', 'wav',
            '-r', pipeline_rate,  # 48k WAV so MP3 is 48k (AM: sox resamples 24k->48k)
            '-'   # stdout
        ]
        # AM from direct sampling is often very quiet; boost and normalize so it's audible (effect after output)
        if is_am:
            sox_cmd.extend(['gain', '20', 'norm', '-3'])  # +20 dB then normalize to -3 dB headroom
        
        # MP3 with iOS Safari-optimized settings: 44.1kHz, CBR, 64k bitrate
        # Using conservative settings to avoid garbled audio on iOS Safari
        # Key: -reservoir 0 disables bit reservoir (ensures consistent frame sizes for streaming)
        ffmpeg_cmd = [
            'ffmpeg',
            '-f', 'wav',
            '-i', '-',
            '-f', 'mp3',
            '-acodec', 'libmp3lame',
            '-b:a', f'{audio_bitrate}k',  # Constant bitrate (CBR) - 64k for iOS compatibility
            '-ar', pipeline_rate,  # 44.1kHz (standard MP3 rate)
            '-ac', '1',  # Mono
            '-write_xing', '0',  # Disable XING header
            '-reservoir', '0',  # Disable bit reservoir (critical for iOS Safari - ensures consistent frame sizes)
            '-'  # stdout
        ]
        
        logger.info(f"Starting stream at {frequency} Hz ({'AM' if is_am else 'FM'})")
        
        def drain_stderr(proc, name, level='debug'):
            """Drain stderr in background so the pipe doesn't fill and block the process."""
            try:
                for line in proc.stderr:
                    line = line.decode('utf-8', errors='replace').strip()
                    if line:
                        if level == 'info':
                            logger.info(f"[{name}] {line}")
                        else:
                            logger.debug(f"[{name}] {line}")
            except Exception:
                pass
        
        last_error = None
        for attempt in range(2):
            # Start processes (use local ref for poll check so concurrent api_stop can't set global to None)
            rtl_proc = subprocess.Popen(
                rtl_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
            rtl_process = rtl_proc  # global for stop_streaming / drain threads
            
            t_rtl = threading.Thread(target=drain_stderr, args=(rtl_proc, 'rtl_fm', 'info'), daemon=True)
            t_rtl.start()
            
            sox_process = subprocess.Popen(
                sox_cmd,
                stdin=rtl_proc.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
            
            rtl_proc.stdout.close()
            
            t_sox = threading.Thread(target=drain_stderr, args=(sox_process, 'sox', 'info'), daemon=True)
            t_sox.start()
            
            audio_process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=sox_process.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
            
            sox_process.stdout.close()
            
            t_ffmpeg = threading.Thread(target=drain_stderr, args=(audio_process, 'ffmpeg', 'info'), daemon=True)
            t_ffmpeg.start()
            
            # If rtl_fm exits within 1s (e.g. usb_claim_interface -6), clean up and retry once
            time.sleep(1.0)
            if rtl_proc.poll() is None:
                global _stream_died_logged
                _stream_died_logged = False
                is_playing = True
                logger.info("Stream started successfully")
                return True
            
            last_error = "rtl_fm exited shortly after start (device may be in use or not released yet)"
            logger.warning("%s; attempt %d/2, retrying after delay...", last_error, attempt + 1)
            stop_streaming()
            if attempt == 0:
                time.sleep(4.0)  # Give USB more time to release before retry
        
        logger.error("Failed to start stream after 2 attempts. %s", last_error or "unknown")
        return False
        
    except Exception as e:
        logger.error(f"Error starting stream: {e}")
        stop_streaming()
        return False


def get_system_status():
    """Get system status. Uses lsusb-only check so we never open the SDR for status polling."""
    status = {
        "rtl_sdr_detected": is_rtl_sdr_present(),  # Do NOT use detect_rtl_sdr() here - would open device every 5s
        "is_playing": is_playing,
        "current_frequency": current_frequency,
        "service_running": True,
        "rds_ps": None,       # RDS Program Service (station name); set when RDS pipeline is implemented
        "rds_radiotext": None # RDS Radio Text (e.g. song/artist); set when RDS pipeline is implemented
    }
    
    # Get CPU temperature (Raspberry Pi)
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp = int(f.read().strip()) / 1000.0
            status["cpu_temperature"] = round(temp, 1)
    except:
        status["cpu_temperature"] = None
    
    return status


# Flask Routes

@app.route('/')
def index():
    """Serve the web interface"""
    index_file = FRONTEND_DIR / 'index.html'
    if not index_file.exists():
        return """
        <html><body>
        <h1>PiFM</h1>
        <p>Frontend files not found. Please ensure index.html is in {}</p>
        <p>API is available at /api/status</p>
        </body></html>
        """.format(FRONTEND_DIR), 503
    return send_from_directory(FRONTEND_DIR, 'index.html')


@app.route('/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory(FRONTEND_DIR, path)


@app.route('/api/status', methods=['GET'])
def api_status():
    """Get system status"""
    return jsonify(get_system_status())


@app.route('/api/config', methods=['GET'])
def api_get_config():
    """Get current configuration"""
    return jsonify(config)


@app.route('/api/config', methods=['POST'])
def api_update_config():
    """Update configuration"""
    global config
    data = request.json
    
    # Update config (allow gain as number or 'auto')
    for key, value in data.items():
        if key in config:
            config[key] = value
    
    save_config()
    
    # Restart stream if frequency or gain changed
    if 'frequency' in data or 'gain' in data:
        gain_override = data.get('gain') if 'gain' in data else None
        start_streaming(config.get('frequency'), gain_override=gain_override)
    
    return jsonify({"success": True, "config": config})


@app.route('/api/presets', methods=['GET'])
def api_get_presets():
    """Get all presets"""
    return jsonify(presets)


@app.route('/api/presets', methods=['POST'])
def api_add_preset():
    """Add a new preset"""
    data = request.json
    
    if 'name' not in data or 'frequency' not in data:
        return jsonify({"success": False, "error": "Missing name or frequency"}), 400
    
    # Generate new ID
    max_id = max([p.get('id', 0) for p in presets['presets']], default=0)
    new_preset = {
        "id": max_id + 1,
        "name": data['name'],
        "frequency": int(data['frequency'])
    }
    
    presets['presets'].append(new_preset)
    save_presets()
    
    return jsonify({"success": True, "preset": new_preset})


@app.route('/api/presets/<int:preset_id>', methods=['PUT'])
def api_update_preset(preset_id):
    """Update a preset"""
    data = request.json
    
    for preset in presets['presets']:
        if preset['id'] == preset_id:
            if 'name' in data:
                preset['name'] = data['name']
            if 'frequency' in data:
                preset['frequency'] = int(data['frequency'])
            save_presets()
            return jsonify({"success": True, "preset": preset})
    
    return jsonify({"success": False, "error": "Preset not found"}), 404


@app.route('/api/presets/<int:preset_id>', methods=['DELETE'])
def api_delete_preset(preset_id):
    """Delete a preset"""
    presets['presets'] = [p for p in presets['presets'] if p['id'] != preset_id]
    save_presets()
    return jsonify({"success": True})


@app.route('/api/tune', methods=['POST'])
def api_tune():
    """Tune to a frequency"""
    try:
        data = request.json or {}
        if 'frequency' not in data:
            return jsonify({"success": False, "error": "Missing frequency"}), 400
        
        frequency = int(data['frequency'])
        if not (530000 <= frequency <= 1700000 or 87500000 <= frequency <= 108000000):
            return jsonify({"success": False, "error": "Use AM 530–1700 kHz or FM 87.5–108 MHz"}), 400
        
        if start_streaming(frequency, is_retune=is_playing):
            config['frequency'] = frequency
            save_config()
            return jsonify({"success": True, "frequency": frequency})
        else:
            return jsonify({"success": False, "error": "Failed to start stream"}), 500
    except (ValueError, TypeError) as e:
        logger.error(f"Tune error: {e}")
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.exception("Tune failed")
        return jsonify({"success": False, "error": "Internal error"}), 500


@app.route('/api/play', methods=['POST'])
def api_play():
    """Start playing"""
    data = request.json or {}
    frequency = data.get('frequency') or config.get('frequency', 101500000)
    gain = data.get('gain')  # None = use config; number or 'auto' to override
    
    # Use lsusb-only check so we don't open the device with rtl_test before rtl_fm (one open = less dropout)
    if not is_rtl_sdr_present():
        return jsonify({
            "success": False, 
            "error": "RTL-SDR not present. Plug in the device and try again."
        }), 503
    
    if start_streaming(frequency, gain_override=gain):
        return jsonify({"success": True})
    else:
        return jsonify({
            "success": False, 
            "error": "Failed to start stream. Check logs for details."
        }), 500


@app.route('/api/stop', methods=['POST'])
def api_stop():
    """Stop playing"""
    stop_streaming()
    return jsonify({"success": True})


_stream_died_logged = False


@app.route('/api/stream')
def api_stream():
    """Audio stream endpoint"""
    global _stream_died_logged
    logger.info("Stream endpoint requested")
    if not is_playing or not audio_process:
        logger.warning("Stream requested but not active (is_playing=%s, audio_process=%s)", is_playing, audio_process is not None)
        return Response("Stream not active", status=503, mimetype='text/plain')
    
    logger.info("Starting stream generation")
    def generate():
        global _stream_died_logged
        bytes_sent = 0
        try:
            logger.info("Stream generator started, entering loop")
            while is_playing and audio_process:
                if audio_process.poll() is not None:
                    if not _stream_died_logged:
                        _stream_died_logged = True
                        logger.error("Audio process terminated unexpectedly (SDR may have disconnected)")
                    stop_streaming()
                    break
                
                # Use 32KB chunks for smooth playback
                chunk = audio_process.stdout.read(32768)
                if not chunk:
                    if audio_process.poll() is not None:
                        if not _stream_died_logged:
                            _stream_died_logged = True
                            logger.error("Audio process terminated unexpectedly (SDR may have disconnected)")
                        stop_streaming()
                        break
                    time.sleep(0.1)
                    continue
                bytes_sent += len(chunk)
                if bytes_sent <= 65536:  # Log first 64KB
                    logger.debug(f"Sending chunk: {len(chunk)} bytes (total: {bytes_sent})")
                yield chunk
        except GeneratorExit:
            pass
        except Exception as e:
            logger.error(f"Stream error: {e}")
    
    return Response(
        generate(),
        mimetype='audio/mpeg',  # MP3 format
        headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
            'X-Content-Type-Options': 'nosniff',
            'Connection': 'keep-alive',
            'Accept-Ranges': 'bytes',
            'Content-Type': 'audio/mpeg',
            'Transfer-Encoding': 'chunked'  # Explicit chunked encoding for live stream
        }
    )


def signal_handler(sig, frame):
    """Handle shutdown signals"""
    logger.info("Shutting down...")
    stop_streaming()
    sys.exit(0)


def main():
    """Main entry point"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Load configuration
    load_config()
    load_presets()
    
    # Don't open the SDR at startup - use lsusb-only check so we don't touch the device
    if is_rtl_sdr_present():
        logger.info("RTL-SDR present (USB). Use web interface to start streaming.")
    else:
        logger.info("RTL-SDR not present. Plug in and use web interface to start streaming.")
    
    # Start Flask server
    port = config.get('port', 8080)
    logger.info(f"Starting PiFM server on port {port}")
    
    try:
        app.run(
            host='0.0.0.0',
            port=port,
            debug=False,
            threaded=True
        )
    except Exception as e:
        logger.error(f"Failed to start Flask server: {e}")
        raise


if __name__ == '__main__':
    main()
