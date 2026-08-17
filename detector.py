import cv2
import numpy as np
import time
import os
import threading

# Try importing ultralytics YOLO if available
HAS_ULTRALYTICS = False
try:
    from ultralytics import YOLO
    HAS_ULTRALYTICS = True
    print("[Detector] Ultralytics YOLO module loaded successfully.")
except Exception as e:
    print(f"[Detector] Ultralytics import notice: {e}. Falling back to OpenCV DNN/Visual Vehicle Detector.")

# COCO Traffic Class IDs:
# 0: pedestrian (person), 1: bicycle, 2: car, 3: motorcycle, 5: bus, 7: truck
COCO_VEHICLE_CLASSES = {
    0: "pedestrian",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck"
}

# Color palette for HUD bounding boxes (BGR)
CLASS_COLORS = {
    "car": (255, 191, 0),        # Cyan/Electric Blue
    "motorcycle": (0, 230, 255), # Yellow/Gold
    "bicycle": (0, 230, 255),    # Gold
    "bus": (255, 105, 180),      # Violet/Purple
    "truck": (0, 140, 255),      # Bright Orange
    "pedestrian": (0, 255, 128), # Mint Green
    "emergency": (0, 0, 255)     # High Alert Red
}

class VehicleDetector:
    def __init__(self, model_name="yolov8n.pt", conf_threshold=0.35):
        self.conf_threshold = conf_threshold
        self.yolo_model = None
        self.is_yolo_active = False
        
        if not os.path.isabs(model_name):
            pkg_model = os.path.join(os.path.dirname(os.path.abspath(__file__)), model_name)
            if os.path.exists(pkg_model):
                model_name = pkg_model

        if HAS_ULTRALYTICS:
            try:
                # Load YOLOv8 model (auto-downloads yolov8n.pt if not present)
                self.yolo_model = YOLO(model_name)
                self.is_yolo_active = True
                print(f"[Detector] YOLOv8 model '{model_name}' initialized.")
            except Exception as e:
                print(f"[Detector] Could not load YOLOv8 model: {e}. Using Vision Vehicle Pipeline.")
                self.is_yolo_active = False

        # Background subtractor & optical tracker fallback
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=32, detectShadows=True)
        self.infer_lock = threading.Lock()
        self.stream_cache = {}
        
    def detect_emergency_features(self, frame, bbox):
        """
        Analyzes vehicle crop for emergency strobe lights (red/blue chromatic flashes),
        emergency white/red livery or siren patterns.
        """
        x1, y1, x2, y2 = bbox
        h, w, _ = frame.shape
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        
        if (x2 - x1) < 20 or (y2 - y1) < 20:
            return False, 0.0
            
        crop = frame[y1:y2, x1:x2]
        
        # Analyze top 30% of vehicle roof for red/blue siren lights
        roof_h = max(5, int((y2 - y1) * 0.35))
        roof_crop = crop[0:roof_h, :]
        
        hsv = cv2.cvtColor(roof_crop, cv2.COLOR_BGR2HSV)
        
        # Red mask in HSV (two ranges)
        mask_red1 = cv2.inRange(hsv, np.array([0, 120, 120]), np.array([10, 255, 255]))
        mask_red2 = cv2.inRange(hsv, np.array([170, 120, 120]), np.array([180, 255, 255]))
        mask_red = mask_red1 | mask_red2
        
        # Blue mask in HSV
        mask_blue = cv2.inRange(hsv, np.array([100, 150, 120]), np.array([135, 255, 255]))
        
        red_ratio = np.sum(mask_red > 0) / (roof_crop.shape[0] * roof_crop.shape[1] + 1e-5)
        blue_ratio = np.sum(mask_blue > 0) / (roof_crop.shape[0] * roof_crop.shape[1] + 1e-5)
        
        # Check overall white/high-contrast emergency body
        gray_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        bright_ratio = np.sum(gray_crop > 200) / (crop.shape[0] * crop.shape[1] + 1e-5)
        
        # Strobe pattern or marked emergency vehicle
        if (red_ratio > 0.04 and blue_ratio > 0.03) or (red_ratio > 0.08 and bright_ratio > 0.35):
            confidence = min(0.98, 0.65 + (red_ratio + blue_ratio) * 2.0)
            return True, confidence
            
        return False, 0.0

    def detect_frame(self, frame, stream_id=1, run_inference=True):
        """
        Runs vehicle detection on a single video frame.
        Supports fast frame interpolation to achieve 30+ FPS without CPU bottlenecks.
        """
        if not run_inference and stream_id in self.stream_cache:
            detections, counts, emergency_detected, emergency_details = self.stream_cache[stream_id]
            annotated_frame = self.draw_hud_overlays(frame.copy(), detections, counts, emergency_detected)
            return annotated_frame, detections, counts, emergency_detected, emergency_details

        h, w = frame.shape[:2]
        detections = []
        counts = {
            "car": 0,
            "motorcycle": 0,
            "bus": 0,
            "truck": 0,
            "emergency": 0
        }
        emergency_detected = False
        emergency_details = []

        if self.is_yolo_active and self.yolo_model is not None:
            try:
                with self.infer_lock:
                    results = self.yolo_model(frame, verbose=False, conf=self.conf_threshold, imgsz=384)[0]
                boxes = results.boxes
                
                for box in boxes:
                    cls_id = int(box.cls[0].item())
                    conf = float(box.conf[0].item())
                    
                    if cls_id in COCO_VEHICLE_CLASSES:
                        class_name = COCO_VEHICLE_CLASSES[cls_id]
                        xyxy = box.xyxy[0].cpu().numpy().astype(int)
                        x1, y1, x2, y2 = xyxy[0], xyxy[1], xyxy[2], xyxy[3]
                        
                        # Emergency vehicle check
                        is_emerg, emerg_conf = self.detect_emergency_features(frame, (x1, y1, x2, y2))
                        if is_emerg:
                            class_name = "emergency"
                            conf = max(conf, emerg_conf)
                            emergency_detected = True
                            emergency_details.append({
                                "type": "Ambulance/Emergency Unit",
                                "confidence": conf,
                                "bbox": [int(x1), int(y1), int(x2), int(y2)]
                            })
                            
                        counts[class_name] = counts.get(class_name, 0) + 1
                        detections.append({
                            "bbox": [int(x1), int(y1), int(x2), int(y2)],
                            "class": class_name,
                            "confidence": round(conf, 2),
                            "is_emergency": is_emerg
                        })
            except Exception as e:
                # If YOLO runtime error occurs, use vision detector
                print(f"[Detector] YOLO inference error: {e}")
                detections, counts, emergency_detected, emergency_details = self._vision_fallback_detect(frame)
        else:
            detections, counts, emergency_detected, emergency_details = self._vision_fallback_detect(frame)

        self.stream_cache[stream_id] = (detections, counts, emergency_detected, emergency_details)

        # Draw HUD overlays on frame
        annotated_frame = self.draw_hud_overlays(frame.copy(), detections, counts, emergency_detected)
        
        return annotated_frame, detections, counts, emergency_detected, emergency_details

    def _vision_fallback_detect(self, frame):
        """High performance OpenCV contour & blob vehicle detector"""
        h, w = frame.shape[:2]
        detections = []
        counts = {"car": 0, "motorcycle": 0, "bus": 0, "truck": 0, "emergency": 0}
        emergency_detected = False
        emergency_details = []

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        fg_mask = self.bg_subtractor.apply(blur)
        _, thresh = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        dilated = cv2.dilate(thresh, kernel, iterations=2)
        
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 750:  # Ignore small noise
                continue
                
            x, y, bw, bh = cv2.boundingRect(cnt)
            aspect_ratio = float(bw) / bh
            
            # Heuristic classification based on aspect ratio & bounding area
            if area > 12000 or (bw > w * 0.35 and bh > h * 0.25):
                class_name = "bus"
                conf = 0.88
            elif area > 6500 or bh > h * 0.3:
                class_name = "truck"
                conf = 0.84
            elif area < 2200 and aspect_ratio < 0.9:
                class_name = "motorcycle"
                conf = 0.79
            else:
                class_name = "car"
                conf = 0.91

            # Check emergency features
            is_emerg, emerg_conf = self.detect_emergency_features(frame, (x, y, x + bw, y + bh))
            if is_emerg:
                class_name = "emergency"
                conf = emerg_conf
                emergency_detected = True
                emergency_details.append({
                    "type": "Emergency Unit",
                    "confidence": conf,
                    "bbox": [x, y, x + bw, y + bh]
                })

            counts[class_name] = counts.get(class_name, 0) + 1
            detections.append({
                "bbox": [x, y, x + bw, y + bh],
                "class": class_name,
                "confidence": round(conf, 2),
                "is_emergency": is_emerg
            })

        return detections, counts, emergency_detected, emergency_details

    def draw_hud_overlays(self, frame, detections, counts, emergency_detected):
        """Draws tech-forward Command Center bounding boxes and HUD diagnostics"""
        h, w = frame.shape[:2]
        
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            cls_name = det["class"]
            conf = det["confidence"]
            
            color = CLASS_COLORS.get(cls_name, (0, 255, 255))
            
            if cls_name == "emergency":
                # High-visibility pulsing emergency box
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                # Flashing corner brackets
                bracket_len = min(20, (x2 - x1) // 3)
                cv2.line(frame, (x1, y1), (x1 + bracket_len, y1), (0, 255, 255), 3)
                cv2.line(frame, (x1, y1), (x1, y1 + bracket_len), (0, 255, 255), 3)
                cv2.line(frame, (x2, y2), (x2 - bracket_len, y2), (0, 255, 255), 3)
                cv2.line(frame, (x2, y2), (x2, y2 - bracket_len), (0, 255, 255), 3)
                
                # Badge label
                label = f"🚨 EMERGENCY {int(conf * 100)}%"
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_DUPLEX, 0.55, 1)
                cv2.rectangle(frame, (x1, max(0, y1 - 22)), (x1 + tw + 10, y1), (0, 0, 220), -1)
                cv2.putText(frame, label, (x1 + 5, y1 - 6), cv2.FONT_HERSHEY_DUPLEX, 0.55, (255, 255, 255), 1)
            else:
                # Sleek modern corner bracket bounding box
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 1)
                corner_len = min(15, (x2 - x1) // 4)
                # Top-Left
                cv2.line(frame, (x1, y1), (x1 + corner_len, y1), color, 2)
                cv2.line(frame, (x1, y1), (x1, y1 + corner_len), color, 2)
                # Bottom-Right
                cv2.line(frame, (x2, y2), (x2 - corner_len, y2), color, 2)
                cv2.line(frame, (x2, y2), (x2, y2 - corner_len), color, 2)

                # Class Tag Pill
                tag = f"{cls_name.upper()} {int(conf * 100)}%"
                (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
                cv2.rectangle(frame, (x1, max(0, y1 - 18)), (x1 + tw + 6, y1), (15, 20, 28), -1)
                cv2.rectangle(frame, (x1, max(0, y1 - 18)), (x1 + tw + 6, y1), color, 1)
                cv2.putText(frame, tag, (x1 + 3, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1)

        # Top-right live telemetry chip on the video frame
        total_veh = sum(counts.values())
        chip_w, chip_h = 160, 48
        cv2.rectangle(frame, (w - chip_w - 10, 10), (w - 10, 10 + chip_h), (10, 15, 25), -1)
        cv2.rectangle(frame, (w - chip_w - 10, 10), (w - 10, 10 + chip_h), (50, 70, 90), 1)
        
        cv2.putText(frame, f"LIVE OBJECTS: {total_veh}", (w - chip_w, 30),
                    cv2.FONT_HERSHEY_DUPLEX, 0.48, (0, 240, 255), 1)
        
        yolo_status = "YOLOv8 DETECT" if self.is_yolo_active else "CV2 AI ENGINE"
        cv2.putText(frame, yolo_status, (w - chip_w, 48),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (140, 255, 140), 1)

        return frame
