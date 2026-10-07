import re

with open('templates/dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

new_init_map = """
        async function initMap() {
            map = L.map('map', { zoomControl: false }).setView(DEFAULT_CENTER, DEFAULT_ZOOM);
            L.control.zoom({ position: 'bottomright' }).addTo(map);
            
            const baseLight = L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', { maxZoom: 20 });
            const baseDark = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', { maxZoom: 20 });
            const baseSat = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { maxZoom: 19 });
            
            baseLight.addTo(map);

            hazardLayer = L.layerGroup().addTo(map);
            citizenLayer = L.layerGroup().addTo(map);
            hospitalLayer = L.layerGroup().addTo(map);
            incidentLayer = L.layerGroup().addTo(map);
            unitLayer = L.layerGroup().addTo(map);
            
            const liveEarthquakeLayer = L.layerGroup();
            let weatherLayer = L.layerGroup();

            try {
                const eqRes = await fetch('https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson');
                const eqData = await eqRes.json();
                eqData.features.forEach(feature => {
                    const coords = feature.geometry.coordinates;
                    const mag = feature.properties.mag;
                    const place = feature.properties.place;
                    L.circleMarker([coords[1], coords[0]], {
                        radius: Math.max(mag * 3, 5),
                        fillColor: '#ff9500',
                        color: '#ff3b30',
                        weight: 2,
                        fillOpacity: 0.6
                    }).bindPopup(`<b>USGS Live Sensor</b><br>Magnitude: ${mag}<br>Location: ${place}`).addTo(liveEarthquakeLayer);
                });
                liveEarthquakeLayer.addTo(map);
            } catch(e) { console.error('USGS fetch failed', e); }

            try {
                const rvRes = await fetch('https://api.rainviewer.com/public/weather-maps.json');
                const rvData = await rvRes.json();
                const latestTime = rvData.radar.past[rvData.radar.past.length - 1].time;
                const radarTile = L.tileLayer(`https://tilecache.rainviewer.com/v2/radar/${latestTime}/256/{z}/{x}/{y}/2/1_1.png`, { opacity: 0.4 });
                radarTile.addTo(weatherLayer);
                weatherLayer.addTo(map);
            } catch(e) {}

            const faultLayer = L.polygon([
                [29.5, 76.0], [29.0, 77.0], [28.2, 77.8], [27.5, 78.5]
            ], {color: '#ff3b30', fillColor: '#ff3b30', fillOpacity: 0.05, weight: 1.5, dashArray: '4'}).bindPopup('<b>Seismic Fault Line</b>');

            const baseMaps = {
                "Apple Light Map": baseLight,
                "Dark Tactical Map": baseDark,
                "Live Satellite View": baseSat
            };
            
            const overlayMaps = {
                "🌧️ Live Global Rain Radar": weatherLayer,
                "🔴 Live USGS Earthquakes (24h)": liveEarthquakeLayer,
                "🌪️ Historical Fault Lines": faultLayer,
                "📡 NOVA-S Active SOS": incidentLayer,
                "🚨 NOVA-S Responder Units": unitLayer
            };

            L.control.layers(baseMaps, overlayMaps, { position: 'topright' }).addTo(map);
        }
"""

content = re.sub(r'async function initMap\(\) \{.*?(?=function initDashboard\(\))', new_init_map, content, flags=re.DOTALL)

with open('templates/dashboard.html', 'w', encoding='utf-8') as f:
    f.write(content)
print('Map logic updated!')
