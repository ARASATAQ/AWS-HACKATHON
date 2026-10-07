from fastapi import APIRouter, Request, HTTPException, Body
from fastapi.responses import HTMLResponse, FileResponse
import logging, uuid, random, os, math
from datetime import datetime, timezone
from config import get_settings
from services.aws_service import get_aws_service
from services.whatsapp_service import send_rescue_dispatched, send_text_message
from services.hazard_monitor import HazardMonitor

router = APIRouter(prefix="/api/admin", tags=["Admin API"])
dashboard_router = APIRouter(tags=["Dashboard"])
logger = logging.getLogger(__name__)

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")

# ---------------------------------------------------------------------------
# Helper: fire SSE event without crashing if broadcaster isn't ready yet
# ---------------------------------------------------------------------------
async def _broadcast(request: Request, event_type: str, data: dict):
    try:
        broadcaster = request.app.state.sse_broadcaster
        await broadcaster.publish(event_type, data)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Helper: Haversine distance (km)
# ---------------------------------------------------------------------------
def _haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------
@dashboard_router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    dashboard_path = os.path.join(TEMPLATES_DIR, "dashboard.html")
    return FileResponse(dashboard_path, media_type="text/html")


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------
@router.get("/stats")
async def get_stats():
    aws = get_aws_service()
    citizens  = aws.get_all_citizens()
    incidents = aws.get_all_incidents()
    hazards   = aws.get_active_hazard_zones()
    hospitals = aws.get_all_hospitals()
    units     = aws.get_all_units()

    safe_count    = len([c for c in citizens if c.get("status") == "SAFE"])
    danger_count  = len([c for c in citizens if c.get("status") == "IN_DANGER"])
    rescued_count = len([c for c in citizens if c.get("status") == "RESCUED"])
    total_beds    = sum(h.get("beds_available", 0) for h in hospitals)

    fire_units    = sum(1 for u in units if u.get("unit_type") == "FIRE")
    police_units  = sum(1 for u in units if u.get("unit_type") == "POLICE")
    rescue_units  = sum(1 for u in units if u.get("unit_type") == "RESCUE")
    units_dispatched = sum(1 for u in units if u.get("status") == "DISPATCHED")

    return {
        "total_citizens":     len(citizens),
        "citizens_safe":      safe_count,
        "citizens_in_danger": danger_count,
        "citizens_rescued":   rescued_count,
        "active_incidents":   len(incidents),
        "active_hazard_zones": len(hazards),
        "hospitals_count":    len(hospitals),
        "total_beds":         total_beds,
        "fire_units":         fire_units,
        "police_units":       police_units,
        "rescue_units":       rescue_units,
        "units_dispatched":   units_dispatched,
    }


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------
@router.get("/incidents")
async def get_incidents():
    aws = get_aws_service()
    incidents = aws.get_all_incidents()
    enriched = []
    for inc in incidents:
        item = dict(inc)
        item["id"]       = item.get("incident_id")
        item["lng"]      = item.get("lon")
        item["severity"] = item.get("severity_level")
        item["findings"] = item.get("visual_findings")
        item["photo_url"]= item.get("image_url")
        enriched.append(item)
    return sorted(enriched, key=lambda i: i.get("severity_score", 0), reverse=True)


# ---------------------------------------------------------------------------
# Citizens
# ---------------------------------------------------------------------------
@router.get("/citizens")
async def get_citizens():
    aws = get_aws_service()
    citizens = aws.get_all_citizens()
    enriched = []
    for c in citizens:
        item = dict(c)
        item["lng"] = item.get("lon")
        enriched.append(item)
    return enriched


# ---------------------------------------------------------------------------
# Hazard zones
# ---------------------------------------------------------------------------
@router.get("/hazard-zones")
async def get_hazard_zones():
    aws = get_aws_service()
    zones = aws.get_active_hazard_zones()
    enriched = []
    for zone in zones:
        item = dict(zone)
        item["lng"]       = item.get("lon")
        item["type"]      = item.get("hazard_type")
        item["radius"]    = float(item.get("radius_km", 5)) * 1000.0
        item["intensity"] = item.get("intensity", item.get("color", "RED"))
        enriched.append(item)
    return enriched


