import requests, json, time

BASE = 'http://localhost:8000'

print('=' * 60)
print('ðŸš€ FULL END-TO-END SYSTEM VALIDATION TEST')
print('=' * 60)

# Wait for server
time.sleep(2)

# 1. Health
print('\n[1/10] Checking System Health...')
r = requests.get(f'{BASE}/health')
assert r.status_code == 200, f'Health failed: {r.status_code}'
data = r.json()
print(f"  âœ“ System: {data['system']} | Mode: {data['mode']} | Backend: {data['aws_backend']}")

# 2. Meta WhatsApp GET Handshake
print('\n[2/10] Verifying Meta WhatsApp GET Handshake...')
r = requests.get(f'{BASE}/webhook', params={'hub.mode': 'subscribe', 'hub.verify_token': 'disaster_verify_token_2024', 'hub.challenge': '12345678'})
assert r.status_code == 200 and r.text == '12345678', f'Webhook handshake failed: {r.status_code}'
print('  âœ“ Webhook verification handshake passed (challenge: 12345678)')

# 3. WhatsApp HELP Workflow
print('\n[3/10] Testing Citizen HELP Signal...')
r = requests.post(f'{BASE}/webhook', json={
    'entry': [{'changes': [{'value': {'messages': [{'from': '+919876500001', 'type': 'text', 'text': {'body': 'HELP'}}]}}]}]
})
assert r.status_code == 200
r_cit = requests.get(f'{BASE}/api/admin/citizens').json()
cit = next((c for c in r_cit if c['phone'] == '+919876500001'), None)
assert cit and cit['status'] == 'IN_DANGER', 'Citizen status not IN_DANGER'
print(f"  âœ“ Citizen +919876500001 status transitioned to: {cit['status']}")

# 4. WhatsApp Location Signal
print('\n[4/10] Testing Citizen WhatsApp Location Pin Drop...')
r = requests.post(f'{BASE}/webhook', json={
    'entry': [{'changes': [{'value': {'messages': [{
        'from': '+919876500001',
        'type': 'location',
        'location': {'latitude': 28.5672, 'longitude': 77.2100}
    }]}}]}]
})
assert r.status_code == 200
r_inc = requests.get(f'{BASE}/api/admin/incidents').json()
loc_inc = next((i for i in r_inc if i['phone'] == '+919876500001'), None)
assert loc_inc, 'Incident report not created'
print(f"  âœ“ Incident report generated: {loc_inc['id']} at ({loc_inc['lat']}, {loc_inc['lng']})")

# 5. WhatsApp Photo + Bedrock Vision Triage
print('\n[5/10] Testing Disaster Photo Submission with Bedrock Vision Triage...')
r = requests.post(f'{BASE}/webhook', json={
    'entry': [{'changes': [{'value': {'messages': [{
        'from': '+919876500001',
        'type': 'image',
        'image': {'id': 'media_flood_evidence_001'}
    }]}}]}]
})
assert r.status_code == 200
r_inc = requests.get(f'{BASE}/api/admin/incidents').json()
vision_inc = next((i for i in r_inc if i['phone'] == '+919876500001' and i.get('severity_score', 0) > 0), None)
assert vision_inc, 'Vision incident not created'
print(f"  âœ“ Bedrock Vision Analysis: Severity {vision_inc['severity_score']}/5 ({vision_inc['severity']})")
print(f"  âœ“ Visual Findings: {vision_inc['findings']}")
print(f"  âœ“ Recommended Dispatch: {vision_inc['recommended_dispatch']}")

# 6. Admin Rescue Dispatch Flow
print('\n[6/10] Testing Command Center Rescue Dispatch...')
target_id = vision_inc['id']
r = requests.post(f'{BASE}/api/admin/dispatch/{target_id}')
assert r.status_code == 200 and r.json()['status'] == 'DISPATCHED'
print(f"  âœ“ Unit Dispatched to Incident {target_id}. Status: DISPATCHED")

# 7. Admin Mark Rescued Flow
print('\n[7/10] Testing Rescue Completion...')
r = requests.post(f'{BASE}/api/admin/mark-rescued/{target_id}')
assert r.status_code == 200 and r.json()['status'] == 'RESCUED'
print(f"  âœ“ Incident {target_id} marked as RESCUED. Citizen safe.")

# 8. Multi-Hazard Simulations
print('\n[8/10] Testing Multi-Hazard Simulation Triggers...')
for event in ['flood', 'earthquake', 'tsunami']:
    r = requests.post(f'{BASE}/api/admin/simulate/{event}')
    assert r.status_code == 200
    print(f"  âœ“ Simulated {event.upper()} hazard zone generated: {r.json()['zone_id']}")

# 9. Hospital Emergency Broadcast via SNS
print('\n[9/10] Testing Hospital Emergency Broadcast (Amazon SNS)...')
r = requests.post(f'{BASE}/api/admin/broadcast-hospital', json={
    'hazard_type': 'FLOOD',
    'victim_count': 15,
    'severity': 'CRITICAL',
    'message': 'Severe flash flooding near central sector. Mobilize trauma teams.'
})
assert r.status_code == 200
print(f"  âœ“ SNS Emergency Dispatch Broadcast transmitted to medical centers")

# 10. Dashboard UI Delivery
print('\n[10/10] Verifying Emergency Command Center Dashboard UI...')
r = requests.get(f'{BASE}/dashboard')
assert r.status_code == 200 and len(r.text) > 40000
print(f"  âœ“ Dashboard UI served ({len(r.text)} bytes, Tailwind CSS + Leaflet.js ready)")

print('\n' + '=' * 60)
print('âœ… ALL 10 ARCHITECTURAL & OPERATIONAL VALIDATION CHECKS PASSED!')
print('=' * 60)

