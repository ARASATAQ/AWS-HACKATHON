"""
NOVA-S Hazard Monitor
=====================
Real-time feeds:
  1. Open-Meteo   — heatwave / cloudburst (free, no key)
  2. GDACS        — earthquakes, tsunamis, floods, cyclones (free, no key)
  3. NASA FIRMS   — active wildfires via VIIRS SNPP (free MAP_KEY)

ML Severity Model
-----------------
A lightweight scikit-learn RandomForest trained on synthetic India-specific
feature vectors. Outputs 1-5 severity and "LOW/MODERATE/CRITICAL" for every
raw event before it is stored — replacing hard-coded thresholds.
"""

import asyncio
import csv
import io
import logging
import math
import uuid
from datetime import datetime, timezone

import aiohttp

from config import get_settings
from services.aws_service import get_aws_service
from services.whatsapp_service import send_emergency_alert

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# India bounding box helpers
# ──────────────────────────────────────────────────────────────────────────────
INDIA_LAT_MIN, INDIA_LAT_MAX =  6.5,  37.5
INDIA_LON_MIN, INDIA_LON_MAX = 68.0,  97.5

def _in_india(lat: float, lon: float) -> bool:
    return (INDIA_LAT_MIN <= lat <= INDIA_LAT_MAX and
            INDIA_LON_MIN <= lon <= INDIA_LON_MAX)

def _haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ──────────────────────────────────────────────────────────────────────────────
# ML Severity Model  (pure Python + scikit-learn, no internet required)
# ──────────────────────────────────────────────────────────────────────────────
_ml_model = None   # lazy-loaded

HAZARD_TYPE_MAP = {
    "FLOOD": 0, "EARTHQUAKE": 1, "TSUNAMI": 2,
    "HEATWAVE": 3, "WILDFIRE": 4, "CYCLONE": 5, "UNKNOWN": 6
}

def _get_ml_model():
    """Build and cache a RandomForest trained on synthetic India data."""
    global _ml_model
    if _ml_model is not None:
        return _ml_model

    try:
        import numpy as np
        from sklearn.ensemble import RandomForestClassifier

        rng = np.random.default_rng(42)

        # Feature vector:
        # [hazard_type_enc, raw_magnitude, area_km2, population_density,
        #  is_coastal, is_urban, hours_since_detected]
        N = 2000
        hazard_enc       = rng.integers(0, 7, N)
        raw_magnitude    = rng.uniform(0, 10, N)
        area_km2         = rng.uniform(10, 50000, N)
        pop_density      = rng.uniform(10, 12000, N)   # India range
        is_coastal       = rng.integers(0, 2, N)
        is_urban         = rng.integers(0, 2, N)
        hours_detected   = rng.uniform(0, 72, N)

        X = np.column_stack([hazard_enc, raw_magnitude, area_km2,
                             pop_density, is_coastal, is_urban, hours_detected])

        # Synthetic labels: higher mag + dense pop + coastal → critical
        score = (raw_magnitude * 0.4 +
                 (pop_density / 12000) * 2.5 +
                 is_coastal * 0.8 +
                 (area_km2 / 50000) * 1.2 -
                 (hours_detected / 72) * 0.5)
        y = np.clip(np.floor(score).astype(int), 1, 5)

        clf = RandomForestClassifier(n_estimators=50, max_depth=6,
                                     random_state=42, n_jobs=1)
        clf.fit(X, y)
        _ml_model = clf
        logger.info("✅ ML severity model trained and ready")
        return clf

    except ImportError:
        logger.warning("scikit-learn not installed — using rule-based severity fallback")
        return None


def predict_severity(hazard_type: str, magnitude: float, area_km2: float,
                     lat: float, lon: float) -> tuple[int, str]:
    """
    Returns (score 1-5, level string).
    Coastal India coords get +0.5 on the pop_density estimate.
    """
    model = _get_ml_model()

    # Simple coastal check: within 100 km of Indian coastline (rough)
    coastline_pts = [(8.5, 76.9), (10.8, 79.8), (13.0, 80.2),
                     (15.5, 73.8), (19.1, 72.8), (22.2, 68.9)]
    is_coastal = int(any(_haversine(lat, lon, c[0], c[1]) < 100 for c in coastline_pts))
    is_urban   = int(any(_haversine(lat, lon, c[0], c[1]) < 50
                         for c in [(28.6, 77.2), (19.1, 72.8), (13.0, 80.2),
                                   (22.6, 88.4), (12.9, 77.6)]))
    pop_density = 5000 if is_urban else (2000 if is_coastal else 300)

    if model is not None:
        try:
            import numpy as np
            h_enc = HAZARD_TYPE_MAP.get(hazard_type, 6)
            feat  = np.array([[h_enc, magnitude, area_km2, pop_density,
                                is_coastal, is_urban, 0.0]])
            score = int(model.predict(feat)[0])
        except Exception:
            score = _rule_based_score(hazard_type, magnitude)
    else:
        score = _rule_based_score(hazard_type, magnitude)

    score = max(1, min(5, score))
    level = "CRITICAL" if score >= 4 else ("MODERATE" if score >= 2 else "LOW")
    return score, level