# ---------------------------------------------------------------------------
# Hospitals
# ---------------------------------------------------------------------------
@router.get("/hospitals")
async def get_hospitals():
    aws = get_aws_service()
    hospitals = aws.get_all_hospitals()
    enriched = []
    for h in hospitals:
        item = dict(h)
        item["lng"]            = item.get("lon")
        item["available_beds"] = item.get("beds_available", 0)
        enriched.append(item)
    return enriched


# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------
@router.get("/units")
async def get_units():
    aws = get_aws_service()
    units = aws.get_all_units()
    for u in units:
        if "lon" in u:
            u["lng"] = u["lon"]
    return units


# ---------------------------------------------------------------------------
# AI: auto-recommend nearest appropriate unit for an incident
# ---------------------------------------------------------------------------
@router.get("/recommend-unit/{incident_id}")
async def recommend_unit(incident_id: str):
    """Returns the nearest STANDBY unit that matches the incident's hazard type."""
    aws = get_aws_service()
    incidents = aws.get_all_incidents()
    incident = next(
        (i for i in incidents if i.get("incident_id") == incident_id or i.get("id") == incident_id),
        None,
    )
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    hazard = incident.get("hazard_type", "UNKNOWN")
    # Preferred unit type per hazard
    preference_map = {
        "FLOOD":      ["RESCUE", "FIRE"],
        "EARTHQUAKE": ["RESCUE", "FIRE"],
        "TSUNAMI":    ["RESCUE", "FIRE"],
        "HEATWAVE":   ["RESCUE", "FIRE"],
        "UNKNOWN":    ["RESCUE", "POLICE", "FIRE"],
    }
    preferred_types = preference_map.get(hazard, ["RESCUE", "FIRE", "POLICE"])

    units = [u for u in aws.get_all_units() if u.get("status") == "STANDBY"]
    if not units:
        return {"recommended_unit": None, "reason": "No standby units available"}

    inc_lat = incident.get("lat", 0)
    inc_lon = incident.get("lon", 0)

    # Sort: preferred type first, then by Haversine distance
    def sort_key(u):
        type_rank = preferred_types.index(u.get("unit_type")) if u.get("unit_type") in preferred_types else 99
        dist = _haversine(inc_lat, inc_lon, u.get("lat", 0), u.get("lon", 0))
        return (type_rank, dist)

    sorted_units = sorted(units, key=sort_key)
    best = sorted_units[0]
    dist = _haversine(inc_lat, inc_lon, best.get("lat", 0), best.get("lon", 0))

    return {
        "recommended_unit": best,
        "distance_km": round(dist, 2),
        "reason": f"Nearest {best.get('unit_type')} unit for {hazard} ({round(dist, 2)} km away)",
    }


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
@router.post("/dispatch/{incident_id}")
async def dispatch_rescue(incident_id: str, request: Request):
    aws = get_aws_service()
    incidents = aws.get_all_incidents()
    incident = next(
        (i for i in incidents if i.get("incident_id") == incident_id or i.get("id") == incident_id),
        None,
    )
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    dispatched_unit = None
    try:
        body = await request.json()
        unit_id = body.get("unit_id")
        if unit_id and aws.use_mock and unit_id in aws._mock_units:
            aws._mock_units[unit_id]["status"] = "DISPATCHED"
            aws._mock_units[unit_id]["lat"] = incident.get("lat", aws._mock_units[unit_id]["lat"])
            aws._mock_units[unit_id]["lon"] = incident.get("lon", aws._mock_units[unit_id]["lon"])
            dispatched_unit = aws._mock_units[unit_id]
    except Exception:
        pass

    real_id = incident.get("incident_id", incident_id)
    aws.update_incident_status(real_id, "DISPATCHED")

    phone = incident.get("phone")
    if phone:
        aws.update_citizen_status(phone, "UNDERGOING_RESCUE")
        send_rescue_dispatched(phone)

    incident["status"] = "DISPATCHED"
    incident["id"] = real_id
    if dispatched_unit:
        incident["assigned_unit_name"] = dispatched_unit.get("name")
        # Save this on the mock incident so it persists across refreshes
        if aws.use_mock and real_id in aws._mock_incidents:
            aws._mock_incidents[real_id]["assigned_unit_name"] = dispatched_unit.get("name")

    # SSE: broadcast dispatch event so all connected dashboards update instantly
    await _broadcast(
        request,
        "dispatch",
        {
            "incident_id": real_id,
            "unit": dispatched_unit,
            "unit_lat": dispatched_unit["lat"] if dispatched_unit else None,
            "unit_lon": dispatched_unit["lon"] if dispatched_unit else None,
            "incident_lat": incident.get("lat"),
            "incident_lon": incident.get("lon"),
        },
    )
    return incident


