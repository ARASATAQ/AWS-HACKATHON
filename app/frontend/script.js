// Initialize the Map, centered on India
const map = L.map('map').setView([22.5937, 78.9629], 5);

// Add OpenStreetMap tiles (Dark Mode via CSS)
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap'
}).addTo(map);

let hazardMarkers = [];
let responderMarkers = [];
let responders = [];
let simulationRunning = false;

// DOM Elements
const gdacsCountEl = document.getElementById('gdacs-count');
const responderCountEl = document.getElementById('responder-count');
const feedListEl = document.getElementById('feed-list');
const refreshBtn = document.getElementById('refresh-btn');

const API_URL = 'http://127.0.0.1:8000/api/hazards';

function createCustomIcon(type) {
    let className = 'marker-normal';
    if (type === 'EQ') className = 'marker-eq';
    if (type === 'FL' || type === 'TS') className = 'marker-fl';
    if (type === 'Anomaly') className = 'marker-anomaly';
    
    return L.divIcon({
        className: 'custom-marker',
        html: `<div class="marker-pulse ${className}"></div>`,
        iconSize: [20, 20],
        iconAnchor: [10, 10]
    });
}

function addToFeed(item) {
    const div = document.createElement('div');
    
    let typeClass = '';
    if (item.source === 'GDACS') {
        typeClass = item.type === 'EQ' ? 'hazard-eq' : 'hazard-fl';
    } else if (item.is_anomaly) {
        typeClass = 'hazard-anomaly';
    } else if (item.source === 'Simulation') {
        typeClass = 'hazard-responder'; // new class for responders in feed
    }

    div.className = `feed-item ${typeClass}`;
    
    let details = '';
    if (item.source === 'GDACS') {
        details = `Severity Score: ${item.severity}`;
    } else if (item.source === 'Simulation') {
        details = `Assigned To: <strong>${item.assignedUser || 'All Units'}</strong><br>Status: En route to target...`;
    } else {
        details = `Temp: ${item.temp}°C | Rain: ${item.precip}mm<br>Risk Score: ${item.risk_score}/100`;
    }
    
    let badgeText = item.source === 'GDACS' ? `GDACS: ${item.type}` : 
                    (item.is_anomaly ? 'ML ALERT' : 
                    (item.source === 'Simulation' ? 'DISPATCH' : 'Normal'));

    let badgeColor = '#fff';
    if(item.is_anomaly) badgeColor = '#ef4444';
    if(item.source === 'Simulation') badgeColor = '#10b981';

    div.innerHTML = `
        <div class="feed-header">
            <span class="feed-type" style="color: ${badgeColor}">${badgeText}</span>
        </div>
        <div class="feed-title">${item.name}</div>
        <div class="feed-details">${details}</div>
    `;
    
    feedListEl.appendChild(div);
}

function generateSimulation(hazards) {
    // Clear old responders
    responderMarkers.forEach(m => map.removeLayer(m));
    responderMarkers = [];
    responders = [];

    const rescueUsers = [
        'Cmdr. Alex (Alpha)', 'Officer Sarah (Bravo)', 'Medic John (Charlie)', 
        'Chief Emma (Delta)', 'Patrol Mike (Echo)', 'Disp. Lisa (Foxtrot)', 
        'Rescue David (Golf)', 'Support Elena (Hotel)', 'Agent James (India)'
    ];

    // For each hazard, spawn multiple units of Ambulance, Police, Fire Brigade
    hazards.forEach((h, index) => {
        const types = [
            'Ambulance', 'Ambulance', 'Ambulance', 'Ambulance',
            'Police', 'Police', 'Police', 'Police', 'Police',
            'Fire Brigade', 'Fire Brigade', 'Fire Brigade', 'Fire Brigade'
        ];

        types.forEach(type => {
            // Random starting offset (approx 100-300km away)
            let latOffset = (Math.random() - 0.5) * 6.0;
            let lonOffset = (Math.random() - 0.5) * 6.0;
            
            // Random speed variation
            let speed = 0.005 + (Math.random() * 0.008);
            
            let emoji = '🚑';
            let classN = 'ambulance';
            if(type === 'Police') { emoji = '🚓'; classN = 'police'; }
            if(type === 'Fire Brigade') { emoji = '🚒'; classN = 'fire'; }

            let assignedUser = rescueUsers[Math.floor(Math.random() * rescueUsers.length)];

            let responder = {
                type: type,
                name: `${type} Unit #${Math.floor(Math.random()*10000)}`,
                source: 'Simulation',
                assignedUser: assignedUser,
                lat: h.lat + latOffset,
                lon: h.lon + lonOffset,
                targetLat: h.lat,
                targetLon: h.lon,
                speed: speed
            };

            let icon = L.divIcon({
                className: 'custom-responder',
                html: `<div class="responder-icon ${classN}">${emoji}</div>`,
                iconSize: [28, 28],
                iconAnchor: [14, 14]
            });
            
            let marker = L.marker([responder.lat, responder.lon], {icon: icon, zIndexOffset: 1000}).addTo(map);
            marker.bindPopup(`
                <div style="font-family: 'Outfit'">
                    <h3 style="margin:0 0 5px 0">${responder.name}</h3>
                    <p style="margin:0; font-weight:600; color:#10b981;">● Status: Dispatched</p>
                    <p style="margin:0; padding: 3px 0;">Assigned User: <strong>${assignedUser}</strong></p>
                    <p style="margin:0">Target: ${h.name || 'Hazard Zone'}</p>
                </div>
            `);
            
            responder.marker = marker;
            responders.push(responder);
            responderMarkers.push(marker);
        });
    });

    responderCountEl.innerText = responders.length;

    // Start simulation loop if not running
    if (!simulationRunning) {
        simulationRunning = true;
        animateResponders();
    }
}

