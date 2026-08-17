import os
import time
import json
import threading
import cv2
import numpy as np
from flask import Flask, render_template, Response, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from detector import VehicleDetector
from analytics import TrafficAnalyticsEngine
from decision_engine import DecisionSupportEngine
import database as db
from youtube_stream import extract_youtube_stream, is_valid_youtube_url, clear_stream_cache

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__, 
    static_folder=BASE_DIR, 
    static_url_path='', 
    template_folder=os.path.join(BASE_DIR, 'templates')
)

UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
SAMPLES_DIR = os.path.join(BASE_DIR, "samples")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(SAMPLES_DIR, exist_ok=True)

# Initialize Core AI & Analytics Engines
detector = VehicleDetector(model_name="yolov8n.pt")
analytics = TrafficAnalyticsEngine(history_window=30)
decision_engine = DecisionSupportEngine(cycle_time=90)

# Feed Configurations
# source_type: "DEMO" | "FILE" | "YOUTUBE" | "DISABLED"
# status: "ONLINE" | "CONNECTING" | "OFFLINE" | "ERROR" | "DISABLED"
STREAM_CONFIGS = {
    1: {
        "source_type": "DEMO",
        "source_url": "",
        "file_path": os.path.join(SAMPLES_DIR, "road1_heavy_highway.mp4"),
        "name": "North Arterial - Highway 101",
        "is_live": False,
        "status": "ONLINE",
        "error_message": None,
        "last_updated": time.time()
    },
    2: {
        "source_type": "DEMO",
        "source_url": "",
        "file_path": os.path.join(SAMPLES_DIR, "road2_medium_urban.mp4"),
        "name": "East Boulevard - City Center Crossing",
        "is_live": False,
        "status": "ONLINE",
        "error_message": None,
        "last_updated": time.time()
    },
    3: {
        "source_type": "DEMO",
        "source_url": "",
        "file_path": os.path.join(SAMPLES_DIR, "road3_suburban_emergency.mp4"),
        "name": "West Parkway - Hospital Corridor",
        "is_live": False,
        "status": "ONLINE",
        "error_message": None,
        "last_updated": time.time()
    }
}

# Live Telemetry Cache
LATEST_METRICS = {}
ACTIVE_EMERGENCY_EVENTS = []
CURRENT_DECISION = None
CURRENT_SESSION_ID = f"SES-{int(time.time())}"

# Signal Execution State (Active phase in physical intersection simulation)
SIGNAL_STATE = {
    "active_stream": 1,
    "remaining_seconds": 45,
    "current_phase": "GREEN", # GREEN, YELLOW, RED
    "active_schedule": {1: 45, 2: 30, 3: 15},
    "operator_mode": "AUTOMATED_APPROVED",
    "emergency_override": False
}

lock = threading.Lock()