# ---------------------------------------------------------------------------
# Mark rescued
# ---------------------------------------------------------------------------
@router.post("/mark-rescued/{incident_id}")
async def mark_rescued(incident_id: str, request: Request):
    aws = get_aws_service()
    incidents = aws.get_all_incidents()
    incident = next(
        (i for i in incidents if i.get("incident_id") == incident_id or i.get("id") == incident_id),
        None,
    )
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    real_id = incident.get("incident_id", incident_id)
    aws.update_incident_status(real_id, "RESCUED")

    phone = incident.get("phone")
    if phone:
        aws.update_citizen_status(phone, "RESCUED")
        send_text_message(
            phone,
            "🎉 You have been marked as rescued. Stay safe and follow local authorities for further guidance.",
        )

    incident["status"] = "RESCUED"
    incident["id"] = real_id

    await _broadcast(request, "rescued", {"incident_id": real_id})
    return incident


# ---------------------------------------------------------------------------
# Broadcast SNS / Hospital alert
# ---------------------------------------------------------------------------
@router.post("/broadcast-hospital")
async def broadcast_hospital(request: Request, payload: dict = Body(...)):
    aws = get_aws_service()
    message      = payload.get("message", "Emergency broadcast")
    hazard_type  = payload.get("hazard_type", "UNKNOWN")
    victim_count = payload.get("victim_count", 0)
    severity     = payload.get("severity", "CRITICAL")

    broadcast_msg = (
        f"🚨 EMERGENCY DISPATCH MANIFEST\n"
        f"Hazard: {hazard_type}\n"
        f"Victims: {victim_count}\n"
        f"Severity: {severity}\n"
        f"Details: {message}\n"
        f"Timestamp: {datetime.now(timezone.utc).isoformat()}"
    )
    aws.broadcast_emergency(
        subject=f"EMERGENCY: {hazard_type} - {severity}",
        message=broadcast_msg,
    )
    await _broadcast(request, "broadcast", {"hazard_type": hazard_type, "severity": severity})
    return {"status": "success", "message": "Broadcast sent to all hospitals"}


# ---------------------------------------------------------------------------
# Manual hazard scan
# ---------------------------------------------------------------------------
@router.post("/trigger-scan")
async def trigger_scan(request: Request):
    monitor = HazardMonitor()
    results = monitor.run_scan()
    await _broadcast(request, "refresh", {"reason": "manual_scan"})
    return {"status": "success", "results": results}


# ---------------------------------------------------------------------------
# Toggle mode
# ---------------------------------------------------------------------------
@router.post("/toggle-mode")
async def toggle_mode(request: Request):
    settings = get_settings()
    settings.demo_mode = not settings.demo_mode
    mode_label = "Demo" if settings.demo_mode else "Real"
    logger.info(f"Mode toggled to: {mode_label}")
    await _broadcast(request, "mode_change", {"demo_mode": settings.demo_mode})
    return {"demo_mode": settings.demo_mode, "mode": mode_label}


