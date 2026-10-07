import random
import re

citizens_code = []
for i in range(1, 21):
    lat = 28.6139 + random.uniform(-0.15, 0.15)
    lon = 77.2090 + random.uniform(-0.15, 0.15)
    status = random.choice(['SAFE', 'SAFE', 'SAFE', 'IN_DANGER'])
    citizens_code.append(f'        "+919876543{i:03d}": {{"phone": "+919876543{i:03d}", "name": "Citizen {i}", "lat": {lat:.4f}, "lon": {lon:.4f}, "status": "{status}"}}')

units_code = []
for i in range(1, 15):
    lat = 28.6139 + random.uniform(-0.15, 0.15)
    lon = 77.2090 + random.uniform(-0.15, 0.15)
    u_type = random.choice(['FIRE', 'POLICE', 'RESCUE'])
    if u_type == 'FIRE': name = f'Fire Engine {random.randint(10,99)}'
    elif u_type == 'POLICE': name = f'Interceptor Unit {random.randint(1,20)}'
    else: name = f'Ambulance ALS-{random.randint(1,10)}'
    units_code.append(f'        "unit-{i}": {{"unit_id": "unit-{i}", "unit_type": "{u_type}", "lat": {lat:.4f}, "lon": {lon:.4f}, "status": "STANDBY", "name": "{name}"}}')

with open('c:\\Users\\arasa\\OneDrive\\Desktop\\NOVA-S AWS PORJECT\\disaster_system\\services\\aws_service.py', 'r') as f:
    content = f.read()

c_block = '    _mock_citizens = {\n' + ',\n'.join(citizens_code) + '\n    }'
content = re.sub(r'    _mock_citizens = \{.*?\}(?=\n    _mock_incidents)', c_block, content, flags=re.DOTALL)

u_block = '    _mock_units = {\n' + ',\n'.join(units_code) + '\n    }'
content = re.sub(r'    _mock_units = \{.*?\}(?=\n\n    def __init__)', u_block, content, flags=re.DOTALL)

with open('c:\\Users\\arasa\\OneDrive\\Desktop\\NOVA-S AWS PORJECT\\disaster_system\\services\\aws_service.py', 'w') as f:
    f.write(content)
print("Data injected.")