function animateResponders() {
    responders.forEach(r => {
        let dLat = r.targetLat - r.lat;
        let dLon = r.targetLon - r.lon;
        let dist = Math.sqrt(dLat*dLat + dLon*dLon);
        
        // Move towards target if not yet arrived
        if (dist > 0.02) {
            r.lat += (dLat / dist) * r.speed;
            r.lon += (dLon / dist) * r.speed;
            r.marker.setLatLng([r.lat, r.lon]);
        }
    });
    
    if (simulationRunning) {
        requestAnimationFrame(animateResponders);
    }
}

async function fetchData() {
    try {
        refreshBtn.innerHTML = 'Loading...';
        feedListEl.innerHTML = '';
        
        // Clear old hazard markers
        hazardMarkers.forEach(m => map.removeLayer(m));
        hazardMarkers = [];
        
        const response = await fetch(API_URL);
        const data = await response.json();
        
        const gdacs = data.gdacs || [];
        const weather = data.weather || [];
        
        const allActiveHazards = [];

        gdacs.forEach(event => {
            const marker = L.marker([event.lat, event.lon], {
                icon: createCustomIcon(event.type)
            }).addTo(map);
            
            marker.bindPopup(`
                <div style="font-family: 'Outfit'">
                    <h3 style="margin:0 0 5px 0">${event.name}</h3>
                    <p style="margin:0">Type: ${event.type}</p>
                    <p style="margin:0">Severity: ${event.severity}</p>
                </div>
            `);
            hazardMarkers.push(marker);
            addToFeed(event);
            allActiveHazards.push(event);
        });

        weather.forEach(w => {
            const markerType = w.is_anomaly ? 'Anomaly' : 'Normal';
            const marker = L.marker([w.lat, w.lon], {
                icon: createCustomIcon(markerType)
            }).addTo(map);
            
            marker.bindPopup(`
                <div style="font-family: 'Outfit'">
                    <h3 style="margin:0 0 5px 0">${w.name}</h3>
                    <p style="margin:0">Condition: ${w.anomaly_type}</p>
                    <p style="margin:0">Temp: ${w.temp}°C</p>
                    <p style="margin:0">Precipitation: ${w.precip}mm</p>
                    <p style="margin:0; font-weight: bold; color: ${w.is_anomaly ? '#ef4444' : '#10b981'}">Risk Score: ${w.risk_score}</p>
                </div>
            `);
            hazardMarkers.push(marker);
            
            if (w.is_anomaly) {
                addToFeed(w);
                allActiveHazards.push(w);
            }
        });
        
        gdacsCountEl.innerText = allActiveHazards.length;
        
        if (allActiveHazards.length === 0) {
             feedListEl.innerHTML = '<div style="padding: 16px; color: var(--text-secondary);">No active hazards detected.</div>';
        } else {
             // Generate live responders for the hazards
             generateSimulation(allActiveHazards);
             
             // Add a few specific dispatch messages to the feed
             if (responders.length > 0) {
                 for (let i=0; i<Math.min(4, responders.length); i++) {
                     let r = responders[i];
                     addToFeed({
                         source: 'Simulation',
                         name: `Dispatch: ${r.name}`,
                         type: 'System',
                         is_anomaly: false,
                         assignedUser: r.assignedUser
                     });
                 }
             } else {
                 addToFeed({
                     source: 'Simulation',
                     name: 'Emergency Dispatch Command',
                     type: 'System',
                     is_anomaly: false,
                     assignedUser: 'All Available Units'
                 });
             }
        }

        refreshBtn.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.59-9.21l5.67-5.67"/></svg>
            Refresh Data
        `;
        
    } catch (error) {
        console.error("Error fetching data:", error);
        feedListEl.innerHTML = `<div style="color: #ef4444; padding: 16px;">Failed to connect to backend.</div>`;
        refreshBtn.innerHTML = 'Retry';
    }
}

refreshBtn.addEventListener('click', fetchData);
fetchData();
