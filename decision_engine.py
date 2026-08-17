import pandas as pd
import json
import time

class DecisionSupportEngine:
    """
    Intelligent Decision Support & Simulation Engine for Smart City Traffic Management.
    Provides advisory signal timing recommendations and simulated phase schedules
    derived from real video detections. Does not directly control physical hardware.
    """
    def __init__(self, cycle_time=90, min_green=12, max_green=55):
        self.total_cycle_time = cycle_time # Total simulated cycle time in seconds
        self.min_green = min_green
        self.max_green = max_green
        self.last_decision = None
        self.pending_operator_action = None

    def evaluate_traffic_state(self, road_metrics_map, emergency_events):
        """
        Takes real-time metrics dictionary from all active video streams and emergency state.
        
        Args:
            road_metrics_map: dict of {stream_id: metrics_dict}
            emergency_events: list of active emergency vehicle sightings
            
        Returns:
            decision_package: dict containing priority sequence, simulated green times,
                              per-road recommendations (congestion, hotspot, trend, action, reason),
                              and operator approval status.
        """
        now = time.time()
        
        # Check if there are any active emergency vehicles
        emergency_stream_id = None
        if emergency_events:
            for evt in emergency_events:
                if evt.get("status") == "ACTIVE" or evt.get("is_active", True):
                    emergency_stream_id = evt.get("stream_id")
                    break

        # Build Pandas DataFrame to rank traffic dynamically
        records = []
        for sid, metrics in road_metrics_map.items():
            records.append({
                "stream_id": sid,
                "name": metrics.get("road_name", f"Road {sid}"),
                "count": metrics.get("vehicle_count", 0),
                "density": metrics.get("density", 0.0),
                "weighted_load": metrics.get("weighted_load", 0.0),
                "congestion_level": metrics.get("congestion_level", "LOW"),
                "trend": metrics.get("trend", "STABLE"),
                "hotspot": metrics.get("hotspot", "Uniform Flow"),
                "is_emergency": (sid == emergency_stream_id),
                "breakdown": metrics.get("breakdown", {})
            })

        if not records:
            return None

        df = pd.DataFrame(records)

        # ----------------------------------------------------
        # SCENARIO A: EMERGENCY VEHICLE DETECTED (ADVISORY PRIORITY)
        # ----------------------------------------------------
        if emergency_stream_id is not None:
            df["priority_rank"] = df["stream_id"].apply(lambda x: 0 if x == emergency_stream_id else 1)
            df = df.sort_values(by=["priority_rank", "weighted_load", "density"], ascending=[True, False, False])
            
            priority_order = df["stream_id"].tolist()
            
            # Simulated Green Timings: 60s emergency clearance corridor
            timings = {}
            timings[emergency_stream_id] = 60
            
            remaining_time = max(20, self.total_cycle_time - 60)
            other_streams = [s for s in priority_order if s != emergency_stream_id]
            
            if other_streams:
                per_other = max(self.min_green, remaining_time // len(other_streams))
                for s in other_streams:
                    timings[s] = per_other

            # Construct Detailed Per-Road Recommendation Cards
            road_recommendations = []
            for _, row in df.iterrows():
                sid = int(row["stream_id"])
                is_emerg = (sid == emergency_stream_id)
                r_name = row["name"]
                c_level = row["congestion_level"]
                h_spot = row["hotspot"]
                t_trend = row["trend"]
                bk = row["breakdown"]
                
                if is_emerg:
                    r_action = f"Simulate Priority Green Corridor ({timings[sid]}s) — Preempt Normal Cycle"
                    r_reason = (
                        f"CRITICAL ADVISORY: Emergency Response Vehicle detected on {r_name}. "
                        f"Recommended immediate clearance wave to prevent transit delay. "
                        f"Hotspot: {h_spot}. Vehicle density: {row['density']}%."
                    )
                else:
                    r_action = f"Hold Red / Standby Phase ({timings.get(sid, 15)}s auxiliary green)"
                    r_reason = (
                        f"Secondary road during emergency corridor. Density: {row['density']}%, "
                        f"Active vehicles: {row['count']} (Cars: {bk.get('cars',0)}, Trucks: {bk.get('trucks',0)}). "
                        f"Traffic trend: {t_trend}."
                    )
                    
                road_recommendations.append({
                    "stream_id": sid,
                    "road_name": r_name,
                    "current_congestion_level": c_level,
                    "detected_hotspot": h_spot,
                    "traffic_trend": t_trend,
                    "recommended_action": r_action,
                    "reason_for_recommendation": r_reason,
                    "recommended_green_sec": timings.get(sid, 15),
                    "is_emergency": is_emerg
                })
                    
            decision = {
                "decision_id": f"REC-{int(now * 1000)}",
                "timestamp": now,
                "is_emergency": True,
                "emergency_stream": emergency_stream_id,
                "target_road": emergency_stream_id,
                "target_road_name": f"Feed 0{emergency_stream_id}",
                "allocated_green_time": 60,
                "headline": f"Emergency Wave: Clear Feed 0{emergency_stream_id} (Hold Green 60s)",
                "subtext": "Immediate preemption authorized for emergency response unit · hold 60s",
                "alert_title": f"[EMERGENCY] VEHICLE DETECTED - PRIORITY ADVISORY (FEED 0{emergency_stream_id})",
                "priority_order": priority_order,
                "recommended_timings": timings,
                "recommended_action": f"Authorize simulated emergency green corridor for Feed 0{emergency_stream_id} (60s).",
                "reasoning": (
                    f"EMERGENCY OVERRIDE ADVISORY: Real-time vision pipeline confirmed an emergency vehicle on Feed 0{emergency_stream_id}. "
                    f"Recommended simulated signal priority: Feed 0{emergency_stream_id} (60s), with other roads on hold. "
                    f"Awaiting Operator authorization."
                ),
                "status": "AWAITING_APPROVAL",
                "road_recommendations": road_recommendations,
                "system_type": "Advisory Decision Support & Simulation System"
            }
            self.last_decision = decision
            return decision

        # ----------------------------------------------------
        # SCENARIO B: DYNAMIC CONGESTION ADVISORY & SIMULATION
        # ----------------------------------------------------
        df = df.sort_values(by=["weighted_load", "density", "count"], ascending=[False, False, False])
        priority_order = df["stream_id"].tolist()

        # Demand-responsive traffic signal timing algorithm (Webster formulation)
        timings = {}
        for _, row in df.iterrows():
            sid = int(row["stream_id"])
            density = float(row["density"])
            count = int(row["count"])
            load = float(row["weighted_load"])
            
            # Realistically scale green duration by actual detected queue backlog
            if density <= 6.0 and count <= 1:
                green_sec = 15
            elif density <= 22.0 or count <= 3:
                green_sec = int(round(16 + (density / 22.0) * 12))  # 16s - 28s
            elif density <= 48.0 or count <= 6:
                green_sec = int(round(28 + ((density - 22) / 26.0) * 16))  # 28s - 44s
            else:
                # Heavy backlog (>48% occupancy or >=7 vehicles)
                green_sec = int(round(45 + min(20, ((density - 48) / 52.0) * 20)))  # 45s - 65s
                
            timings[sid] = max(self.min_green, min(65, green_sec))

        # Construct Detailed Per-Road Recommendation Cards
        road_recommendations = []
        for rank_idx, (_, row) in enumerate(df.iterrows(), 1):
            sid = int(row["stream_id"])
            r_name = row["name"]
            c_level = row["congestion_level"]
            h_spot = row["hotspot"]
            t_trend = row["trend"]
            load = row["weighted_load"]
            density = row["density"]
            count = row["count"]
            bk = row["breakdown"]
            alloc_time = timings.get(sid, 30)

            # Formulate specific deterministic reasoning for this road
            r_action = f"Simulate Priority #{rank_idx} Green Phase ({alloc_time}s)"
            r_reason = (
                f"{r_name} shows {c_level} congestion (Density: {density}%, Load: {load}, Trend: {t_trend}). "
                f"Detected queue concentration at {h_spot}. Vehicle breakdown: {bk.get('cars',0)} cars, "
                f"{bk.get('buses',0)} buses, {bk.get('trucks',0)} trucks, {bk.get('motorcycles',0)} bikes. "
                f"Simulating {alloc_time}s green phase to maximize intersection throughput."
            )

            road_recommendations.append({
                "stream_id": sid,
                "road_name": r_name,
                "priority_rank": rank_idx,
                "current_congestion_level": c_level,
                "detected_hotspot": h_spot,
                "traffic_trend": t_trend,
                "recommended_action": r_action,
                "reason_for_recommendation": r_reason,
                "recommended_green_sec": alloc_time,
                "is_emergency": False
            })

        top_road = df.iloc[0]
        top_id = int(top_road["stream_id"])
        top_name = top_road["name"]
        priority_text = " -> ".join([f"Feed 0{s}" for s in priority_order])
        top_green = timings.get(top_id, 45)
        
        overall_reasoning = (
            f"Advisory Calculation: Feed 0{top_id} ({top_name}) carries highest traffic burden "
            f"(Density: {top_road['density']}%, Weighted Load: {top_road['weighted_load']}, Hotspot: {top_road['hotspot']}). "
            f"Recommended priority sequence: {priority_text}. "
            f"Allocates {top_green}s green corridor to Feed 0{top_id} to clear queue backlog."
        )

        decision = {
            "decision_id": f"REC-{int(now * 1000)}",
            "timestamp": now,
            "is_emergency": False,
            "emergency_stream": None,
            "target_road": top_id,
            "target_road_name": top_name,
            "allocated_green_time": top_green,
            "headline": f"Hold {top_name} (Feed 0{top_id}) corridor green for {top_green}s",
            "subtext": f"Engine proposed {top_green}s based on {top_road['density']}% occupancy | adjustable 10-90s",
            "alert_title": "ADVISORY SIGNAL SCHEDULE SIMULATED",
            "priority_order": priority_order,
            "recommended_timings": timings,
            "recommended_action": f"Hold Feed 0{top_id} ({top_name}) corridor green for {top_green}s",
            "reasoning": overall_reasoning,
            "status": "AWAITING_APPROVAL",
            "road_recommendations": road_recommendations,
            "system_type": "Advisory Decision Support & Simulation System"
        }
        
        self.last_decision = decision
        return decision
