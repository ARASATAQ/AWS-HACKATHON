
/* ── constants ── */
const API  = '';
const CTR  = { lat: 28.6139, lng: 77.2090 };
const ZOOM = 11;
const PAGE_TITLES = { 'p-map':'Global Overview','p-fire':'Fire Operations','p-police':'Police Command','p-rescue':'Medical Rescue','p-triage':'AI Triage','p-sim':'Simulator Center' };

/* ── state ── */
let gmap = null;                  // Mapbox map object
let gMarkers = {};                // unit_id → marker element + popup
let gHazardCircles = [];
let gRouteLines = [];
let gCitizenMarkers = [];
let gHospitalMarkers = [];
let gIncidentMarkers = [];
let isDemoMode = false;
let sseSource  = null;
let patrolTimer = null;

/* ════════════════════════════════
   NAV
════════════════════════════════ */
function go(id, el) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById(id).classList.add('active');
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    el.classList.add('active');
    document.getElementById('pg-title').textContent = PAGE_TITLES[id] || '';
    if (id === 'p-map' && gmap) gmap.resize();
    if (id === 'p-police') renderPoliceGrid();
}

/* ════════════════════════════════
   CLOCK
════════════════════════════════ */
function tick() { document.getElementById('clock').textContent = new Date().toLocaleTimeString('en-US',{hour12:false}); }

/* ════════════════════════════════
   TOAST
════════════════════════════════ */
function toast(msg, icon='✅', color='var(--green)') {
    const w = document.getElementById('toasts');
    const d = document.createElement('div');
    d.className = 'toast';
    d.innerHTML = `<span style="color:${color}">${icon}</span> ${msg}`;
    w.appendChild(d);
    setTimeout(() => d.remove(), 2900);
}

/* ════════════════════════════════
   MAPBOX INIT
   Called once Mapbox GL JS is ready
════════════════════════════════ */
function initGoogleMap() {   // name kept so existing callers still work
    gmap = new mapboxgl.Map({
        container: 'map',
        style: 'mapbox://styles/mapbox/dark-v11',
        center: [CTR.lng, CTR.lat],
        zoom: ZOOM,
        attributionControl: false
    });
    gmap.addControl(new mapboxgl.NavigationControl({ showCompass: false }), 'bottom-right');
    gmap.addControl(new mapboxgl.AttributionControl({ compact: true }));

    gmap.on('load', () => fetchAll());
}

/* ════════════════════════════════
   SSE
════════════════════════════════ */
function initSSE() {
    if (sseSource) sseSource.close();
    const dot = document.getElementById('sse-dot'), lbl = document.getElementById('sse-lbl');
    sseSource = new EventSource(`${API}/api/admin/events`);
    sseSource.onopen = () => { dot.className = 'on'; lbl.textContent = 'Live'; };
    sseSource.onerror = () => { dot.className = 'err'; lbl.textContent = 'Reconnecting…'; };
    sseSource.onmessage = e => { try { onSSE(JSON.parse(e.data)); } catch(_){} };
}

function onSSE(ev) {
    const d = ev.data || {};
    if (ev.type === 'connected')   return;
    if (ev.type === 'patrol_tick') { onPatrolTick(d.units || []); return; }
    if (ev.type === 'dispatch')    { if (d.unit_lat && d.incident_lat) drawRoute(d.unit_lat, d.unit_lon, d.incident_lat, d.incident_lon); fetchAll(); toast('Unit Dispatched','🚨','var(--blue)'); return; }
    if (ev.type === 'sos')         { fetchAll(); toast('New SOS Signal','🆘','var(--red)'); return; }
    if (ev.type === 'hazard')      { fetchAll(); toast(`${d.hazard_type||'Hazard'} Detected','⚠️','var(--orange)`); return; }
    if (ev.type === 'rescued')     { fetchAll(); toast('Citizen Secured','✅'); return; }
    if (ev.type === 'unit_deployed'){ fetchAll(); toast(`${d.unit_type||'Unit'} Deployed`,'🚒'); return; }
    if (ev.type === 'broadcast')   { toast('SNS Alert Sent','📡','var(--red)'); return; }
    fetchAll();
}