def _rule_based_score(hazard_type: str, magnitude: float) -> int:
    rules = {
        "EARTHQUAKE": lambda m: 5 if m >= 7 else (4 if m >= 6 else (3 if m >= 5 else 2)),
        "TSUNAMI":    lambda m: 5,
        "FLOOD":      lambda m: 4 if m >= 50 else (3 if m >= 20 else 2),
        "HEATWAVE":   lambda m: 4 if m >= 44 else (3 if m >= 40 else 2),
        "WILDFIRE":   lambda m: 4 if m >= 100 else 3,
        "CYCLONE":    lambda m: 5 if m >= 4 else 3,
    }
    fn = rules.get(hazard_type)
    return fn(magnitude) if fn else 2


# ──────────────────────────────────────────────────────────────────────────────
# HazardMonitor
# ──────────────────────────────────────────────────────────────────────────────
class HazardMonitor:
    def __init__(self):
        self.settings = get_settings()
        self.aws = get_aws_service()

    # ── 1. Open-Meteo ─────────────────────────────────────────────────────────
    async def check_weather(self) -> list[dict]:
        lat, lon = self.settings.monitor_lat, self.settings.monitor_lon
        url = (f"{self.settings.open_meteo_base_url}"
               f"?latitude={lat}&longitude={lon}"
               f"&current=temperature_2m,apparent_temperature,precipitation"
               f"&timezone=auto")
        events = []
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                    if r.status != 200:
                        return []
                    data = await r.json()

            cur  = data.get("current", {})
            rain = cur.get("precipitation", 0) or 0
            temp = cur.get("temperature_2m", 0) or 0
            feel = cur.get("apparent_temperature", temp) or temp
            now  = datetime.now(timezone.utc).isoformat()
            ts   = int(datetime.now(timezone.utc).timestamp())

            if rain >= self.settings.rainfall_threshold_mm:
                score, level = predict_severity("FLOOD", rain, 2500.0, lat, lon)
                zid = f"FLOOD_{ts}"
                self.aws.save_hazard_zone(
                    zone_id=zid, hazard_type="FLOOD", lat=lat, lon=lon,
                    radius_km=50.0, intensity=level,
                    color="RED" if score >= 4 else "YELLOW",
                    description=f"Cloudburst — {rain}mm/h precipitation (ML severity {score}/5)",
                    source="Open-Meteo", detected_at=now)
                events.append({"zone_id": zid, "hazard_type": "FLOOD",
                               "lat": lat, "lon": lon, "radius_km": 50,
                               "color": "RED", "severity_score": score,
                               "severity_level": level,
                               "description": f"Cloudburst {rain}mm/h",
                               "source": "Open-Meteo"})

            if feel >= self.settings.temperature_threshold_c:
                score, level = predict_severity("HEATWAVE", feel, 10000.0, lat, lon)
                zid = f"HEAT_{ts}"
                self.aws.save_hazard_zone(
                    zone_id=zid, hazard_type="HEATWAVE", lat=lat, lon=lon,
                    radius_km=150.0, intensity=level,
                    color="ORANGE" if score < 4 else "RED",
                    description=f"Heatwave — feels {feel}°C / air {temp}°C (ML severity {score}/5)",
                    source="Open-Meteo", detected_at=now)
                events.append({"zone_id": zid, "hazard_type": "HEATWAVE",
                               "lat": lat, "lon": lon, "radius_km": 150,
                               "color": "ORANGE", "severity_score": score,
                               "severity_level": level,
                               "description": f"Feels {feel}°C",
                               "source": "Open-Meteo"})
        except Exception as e:
            logger.warning(f"Open-Meteo error: {e}")
        return events

    # ── 2. GDACS ──────────────────────────────────────────────────────────────
    async def check_gdacs(self) -> list[dict]:
        """
        GDACS GeoJSON feed — earthquakes, tsunamis, floods, cyclones.
        Filters to events affecting India or nearby (within 1500 km).
        """
        params = {
            "alertlevel": "Orange,Red",   # only significant events
            "eventtype":  "EQ,TS,FL,TC",
            "fromdate":   datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "todate":     datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "country":    "IND",
        }
        events = []
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(self.settings.gdacs_api_url,
                                 params=params,
                                 timeout=aiohttp.ClientTimeout(total=15)) as r:
                    if r.status != 200:
                        logger.warning(f"GDACS returned HTTP {r.status}")
                        return []
                    data = await r.json(content_type=None)

            features = data.get("features", []) if isinstance(data, dict) else []
            now = datetime.now(timezone.utc).isoformat()

            for feat in features:
                props = feat.get("properties", {})
                geom  = feat.get("geometry", {})
                coords = geom.get("coordinates", [0, 0])
                if len(coords) < 2:
                    continue

                lon, lat = float(coords[0]), float(coords[1])

                # Accept events in India OR within 1500 km of centre
                dist = _haversine(self.settings.monitor_lat,
                                  self.settings.monitor_lon, lat, lon)
                if not _in_india(lat, lon) and dist > 1500:
                    continue

                event_type = props.get("eventtype", "").upper()
                hazard_map = {"EQ": "EARTHQUAKE", "TS": "TSUNAMI",
                              "FL": "FLOOD",      "TC": "CYCLONE"}
                hazard_type = hazard_map.get(event_type, "UNKNOWN")

                alert  = (props.get("alertlevel") or "").lower()
                name   = props.get("eventname") or props.get("name") or "GDACS event"
                mag    = float(props.get("magnitude") or
                               props.get("alertscore") or 5.0)
                radius = {"EARTHQUAKE": mag * 18, "TSUNAMI": 200,
                          "FLOOD": 80, "CYCLONE": 300}.get(hazard_type, 50)

                score, level = predict_severity(hazard_type, mag,
                                               radius * radius * math.pi / 1e6,
                                               lat, lon)
                color = "RED" if alert == "red" else ("ORANGE" if alert == "orange" else "YELLOW")
                zid   = f"GDACS_{event_type}_{int(datetime.now(timezone.utc).timestamp())}"

                self.aws.save_hazard_zone(
                    zone_id=zid, hazard_type=hazard_type, lat=lat, lon=lon,
                    radius_km=float(radius), intensity=level, color=color,
                    description=f"{name} (GDACS alert={alert.upper()}, ML sev={score}/5)",
                    source="GDACS", detected_at=now)

                events.append({
                    "zone_id": zid, "hazard_type": hazard_type,
                    "lat": lat, "lon": lon, "radius_km": radius,
                    "color": color, "severity_score": score,
                    "severity_level": level, "magnitude": mag,
                    "description": name, "source": "GDACS",
                })

        except Exception as e:
            logger.warning(f"GDACS error: {e}")
        return events

    # ── 3. NASA FIRMS ─────────────────────────────────────────────────────────
    async def check_wildfires(self) -> list[dict]:
        """NASA FIRMS VIIRS active fire CSV — requires MAP_KEY in .env."""
        key = self.settings.nasa_firms_map_key
        if not key:
            logger.debug("NASA_FIRMS_MAP_KEY not set — skipping wildfire feed")
            return []

        bbox = self.settings.india_bbox   # "lon_min,lat_min,lon_max,lat_max"
        url  = (f"https://firms.modaps.eosdis.nasa.gov/api/area/csv"
                f"/{key}/VIIRS_SNPP_NRT/{bbox}/1")
        events = []
        seen_cells: set[str] = set()   # deduplicate 0.1° grid cells

        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                    if r.status != 200:
                        logger.warning(f"NASA FIRMS HTTP {r.status}")
                        return []
                    text = await r.text()

            reader = csv.DictReader(io.StringIO(text))
            now    = datetime.now(timezone.utc).isoformat()

            for row in reader:
                try:
                    lat  = float(row.get("latitude",  0))
                    lon  = float(row.get("longitude", 0))
                    frp  = float(row.get("frp", 0) or 0)   # Fire Radiative Power (MW)
                    conf = (row.get("confidence") or "").lower()
                except (ValueError, KeyError):
                    continue

                if not _in_india(lat, lon):
                    continue
                if conf not in ("nominal", "high", "n", "h"):
                    continue   # skip low-confidence detections

                # Grid-level deduplication
                cell = f"{round(lat,1):.1f}_{round(lon,1):.1f}"
                if cell in seen_cells:
                    continue
                seen_cells.add(cell)

                score, level = predict_severity("WILDFIRE", frp, 25.0, lat, lon)
                zid = f"FIRE_{int(datetime.now(timezone.utc).timestamp())}_{cell}"
                self.aws.save_hazard_zone(
                    zone_id=zid, hazard_type="WILDFIRE", lat=lat, lon=lon,
                    radius_km=10.0, intensity=level,
                    color="RED" if score >= 4 else "ORANGE",
                    description=f"Active fire — FRP {frp:.0f} MW, conf={conf} (ML sev={score}/5)",
                    source="NASA-FIRMS", detected_at=now)

                events.append({
                    "zone_id": zid, "hazard_type": "WILDFIRE",
                    "lat": lat, "lon": lon, "radius_km": 10,
                    "color": "RED" if score >= 4 else "ORANGE",
                    "severity_score": score, "severity_level": level,
                    "frp": frp, "source": "NASA-FIRMS",
                    "description": f"Active fire FRP={frp:.0f}MW",
                })

        except Exception as e:
            logger.warning(f"NASA FIRMS error: {e}")
        return events

    # ── Citizens alert ─────────────────────────────────────────────────────────
    def alert_affected_citizens(self, hazard_zone: dict):
        try:
            hz_lat, hz_lon = hazard_zone["lat"], hazard_zone["lon"]
            hz_r   = hazard_zone.get("radius_km", 50)
            for c in self.aws.get_all_citizens():
                c_lat, c_lon = c.get("lat"), c.get("lon")
                if c_lat and c_lon and _haversine(hz_lat, hz_lon, c_lat, c_lon) <= hz_r:
                    phone = c.get("phone")
                    if phone:
                        send_emergency_alert(
                            to=phone,
                            hazard_type=hazard_zone.get("hazard_type", "UNKNOWN"),
                            area=hazard_zone.get("description", "your area"))
        except Exception as e:
            logger.error(f"alert_affected_citizens error: {e}")

    # ── Main scan ──────────────────────────────────────────────────────────────
    def run_scan(self) -> dict:
        if self.settings.demo_mode:
            logger.info("Demo mode — skipping live scan")
            return {"weather": 0, "gdacs": 0, "wildfire": 0, "mode": "demo"}
        try:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self._async_scan())
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"run_scan error: {e}")
            return {"weather": 0, "gdacs": 0, "wildfire": 0, "error": str(e)}

    async def _async_scan(self) -> dict:
        weather_ev, gdacs_ev, fire_ev = await asyncio.gather(
            self.check_weather(),
            self.check_gdacs(),
            self.check_wildfires(),
            return_exceptions=False,
        )
        all_ev = weather_ev + gdacs_ev + fire_ev
        for ev in all_ev:
            self.alert_affected_citizens(ev)
        return {"weather": len(weather_ev),
                "gdacs":   len(gdacs_ev),
                "wildfire": len(fire_ev)}

    # ── Demo data ──────────────────────────────────────────────────────────────
    def get_demo_hazards(self) -> list[dict]:
        lat, lon = self.settings.monitor_lat, self.settings.monitor_lon
        ts = int(datetime.now(timezone.utc).timestamp())
        return [
            {"zone_id": f"EQ_{ts}",    "hazard_type": "EARTHQUAKE", "color": "RED",
             "radius_km": 120, "lat": lat+0.1,  "lon": lon+0.1,
             "severity_score": 5, "severity_level": "CRITICAL",
             "description": "Demo M6.5 earthquake — ML sev 5/5", "source": "Demo"},
            {"zone_id": f"FLOOD_{ts}", "hazard_type": "FLOOD",      "color": "RED",
             "radius_km": 50,  "lat": lat-0.1,  "lon": lon-0.1,
             "severity_score": 4, "severity_level": "CRITICAL",
             "description": "Demo cloudburst 65mm/h — ML sev 4/5", "source": "Demo"},
            {"zone_id": f"HEAT_{ts}",  "hazard_type": "HEATWAVE",   "color": "ORANGE",
             "radius_km": 200, "lat": lat+0.2,  "lon": lon-0.2,
             "severity_score": 3, "severity_level": "MODERATE",
             "description": "Demo heatwave feels 44°C — ML sev 3/5", "source": "Demo"},
            {"zone_id": f"FIRE_{ts}",  "hazard_type": "WILDFIRE",   "color": "ORANGE",
             "radius_km": 12,  "lat": lat-0.15, "lon": lon+0.15,
             "severity_score": 3, "severity_level": "MODERATE",
             "description": "Demo active fire FRP=180MW — ML sev 3/5", "source": "Demo"},
            {"zone_id": f"TC_{ts}",    "hazard_type": "CYCLONE",    "color": "RED",
             "radius_km": 350, "lat": lat-1.5,  "lon": lon+1.0,
             "severity_score": 5, "severity_level": "CRITICAL",
             "description": "Demo Cat-4 cyclone landfall — ML sev 5/5", "source": "Demo"},
        ]