# ---------------------------------------------------------------------------
# Simulate events
# ---------------------------------------------------------------------------
@router.post("/simulate/{event_type}")
async def simulate_event(event_type: str, request: Request):
    aws = get_aws_service()
    settings = get_settings()
    base_lat = settings.monitor_lat
    base_lon = settings.monitor_lon
    now_iso  = datetime.now(timezone.utc).isoformat()

    if event_type == "flood":
        zone_id = f"SIM_FLOOD_{uuid.uuid4().hex[:8]}"
        aws.save_hazard_zone(
            zone_id=zone_id, hazard_type="FLOOD",
            lat=base_lat + random.uniform(-0.05, 0.05),
            lon=base_lon + random.uniform(-0.05, 0.05),
            radius_km=15.0, intensity="CRITICAL", color="RED",
            description="Simulated 50mm/h cloudburst - Flash flood warning",
            source="SIMULATION", detected_at=now_iso,
        )
        await _broadcast(request, "hazard", {"hazard_type": "FLOOD", "zone_id": zone_id})
        return {"status": "success", "event": "flood", "zone_id": zone_id}

    elif event_type == "earthquake":
        zone_id = f"SIM_EQ_{uuid.uuid4().hex[:8]}"
        aws.save_hazard_zone(
            zone_id=zone_id, hazard_type="EARTHQUAKE",
            lat=base_lat + random.uniform(-0.08, 0.08),
            lon=base_lon + random.uniform(-0.08, 0.08),
            radius_km=124.0, intensity="CRITICAL", color="RED",
            description="Simulated M6.2 earthquake - Structural collapse risk",
            source="SIMULATION", detected_at=now_iso,
        )
        await _broadcast(request, "hazard", {"hazard_type": "EARTHQUAKE", "zone_id": zone_id})
        return {"status": "success", "event": "earthquake", "zone_id": zone_id}

    elif event_type == "tsunami":
        zone_id = f"SIM_TSUNAMI_{uuid.uuid4().hex[:8]}"
        aws.save_hazard_zone(
            zone_id=zone_id, hazard_type="TSUNAMI",
            lat=base_lat, lon=base_lon,
            radius_km=200.0, intensity="CRITICAL", color="RED",
            description="Simulated tsunami warning - Coastal evacuation advised",
            source="SIMULATION", detected_at=now_iso,
        )
        await _broadcast(request, "hazard", {"hazard_type": "TSUNAMI", "zone_id": zone_id})
        return {"status": "success", "event": "tsunami", "zone_id": zone_id}

    elif event_type == "heatwave":
        zone_id = f"SIM_HEAT_{uuid.uuid4().hex[:8]}"
        aws.save_hazard_zone(
            zone_id=zone_id, hazard_type="HEATWAVE",
            lat=base_lat, lon=base_lon,
            radius_km=300.0, intensity="CRITICAL", color="RED",
            description="Simulated 45°C Extreme Heatwave - High risk of wildfires and thermal collapse",
            source="SIMULATION", detected_at=now_iso,
        )
        await _broadcast(request, "hazard", {"hazard_type": "HEATWAVE", "zone_id": zone_id})
        return {"status": "success", "event": "heatwave", "zone_id": zone_id}

    elif event_type == "sos":
        phone = f"+91{random.randint(7000000000, 9999999999)}"
        citizen_lat = base_lat + random.uniform(-0.03, 0.03)
        citizen_lon = base_lon + random.uniform(-0.03, 0.03)

        aws.save_citizen(phone=phone, name=f"Test Citizen {random.randint(100, 999)}",
                         lat=citizen_lat, lon=citizen_lon, status="IN_DANGER")

        incident_id  = str(uuid.uuid4())
        severity     = random.randint(3, 5)
        hazard       = random.choice(["FLOOD", "EARTHQUAKE", "TSUNAMI", "HEATWAVE"])
        severity_level = "CRITICAL" if severity >= 4 else "MODERATE"

        aws.save_incident(
            incident_id=incident_id, phone=phone,
            lat=citizen_lat, lon=citizen_lon,
            hazard_type=hazard, severity_score=severity,
            severity_level=severity_level,
            visual_findings=f"Simulated SOS: {hazard} detected with severity {severity}/5. Immediate assistance required.",
            image_url="", status="PENDING",
            recommended_dispatch=random.choice(["BOAT", "MEDICAL", "AMBULANCE", "AIRLIFT"]),
            immediate_life_threat=severity >= 4,
        )
        await _broadcast(request, "sos", {"incident_id": incident_id, "hazard_type": hazard, "severity": severity})
        return {"status": "success", "event": "sos", "incident_id": incident_id, "phone": phone}

    elif event_type.startswith("unit_"):
        unit_type = event_type.split("_")[1].upper()
        unit_id   = f"SIM_{unit_type}_{uuid.uuid4().hex[:4]}"
        aws.save_unit(
            unit_id=unit_id, unit_type=unit_type,
            lat=base_lat + random.uniform(-0.08, 0.08),
            lon=base_lon + random.uniform(-0.08, 0.08),
            status="PATROL",
            name=f"{unit_type.capitalize()} Unit {random.randint(10, 99)}",
        )
        await _broadcast(request, "unit_deployed", {"unit_id": unit_id, "unit_type": unit_type})
        return {"status": "success", "event": event_type, "unit_id": unit_id}

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid event type: {event_type}. Use: flood, earthquake, tsunami, heatwave, sos, unit_fire, unit_police, unit_rescue",
        )