/* ════════════════════════════════
   PATROL TICK — smooth marker animation
════════════════════════════════ */
function onPatrolTick(units) {
    units.forEach(u => {
        const mk = gMarkers[u.unit_id];
        if (mk && mk.marker) animateMarker(mk.marker, u.lat, u.lon);
    });
}

function animateMarker(marker, toLat, toLng) {
    if (!marker.getLngLat) return;
    const from = marker.getLngLat();
    const STEPS = 20, DELAY = 50;
    let step = 0;
    const interval = setInterval(() => {
        step++;
        const lat = from.lat + (toLat - from.lat) * step / STEPS;
        const lng = from.lng + (toLng - from.lng) * step / STEPS;
        marker.setLngLat([lng, lat]);
        if (step >= STEPS) clearInterval(interval);
    }, DELAY);
}

/* ════════════════════════════════
   PATROL TIMER — fires every 4 s in demo mode
════════════════════════════════ */
function startPatrol() {
    if (patrolTimer) clearInterval(patrolTimer);
    if (!isDemoMode) return;
    patrolTimer = setInterval(async () => {
        try { await fetch(`${API}/api/admin/patrol-tick`, { method: 'POST' }); } catch(_){}
    }, 4000);
}
function stopPatrol() { if (patrolTimer) { clearInterval(patrolTimer); patrolTimer = null; } }

/* ════════════════════════════════
   FETCH ALL
════════════════════════════════ */
async function fetchAll() {
    if (!gmap) return;
    await fetchUnits();
    fetchStats();
    fetchIncidents();
    fetchCitizens();
    fetchHazardZones();
    fetchHospitals();
}

async function fetchStats() {
    try {
        const d = await fetch(`${API}/api/admin/stats`).then(r=>r.json());
        document.getElementById('s-safe').textContent  = d.citizens_safe + d.citizens_rescued;
        document.getElementById('s-sos').textContent   = d.active_incidents;
        document.getElementById('s-haz').textContent   = d.active_hazard_zones;
        document.getElementById('s-avail').textContent = (d.fire_units+d.police_units+d.rescue_units)-(d.units_dispatched||0);
        document.getElementById('s-disp').textContent  = d.units_dispatched||0;
    } catch(_){}
}

/* ── Units ── */
async function fetchUnits() {
    try {
        const units = await fetch(`${API}/api/admin/units`).then(r=>r.json());
        window.gUnits = units;

        // Remove stale markers
        const currentIds = new Set(units.map(u=>u.unit_id));
        Object.keys(gMarkers).forEach(id => {
            if (!currentIds.has(id)) { gMarkers[id].el.remove(); if (gMarkers[id].popup) gMarkers[id].popup.remove(); delete gMarkers[id]; }
        });

        units.forEach(u => {
            const lat = u.lat, lng = u.lng || u.lon;
            if (!lat || !lng) return;

            // Pick icon
            let iconHtml = '';
            let color = '';
            if (u.unit_type === 'FIRE')   { iconHtml = '<i class="fa-solid fa-fire"></i>'; color = 'var(--orange)'; }
            else if (u.unit_type === 'POLICE') { iconHtml = '<i class="fa-solid fa-shield-halved"></i>'; color = 'var(--purple)'; }
            else { iconHtml = '<i class="fa-solid fa-heart-pulse"></i>'; color = 'var(--green)'; }

            if (gMarkers[u.unit_id]) {
                if (!patrolTimer) gMarkers[u.unit_id].marker.setLngLat([lng, lat]);
                gMarkers[u.unit_id].el.style.opacity = u.status === 'DISPATCHED' ? '0.5' : '1';
            } else {
                const el = document.createElement('div');
                el.style.cssText = `width:28px;height:28px;border-radius:50%;background:${color};color:#fff;display:flex;align-items:center;justify-content:center;font-size:14px;box-shadow:0 0 10px ${color};border:2px solid var(--surf2);cursor:pointer;`;
                el.innerHTML = iconHtml;
                
                const popup = new mapboxgl.Popup({ offset: 15, closeButton: false })
                    .setHTML(`<div style="font-family:Inter;color:#e8e8f0;padding:4px;">
                        <b style="font-size:13px;">${u.name}</b><br>
                        <span style="font-size:11px;color:#6b6b80;">Type: ${u.unit_type} · Status: ${u.status}</span>
                        ${u.station ? `<br><span style="font-size:11px;color:#6b6b80;">${u.station}</span>` : ''}
                    </div>`);
                const marker = new mapboxgl.Marker({ element: el }).setLngLat([lng, lat]).setPopup(popup).addTo(gmap);
                el.addEventListener('click', () => popup.addTo(gmap));
                gMarkers[u.unit_id] = { el, marker, popup };
            }
        });
    } catch(_){}
}

