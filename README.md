# 🚦 Aether.Traffic — Intelligent Multi-Corridor Traffic Command Center

A real-time, AI-driven traffic intelligence and signal optimization platform powered by **YOLOv8**, **OpenCV**, **Pandas Analytics**, and **Flask**.

Designed with an editorial command-center interface, Aether.Traffic monitors three concurrent intersection corridors via YouTube livestreams, uploaded videos, or synthetic traffic simulations. It dynamically computes road density, detects bottlenecks, tracks emergency vehicles with chromatic strobe analysis, and calculates dynamic signal green-wave timings.

---

## 🌟 Key Features

1. **Multi-Channel Video Ingestion**:
   * **Live YouTube Streams**: Ingests direct HLS (`.m3u8`) livestreams (e.g. Shibuya, Tokyo, Shinjuku, custom CCTV streams) using mobile client bot-bypass extraction.
   * **Local Video Uploads**: Drag-and-drop or select `.mp4`, `.avi`, `.mov` files per panel.
   * **Synthetic Scenario Simulator**: Built-in heavy highway, urban grid, and emergency corridor scenarios.

2. **Computer Vision & Emergency Detection**:
   * **YOLOv8n Object Detection**: Fast vehicle detection and classification (`car`, `motorcycle`, `bus`, `truck`).
   * **Emergency Strobe & Livery Detection**: Real-time HSV chromatic strobe and high-contrast emergency vehicle recognition for instant priority green-wave preemption.
   * **High Frame-Rate Pipeline**: Multi-threaded camera workers delivering 30–60 FPS processing and ~120 FPS socket delivery.

3. **Pandas-Powered Traffic Analytics**:
   * **Geometric Road Occupancy**: Bounding-box area coverage relative to drivable ROI lanes.
   * **Passenger Car Equivalent (PCE) Weighted Load**: Differentiates buses (2.5x), trucks (2.2x), cars (1.0x), and bikes (0.5x).
   * **Spatial Hotspot Clustering**: Spatial density clustering identifying intersection bottlenecks.
   * **Traffic Trend Slope**: Real-time polynomial regression tracking whether congestion is rising, falling, or stable.

4. **Dynamic Decision Intelligence**:
   * Computes optimal green light durations (10s–90s) based on proportional queue backlog.
   * Provides full transparent reasoning for every timing recommendation.
   * Operator human-in-the-loop controls: Approve recommendation, adjust duration slider, reject proposal, or trigger manual emergency override.

5. **Aether Command Center UI**:
   * Inspired by MagicPatterns editorial design system.
   * Active focus corridor showcase with 4-metric HUD telemetry.
   * Monitored corridors grid with dedicated per-panel source drawers.
   * Real-time network occupancy meters, vehicle classification breakdowns, and SQLite decision audit logs.

---

## 🏗️ Project Architecture

```
smart_traffic_center/
├── app.py                  # Main Flask application, background worker threads, API routes
├── detector.py             # YOLOv8 vehicle detection & emergency strobe feature analyzer
├── analytics.py            # Pandas traffic analytics engine (density, PCE load, trend slope)
├── decision_engine.py      # Signal scheduling algorithm & priority recommendation logic
├── database.py             # SQLite persistence for telemetry logs & operator audit decisions
├── youtube_stream.py       # Multi-client yt-dlp live stream resolver & bot bypass
├── sample_generator.py     # Procedural video generator for built-in demo scenarios
├── requirements.txt        # Python dependencies
├── yolov8n.pt              # YOLOv8 nano pre-trained model weights
├── static/
│   ├── css/
│   │   └── command_center.css  # Aether design system stylesheet
│   └── js/
│       └── app.js              # Frontend UI controller, telemetry polling, per-card drawers
├── templates/
│   └── index.html          # Main command center dashboard
├── samples/                # Built-in demo video files
└── uploads/                # Directory for user-uploaded corridor videos
```

---

## 📐 Mathematical Models & Formulas

### 1. Geometric Road Occupancy (%)
$$\text{Occupancy} = \min\left(100.0, \frac{\sum_{i=1}^{N} (\text{width}_i \times \text{height}_i)}{\text{Frame Area} \times 0.65} \times 100\right)$$

### 2. Weighted Traffic Load (PCE)
$$\text{Load} = 1.0 \times N_{\text{car}} + 0.5 \times N_{\text{motorcycle}} + 2.5 \times N_{\text{bus}} + 2.2 \times N_{\text{truck}} + 3.0 \times N_{\text{emergency}}$$

### 3. Dynamic Green Time Allocation
For road $k$ with queue backlog $Q_k = 0.55 \times \text{Density}_k + 0.45 \times \text{Load}_k$:
$$T_k = \text{clamp}\left(15, 80, \text{Round}\left(T_{\text{cycle}} \times \frac{Q_k}{\sum_{j} Q_j}\right)\right)$$

---

## 🚀 Quick Start Guide

### Prerequisites
* Python 3.10+
* Windows, macOS, or Linux

### Installation

1. **Clone or Extract the Project**:
```bash
git clone <your-repo-url>
cd smart_traffic_center
```

2. **Create a Virtual Environment (Optional but recommended)**:
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate
```

3. **Install Dependencies**:
```bash
pip install -r requirements.txt
```

4. **Launch the Command Center Server**:
```bash
python app.py
```

5. **Open in Browser**:
Visit **[http://127.0.0.1:5000](http://127.0.0.1:5000)**.

---

## 🛠️ Tech Stack

* **Backend**: Flask 3.0, OpenCV (cv2), Ultralytics (YOLOv8), Pandas, NumPy, SQLite3, yt-dlp
* **Frontend**: Modern Vanilla JavaScript (ES6+), Vanilla CSS (Custom tokens), Semantic HTML5
* **AI Model**: YOLOv8 Nano (`yolov8n.pt`)

---

## 📄 License
MIT License. Free for educational, research, and production use.
