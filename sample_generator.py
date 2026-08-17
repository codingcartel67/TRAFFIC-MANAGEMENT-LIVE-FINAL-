import cv2
import numpy as np
import os
import math

def generate_sample_videos(output_dir):
    os.makedirs(output_dir, exist_ok=True)
    
    fps = 25
    duration_sec = 14
    total_frames = fps * duration_sec
    width, height = 640, 360
    
    # ----------------------------------------------------
    # Video 1: Heavy Congestion Highway (Road 1)
    # Multiple cars, trucks, buses bumper-to-bumper
    # ----------------------------------------------------
    v1_path = os.path.join(output_dir, "road1_heavy_highway.mp4")
    if not os.path.exists(v1_path):
        print("[Sample Gen] Creating Road 1 (Heavy Traffic Highway)...")
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out1 = cv2.VideoWriter(v1_path, fourcc, fps, (width, height))
        
        # Vehicles with start positions and speeds
        vehicles = [
            {"type": "bus", "color": (180, 100, 30), "w": 120, "h": 52, "x": 50, "y": 90, "speed": 1.2},
            {"type": "truck", "color": (40, 100, 180), "w": 135, "h": 56, "x": 240, "y": 90, "speed": 1.1},
            {"type": "car", "color": (200, 40, 40), "w": 75, "h": 40, "x": 420, "y": 95, "speed": 1.3},
            {"type": "car", "color": (40, 180, 40), "w": 70, "h": 38, "x": 30, "y": 170, "speed": 1.6},
            {"type": "car", "color": (180, 180, 20), "w": 72, "h": 38, "x": 160, "y": 170, "speed": 1.5},
            {"type": "truck", "color": (80, 80, 80), "w": 125, "h": 54, "x": 280, "y": 165, "speed": 1.4},
            {"type": "bus", "color": (20, 120, 200), "w": 130, "h": 54, "x": 450, "y": 165, "speed": 1.3},
            {"type": "motorcycle", "color": (0, 200, 255), "w": 38, "h": 22, "x": 80, "y": 250, "speed": 2.0},
            {"type": "car", "color": (210, 210, 210), "w": 74, "h": 40, "x": 180, "y": 245, "speed": 1.8},
            {"type": "car", "color": (130, 40, 160), "w": 70, "h": 39, "x": 320, "y": 245, "speed": 1.7},
            {"type": "car", "color": (30, 90, 200), "w": 75, "h": 40, "x": 460, "y": 245, "speed": 1.7},
        ]
        
        for f in range(total_frames):
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            # Asphalt road background
            frame[:] = (42, 45, 48)
            # Lane markings
            for y_lane in [70, 150, 230, 310]:
                cv2.line(frame, (0, y_lane), (width, y_lane), (180, 180, 180), 2)
            # Dashed center lines
            for y_dash in [150, 230]:
                for x_dash in range(0, width, 40):
                    cv2.line(frame, (x_dash, y_dash), (x_dash + 20, y_dash), (255, 255, 255), 2)
                    
            # Draw Road Title HUD
            cv2.putText(frame, "NORTH ARTERIAL - HIGHWAY CORRIDOR 01", (20, 35),
                        cv2.FONT_HERSHEY_DUPLEX, 0.55, (220, 220, 220), 1)

            # Move and render vehicles
            for v in vehicles:
                v["x"] = (v["x"] + v["speed"]) % (width + 150)
                vx = int(v["x"]) - 100
                vy = int(v["y"])
                vw = v["w"]
                vh = v["h"]
                
                # Draw vehicle body
                cv2.rectangle(frame, (vx, vy), (vx + vw, vy + vh), v["color"], -1)
                cv2.rectangle(frame, (vx, vy), (vx + vw, vy + vh), (20, 20, 20), 2)
                # Windshield & details
                cv2.rectangle(frame, (vx + vw - 22, vy + 4), (vx + vw - 6, vy + vh - 4), (70, 85, 100), -1)
                # Headlights
                cv2.circle(frame, (vx + vw - 2, vy + 7), 3, (150, 255, 255), -1)
                cv2.circle(frame, (vx + vw - 2, vy + vh - 7), 3, (150, 255, 255), -1)
                
            out1.write(frame)
        out1.release()
        print("[Sample Gen] Road 1 generated successfully.")

    # ----------------------------------------------------
    # Video 2: Medium Traffic Urban Crossing (Road 2)
    # ----------------------------------------------------
    v2_path = os.path.join(output_dir, "road2_medium_urban.mp4")
    if not os.path.exists(v2_path):
        print("[Sample Gen] Creating Road 2 (Medium Traffic Urban)...")
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out2 = cv2.VideoWriter(v2_path, fourcc, fps, (width, height))
        
        vehicles2 = [
            {"type": "car", "color": (220, 220, 220), "w": 75, "h": 40, "x": 60, "y": 105, "speed": 2.5},
            {"type": "car", "color": (50, 60, 200), "w": 72, "h": 38, "x": 300, "y": 105, "speed": 2.3},
            {"type": "motorcycle", "color": (0, 220, 255), "w": 38, "h": 22, "x": 180, "y": 185, "speed": 3.2},
            {"type": "bus", "color": (20, 160, 220), "w": 125, "h": 52, "x": 420, "y": 175, "speed": 2.0},
            {"type": "car", "color": (40, 170, 60), "w": 74, "h": 39, "x": 100, "y": 255, "speed": 2.6},
        ]
        
        for f in range(total_frames):
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            frame[:] = (45, 48, 52)
            # Lanes
            for y_lane in [80, 160, 240, 320]:
                cv2.line(frame, (0, y_lane), (width, y_lane), (180, 180, 180), 2)
            for y_dash in [160, 240]:
                for x_dash in range(0, width, 50):
                    cv2.line(frame, (x_dash, y_dash), (x_dash + 25, y_dash), (255, 255, 255), 2)
                    
            cv2.putText(frame, "EAST ARTERIAL - CITY CENTER BOULEVARD", (20, 40),
                        cv2.FONT_HERSHEY_DUPLEX, 0.55, (220, 220, 220), 1)

            for v in vehicles2:
                v["x"] = (v["x"] + v["speed"]) % (width + 120)
                vx = int(v["x"]) - 80
                vy = int(v["y"])
                vw = v["w"]
                vh = v["h"]
                
                cv2.rectangle(frame, (vx, vy), (vx + vw, vy + vh), v["color"], -1)
                cv2.rectangle(frame, (vx, vy), (vx + vw, vy + vh), (20, 20, 20), 2)
                cv2.rectangle(frame, (vx + vw - 20, vy + 4), (vx + vw - 5, vy + vh - 4), (70, 85, 100), -1)
                cv2.circle(frame, (vx + vw - 2, vy + 7), 3, (150, 255, 255), -1)
                cv2.circle(frame, (vx + vw - 2, vy + vh - 7), 3, (150, 255, 255), -1)
                
            out2.write(frame)
        out2.release()
        print("[Sample Gen] Road 2 generated successfully.")

    # ----------------------------------------------------
    # Video 3: Suburban Road with EMERGENCY AMBULANCE (Road 3)
    # Triggers Emergency Priority Override USP!
    # ----------------------------------------------------
    v3_path = os.path.join(output_dir, "road3_suburban_emergency.mp4")
    if not os.path.exists(v3_path):
        print("[Sample Gen] Creating Road 3 (Emergency Ambulance Transit)...")
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out3 = cv2.VideoWriter(v3_path, fourcc, fps, (width, height))
        
        vehicles3 = [
            {"type": "car", "color": (50, 140, 220), "w": 72, "h": 38, "x": 380, "y": 105, "speed": 2.0},
            {"type": "emergency", "color": (245, 245, 245), "w": 115, "h": 50, "x": 20, "y": 180, "speed": 3.8},
            {"type": "motorcycle", "color": (200, 200, 30), "w": 36, "h": 22, "x": 420, "y": 260, "speed": 2.2},
        ]
        
        for f in range(total_frames):
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            frame[:] = (40, 44, 48)
            # Lanes
            for y_lane in [80, 160, 240, 320]:
                cv2.line(frame, (0, y_lane), (width, y_lane), (180, 180, 180), 2)
            for y_dash in [160, 240]:
                for x_dash in range(0, width, 50):
                    cv2.line(frame, (x_dash, y_dash), (x_dash + 25, y_dash), (255, 255, 255), 2)
                    
            cv2.putText(frame, "WEST PARKWAY - HOSPITAL CORRIDOR (EMERGENCY)", (20, 40),
                        cv2.FONT_HERSHEY_DUPLEX, 0.55, (220, 220, 220), 1)

            for v in vehicles3:
                v["x"] = (v["x"] + v["speed"]) % (width + 150)
                vx = int(v["x"]) - 100
                vy = int(v["y"])
                vw = v["w"]
                vh = v["h"]
                
                if v["type"] == "emergency":
                    # Draw Ambulance / Critical Response Vehicle
                    cv2.rectangle(frame, (vx, vy), (vx + vw, vy + vh), (250, 250, 250), -1)
                    cv2.rectangle(frame, (vx, vy), (vx + vw, vy + vh), (20, 20, 20), 2)
                    # Red emergency side stripes
                    cv2.rectangle(frame, (vx + 10, vy + vh//2 - 4), (vx + vw - 10, vy + vh//2 + 4), (0, 0, 220), -1)
                    # Medical Red Cross
                    cx, cy = vx + vw//2, vy + vh//2
                    cv2.rectangle(frame, (cx - 10, cy - 3), (cx + 10, cy + 3), (0, 0, 220), -1)
                    cv2.rectangle(frame, (cx - 3, cy - 10), (cx + 3, cy + 10), (0, 0, 220), -1)
                    
                    # Flashing Red/Blue Siren Light Bar on roof
                    siren_phase = (f // 3) % 2
                    siren_c1 = (0, 0, 255) if siren_phase == 0 else (255, 0, 0)
                    siren_c2 = (255, 0, 0) if siren_phase == 0 else (0, 0, 255)
                    cv2.rectangle(frame, (cx - 14, vy - 6), (cx - 2, vy), siren_c1, -1)
                    cv2.rectangle(frame, (cx + 2, vy - 6), (cx + 14, vy), siren_c2, -1)
                    # Siren light aura
                    cv2.circle(frame, (cx - 8, vy - 4), 7, siren_c1, 1)
                    cv2.circle(frame, (cx + 8, vy - 4), 7, siren_c2, 1)
                else:
                    cv2.rectangle(frame, (vx, vy), (vx + vw, vy + vh), v["color"], -1)
                    cv2.rectangle(frame, (vx, vy), (vx + vw, vy + vh), (20, 20, 20), 2)
                    cv2.rectangle(frame, (vx + vw - 20, vy + 4), (vx + vw - 5, vy + vh - 4), (70, 85, 100), -1)
                    
            out3.write(frame)
        out3.release()
        print("[Sample Gen] Road 3 generated successfully.")

    return [v1_path, v2_path, v3_path]

if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(__file__), "samples")
    generate_sample_videos(out_dir)