/* ── Citizens ── */
async function fetchCitizens() {
    try {
        const citizens = await fetch(`${API}/api/admin/citizens`).then(r=>r.json());
        gCitizenMarkers.forEach(m => { m.el.remove(); if (m.popup) m.popup.remove(); });
        gCitizenMarkers = [];
        citizens.forEach(c => {
            const lat = c.lat, lng = c.lng || c.lon;
            if (!lat || !lng) return;
            if (!['IN_DANGER','UNDERGOING_RESCUE','RESCUED'].includes(c.status)) return;
            const colors = { IN_DANGER:'#ff3b30', UNDERGOING_RESCUE:'#ffd60a', RESCUED:'#30d158' };
            const color = colors[c.status] || '#ff3b30';
            const el = document.createElement('div');
            el.style.cssText = `width:14px;height:14px;border-radius:50%;background:${color};border:2px solid #fff;box-shadow:0 0 8px ${color};cursor:pointer;`;
            const popup = new mapboxgl.Popup({ offset: 10, closeButton: false })
                .setHTML(`<div style="font-family:Inter;color:#e8e8f0;padding:4px;"><b>${c.name||'Citizen'}</b><br><span style="font-size:11px;color:${color};">${c.status}</span></div>`);
            const marker = new mapboxgl.Marker({ element: el }).setLngLat([lng, lat]).setPopup(popup).addTo(gmap);
            el.addEventListener('click', () => popup.addTo(gmap));
            gCitizenMarkers.push({ el, marker, popup });
        });
    } catch(_){}
}

/* ── Layer visibility state ── */
const layerVisible = {
    EARTHQUAKE: true, TSUNAMI: true, FLOOD: true,
    HEATWAVE: true, WILDFIRE: true, CYCLONE: true,
};
let unitsVisible    = true;
let citizensVisible = true;
let hospitalsVisible = true;

function toggleLayer(type) {
    layerVisible[type] = !layerVisible[type];
    gHazardCircles.forEach(c => {
        if (c.hazardType === type) {
            try {
                const vis = layerVisible[type] ? 'visible' : 'none';
                gmap.setLayoutProperty(c.fillId, 'visibility', vis);
                gmap.setLayoutProperty(c.lineId, 'visibility', vis);
            } catch(e){}
        }
    });
}

function toggleUnitsLayer() {
    unitsVisible = !unitsVisible;
    Object.values(gMarkers).forEach(m => m.el.style.display = unitsVisible ? '' : 'none');
}
function toggleCitizensLayer() {
    citizensVisible = !citizensVisible;
    gCitizenMarkers.forEach(m => m.el.style.display = citizensVisible ? '' : 'none');
}
function toggleHospitalsLayer() {
    hospitalsVisible = !hospitalsVisible;
    gHospitalMarkers.forEach(m => m.el.style.display = hospitalsVisible ? '' : 'none');
}

