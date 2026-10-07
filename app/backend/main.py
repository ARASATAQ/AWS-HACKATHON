from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/hazards")
def get_hazards():
    # 1. Fetch GDACS Data (Earthquakes, Floods, Tsunamis)
    gdacs_url = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH?"
    
    india_events = []
    try:
        gdacs_res = requests.get(gdacs_url).json()
        if 'features' in gdacs_res:
            for feat in gdacs_res['features']:
                geom = feat.get('geometry', {})
                props = feat.get('properties', {})
                if geom and geom.get('type') == 'Point':
                    lon, lat = geom['coordinates']
                    # Rough bounding box for India
                    if 8 <= lat <= 37 and 68 <= lon <= 97:
                        india_events.append({
                            "type": props.get('eventtype'),
                            "name": props.get('eventname'),
                            "severity": props.get('alertscore'),
                            "description": props.get('htmldescription'),
                            "lat": lat,
                            "lon": lon,
                            "source": "GDACS"
                        })
    except Exception as e:
        print("Error fetching GDACS:", e)
    
    # 2. Fetch Open-Meteo for major Indian cities to find heatwaves / extreme rainfall
    cities = [
        {"name": "Delhi", "lat": 28.61, "lon": 77.20},
        {"name": "Mumbai", "lat": 19.07, "lon": 72.87},
        {"name": "Chennai", "lat": 13.08, "lon": 80.27},
        {"name": "Kolkata", "lat": 22.57, "lon": 88.36},
        {"name": "Hyderabad", "lat": 17.38, "lon": 78.48},
        {"name": "Bangalore", "lat": 12.97, "lon": 77.59},
        {"name": "Ahmedabad", "lat": 23.02, "lon": 72.57},
        {"name": "Jaipur", "lat": 26.91, "lon": 75.78},
    ]
    
    weather_data = []
    for city in cities:
        meteo_url = f"https://api.open-meteo.com/v1/forecast?latitude={city['lat']}&longitude={city['lon']}&current=temperature_2m,apparent_temperature,precipitation"
        try:
            m_res = requests.get(meteo_url, timeout=5).json()
            current = m_res.get('current', {})
            weather_data.append({
                "type": "Weather",
                "name": city['name'],
                "temp": current.get('temperature_2m'),
                "apparent_temp": current.get('apparent_temperature'),
                "precip": current.get('precipitation'),
                "lat": city['lat'],
                "lon": city['lon'],
                "source": "Open-Meteo"
            })
        except Exception as e:
            print(f"Error fetching Open-Meteo for {city['name']}:", e)

    # 3. Apply a Basic ML Model: Anomaly Detection on Weather Data
    # We use Isolation Forest to detect extreme weather anomalies across cities
    if len(weather_data) > 3:
        df = pd.DataFrame(weather_data)
        # Fill missing values with 0
        features = df[['temp', 'apparent_temp', 'precip']].fillna(0)
        
        # Fit Isolation Forest
        model = IsolationForest(contamination=0.15, random_state=42)
        df['anomaly'] = model.fit_predict(features)
        
        # Calculate a simulated 'Risk Score' (0 to 100)
        # Using distance from mean as a simple heuristic
        temp_mean = df['temp'].mean()
        df['risk_score'] = ((abs(df['temp'] - temp_mean) / temp_mean) * 100).clip(0, 100)
        
        for i, row in df.iterrows():
            weather_data[i]['is_anomaly'] = True if row['anomaly'] == -1 else False
            weather_data[i]['risk_score'] = round(row['risk_score'], 1)
            
            # Identify specific anomaly type
            if weather_data[i]['is_anomaly']:
                if row['temp'] > 40:
                    weather_data[i]['anomaly_type'] = "Extreme Heatwave"
                elif row['precip'] > 15:
                    weather_data[i]['anomaly_type'] = "Cloudburst / Heavy Rain"
                else:
                    weather_data[i]['anomaly_type'] = "General Weather Anomaly"
            else:
                weather_data[i]['anomaly_type'] = "Normal"
    
    return {
        "gdacs": india_events,
        "weather": weather_data
    }