def create_status_frame(stream_id: int, status_title: str, message: str, is_error: bool = False):
    """Generates an informative HUD status frame when a stream is disabled, connecting, or in error."""
    img = np.zeros((360, 640, 3), dtype=np.uint8)
    # Background subtle dark gradient
    img[:, :] = (15, 20, 26)
    
    # Border
    border_color = (0, 0, 220) if is_error else (100, 140, 180)
    cv2.rectangle(img, (10, 10), (630, 350), border_color, 1)
    
    # Corner brackets
    corner_len = 20
    cv2.line(img, (10, 10), (10 + corner_len, 10), (0, 230, 255), 2)
    cv2.line(img, (10, 10), (10, 10 + corner_len), (0, 230, 255), 2)
    cv2.line(img, (630, 10), (630 - corner_len, 10), (0, 230, 255), 2)
    cv2.line(img, (630, 10), (630, 10 + corner_len), (0, 230, 255), 2)
    
    cv2.line(img, (10, 350), (10 + corner_len, 350), (0, 230, 255), 2)
    cv2.line(img, (10, 350), (10, 350 - corner_len), (0, 230, 255), 2)
    cv2.line(img, (630, 350), (630 - corner_len, 350), (0, 230, 255), 2)
    cv2.line(img, (630, 350), (630, 350 - corner_len), (0, 230, 255), 2)
    
    # Header
    name = STREAM_CONFIGS.get(stream_id, {}).get("name", f"Feed {stream_id}")
    cv2.putText(img, f"AETHER-TRAFFIC // FEED 0{stream_id}", (30, 50),
                cv2.FONT_HERSHEY_DUPLEX, 0.6, (0, 240, 255), 1)
    cv2.putText(img, name[:38], (30, 80),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 180, 200), 1)
                
    # Center Status
    title_color = (0, 70, 255) if is_error else (0, 230, 255)
    cv2.putText(img, status_title, (30, 170),
                cv2.FONT_HERSHEY_DUPLEX, 0.8, title_color, 2)
                
    # Multi-line message
    msg_lines = []
    while len(message) > 48:
        split_pt = message[:48].rfind(' ')
        if split_pt == -1:
            split_pt = 48
        msg_lines.append(message[:split_pt])
        message = message[split_pt:].strip()
    if message:
        msg_lines.append(message)
        
    y_text = 210
    for line in msg_lines[:4]:
        cv2.putText(img, line, (30, y_text),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 210, 220), 1)
        y_text += 26
        
    # Bottom Instruction
    cv2.putText(img, "Use 'Change Source' or 'Configure Feeds' to update input.", (30, 325),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (120, 140, 160), 1)
                
    ret_enc, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return buffer.tobytes() if ret_enc else None

class ThreadedCamera:
    """
    Asynchronous threaded video reader that runs capture on a background thread.
    Completely decouples network buffering/HLS segment loading from the 20 FPS AI pipeline.
    """
    def __init__(self, source_path_or_url, is_live=False, is_file=False):
        self.source = source_path_or_url
        self.is_live = is_live
        self.is_file = is_file
        self.cap = None
        self.latest_frame = None
        self.running = True
        self.lock = threading.Lock()
        self.opened = False
        self.last_read_time = time.time()
        
        # Open capture with FFmpeg backend for network streams
        if str(source_path_or_url).startswith("http"):
            self.cap = cv2.VideoCapture(source_path_or_url, cv2.CAP_FFMPEG)
            if not self.cap.isOpened():
                self.cap = cv2.VideoCapture(source_path_or_url)
        else:
            self.cap = cv2.VideoCapture(source_path_or_url)
            
        if self.cap and self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.opened = True
            ret, frame = self.cap.read()
            if ret and frame is not None:
                self.latest_frame = frame
            self.thread = threading.Thread(target=self._reader_loop, daemon=True)
            self.thread.start()

    def _reader_loop(self):
        while self.running and self.cap and self.cap.isOpened():
            try:
                ret, frame = self.cap.read()
                if ret and frame is not None and frame.size > 0:
                    with self.lock:
                        self.latest_frame = frame
                        self.last_read_time = time.time()
                    if self.is_file or not self.is_live:
                        time.sleep(0.016)
                    else:
                        time.sleep(0.004)
                else:
                    if self.is_file or not self.is_live:
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        time.sleep(0.016)
                    else:
                        time.sleep(0.08)
            except Exception:
                time.sleep(0.2)

    def read(self):
        with self.lock:
            if self.latest_frame is not None:
                return True, self.latest_frame.copy()
            return False, None

    def release(self):
        self.running = False
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        self.opened = False