/* ── Incidents ── */
async function fetchIncidents() {
    try {
        const incidents = await fetch(`${API}/api/admin/incidents`).then(r=>r.json());

        // Clear old incident markers
        gIncidentMarkers.forEach(m => { m.el.remove(); if (m.popup) m.popup.remove(); });
        gIncidentMarkers = [];

        // Render incident markers on map
        incidents.forEach(i => {
            const lat = i.lat, lng = i.lng || i.lon;
            if (!lat || !lng || lat === 0) return;
            const sev = i.severity_score || 0;
            const color = sev >= 4 ? '#ff3b30' : sev >= 2 ? '#ff9500' : '#ffd60a';
            const el = document.createElement('div');
            el.style.cssText = `width:18px;height:18px;border-radius:50%;background:${color};border:2px solid #fff;cursor:pointer;${sev>=4?'animation:pulse 1s infinite;':''}`;
            const popup = new mapboxgl.Popup({ offset: 12, closeButton: false })
                .setHTML(`<div style="font-family:Inter;color:#e8e8f0;padding:4px;"><b>${i.hazard_type}</b><br><span style="font-size:11px;color:${color};">S${sev} · ${i.status}</span><br><span style="font-size:11px;color:#6b6b80;">${(i.findings||'').slice(0,80)}</span></div>`);
            const marker = new mapboxgl.Marker({ element: el }).setLngLat([lng, lat]).setPopup(popup).addTo(gmap);
            el.addEventListener('click', () => popup.addTo(gmap));
            gIncidentMarkers.push({ el, marker, popup });
        });

        // Render queue cards
        const renderQ = (elId, typeFilter) => {
            const el = document.getElementById(elId);
            if (!el) return;
            const list = typeFilter ? incidents.filter(i => {
                if (typeFilter === 'FIRE')   return true;
                if (typeFilter === 'POLICE') return ['FLOOD','EARTHQUAKE','TSUNAMI','UNKNOWN'].includes(i.hazard_type);
                if (typeFilter === 'RESCUE') return true;
            }) : incidents;
            el.innerHTML = list.length ? list.map(i => incCard(i, false)).join('') :
                '<div style="text-align:center;color:var(--muted);padding:28px 0;font-size:13px;">No active incidents.</div>';
        };
        renderQ('q-fire',   'FIRE');
        renderQ('q-police', 'POLICE');
        renderQ('q-rescue', 'RESCUE');

        // AI Triage — full findings
        const el = document.getElementById('q-triage');
        if (el) el.innerHTML = incidents.length ? incidents.map(i => incCard(i, true)).join('') :
            '<div style="text-align:center;color:var(--muted);padding:28px 0;font-size:13px;">No incidents in triage.</div>';

    } catch(_){}
}

/* ── Incident card builder ── */
function incCard(inc, full) {
    const id  = inc.id || inc.incident_id;
    const res = inc.status === 'RESCUED', dis = inc.status === 'DISPATCHED';
    const sev = inc.severity_score || 0;
    let cls = 'qi';
    if (res) cls += ' res'; else if (sev >= 4) cls += ' crit'; else if (sev >= 2) cls += ' mod'; else cls += ' low';

    const sBadge = res  ? '<span class="badge b-g">RESCUED</span>'
                 : dis  ? '<span class="badge b-o">DISPATCHED</span>'
                        : '<span class="badge b-r">PENDING</span>';
    const sevBadge = sev>=4 ? `<span class="badge b-r">S${sev} CRITICAL</span>`
                   : sev>=2 ? `<span class="badge b-o">S${sev} MODERATE</span>`
                             : `<span class="badge b-y">S${sev||'?'} LOW</span>`;

    const phone    = inc.phone ? inc.phone.replace(/.(?=.{4})/g,'*') : 'Unknown';
    const findings = inc.findings || inc.visual_findings || 'Awaiting analysis';
    const fDisplay = full
        ? `<div style="font-size:12px;line-height:1.65;color:var(--muted);background:var(--bg);border-radius:8px;padding:10px;margin-top:8px;white-space:pre-wrap;">${findings}</div>`
        : `<div style="font-size:12px;color:var(--muted);margin-top:4px;">${findings.length>120?findings.slice(0,120)+'…':findings}</div>`;

    let unitSel = '';
    if (!res && !dis && window.gUnits) {
        const avail = window.gUnits.filter(u => u.status !== 'DISPATCHED');
        if (avail.length) {
            const opts = avail.map(u=>`<option value="${u.unit_id}">${u.name} (${u.unit_type})</option>`).join('');
            unitSel = `<select id="sel-${id}" class="inp" style="max-width:170px;padding:5px 8px;font-size:11px;">
                <option value="">Assign unit…</option>${opts}</select>
                <span class="ai-badge" onclick="aiPick('${id}','sel-${id}')"><i class="fa-solid fa-wand-magic-sparkles fa-xs"></i> AI Pick</span>`;
        } else unitSel = '<span style="font-size:11px;color:var(--red);">No units available</span>';
    }

    const photoUrl = inc.photo_url || inc.image_url || '';
    const photoBtn = photoUrl
        ? `<button class="btn btn-ghost" style="font-size:11px;padding:5px 10px;" onclick="openPhoto('${photoUrl}','${encodeURIComponent(findings)}')"><i class="fa-solid fa-image fa-xs"></i> View Photo</button>`
        : '';

    const actionBtn = !res && !dis
        ? `<button class="btn btn-blue" style="font-size:11px;" onclick="doDispatch('${id}')"><i class="fa-solid fa-truck-fast fa-xs"></i> Dispatch Rescue Unit</button>`
        : dis
        ? `<button class="btn btn-green" style="font-size:11px;" onclick="doRescued('${id}')"><i class="fa-solid fa-circle-check fa-xs"></i> Mark Rescued</button>`
        : '';

    return `<div class="${cls}">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;">
            <div>
                <div style="font-size:14px;font-weight:600;margin-bottom:2px;">${inc.hazard_type||'UNKNOWN'} — ${phone}</div>
                <div style="font-size:11px;color:var(--muted);">${inc.lat?`${Number(inc.lat).toFixed(4)}, ${Number(inc.lng||inc.lon||0).toFixed(4)}`:'No coords'} · ${inc.recommended_dispatch||'—'}</div>
            </div>
            <div style="display:flex;gap:5px;flex-shrink:0;">${sevBadge}${sBadge}</div>
        </div>
        ${fDisplay}
        <div style="display:flex;flex-wrap:wrap;gap:7px;align-items:center;margin-top:9px;">${unitSel}</div>
        <div style="display:flex;flex-wrap:wrap;gap:7px;align-items:center;margin-top:7px;">${photoBtn}${actionBtn}</div>
    </div>`;
}