# ---------------------------------------------------------------------------
# Clear demo data
# ---------------------------------------------------------------------------
@router.post("/clear-demo")
async def clear_demo(request: Request):
    aws = get_aws_service()
    aws._mock_incidents.clear()

    for k in [k for k in aws._mock_hazard_zones if k.startswith("SIM_") or k.startswith("EQ_") or k.startswith("FLOOD_") or k.startswith("HEATWAVE_") or k.startswith("TSUNAMI_")]:
        del aws._mock_hazard_zones[k]

    for p in [p for p, c in aws._mock_citizens.items() if c.get("name", "").startswith("Test")]:
        del aws._mock_citizens[p]

    for k in [k for k in aws._mock_units if k.startswith("SIM_")]:
        del aws._mock_units[k]

    # Reset dispatched units back to STANDBY
    for u in aws._mock_units.values():
        if u.get("status") == "DISPATCHED":
            u["status"] = "STANDBY"

    await _broadcast(request, "refresh", {"reason": "clear_demo"})
    return {"status": "success", "message": "Demo simulation data cleared"}


# ---------------------------------------------------------------------------
# Live hazards — combines stored zones + demo feed + ML metadata
# ---------------------------------------------------------------------------
@router.get("/live-hazards")
async def get_live_hazards():
    """Returns all active hazard zones enriched with ML severity + source."""
    aws      = get_aws_service()
    settings = get_settings()
    zones    = aws.get_active_hazard_zones()

    # In demo mode, merge in demo hazards so the map always has data
    if settings.demo_mode:
        monitor    = HazardMonitor()
        demo       = monitor.get_demo_hazards()
        demo_ids   = {z["zone_id"] for z in zones}
        for d in demo:
            if d["zone_id"] not in demo_ids:
                zones.append(d)

    enriched = []
    for z in zones:
        enriched.append({
            "zone_id":       z.get("zone_id"),
            "hazard_type":   z.get("hazard_type", "UNKNOWN"),
            "lat":           z.get("lat"),
            "lon":           z.get("lon", z.get("lng")),
            "lng":           z.get("lon", z.get("lng")),
            "radius_km":     float(z.get("radius_km", 5)),
            "radius":        float(z.get("radius_km", 5)) * 1000,
            "intensity":     z.get("intensity", z.get("color", "YELLOW")),
            "color":         z.get("color", "YELLOW"),
            "description":   z.get("description", ""),
            "source":        z.get("source", "Unknown"),
            "severity_score": int(z.get("severity_score", 1)),
            "severity_level": z.get("severity_level",
                                    z.get("intensity", "LOW")),
            "detected_at":   z.get("detected_at", ""),
        })
    return enriched


# ---------------------------------------------------------------------------
# Frontend config — exposes non-secret keys to the dashboard
# ---------------------------------------------------------------------------
@router.get("/config")
async def get_frontend_config():
    settings = get_settings()
    return {
        "mapbox_token":      settings.mapbox_token,
        "google_maps_api_key": settings.google_maps_api_key,  # kept for compat
        "demo_mode":         settings.demo_mode,
        "firms_configured":  bool(settings.nasa_firms_map_key),
    }


# ---------------------------------------------------------------------------
# Patrol tick — moves PATROL units slightly to simulate live movement
# Called by the frontend every 4 seconds in Demo mode
# ---------------------------------------------------------------------------
@router.post("/patrol-tick")
async def patrol_tick(request: Request):
    """Nudge every PATROL unit by a tiny random delta to simulate movement."""
    aws = get_aws_service()
    moved = []
    for uid, u in aws._mock_units.items():
        if u.get("status") == "PATROL":
            # Small random walk: ±0.0008° ≈ ±90 m per tick
            u["lat"] = round(u["lat"] + random.uniform(-0.0008, 0.0008), 6)
            u["lon"] = round(u["lon"] + random.uniform(-0.0008, 0.0008), 6)
            moved.append({"unit_id": uid, "lat": u["lat"], "lon": u["lon"]})

    await _broadcast(request, "patrol_tick", {"units": moved})
    return {"moved": len(moved)}
