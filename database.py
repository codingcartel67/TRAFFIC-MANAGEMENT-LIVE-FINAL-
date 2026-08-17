import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "traffic_center.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def reset_db():
    """Wipes all old session logs and starts fresh."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS traffic_sessions")
        cursor.execute("DROP TABLE IF EXISTS traffic_telemetry")
        cursor.execute("DROP TABLE IF EXISTS decision_logs")
        cursor.execute("DROP TABLE IF EXISTS emergency_alerts")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB Reset Error] {e}")
    init_db()

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Sessions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS traffic_sessions (
        session_id TEXT PRIMARY KEY,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        video1_name TEXT,
        video2_name TEXT,
        video3_name TEXT,
        status TEXT DEFAULT 'ACTIVE'
    )
    """)
    
    # Telemetry table for high-frequency Pandas/YOLO detection metrics
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS traffic_telemetry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        timestamp REAL,
        video_id INTEGER,
        vehicle_count INTEGER,
        density REAL,
        congestion_level TEXT,
        cars INTEGER DEFAULT 0,
        motorcycles INTEGER DEFAULT 0,
        buses INTEGER DEFAULT 0,
        trucks INTEGER DEFAULT 0,
        emergency INTEGER DEFAULT 0,
        trend TEXT,
        fps REAL DEFAULT 0.0
    )
    """)
    
    # Decision logs for Operator Approval USP
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS decision_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        recommended_priority TEXT,
        recommended_timings TEXT,
        reasoning TEXT,
        status TEXT DEFAULT 'PENDING',
        operator_action TEXT,
        actual_timings TEXT,
        emergency_flag INTEGER DEFAULT 0
    )
    """)
    
    # Emergency vehicle detection events
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS emergency_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        video_id INTEGER,
        vehicle_type TEXT,
        confidence REAL,
        cleared_at TIMESTAMP,
        status TEXT DEFAULT 'ACTIVE'
    )
    """)
    
    conn.commit()
    conn.close()

def log_telemetry(session_id, video_id, timestamp, metrics):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO traffic_telemetry (
            session_id, timestamp, video_id, vehicle_count, density, congestion_level,
            cars, motorcycles, buses, trucks, emergency, trend, fps
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            timestamp,
            video_id,
            metrics.get('vehicle_count', 0),
            metrics.get('density', 0.0),
            metrics.get('congestion_level', 'LOW'),
            metrics.get('breakdown', {}).get('cars', 0),
            metrics.get('breakdown', {}).get('motorcycles', 0),
            metrics.get('breakdown', {}).get('buses', 0),
            metrics.get('breakdown', {}).get('trucks', 0),
            metrics.get('breakdown', {}).get('emergency', 0),
            metrics.get('trend', 'STABLE'),
            metrics.get('fps', 0.0)
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB Error] log_telemetry: {e}")

def create_decision(session_id, priority_list, timings_dict, reasoning, emergency_flag=0):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO decision_logs (
            session_id, recommended_priority, recommended_timings, reasoning, status, emergency_flag
        ) VALUES (?, ?, ?, ?, 'PENDING', ?)
        """, (
            session_id,
            json.dumps(priority_list),
            json.dumps(timings_dict),
            reasoning,
            emergency_flag
        ))
        decision_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return decision_id
    except Exception as e:
        print(f"[DB Error] create_decision: {e}")
        return None

def update_decision_status(decision_id, status, operator_action, actual_timings=None):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE decision_logs
        SET status = ?, operator_action = ?, actual_timings = ?
        WHERE id = ?
        """, (
            status,
            operator_action,
            json.dumps(actual_timings) if actual_timings else None,
            decision_id
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB Error] update_decision_status: {e}")
        return False

def get_recent_decisions(session_id=None, limit=20):
    try:
        conn = get_db()
        cursor = conn.cursor()
        if session_id:
            cursor.execute("""
            SELECT * FROM decision_logs WHERE session_id = ? ORDER BY id DESC LIMIT ?
            """, (session_id, limit))
        else:
            cursor.execute("""
            SELECT * FROM decision_logs ORDER BY id DESC LIMIT ?
            """, (limit,))
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        print(f"[DB Error] get_recent_decisions: {e}")
        return []

def log_emergency_event(session_id, video_id, vehicle_type, confidence):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO emergency_alerts (session_id, video_id, vehicle_type, confidence)
        VALUES (?, ?, ?, ?)
        """, (session_id, video_id, vehicle_type, confidence))
        alert_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return alert_id
    except Exception as e:
        print(f"[DB Error] log_emergency_event: {e}")
        return None

# Initialize on module load
init_db()
