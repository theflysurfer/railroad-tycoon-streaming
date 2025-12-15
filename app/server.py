#!/usr/bin/env python3
"""
JPEG Polling Streaming Server for Windows Games (via DOSBox-X)
Compatible with Safari 5.1.1 / iOS 5.1.1 (iPad 1)

This server:
1. Captures the Xvfb display using FFmpeg (single JPEG frames)
2. Serves frames via /frame.jpg endpoint
3. Client polls with JavaScript for maximum compatibility
4. Handles touch input via HTTP POST and translates to xdotool commands
"""

import subprocess
import os
import signal
import sys
import threading
import time
from flask import Flask, Response, request, send_from_directory

app = Flask(__name__, static_folder='static')

# Configuration
DISPLAY = os.environ.get('DISPLAY', ':99')
FRAME_RATE = 12  # Target FPS
VIDEO_SIZE = '640x480'
JPEG_QUALITY = 8  # 2-31, lower = better quality

# Frame buffer - stores the latest JPEG frame
frame_lock = threading.Lock()
current_frame = None
frame_capture_running = False


def capture_frames():
    """
    Background thread that continuously captures frames from X11 display.
    Uses FFmpeg to grab single frames at regular intervals.
    """
    global current_frame, frame_capture_running
    frame_capture_running = True
    print(f"Frame capture thread started. DISPLAY={DISPLAY}, SIZE={VIDEO_SIZE}", file=sys.stderr)

    frame_interval = 1.0 / FRAME_RATE

    while frame_capture_running:
        try:
            start_time = time.time()

            # Capture single frame using FFmpeg
            result = subprocess.run(
                [
                    'ffmpeg',
                    '-loglevel', 'error',
                    '-f', 'x11grab',
                    '-video_size', VIDEO_SIZE,
                    '-i', DISPLAY,
                    '-vframes', '1',
                    '-c:v', 'mjpeg',
                    '-q:v', str(JPEG_QUALITY),
                    '-f', 'image2pipe',
                    'pipe:1'
                ],
                capture_output=True,
                timeout=2
            )

            if result.returncode == 0 and result.stdout:
                with frame_lock:
                    current_frame = result.stdout
            else:
                print(f"FFmpeg failed: returncode={result.returncode}, stderr={result.stderr.decode() if result.stderr else 'none'}", file=sys.stderr)

            # Sleep to maintain target frame rate
            elapsed = time.time() - start_time
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        except subprocess.TimeoutExpired:
            print("FFmpeg timeout", file=sys.stderr)
        except Exception as e:
            print(f"Frame capture error: {e}", file=sys.stderr)
            time.sleep(0.1)


# Start frame capture thread
capture_thread = None


def start_capture():
    """Start the background frame capture thread."""
    global capture_thread
    if capture_thread is None or not capture_thread.is_alive():
        print("Starting frame capture thread...", file=sys.stderr)
        capture_thread = threading.Thread(target=capture_frames, daemon=True)
        capture_thread.start()
        print("Frame capture thread started!", file=sys.stderr)


@app.route('/')
def index():
    """Serve the main HTML page."""
    start_capture()  # Ensure capture is running
    return send_from_directory('static', 'index.html')


@app.route('/frame.jpg')
def get_frame():
    """
    Serve the latest captured frame as JPEG.
    Client should poll this endpoint with JavaScript.
    """
    start_capture()  # Ensure capture is running

    with frame_lock:
        frame = current_frame

    if frame:
        return Response(
            frame,
            mimetype='image/jpeg',
            headers={
                'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
                'Pragma': 'no-cache',
                'Expires': '0',
                'Access-Control-Allow-Origin': '*'
            }
        )
    else:
        # Return 1x1 black JPEG if no frame yet
        return Response(
            b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7teleN/teleN/\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa\x07"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17\x18\x19\x1a%&\'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xfb\xd5\xff\xd9',
            mimetype='image/jpeg',
            headers={
                'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
                'Pragma': 'no-cache'
            }
        )


@app.route('/stream.mjpeg')
def stream():
    """
    Legacy MJPEG endpoint - redirects to polling approach.
    Kept for backwards compatibility.
    """
    # Return a simple redirect message
    return Response(
        'Use /frame.jpg with JavaScript polling instead',
        status=410,
        mimetype='text/plain'
    )


@app.route('/input', methods=['POST', 'GET'])
def handle_input():
    """
    Handle touch/click input from the iPad.
    """
    try:
        if request.method == 'POST':
            x = request.form.get('x', type=int)
            y = request.form.get('y', type=int)
            input_type = request.form.get('type', 'click')
            key = request.form.get('key', '')
        else:
            x = request.args.get('x', type=int)
            y = request.args.get('y', type=int)
            input_type = request.args.get('type', 'click')
            key = request.args.get('key', '')

        env = {'DISPLAY': DISPLAY}

        if input_type == 'click' and x is not None and y is not None:
            subprocess.Popen(
                ['xdotool', 'mousemove', '--', str(x), str(y), 'click', '1'],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

        elif input_type == 'rightclick' and x is not None and y is not None:
            subprocess.Popen(
                ['xdotool', 'mousemove', '--', str(x), str(y), 'click', '3'],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

        elif input_type == 'key' and key:
            subprocess.run(
                ['xdotool', 'key', key],
                env=env,
                timeout=2
            )

        return 'OK', 200, {'Content-Type': 'text/plain'}

    except subprocess.TimeoutExpired:
        return 'Timeout', 504, {'Content-Type': 'text/plain'}
    except Exception as e:
        return str(e), 500, {'Content-Type': 'text/plain'}


@app.route('/key/<keyname>')
def send_key(keyname):
    """GET-based key input for maximum compatibility."""
    try:
        key_map = {
            'enter': 'Return', 'return': 'Return',
            'esc': 'Escape', 'escape': 'Escape',
            'space': 'space',
            'up': 'Up', 'down': 'Down', 'left': 'Left', 'right': 'Right',
            'tab': 'Tab', 'backspace': 'BackSpace', 'delete': 'Delete',
            'f1': 'F1', 'f2': 'F2', 'f3': 'F3', 'f4': 'F4', 'f5': 'F5',
            'f6': 'F6', 'f7': 'F7', 'f8': 'F8', 'f9': 'F9', 'f10': 'F10',
        }
        actual_key = key_map.get(keyname.lower(), keyname)
        subprocess.run(['xdotool', 'key', actual_key], env={'DISPLAY': DISPLAY}, timeout=2)
        return 'OK', 200, {'Content-Type': 'text/plain'}
    except Exception as e:
        return str(e), 500, {'Content-Type': 'text/plain'}


@app.route('/status')
def status():
    """Health check endpoint."""
    return 'OK', 200, {'Content-Type': 'text/plain'}


def signal_handler(signum, frame):
    """Clean up on shutdown."""
    global frame_capture_running
    frame_capture_running = False
    sys.exit(0)


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    app.run(host='0.0.0.0', port=8081, threaded=True, debug=False)
