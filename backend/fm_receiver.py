#!/usr/bin/env python3
"""
FM-Go Backend Service
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
if os.path.exists('/opt/fm-go'):
    BASE_DIR = Path('/opt/fm-go')
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


def load_config():
    """Load configuration from file"""
    global config
    default_config = {
        "port": 8080,
        "sample_rate": 240000,
        "frequency": 101500000,
        "gain": "auto",
        "audio_format": "mp3",
        "audio_bitrate": 128
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
            {
                "id": 1,
                "name": "Default Station",
                "frequency": 101500000
            }
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


def detect_rtl_sdr():
    """Detect if RTL-SDR is available"""
    try:
        # Try without sudo first
        result = subprocess.run(
            ['rtl_test', '-t'],
            capture_output=True,
            timeout=5,
            text=True
        )
        output = result.stdout + result.stderr
        
        # Check for successful detection - device found AND tuner found
        # Look for "Found X device(s)" and tuner identification
        if 'Found' in output and 'device' in output.lower():
            # Check if a tuner was actually found (R820T, E4000, etc.)
            if any(tuner in output for tuner in ['R820T', 'E4000', 'tuner', 'Supported gain']):
                return True
            # If device found but no tuner, still consider it detected
            # (might be initialization issue, but device exists)
            return True
        
        # If that didn't work, try with sudo (for permission issues)
        result = subprocess.run(
            ['sudo', 'rtl_test', '-t'],
            capture_output=True,
            timeout=5,
            text=True
        )
        output = result.stdout + result.stderr
        if 'Found' in output and 'device' in output.lower():
            if any(tuner in output for tuner in ['R820T', 'E4000', 'tuner', 'Supported gain']):
                return True
            return True
        return False
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError) as e:
        logger.debug(f"RTL-SDR detection error: {e}")
        return False


def stop_streaming():
    """Stop the current audio stream"""
    global rtl_process, audio_process, is_playing
    
    is_playing = False
    
    if audio_process:
        try:
            audio_process.terminate()
            audio_process.wait(timeout=5)
        except:
            try:
                audio_process.kill()
            except:
                pass
        audio_process = None
    
    if rtl_process:
        try:
            rtl_process.terminate()
            rtl_process.wait(timeout=5)
        except:
            try:
                rtl_process.kill()
            except:
                pass
        rtl_process = None
    
    logger.info("Streaming stopped")


def start_streaming(frequency=None):
    """Start FM streaming at the given frequency"""
    global rtl_process, audio_process, is_playing, current_frequency
    
    if frequency is None:
        frequency = config.get('frequency', 101500000)
    
    # Validate frequency range (FM broadcast band: 87.5-108 MHz)
    if frequency < 87500000 or frequency > 108000000:
        logger.error(f"Frequency {frequency} out of valid FM range (87.5-108 MHz)")
        return False
    
    current_frequency = frequency
    
    if is_playing:
        stop_streaming()
        # Give processes time to clean up
        time.sleep(0.5)
    
    if not detect_rtl_sdr():
        logger.error("RTL-SDR not detected")
        return False
    
    try:
        sample_rate = config.get('sample_rate', 240000)
        gain = config.get('gain', 'auto')
        audio_bitrate = config.get('audio_bitrate', 128)
        
        # Build rtl_fm command
        rtl_cmd = [
            'rtl_fm',
            '-f', str(frequency),
            '-s', str(sample_rate),
            '-M', 'wfm',  # Wideband FM
            '-r', '48000',  # Audio sample rate
            '-A', 'fast',  # Fast AGC
        ]
        
        if gain != 'auto':
            rtl_cmd.extend(['-g', str(gain)])
        else:
            rtl_cmd.append('-T')  # Enable AGC
        
        # Build audio encoding pipeline
        # rtl_fm -> sox (convert to WAV) -> ffmpeg (encode to MP3)
        sox_cmd = [
            'sox',
            '-t', 'raw',
            '-r', '48000',
            '-c', '1',
            '-b', '16',
            '-e', 'signed-integer',
            '-',  # stdin
            '-t', 'wav',
            '-'  # stdout
        ]
        
        ffmpeg_cmd = [
            'ffmpeg',
            '-f', 'wav',
            '-i', '-',
            '-f', 'mp3',
            '-b:a', f'{audio_bitrate}k',
            '-acodec', 'libmp3lame',
            '-'  # stdout
        ]
        
        logger.info(f"Starting stream at {frequency} Hz")
        
        # Start processes
        rtl_process = subprocess.Popen(
            rtl_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0
        )
        
        sox_process = subprocess.Popen(
            sox_cmd,
            stdin=rtl_process.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0
        )
        
        rtl_process.stdout.close()
        
        audio_process = subprocess.Popen(
            ffmpeg_cmd,
            stdin=sox_process.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0
        )
        
        sox_process.stdout.close()
        
        is_playing = True
        logger.info("Stream started successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error starting stream: {e}")
        stop_streaming()
        return False


def get_system_status():
    """Get system status information"""
    status = {
        "rtl_sdr_detected": detect_rtl_sdr(),
        "is_playing": is_playing,
        "current_frequency": current_frequency,
        "service_running": True
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
        <h1>FM-Go</h1>
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
    
    # Update config
    for key, value in data.items():
        if key in config:
            config[key] = value
    
    save_config()
    
    # Restart stream if frequency changed
    if 'frequency' in data:
        start_streaming(data['frequency'])
    
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
    data = request.json
    
    if 'frequency' not in data:
        return jsonify({"success": False, "error": "Missing frequency"}), 400
    
    frequency = int(data['frequency'])
    
    if start_streaming(frequency):
        config['frequency'] = frequency
        save_config()
        return jsonify({"success": True, "frequency": frequency})
    else:
        return jsonify({"success": False, "error": "Failed to start stream"}), 500


@app.route('/api/play', methods=['POST'])
def api_play():
    """Start playing"""
    frequency = request.json.get('frequency') or config.get('frequency', 101500000)
    
    if start_streaming(frequency):
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "error": "Failed to start stream"}), 500


@app.route('/api/stop', methods=['POST'])
def api_stop():
    """Stop playing"""
    stop_streaming()
    return jsonify({"success": True})


@app.route('/api/stream')
def api_stream():
    """Audio stream endpoint"""
    if not is_playing or not audio_process:
        return Response("Stream not active", status=503, mimetype='text/plain')
    
    def generate():
        try:
            while is_playing and audio_process:
                if audio_process.poll() is not None:
                    # Process died
                    logger.error("Audio process terminated unexpectedly")
                    break
                
                chunk = audio_process.stdout.read(8192)
                if not chunk:
                    # Check if process is still alive
                    if audio_process.poll() is not None:
                        break
                    time.sleep(0.1)
                    continue
                yield chunk
        except GeneratorExit:
            # Client disconnected, this is normal
            logger.debug("Client disconnected from stream")
        except Exception as e:
            logger.error(f"Stream error: {e}")
    
    return Response(
        generate(),
        mimetype='audio/mpeg',
        headers={
            'Cache-Control': 'no-cache',
            'X-Content-Type-Options': 'nosniff',
            'Connection': 'keep-alive'
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
    
    # Check for RTL-SDR
    if not detect_rtl_sdr():
        logger.warning("RTL-SDR not detected. Service will start but streaming may fail.")
        logger.info("Plug in RTL-SDR and use the web interface to start streaming.")
    else:
        # Try to start streaming at default frequency (non-blocking if it fails)
        logger.info("Attempting to start streaming at default frequency...")
        if not start_streaming():
            logger.warning("Failed to start streaming. Use web interface to start manually.")
    
    # Start Flask server
    port = config.get('port', 8080)
    logger.info(f"Starting FM-Go server on port {port}")
    
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