class VideoStreamWorker:
    def __init__(self, stream_id: int):
        self.stream_id = stream_id
        self.camera = None
        self.running = True
        self.last_frame_bytes = None
        self.fps = 20.0
        self.active_stream_url = None
        self.last_config_check = 0
        self.reconnect_cooldown = 0
        self.frame_count = 0
        self.fps_tracker = 20.0

    def release_capture(self):
        """Safely release camera reader."""
        if self.camera is not None:
            try:
                self.camera.release()
            except Exception:
                pass
            self.camera = None

    def get_capture(self):
        """Initializes or re-initializes ThreadedCamera based on current feed configuration."""
        cfg = STREAM_CONFIGS.get(self.stream_id, {})
        source_type = cfg.get("source_type", "DEMO")
        
        if source_type == "DISABLED":
            cfg["status"] = "DISABLED"
            cfg["error_message"] = "Feed is disabled by operator."
            self.release_capture()
            return None
            
        elif source_type in ["DEMO", "FILE"]:
            path = cfg.get("file_path")
            if path and os.path.exists(path):
                self.release_capture()
                cam = ThreadedCamera(path, is_live=False, is_file=True)
                if cam.opened:
                    cfg["status"] = "ONLINE"
                    cfg["error_message"] = None
                    return cam
                else:
                    cfg["status"] = "ERROR"
                    cfg["error_message"] = f"Failed to open video file: {os.path.basename(path)}"
                    return None
            else:
                cfg["status"] = "ERROR"
                cfg["error_message"] = "Video file not found."
                return None
                
        elif source_type == "YOUTUBE":
            yt_url = cfg.get("source_url", "")
            if not yt_url:
                cfg["status"] = "ERROR"
                cfg["error_message"] = "No YouTube URL specified."
                return None
                
            cfg["status"] = "CONNECTING"
            extract_res = extract_youtube_stream(yt_url)
            if not extract_res.get("success"):
                cfg["status"] = "ERROR"
                cfg["error_message"] = extract_res.get("error", "YouTube stream extraction failed.")
                return None
                
            stream_url = extract_res.get("stream_url")
            is_live = extract_res.get("is_live", False)
            cfg["is_live"] = is_live
            if extract_res.get("title") and cfg.get("name") == f"Feed {self.stream_id}":
                cfg["name"] = extract_res.get("title")[:32]
                
            self.release_capture()
            self.active_stream_url = stream_url
            
            cam = ThreadedCamera(stream_url, is_live=is_live, is_file=False)
            if cam.opened:
                cfg["status"] = "ONLINE"
                cfg["error_message"] = None
                return cam
            else:
                cfg["status"] = "ERROR"
                cfg["error_message"] = "Could not open direct stream from YouTube."
                return None
                
        return None

    def run(self):
        global ACTIVE_EMERGENCY_EVENTS, CURRENT_DECISION
        frame_time_tracker = time.time()
        
        while self.running:
            loop_start = time.time()
            try:
                cfg = STREAM_CONFIGS.get(self.stream_id, {})
                source_type = cfg.get("source_type", "DEMO")
                
                # If disabled or errored, render informative placeholder frame
                if source_type == "DISABLED":
                    self.last_frame_bytes = create_status_frame(
                        self.stream_id,
                        "FEED INACTIVE",
                        "This camera feed has been disabled in the feed configuration.",
                        is_error=False
                    )
                    with lock:
                        if self.stream_id in LATEST_METRICS:
                            del LATEST_METRICS[self.stream_id]
                    time.sleep(0.4)
                    continue

                if self.camera is None or not self.camera.opened:
                    now = time.time()
                    if now < self.reconnect_cooldown:
                        time.sleep(0.5)
                        continue
                        
                    self.camera = self.get_capture()
                    if self.camera is None:
                        err_msg = cfg.get("error_message") or "Stream connection error"
                        self.last_frame_bytes = create_status_frame(
                            self.stream_id,
                            "STREAM UNAVAILABLE",
                            err_msg,
                            is_error=True
                        )
                        self.reconnect_cooldown = now + 4.0
                        time.sleep(0.5)
                        continue

                ret, frame = self.camera.read()
                if not ret or frame is None or frame.size == 0:
                    time.sleep(0.04)
                    continue

                # Resize frame for uniform 20 FPS processing
                frame = cv2.resize(frame, (640, 360))
                
                # Calculate real-time FPS
                now = time.time()
                dt = now - frame_time_tracker
                frame_time_tracker = now
                if dt > 0:
                    inst_fps = 1.0 / dt
                    self.fps_tracker = 0.85 * self.fps_tracker + 0.15 * min(60.0, inst_fps)
                    self.fps = round(self.fps_tracker, 1)

                self.frame_count += 1
                run_inference = (self.frame_count % 2 == 0)

                # 1. Run YOLO + Emergency Vehicle Detection
                annotated_frame, detections, counts, emerg_detected, emerg_details = detector.detect_frame(
                    frame, stream_id=self.stream_id, run_inference=run_inference
                )

                # 2. Process with Pandas Analytics
                with lock:
                    road_name = cfg.get("name", f"Stream {self.stream_id}")
                    metrics = analytics.process_frame_detections(self.stream_id, detections, counts, frame.shape)
                    metrics["fps"] = self.fps
                    metrics["road_name"] = road_name
                    metrics["source_type"] = source_type
                    metrics["is_live"] = cfg.get("is_live", False)
                    metrics["status"] = "ONLINE"
                    LATEST_METRICS[self.stream_id] = metrics
                    
                    if emerg_detected:
                        evt = {
                            "stream_id": self.stream_id,
                            "road_name": road_name,
                            "timestamp": now,
                            "status": "ACTIVE",
                            "details": emerg_details
                        }
                        ACTIVE_EMERGENCY_EVENTS = [e for e in ACTIVE_EMERGENCY_EVENTS if e["stream_id"] != self.stream_id]
                        ACTIVE_EMERGENCY_EVENTS.append(evt)
                        db.log_emergency_event(CURRENT_SESSION_ID, self.stream_id, "Ambulance/Emergency Unit", 0.95)
                    else:
                        ACTIVE_EMERGENCY_EVENTS = [
                            e for e in ACTIVE_EMERGENCY_EVENTS 
                            if not (e["stream_id"] == self.stream_id and (now - e["timestamp"] > 6.0))
                        ]

                    if int(now * 10) % 20 == 0:
                        db.log_telemetry(CURRENT_SESSION_ID, self.stream_id, now, metrics)

                # Fast JPEG encoding
                ret_enc, buffer = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 68])
                if ret_enc:
                    self.last_frame_bytes = buffer.tobytes()

                # Smooth high framerate pacing (target 40-45 FPS)
                TARGET_FPS = 45.0
                elapsed = time.time() - loop_start
                sleep_target = max(0.001, (1.0 / TARGET_FPS) - elapsed)
                time.sleep(sleep_target)

            except Exception as e:
                print(f"[Stream Worker {self.stream_id} Exception] {e}")
                cfg = STREAM_CONFIGS.get(self.stream_id, {})
                cfg["status"] = "ERROR"
                cfg["error_message"] = f"Processing error: {str(e)[:60]}"
                self.last_frame_bytes = create_status_frame(
                    self.stream_id,
                    "STREAM ERROR",
                    str(e),
                    is_error=True
                )
                self.release_capture()
                time.sleep(1.0)