/* ── Police grid ── */
function renderPoliceGrid() {
    const grid = document.getElementById('police-stations-grid');
    if (!grid || !window.gUnits) return;
    const ps = window.gUnits.filter(u => u.unit_type === 'POLICE');
    grid.innerHTML = ps.map(p => {
        const statusColor = p.status === 'PATROL' ? 'var(--green)' : p.status === 'DISPATCHED' ? 'var(--orange)' : 'var(--muted)';
        const statusIcon  = p.status === 'PATROL' ? '🟢' : p.status === 'DISPATCHED' ? '🟠' : '⚪';
        return `<div style="background:var(--surf2);border:1px solid var(--border);border-radius:10px;padding:12px;">
            <div style="font-size:12px;font-weight:600;margin-bottom:3px;">${p.name}</div>
            <div style="font-size:10px;color:var(--muted);margin-bottom:5px;">${p.station||''}</div>
            <div style="font-size:11px;color:${statusColor};">${statusIcon} ${p.status}</div>
            <div style="font-size:10px;color:var(--muted);margin-top:3px;">${Number(p.lat).toFixed(4)}, ${Number(p.lon||p.lng||0).toFixed(4)}</div>
        </div>`;
    }).join('');
}

/* ── AI recommend ── */
async function aiPick(incId, selId) {
    try {
        const d = await fetch(`${API}/api/admin/recommend-unit/${incId}`).then(r=>r.json());
        if (d.recommended_unit) {
            document.getElementById(selId).value = d.recommended_unit.unit_id;
            toast(`AI → ${d.recommended_unit.name} (${d.distance_km} km)`, '🤖', 'var(--purple)');
        } else toast('No standby units','⚠️','var(--orange)');
    } catch(_){}
}

/* ── Dispatch ── */
async function doDispatch(id) {
    const sel = document.getElementById(`sel-${id}`);
    const uid = sel ? sel.value : null;
    try {
        await fetch(`${API}/api/admin/dispatch/${id}`, { method:'POST', headers:{'Content-Type':'application/json'}, body: uid ? JSON.stringify({unit_id:uid}) : '{}' });
    } catch(_){}
}
async function doRescued(id) {
    try { await fetch(`${API}/api/admin/mark-rescued/${id}`, { method:'POST' }); } catch(_){}
}

