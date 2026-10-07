import os
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # App
    app_name: str = "NOVA-S Disaster Management System"
    debug: bool = True
    demo_mode: bool = True  # Start in demo mode by default

    # Mapbox
    mapbox_token: str = ""  # Set in .env as MAPBOX_TOKEN  (pk.eyJ1...)

    # Google Maps (kept for backward compat, not used)
    google_maps_api_key: str = ""
    
    # AWS
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    
    # DynamoDB Tables
    dynamodb_citizens_table: str = "disaster_citizens"
    dynamodb_incidents_table: str = "disaster_incidents"
    dynamodb_hazard_zones_table: str = "disaster_hazard_zones"
    dynamodb_hospitals_table: str = "disaster_hospitals"
    
    # S3
    s3_bucket_name: str = "disaster-evidence-bucket"
    
    # SNS
    sns_topic_arn: str = ""
    
    # Amazon Bedrock
    bedrock_model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"
    bedrock_region: str = "us-east-1"
    
    # Meta WhatsApp Cloud API
    meta_whatsapp_token: str = ""
    meta_phone_number_id: str = ""
    meta_verify_token: str = "disaster_verify_token_2024"
    meta_api_version: str = "v17.0"
    
    # Open-Meteo (free, no key)
    open_meteo_base_url: str = "https://api.open-meteo.com/v1/forecast"

    # GDACS — Global Disaster Alert & Coordination System (free, no key)
    gdacs_api_url: str = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"

    # NASA FIRMS — active fire telemetry (free, needs MAP_KEY)
    nasa_firms_map_key: str = ""   # set NASA_FIRMS_MAP_KEY in .env
    nasa_firms_url: str = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_SNPP_NRT/{bbox}/1"

    # USGS (kept as fallback)
    usgs_earthquake_url: str = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_hour.geojson"

    # Monitoring — India focus: New Delhi
    monitor_lat: float = 28.6139
    monitor_lon: float = 77.2090
    monitor_radius_km: float = 500.0   # wider radius to catch India-wide events
    india_bbox: str = "68.0,8.0,97.5,37.5"   # lon_min,lat_min,lon_max,lat_max

    rainfall_threshold_mm: float = 20.0
    temperature_threshold_c: float = 40.0
    earthquake_magnitude_threshold: float = 4.5

    # Polling
    hazard_poll_interval_seconds: int = 60
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

def reload_settings() -> Settings:
    """Clear the settings cache and reload from .env"""
    get_settings.cache_clear()
    return get_settings()
