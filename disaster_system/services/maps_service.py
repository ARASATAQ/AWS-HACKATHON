import logging
import math
import requests
from config import get_settings

from services.aws_service import get_aws_service

logger = logging.getLogger(__name__)
settings = get_settings()

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def find_nearest_shelter(lat: float, lon: float) -> dict:
    nearest_shelter = None
    min_distance = float('inf')
    
    if True:
        try:
            aws = get_aws_service()
            hospitals = aws.get_all_hospitals()
            for h in hospitals:
                h_lat = h.get("lat")
                h_lon = h.get("lon")
                if h_lat is not None and h_lon is not None:
                    dist = _haversine(lat, lon, float(h_lat), float(h_lon))
                    if dist < min_distance:
                        min_distance = dist
                        nearest_shelter = {
                            "name": h.get("name", "Unknown Shelter"),
                            "lat": h_lat,
                            "lon": h_lon,
                            "distance_km": round(dist, 2),
                            "phone": h.get("phone", "N/A")
                        }
        except Exception as e:
            logger.error(f"Error finding nearest shelter: {e}")
            
    if not nearest_shelter:
        nearest_shelter = {
            "name": "Central Emergency Shelter",
            "lat": lat + 0.05,
            "lon": lon + 0.05,
            "distance_km": 5.5,
            "phone": "555-0199"
        }
        
    return nearest_shelter

def generate_safe_route_url(from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> str:
    return f"https://www.google.com/maps/dir/{from_lat},{from_lon}/{to_lat},{to_lon}"

def geocode_address(address: str) -> dict:
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": address,
        "format": "json",
        "limit": 1
    }
    headers = {
        "User-Agent": "DisasterManagementSystem/1.0"
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if data and len(data) > 0:
            result = data[0]
            return {
                "lat": float(result.get("lat")),
                "lon": float(result.get("lon")),
                "display_name": result.get("display_name")
            }
    except Exception as e:
        logger.error(f"Error geocoding address '{address}': {e}")
        
    return {
        "lat": settings.monitor_lat,
        "lon": settings.monitor_lon,
        "display_name": f"{address} (Mocked)"
    }

def get_hazard_overlay_data() -> list[dict]:
    overlays = []
    try:
        aws = get_aws_service()
        zones = aws.get_active_hazard_zones()
        for z in zones:
            overlays.append({
                "lat": z.get("lat"),
                "lon": z.get("lon"),
                "radius": z.get("radius_km", 50) * 1000,
                "color": z.get("color", "red").lower(),
                "type": z.get("hazard_type", "UNKNOWN"),
                "description": z.get("description", z.get("place", ""))
            })
    except Exception as e:
        logger.error(f"Error getting hazard overlay data: {e}")
            
    return overlays