/* ── Draw dispatch route ── */
function drawRoute(fromLat, fromLng, toLat, toLng) {
    if (!gmap) return;
    const idx = gmap._layerIdx || (gmap._layerIdx = 1);
    gmap._layerIdx++;
    const srcId = `route-src-${idx}`, lineId = `route-line-${idx}`;
    gmap.addSource(srcId, {
        type: 'geojson',
        data: { type:'Feature', geometry:{ type:'LineString', coordinates:[[fromLng,fromLat],[toLat,toLng]] } }
    });
    gmap.addLayer({
        id: lineId, type: 'line', source: srcId,
        paint: { 'line-color': '#0a84ff', 'line-width': 2.5, 'line-opacity': 0.85, 'line-dasharray': [2, 1] }
    });
    gmap._routes = gmap._routes || [];
    gmap._routes.push({ lineId, srcId });
    setTimeout(() => {
        try { gmap.removeLayer(lineId); gmap.removeSource(srcId); } catch(e){}
        gmap._routes = gmap._routes.filter(r => r.lineId !== lineId);
    }, 30000);
}

/* ── Photo modal ── */
function openPhoto(url, enc) {
    document.getElementById('photo-img').src = url;
    try { document.getElementById('photo-findings').textContent = decodeURIComponent(enc); } catch(_){}
    document.getElementById('photo-modal').classList.add('open');
}
function closePhoto() {
    document.getElementById('photo-modal').classList.remove('open');
    document.getElementById('photo-img').src = '';
}
document.getElementById('photo-modal').addEventListener('click', e => { if (e.target === document.getElementById('photo-modal')) closePhoto(); });

/* ── SNS modal ── */
function openSNS()  { document.getElementById('sns-modal').classList.add('open'); }
function closeSNS() { document.getElementById('sns-modal').classList.remove('open'); }
document.getElementById('sns-modal').addEventListener('click', e => { if (e.target === document.getElementById('sns-modal')) closeSNS(); });
async function sendSNS() {
    try {
        const res = await fetch(`${API}/api/admin/broadcast-hospital`, {
            method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({ hazard_type: document.getElementById('sns-h').value, severity: document.getElementById('sns-s').value, victim_count: parseInt(document.getElementById('sns-v').value)||0, message: document.getElementById('sns-m').value })
        });
        if (res.ok) { closeSNS(); toast('SNS Alert dispatched','📡','var(--red)'); }
    } catch(_){}
}

/* ── Simulator ── */
async function sim(type) {
    try {
        await fetch(`${API}/api/admin/simulate/${type}`,{method:'POST'});
        toast('Event simulated','⚡','var(--cyan)');
        fetchAll();
    } catch(_){}
}
async function purge() {
    try {
        await fetch(`${API}/api/admin/clear-demo`,{method:'POST'});
        gRouteLines.forEach(l => l.setMap(null)); gRouteLines = [];
        toast('Data purged','🗑️','var(--muted)');
        fetchAll();
    } catch(_){}
}

/* ── Mode toggle ── */
function syncSimNav() {
    document.getElementById('nav-sim').style.display = isDemoMode ? '' : 'none';
    if (isDemoMode) startPatrol(); else stopPatrol();
}

/* ════════════════════════════════
   BOOT
════════════════════════════════ */
document.addEventListener('DOMContentLoaded', async () => {
    setInterval(tick, 1000); tick();

    // 1. Fetch config (Mapbox token + mode)
    let mbToken = '';
    try {
        const cfg = await fetch(`${API}/api/admin/config`).then(r=>r.json());
        mbToken    = cfg.mapbox_token || '';
        isDemoMode = cfg.demo_mode !== false;
    } catch(_){}

    // 2. Fallback: read mode from /health
    if (!mbToken) {
        try { const h = await fetch(`${API}/health`).then(r=>r.json()); isDemoMode = h.mode === 'demo'; } catch(_){}
    }

    // 3. Wire mode radios
    document.querySelectorAll('input[name="mode"]').forEach(r => {
        r.checked = r.value === (isDemoMode ? 'demo' : 'live');
        r.addEventListener('change', async e => {
            isDemoMode = e.target.value === 'demo';
            try { await fetch(`${API}/api/admin/toggle-mode`,{method:'POST'}); } catch(_){}
            syncSimNav();
            toast(`Switched to ${isDemoMode?'Demo':'Live'} Mode`,'🔄','var(--blue)');
        });
    });
    syncSimNav();

    // 4. Init Mapbox
    if (mbToken) {
        mapboxgl.accessToken = mbToken;
        initGoogleMap();
    } else {
        alert("No Mapbox token configured.");
    }

    initSSE();
    setInterval(fetchAll, 30000); // safety fallback poll
});