stream_workers = {}

def start_stream_workers():
    for sid in [1, 2, 3]:
        worker = VideoStreamWorker(sid)
        stream_workers[sid] = worker
        t = threading.Thread(target=worker.run, daemon=True)
        t.start()

def reload_feed_source(stream_id: int):
    """Signals a specific stream worker to reload its video source."""
    if stream_id in stream_workers:
        worker = stream_workers[stream_id]
        worker.release_capture()
        worker.reconnect_cooldown = 0

def decision_scheduler_loop():
    """Background worker that continuously computes optimal signal timings & decisions"""
    global CURRENT_DECISION
    while True:
        try:
            with lock:
                if LATEST_METRICS:
                    decision = decision_engine.evaluate_traffic_state(LATEST_METRICS, ACTIVE_EMERGENCY_EVENTS)
                    if decision:
                        CURRENT_DECISION = decision
                        if SIGNAL_STATE["operator_mode"] == "AUTOMATED_APPROVED":
                            SIGNAL_STATE["active_schedule"] = decision["recommended_timings"]
                            SIGNAL_STATE["current_decision"] = decision
        except Exception as e:
            print(f"[Decision Engine Error] {e}")
            
        time.sleep(2.0)

def signal_countdown_loop():
    """Real-time signal cycle state machine"""
    while True:
        try:
            with lock:
                schedule = SIGNAL_STATE.get("active_schedule", {})
                cur_stream = SIGNAL_STATE.get("active_stream", 1)
                rem = SIGNAL_STATE.get("remaining_seconds", 30) - 1
                
                if rem <= 0:
                    streams = [1, 2, 3]
                    next_idx = (streams.index(cur_stream) + 1) % len(streams) if cur_stream in streams else 0
                    next_stream = streams[next_idx]
                    SIGNAL_STATE["active_stream"] = next_stream
                    SIGNAL_STATE["current_phase"] = "GREEN"
                    SIGNAL_STATE["remaining_seconds"] = schedule.get(next_stream, 30)
                else:
                    SIGNAL_STATE["remaining_seconds"] = rem
                    if rem <= 3:
                        SIGNAL_STATE["current_phase"] = "YELLOW"
                    else:
                        SIGNAL_STATE["current_phase"] = "GREEN"
        except Exception as e:
            print(f"[Signal Controller Error] {e}")
            
        time.sleep(1.0)

# Flask Routes
@app.route('/')
def index():
    return render_template('index.html')

def generate_mjpeg(stream_id: int):
    worker = stream_workers.get(stream_id)
    while True:
        if worker and worker.last_frame_bytes:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + worker.last_frame_bytes + b'\r\n')
        else:
            # Fallback frame if worker hasn't generated one yet
            fallback = create_status_frame(stream_id, "CONNECTING", "Initializing camera stream...", False)
            if fallback:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + fallback + b'\r\n')
        time.sleep(0.008)

@app.route('/api/stream/<int:stream_id>')
def stream_video(stream_id):
    return Response(generate_mjpeg(stream_id),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/metrics/live')
def get_live_metrics():
    with lock:
        return jsonify({
            "status": "success",
            "session_id": CURRENT_SESSION_ID,
            "metrics": LATEST_METRICS,
            "stream_configs": STREAM_CONFIGS,
            "decision": CURRENT_DECISION,
            "emergency_active": len(ACTIVE_EMERGENCY_EVENTS) > 0,
            "emergency_events": ACTIVE_EMERGENCY_EVENTS,
            "signal_state": SIGNAL_STATE,
            "detector_yolo": detector.is_yolo_active
        })

@app.route('/api/feed/status')
def get_feed_status():
    with lock:
        return jsonify({
            "status": "success",
            "feeds": STREAM_CONFIGS
        })

@app.route('/api/system/reset', methods=['POST'])
def reset_system():
    """Resets entire database, telemetry history, and reinitializes feeds."""
    global CURRENT_SESSION_ID, CURRENT_DECISION, ACTIVE_EMERGENCY_EVENTS
    with lock:
        db.reset_db()
        CURRENT_SESSION_ID = f"SES-{int(time.time())}"
        CURRENT_DECISION = None
        ACTIVE_EMERGENCY_EVENTS = []
        analytics.buffers = {
            1: pd.DataFrame(columns=["timestamp", "vehicle_count", "density", "cars", "motorcycles", "buses", "trucks", "emergency", "weighted_load"]),
            2: pd.DataFrame(columns=["timestamp", "vehicle_count", "density", "cars", "motorcycles", "buses", "trucks", "emergency", "weighted_load"]),
            3: pd.DataFrame(columns=["timestamp", "vehicle_count", "density", "cars", "motorcycles", "buses", "trucks", "emergency", "weighted_load"])
        }
        LATEST_METRICS.clear()
        
    return load_demo()

@app.route('/api/youtube/validate', methods=['POST'])
def validate_youtube():
    """Validates a YouTube URL before applying it to a stream."""
    data = request.get_json() or {}
    url = data.get("url", "").strip()
    
    if not url:
        return jsonify({"status": "error", "message": "Please provide a YouTube URL."}), 400
        
    if not is_valid_youtube_url(url):
        return jsonify({
            "status": "error",
            "message": "Invalid YouTube URL format. Enter a valid YouTube link (e.g. https://www.youtube.com/watch?v=... or https://youtu.be/...)."
        }), 400
        
    info = extract_youtube_stream(url, force_refresh=True)
    if info.get("success"):
        return jsonify({
            "status": "success",
            "title": info.get("title"),
            "is_live": info.get("is_live"),
            "duration": info.get("duration")
        })
    else:
        return jsonify({
            "status": "error",
            "message": info.get("error", "Could not extract stream from this YouTube link.")
        }), 400

@app.route('/api/feed/configure', methods=['POST'])
def configure_single_feed():
    """Configures source for a single feed (1, 2, or 3). Handles JSON and FormData safely."""
    data = request.get_json(silent=True) or {}
    
    feed_id = request.form.get("feed_id", type=int) or data.get("feed_id")
    if isinstance(feed_id, str) and feed_id.isdigit():
        feed_id = int(feed_id)
        
    if not feed_id or feed_id not in [1, 2, 3]:
        return jsonify({"status": "error", "message": "Invalid feed_id (must be 1, 2, or 3)"}), 400

    source_type = request.form.get("source_type") or data.get("source_type")
    custom_name = request.form.get("name") or data.get("name")
    
    with lock:
        cfg = STREAM_CONFIGS[feed_id]
        
        if source_type == "DEMO":
            demo_files = {
                1: "road1_heavy_highway.mp4",
                2: "road2_medium_urban.mp4",
                3: "road3_suburban_emergency.mp4"
            }
            demo_names = {
                1: "North Arterial - Highway 101",
                2: "East Boulevard - City Center",
                3: "West Parkway - Hospital Corridor"
            }
            cfg["source_type"] = "DEMO"
            cfg["source_url"] = ""
            cfg["file_path"] = os.path.join(SAMPLES_DIR, demo_files[feed_id])
            cfg["name"] = custom_name or demo_names[feed_id]
            cfg["is_live"] = False
            cfg["status"] = "CONNECTING"
            cfg["error_message"] = None

        elif source_type == "YOUTUBE":
            yt_url = (request.form.get("youtube_url") or data.get("youtube_url") or "").strip()
            if not yt_url:
                return jsonify({"status": "error", "message": "YouTube URL is required."}), 400
                
            clean_url = yt_url.rstrip("/")
            if clean_url in ["http://www.youtube.com", "https://www.youtube.com", "http://youtube.com", "https://youtube.com"]:
                return jsonify({
                    "status": "error",
                    "message": "Please enter a specific video or livestream link (e.g. https://www.youtube.com/live/... or https://www.youtube.com/watch?v=...)."
                }), 400
                
            if not is_valid_youtube_url(yt_url):
                return jsonify({"status": "error", "message": "Invalid video URL format."}), 400
                
            cfg["source_type"] = "YOUTUBE"
            cfg["source_url"] = yt_url
            cfg["status"] = "CONNECTING"
            cfg["error_message"] = None
            clear_stream_cache(yt_url)
            
            # Extract stream immediately
            extract_res = extract_youtube_stream(yt_url, force_refresh=True)
            if not extract_res.get("success"):
                cfg["status"] = "ERROR"
                cfg["error_message"] = extract_res.get("error", "Failed to extract YouTube stream.")
                return jsonify({"status": "error", "message": cfg["error_message"]}), 400
                
            title = extract_res.get("title") or f"YouTube Feed {feed_id}"
            cfg["name"] = custom_name or title
            cfg["is_live"] = extract_res.get("is_live", False)
            cfg["status"] = "ONLINE"
            reload_feed_source(feed_id)
            
            return jsonify({
                "status": "success",
                "message": f"Successfully connected Feed 0{feed_id} to: {cfg['name']}",
                "title": cfg["name"],
                "config": cfg
            })

        elif source_type == "FILE":
            uploaded_file = request.files.get("video_file")
            if not uploaded_file and not cfg.get("file_path"):
                return jsonify({"status": "error", "message": "No video file provided."}), 400
                
            if uploaded_file:
                filename = secure_filename(uploaded_file.filename)
                save_path = os.path.join(UPLOAD_DIR, f"stream_{feed_id}_{filename}")
                uploaded_file.save(save_path)
                cfg["file_path"] = save_path
                cfg["name"] = custom_name or f"Upload: {filename[:18]}"
                
            cfg["source_type"] = "FILE"
            cfg["source_url"] = ""
            cfg["is_live"] = False
            cfg["status"] = "CONNECTING"
            cfg["error_message"] = None

        elif source_type == "DISABLED":
            cfg["source_type"] = "DISABLED"
            cfg["status"] = "DISABLED"
            cfg["error_message"] = "Feed disabled by operator."
            
        else:
            return jsonify({"status": "error", "message": "Invalid source_type."}), 400

        cfg["last_updated"] = time.time()
        reload_feed_source(feed_id)

    return jsonify({
        "status": "success",
        "message": f"Feed {feed_id} successfully configured as {cfg['source_type']}.",
        "config": cfg
    })

@app.route('/api/upload', methods=['POST'])
def upload_videos():
    """Supports simultaneous 1-3 video file uploads."""
    uploaded_files = request.files.getlist("videos")
    if not uploaded_files or len(uploaded_files) == 0:
        return jsonify({"status": "error", "message": "No video files provided"}), 400

    assigned = {}
    with lock:
        for idx, file in enumerate(uploaded_files[:3]):
            stream_id = idx + 1
            filename = secure_filename(file.filename)
            save_path = os.path.join(UPLOAD_DIR, f"stream_{stream_id}_{filename}")
            file.save(save_path)
            
            cfg = STREAM_CONFIGS[stream_id]
            cfg["source_type"] = "FILE"
            cfg["source_url"] = ""
            cfg["file_path"] = save_path
            cfg["name"] = f"Upload {stream_id}: {filename[:18]}"
            cfg["is_live"] = False
            cfg["status"] = "CONNECTING"
            cfg["error_message"] = None
            assigned[stream_id] = cfg["name"]
            reload_feed_source(stream_id)

    return jsonify({
        "status": "success",
        "message": f"Successfully loaded {len(assigned)} live video stream(s).",
        "assigned_streams": assigned
    })

@app.route('/api/load_demo', methods=['POST'])
def load_demo():
    """Resets all 3 feeds to realistic built-in multi-video traffic demo scenarios."""
    demo_files = {
        1: "road1_heavy_highway.mp4",
        2: "road2_medium_urban.mp4",
        3: "road3_suburban_emergency.mp4"
    }
    demo_names = {
        1: "North Arterial - Highway 101",
        2: "East Boulevard - City Center",
        3: "West Parkway - Hospital Corridor"
    }
    with lock:
        for sid in [1, 2, 3]:
            cfg = STREAM_CONFIGS[sid]
            cfg["source_type"] = "DEMO"
            cfg["source_url"] = ""
            cfg["file_path"] = os.path.join(SAMPLES_DIR, demo_files[sid])
            cfg["name"] = demo_names[sid]
            cfg["is_live"] = False
            cfg["status"] = "CONNECTING"
            cfg["error_message"] = None
            reload_feed_source(sid)
            
    return jsonify({
        "status": "success",
        "message": "Loaded 3 Smart City Demonstration Traffic Streams (Highway, Urban Crossing, Ambulance)."
    })

@app.route('/api/decision/latest')
def get_latest_decision():
    with lock:
        return jsonify({
            "status": "success",
            "decision": CURRENT_DECISION,
            "signal_state": SIGNAL_STATE
        })

@app.route('/api/decision/action', methods=['POST'])
def submit_operator_action():
    """Human-in-the-loop operator action on AI decision recommendations."""
    global CURRENT_DECISION
    data = request.get_json() or {}
    action = data.get("action")
    allocated_green = data.get("allocated_green_time")
    custom_timings = data.get("custom_timings")
    
    with lock:
        if not CURRENT_DECISION:
            # Fallback if no decision yet
            CURRENT_DECISION = {
                "priority_order": [1, 2, 3],
                "recommended_timings": {1: 45, 2: 30, 3: 20},
                "reasoning": "Standard density equilibrium",
                "is_emergency": False,
                "target_road": 1
            }
            
        target = CURRENT_DECISION.get("target_road", 1)
        if allocated_green and isinstance(allocated_green, (int, float)):
            CURRENT_DECISION["recommended_timings"][target] = int(allocated_green)
            
        if action == "APPROVE":
            SIGNAL_STATE["operator_mode"] = "OPERATOR_APPROVED"
            SIGNAL_STATE["active_schedule"] = CURRENT_DECISION["recommended_timings"]
            CURRENT_DECISION["status"] = "APPROVED"
            db.create_decision(
                CURRENT_SESSION_ID,
                CURRENT_DECISION["priority_order"],
                CURRENT_DECISION["recommended_timings"],
                CURRENT_DECISION["reasoning"],
                1 if CURRENT_DECISION["is_emergency"] else 0
            )
            msg = f"Operator APPROVED plan. Road {target} allocated {CURRENT_DECISION['recommended_timings'].get(target, 45)}s green."
            
        elif action == "REJECT":
            CURRENT_DECISION["status"] = "REJECTED"
            msg = "Operator REJECTED proposal. Standard balanced schedule active."
            
        elif action == "CUSTOMIZE" and custom_timings:
            SIGNAL_STATE["active_schedule"] = custom_timings
            CURRENT_DECISION["status"] = "MODIFIED"
            CURRENT_DECISION["recommended_timings"] = custom_timings
            msg = f"Operator applied CUSTOM timings: {custom_timings}."
            
        elif action in ["EMERGENCY_CLEAR", "EMERGENCY_CLEARANCE"]:
            emerg_stream = data.get("corridor") or data.get("stream_id", 3)
            SIGNAL_STATE["emergency_override"] = True
            SIGNAL_STATE["active_stream"] = emerg_stream
            SIGNAL_STATE["remaining_seconds"] = 60
            SIGNAL_STATE["current_phase"] = "GREEN"
            msg = f"EMERGENCY GREEN CORRIDOR authorized for Road {emerg_stream}."
        else:
            return jsonify({"status": "error", "message": "Invalid operator action"}), 400

    return jsonify({
        "status": "success",
        "message": msg,
        "current_decision": CURRENT_DECISION,
        "signal_state": SIGNAL_STATE
    })

@app.route('/api/decisions/history')
@app.route('/api/audit_logs')
def get_decision_history():
    history = db.get_recent_decisions(limit=25)
    return jsonify({"status": "success", "history": history, "logs": history})

@app.route('/api/analytics/system')
def get_system_analytics_api():
    """Returns Pandas statistical analytics for the Analytics view tab."""
    with lock:
        sys_data = analytics.get_system_analytics()
    return jsonify({"status": "success", "analytics": sys_data})

if __name__ == '__main__':
    # Ensure sample videos exist
    from sample_generator import generate_sample_videos
    generate_sample_videos(SAMPLES_DIR)
    
    # Start streaming workers & decision background threads
    start_stream_workers()
    threading.Thread(target=decision_scheduler_loop, daemon=True).start()
    threading.Thread(target=signal_countdown_loop, daemon=True).start()
    
    port = int(os.environ.get("PORT", 5000))
    print("\n" + "="*70)
    print("🚦 SMART CITY TRAFFIC COMMAND CENTER SERVER RUNNING")
    print(f"🌐 Interface: http://0.0.0.0:{port}")
    print("="*70 + "\n")
    
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
