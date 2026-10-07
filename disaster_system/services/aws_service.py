import logging
import boto3
import json
import uuid
import datetime
from functools import lru_cache
from config import get_settings

logger = logging.getLogger(__name__)

class AWSService:
    # In-memory mock databases
    _mock_citizens = {
        "+919876543001": {"phone": "+919876543001", "name": "Citizen 1", "lat": 28.7233, "lon": 77.3134, "status": "SAFE"},
        "+919876543002": {"phone": "+919876543002", "name": "Citizen 2", "lat": 28.5247, "lon": 77.1155, "status": "SAFE"},
        "+919876543003": {"phone": "+919876543003", "name": "Citizen 3", "lat": 28.6417, "lon": 77.2383, "status": "SAFE"},
        "+919876543004": {"phone": "+919876543004", "name": "Citizen 4", "lat": 28.7424, "lon": 77.1456, "status": "SAFE"},
        "+919876543005": {"phone": "+919876543005", "name": "Citizen 5", "lat": 28.6291, "lon": 77.1142, "status": "IN_DANGER"},
        "+919876543006": {"phone": "+919876543006", "name": "Citizen 6", "lat": 28.5367, "lon": 77.2811, "status": "SAFE"},
        "+919876543007": {"phone": "+919876543007", "name": "Citizen 7", "lat": 28.4756, "lon": 77.2188, "status": "SAFE"},
        "+919876543008": {"phone": "+919876543008", "name": "Citizen 8", "lat": 28.6489, "lon": 77.0604, "status": "SAFE"},
        "+919876543009": {"phone": "+919876543009", "name": "Citizen 9", "lat": 28.5753, "lon": 77.2634, "status": "IN_DANGER"},
        "+919876543010": {"phone": "+919876543010", "name": "Citizen 10", "lat": 28.5281, "lon": 77.3104, "status": "SAFE"},
        "+919876543011": {"phone": "+919876543011", "name": "Citizen 11", "lat": 28.5179, "lon": 77.1136, "status": "SAFE"},
        "+919876543012": {"phone": "+919876543012", "name": "Citizen 12", "lat": 28.6827, "lon": 77.1335, "status": "SAFE"},
        "+919876543013": {"phone": "+919876543013", "name": "Citizen 13", "lat": 28.6282, "lon": 77.0866, "status": "SAFE"},
        "+919876543014": {"phone": "+919876543014", "name": "Citizen 14", "lat": 28.6251, "lon": 77.1504, "status": "IN_DANGER"},
        "+919876543015": {"phone": "+919876543015", "name": "Citizen 15", "lat": 28.7226, "lon": 77.2436, "status": "SAFE"},
        "+919876543016": {"phone": "+919876543016", "name": "Citizen 16", "lat": 28.5005, "lon": 77.1183, "status": "SAFE"},
        "+919876543017": {"phone": "+919876543017", "name": "Citizen 17", "lat": 28.5769, "lon": 77.1666, "status": "IN_DANGER"},
        "+919876543018": {"phone": "+919876543018", "name": "Citizen 18", "lat": 28.5642, "lon": 77.3323, "status": "SAFE"},
        "+919876543019": {"phone": "+919876543019", "name": "Citizen 19", "lat": 28.7450, "lon": 77.2152, "status": "SAFE"},
        "+919876543020": {"phone": "+919876543020", "name": "Citizen 20", "lat": 28.7201, "lon": 77.0714, "status": "SAFE"}
    }
    _mock_incidents = {}
    _mock_hazard_zones = {
        "zone-001": {"zone_id": "zone-001", "hazard_type": "FLOOD", "lat": 28.6139, "lon": 77.2090, "radius_km": 5.0, "intensity": "HIGH", "color": "RED", "description": "Severe flooding in central district.", "source": "SENSOR", "detected_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    }
    _mock_hospitals = {
        "hosp-001": {"hospital_id": "hosp-001", "name": "AIIMS New Delhi", "lat": 28.5672, "lon": 77.2100, "beds_available": 150, "phone": "+911126588500", "specialties": ["TRAUMA", "CARDIOLOGY"]},
        "hosp-002": {"hospital_id": "hosp-002", "name": "Safdarjung Hospital", "lat": 28.5683, "lon": 77.2057, "beds_available": 85, "phone": "+911126165060", "specialties": ["BURN", "GENERAL"]},
        "hosp-003": {"hospital_id": "hosp-003", "name": "Fortis Escorts", "lat": 28.5583, "lon": 77.2764, "beds_available": 40, "phone": "+911147135000", "specialties": ["CARDIOLOGY", "NEUROLOGY"]}
    }
    
    # -----------------------------------------------------------------------
    # Real Delhi Police Stations as POLICE units (actual GPS coordinates)
    # + Fire Stations + Ambulance depots
    # -----------------------------------------------------------------------
    _mock_units = {
        # ── Delhi Police Stations (real locations) ──
        "ps-connaught":  {"unit_id": "ps-connaught",  "unit_type": "POLICE", "lat": 28.6315, "lon": 77.2167, "status": "PATROL",  "name": "Connaught Place PS",       "station": "Connaught Place"},
        "ps-chandni":    {"unit_id": "ps-chandni",    "unit_type": "POLICE", "lat": 28.6562, "lon": 77.2300, "status": "PATROL",  "name": "Chandni Chowk PS",         "station": "Chandni Chowk"},
        "ps-karolbagh":  {"unit_id": "ps-karolbagh",  "unit_type": "POLICE", "lat": 28.6519, "lon": 77.1909, "status": "STANDBY", "name": "Karol Bagh PS",            "station": "Karol Bagh"},
        "ps-lajpatnagar":{"unit_id": "ps-lajpatnagar","unit_type": "POLICE", "lat": 28.5679, "lon": 77.2431, "status": "PATROL",  "name": "Lajpat Nagar PS",         "station": "Lajpat Nagar"},
        "ps-saketdistrict":{"unit_id":"ps-saketdistrict","unit_type":"POLICE","lat":28.5244, "lon": 77.2066, "status": "STANDBY", "name": "Saket PS",                 "station": "Saket"},
        "ps-hauzkhaz":   {"unit_id": "ps-hauzkhaz",   "unit_type": "POLICE", "lat": 28.5494, "lon": 77.2001, "status": "PATROL",  "name": "Hauz Khas PS",            "station": "Hauz Khas"},
        "ps-rohini":     {"unit_id": "ps-rohini",     "unit_type": "POLICE", "lat": 28.7341, "lon": 77.1025, "status": "PATROL",  "name": "Rohini PS",               "station": "Rohini Sector 9"},
        "ps-dwarka":     {"unit_id": "ps-dwarka",     "unit_type": "POLICE", "lat": 28.5921, "lon": 77.0460, "status": "STANDBY", "name": "Dwarka PS",               "station": "Dwarka Sector 10"},
        "ps-janakpuri":  {"unit_id": "ps-janakpuri",  "unit_type": "POLICE", "lat": 28.6219, "lon": 77.0878, "status": "PATROL",  "name": "Janakpuri PS",            "station": "Janakpuri"},
        "ps-shahdara":   {"unit_id": "ps-shahdara",   "unit_type": "POLICE", "lat": 28.6742, "lon": 77.2931, "status": "PATROL",  "name": "Shahdara PS",             "station": "Shahdara"},
        "ps-mustafabad": {"unit_id": "ps-mustafabad", "unit_type": "POLICE", "lat": 28.7192, "lon": 77.3052, "status": "STANDBY", "name": "Mustafabad PS",           "station": "Mustafabad"},
        "ps-mehrauli":   {"unit_id": "ps-mehrauli",   "unit_type": "POLICE", "lat": 28.5240, "lon": 77.1855, "status": "PATROL",  "name": "Mehrauli PS",             "station": "Mehrauli"},
        "ps-vasantkunj": {"unit_id": "ps-vasantkunj", "unit_type": "POLICE", "lat": 28.5214, "lon": 77.1583, "status": "STANDBY", "name": "Vasant Kunj PS",          "station": "Vasant Kunj"},
        "ps-gtbnagar":   {"unit_id": "ps-gtbnagar",   "unit_type": "POLICE", "lat": 28.7022, "lon": 77.2031, "status": "PATROL",  "name": "GTB Nagar PS",            "station": "GTB Nagar"},
        "ps-paharganj":  {"unit_id": "ps-paharganj",  "unit_type": "POLICE", "lat": 28.6432, "lon": 77.2101, "status": "PATROL",  "name": "Paharganj PS",            "station": "Paharganj"},
        "ps-okhla":      {"unit_id": "ps-okhla",      "unit_type": "POLICE", "lat": 28.5355, "lon": 77.2742, "status": "PATROL",  "name": "Okhla PS",                "station": "Okhla Industrial Area"},
        "ps-geeta-colony":{"unit_id":"ps-geeta-colony","unit_type":"POLICE", "lat": 28.6601, "lon": 77.2713, "status": "STANDBY", "name": "Geeta Colony PS",         "station": "Geeta Colony"},
        "ps-yamuna-vihar":{"unit_id":"ps-yamuna-vihar","unit_type":"POLICE", "lat": 28.6932, "lon": 77.2741, "status": "PATROL",  "name": "Yamuna Vihar PS",         "station": "Yamuna Vihar"},
        "ps- डिफेंस":      {"unit_id": "ps-def-colony","unit_type": "POLICE", "lat": 28.5733, "lon": 77.2345, "status": "STANDBY", "name": "Defence Colony PS",       "station": "Defence Colony"},
        "ps-narela":     {"unit_id": "ps-narela",     "unit_type": "POLICE", "lat": 28.8523, "lon": 77.0854, "status": "PATROL",  "name": "Narela PS",               "station": "Narela"},
        "ps-bana":       {"unit_id": "ps-bana",       "unit_type": "POLICE", "lat": 28.6750, "lon": 77.1000, "status": "STANDBY", "name": "Punjabi Bagh PS",         "station": "Punjabi Bagh"},
        # ── Delhi Fire Stations (real locations) ──
        "fire-connaught": {"unit_id": "fire-connaught","unit_type": "FIRE",  "lat": 28.6340, "lon": 77.2195, "status": "STANDBY", "name": "Fire Stn Connaught Place", "station": "Connaught Place"},
        "fire-kashmere":  {"unit_id": "fire-kashmere", "unit_type": "FIRE",  "lat": 28.6673, "lon": 77.2285, "status": "STANDBY", "name": "Fire Stn Kashmere Gate",   "station": "Kashmere Gate"},
        "fire-lodi":      {"unit_id": "fire-lodi",     "unit_type": "FIRE",  "lat": 28.5931, "lon": 77.2236, "status": "STANDBY", "name": "Fire Stn Lodi Road",       "station": "Lodi Road"},
        "fire-rohini":    {"unit_id": "fire-rohini",   "unit_type": "FIRE",  "lat": 28.7195, "lon": 77.1190, "status": "STANDBY", "name": "Fire Stn Rohini",          "station": "Rohini"},
        "fire-dwarka":    {"unit_id": "fire-dwarka",   "unit_type": "FIRE",  "lat": 28.5927, "lon": 77.0590, "status": "STANDBY", "name": "Fire Stn Dwarka",          "station": "Dwarka"},
        "fire-mayur":     {"unit_id": "fire-mayur",    "unit_type": "FIRE",  "lat": 28.6050, "lon": 77.2955, "status": "STANDBY", "name": "Fire Stn Mayur Vihar",     "station": "Mayur Vihar"},
        "fire-laxmi":     {"unit_id": "fire-laxmi",    "unit_type": "FIRE",  "lat": 28.6358, "lon": 77.2750, "status": "STANDBY", "name": "Fire Stn Laxmi Nagar",     "station": "Laxmi Nagar"},
        "fire-najafgarh": {"unit_id": "fire-najaf",    "unit_type": "FIRE",  "lat": 28.6120, "lon": 76.9830, "status": "STANDBY", "name": "Fire Stn Najafgarh",       "station": "Najafgarh"},
        "fire-bawana":    {"unit_id": "fire-bawana",   "unit_type": "FIRE",  "lat": 28.8050, "lon": 77.0345, "status": "STANDBY", "name": "Fire Stn Bawana",          "station": "Bawana Industrial"},
        "fire-okla":      {"unit_id": "fire-okla",     "unit_type": "FIRE",  "lat": 28.5255, "lon": 77.2842, "status": "STANDBY", "name": "Fire Stn Okhla Phase 1",   "station": "Okhla Phase 1"},
        "fire-vasant":    {"unit_id": "fire-vasant",   "unit_type": "FIRE",  "lat": 28.5314, "lon": 77.1553, "status": "STANDBY", "name": "Fire Stn Vasant Kunj",     "station": "Vasant Kunj"},
        # ── Delhi Ambulance Depots ──
        "amb-aiims":      {"unit_id": "amb-aiims",     "unit_type": "RESCUE","lat": 28.5672, "lon": 77.2100, "status": "STANDBY", "name": "Ambulance — AIIMS",        "station": "AIIMS"},
        "amb-gtb":        {"unit_id": "amb-gtb",       "unit_type": "RESCUE","lat": 28.6791, "lon": 77.3041, "status": "STANDBY", "name": "Ambulance — GTB Hospital",  "station": "GTB Hospital"},
        "amb-safdarjung": {"unit_id": "amb-safdarjung","unit_type": "RESCUE","lat": 28.5683, "lon": 77.2057, "status": "STANDBY", "name": "Ambulance — Safdarjung",    "station": "Safdarjung"},
        "amb-rml":        {"unit_id": "amb-rml",       "unit_type": "RESCUE","lat": 28.6367, "lon": 77.2088, "status": "STANDBY", "name": "Ambulance — RML Hospital",  "station": "RML Hospital"},
        "amb-apollo":     {"unit_id": "amb-apollo",    "unit_type": "RESCUE","lat": 28.5412, "lon": 77.2798, "status": "STANDBY", "name": "Ambulance — Apollo Hosp",   "station": "Sarita Vihar"},
        "amb-max-saket":  {"unit_id": "amb-max-saket", "unit_type": "RESCUE","lat": 28.5265, "lon": 77.2120, "status": "STANDBY", "name": "Ambulance — Max Saket",     "station": "Saket"},
        "amb-fortis":     {"unit_id": "amb-fortis",    "unit_type": "RESCUE","lat": 28.6950, "lon": 77.1432, "status": "STANDBY", "name": "Ambulance — Fortis Shalimar","station":"Shalimar Bagh"},
        "amb-gangaram":   {"unit_id": "amb-gangaram",  "unit_type": "RESCUE","lat": 28.6385, "lon": 77.1895, "status": "STANDBY", "name": "Ambulance — Ganga Ram",     "station": "Rajinder Nagar"},
        "amb-holyfamily": {"unit_id": "amb-holy",      "unit_type": "RESCUE","lat": 28.5620, "lon": 77.2754, "status": "STANDBY", "name": "Ambulance — Holy Family",   "station": "Okhla"},
        "amb-venky":      {"unit_id": "amb-venky",     "unit_type": "RESCUE","lat": 28.5830, "lon": 77.0255, "status": "STANDBY", "name": "Ambulance — Venkateshwar",  "station": "Dwarka"},
    }

    def __init__(self):
        self.settings = get_settings()
        self.use_mock = self.settings.demo_mode
        self.clients = {}
        
        if not self.use_mock:
            if not self.settings.aws_access_key_id or not self.settings.aws_secret_access_key:
                logger.warning("AWS credentials not found. Falling back to mock mode.")
                self.use_mock = True

    def _get_client(self, service_name):
        if self.use_mock:
            return None
            
        if service_name in self.clients:
            return self.clients[service_name]
            
        try:
            region = self.settings.bedrock_region if service_name == 'bedrock-runtime' else self.settings.aws_region
            client = boto3.client(
                service_name,
                region_name=region,
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key
            )
            self.clients[service_name] = client
            return client
        except Exception as e:
            logger.error(f"Failed to initialize AWS client for {service_name}: {e}")
            self.use_mock = True
            return None

    # DynamoDB operations
    def save_citizen(self, phone, name, lat, lon, status):
        item = {
            "phone": phone,
            "name": name,
            "lat": float(lat),
            "lon": float(lon),
            "status": status,
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        if self.use_mock:
            self._mock_citizens[phone] = item
            return
            
        client = self._get_client('dynamodb')
        if self.use_mock:
            self._mock_citizens[phone] = item
            return
            
        try:
            dynamo_item = {
                'phone': {'S': phone},
                'name': {'S': name},
                'lat': {'N': str(lat)},
                'lon': {'N': str(lon)},
                'status': {'S': status},
                'updated_at': {'S': item['updated_at']}
            }
            client.put_item(
                TableName=self.settings.dynamodb_citizens_table,
                Item=dynamo_item
            )
        except Exception as e:
            logger.error(f"DynamoDB save_citizen error: {e}")

    def update_citizen_status(self, phone, status):
        if self.use_mock:
            if phone in self._mock_citizens:
                self._mock_citizens[phone]['status'] = status
                self._mock_citizens[phone]['updated_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            return
            
        client = self._get_client('dynamodb')
        if self.use_mock:
            if phone in self._mock_citizens:
                self._mock_citizens[phone]['status'] = status
            return
            
        try:
            client.update_item(
                TableName=self.settings.dynamodb_citizens_table,
                Key={'phone': {'S': phone}},
                UpdateExpression="SET #status_attr = :status_val, updated_at = :updated_val",
                ExpressionAttributeNames={'#status_attr': 'status'},
                ExpressionAttributeValues={
                    ':status_val': {'S': status},
                    ':updated_val': {'S': datetime.datetime.now(datetime.timezone.utc).isoformat()}
                }
            )
        except Exception as e:
            logger.error(f"DynamoDB update_citizen_status error: {e}")

    def get_citizen(self, phone):
        if self.use_mock:
            return self._mock_citizens.get(phone)
            
        client = self._get_client('dynamodb')
        if self.use_mock:
            return self._mock_citizens.get(phone)
            
        try:
            response = client.get_item(
                TableName=self.settings.dynamodb_citizens_table,
                Key={'phone': {'S': phone}}
            )
            item = response.get('Item')
            if item:
                return {
                    'phone': item['phone']['S'],
                    'name': item['name']['S'],
                    'lat': float(item.get('lat', {}).get('N', 0)),
                    'lon': float(item.get('lon', {}).get('N', 0)),
                    'status': item.get('status', {}).get('S', 'REGISTERED')
                }
            return None
        except Exception as e:
            logger.error(f"DynamoDB get_citizen error: {e}")
            return None

    def get_all_citizens(self):
        if self.use_mock:
            return list(self._mock_citizens.values())
            
        client = self._get_client('dynamodb')
        if self.use_mock:
            return list(self._mock_citizens.values())
            
        try:
            response = client.scan(TableName=self.settings.dynamodb_citizens_table)
            results = []
            for item in response.get('Items', []):
                results.append({
                    'phone': item['phone']['S'],
                    'name': item['name']['S'],
                    'lat': float(item.get('lat', {}).get('N', 0)),
                    'lon': float(item.get('lon', {}).get('N', 0)),
                    'status': item.get('status', {}).get('S', 'REGISTERED')
                })
            return results
        except Exception as e:
            logger.error(f"DynamoDB get_all_citizens error: {e}")
            return []

    def get_citizens_by_status(self, status):
        all_citizens = self.get_all_citizens()
        return [c for c in all_citizens if c.get('status') == status]

    def save_incident(self, incident_id, phone, lat, lon, hazard_type, severity_score, severity_level, visual_findings, image_url, status, recommended_dispatch, immediate_life_threat):
        item = {
            "incident_id": incident_id,
            "phone": phone,
            "lat": float(lat),
            "lon": float(lon),
            "hazard_type": hazard_type,
            "severity_score": severity_score,
            "severity_level": severity_level,
            "visual_findings": visual_findings,
            "image_url": image_url,
            "status": status,
            "recommended_dispatch": recommended_dispatch,
            "immediate_life_threat": immediate_life_threat,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        
        if self.use_mock:
            self._mock_incidents[incident_id] = item
            return
            
        client = self._get_client('dynamodb')
        if self.use_mock:
            self._mock_incidents[incident_id] = item
            return
            
        try:
            dynamo_item = {
                'incident_id': {'S': incident_id},
                'phone': {'S': phone},
                'lat': {'N': str(lat)},
                'lon': {'N': str(lon)},
                'hazard_type': {'S': hazard_type},
                'severity_score': {'N': str(severity_score)},
                'severity_level': {'S': severity_level},
                'visual_findings': {'S': visual_findings},
                'image_url': {'S': image_url},
                'status': {'S': status},
                'recommended_dispatch': {'S': recommended_dispatch},
                'immediate_life_threat': {'BOOL': immediate_life_threat},
                'timestamp': {'S': item['timestamp']}
            }
            client.put_item(
                TableName=self.settings.dynamodb_incidents_table,
                Item=dynamo_item
            )
        except Exception as e:
            logger.error(f"DynamoDB save_incident error: {e}")

    def update_incident_status(self, incident_id, status):
        if self.use_mock:
            if incident_id in self._mock_incidents:
                self._mock_incidents[incident_id]['status'] = status
            return
            
        client = self._get_client('dynamodb')
        if self.use_mock:
            if incident_id in self._mock_incidents:
                self._mock_incidents[incident_id]['status'] = status
            return
            
        try:
            client.update_item(
                TableName=self.settings.dynamodb_incidents_table,
                Key={'incident_id': {'S': incident_id}},
                UpdateExpression="SET #status_attr = :status_val",
                ExpressionAttributeNames={'#status_attr': 'status'},
                ExpressionAttributeValues={':status_val': {'S': status}}
            )
        except Exception as e:
            logger.error(f"DynamoDB update_incident_status error: {e}")

    def get_all_incidents(self):
        if self.use_mock:
            return list(self._mock_incidents.values())
            
        client = self._get_client('dynamodb')
        if self.use_mock:
            return list(self._mock_incidents.values())
            
        try:
            response = client.scan(TableName=self.settings.dynamodb_incidents_table)
            results = []
            for item in response.get('Items', []):
                results.append({
                    'incident_id': item['incident_id']['S'],
                    'phone': item.get('phone', {}).get('S', ''),
                    'lat': float(item.get('lat', {}).get('N', 0)),
                    'lon': float(item.get('lon', {}).get('N', 0)),
                    'hazard_type': item.get('hazard_type', {}).get('S', 'UNKNOWN'),
                    'severity_score': int(item.get('severity_score', {}).get('N', 1)),
                    'severity_level': item.get('severity_level', {}).get('S', 'LOW'),
                    'status': item.get('status', {}).get('S', 'PENDING'),
                    'timestamp': item.get('timestamp', {}).get('S', '')
                })
            return results
        except Exception as e:
            logger.error(f"DynamoDB get_all_incidents error: {e}")
            return []

    def get_incidents_by_status(self, status):
        all_incidents = self.get_all_incidents()
        return [i for i in all_incidents if i.get('status') == status]

    def save_hazard_zone(self, zone_id, hazard_type, lat, lon, radius_km, intensity, color, description, source, detected_at):
        item = {
            "zone_id": zone_id,
            "hazard_type": hazard_type,
            "lat": float(lat),
            "lon": float(lon),
            "radius_km": float(radius_km),
            "intensity": intensity,
            "color": color,
            "description": description,
            "source": source,
            "detected_at": detected_at
        }
        
        if self.use_mock:
            self._mock_hazard_zones[zone_id] = item
            return
            
        client = self._get_client('dynamodb')
        if self.use_mock:
            self._mock_hazard_zones[zone_id] = item
            return
            
        try:
            dynamo_item = {
                'zone_id': {'S': zone_id},
                'hazard_type': {'S': hazard_type},
                'lat': {'N': str(lat)},
                'lon': {'N': str(lon)},
                'radius_km': {'N': str(radius_km)},
                'intensity': {'S': intensity},
                'color': {'S': color},
                'description': {'S': description},
                'source': {'S': source},
                'detected_at': {'S': detected_at}
            }
            client.put_item(
                TableName=self.settings.dynamodb_hazard_zones_table,
                Item=dynamo_item
            )
        except Exception as e:
            logger.error(f"DynamoDB save_hazard_zone error: {e}")

    def get_active_hazard_zones(self):
        if self.use_mock:
            return list(self._mock_hazard_zones.values())
            
        client = self._get_client('dynamodb')
        if self.use_mock:
            return list(self._mock_hazard_zones.values())
            
        try:
            response = client.scan(TableName=self.settings.dynamodb_hazard_zones_table)
            results = []
            for item in response.get('Items', []):
                results.append({
                    'zone_id': item['zone_id']['S'],
                    'hazard_type': item.get('hazard_type', {}).get('S', 'UNKNOWN'),
                    'lat': float(item.get('lat', {}).get('N', 0)),
                    'lon': float(item.get('lon', {}).get('N', 0)),
                    'radius_km': float(item.get('radius_km', {}).get('N', 1.0)),
                    'color': item.get('color', {}).get('S', 'YELLOW')
                })
            return results
        except Exception as e:
            logger.error(f"DynamoDB get_active_hazard_zones error: {e}")
            return []

    def clear_hazard_zone(self, zone_id):
        if self.use_mock:
            if zone_id in self._mock_hazard_zones:
                del self._mock_hazard_zones[zone_id]
            return
            
        client = self._get_client('dynamodb')
        if self.use_mock:
            if zone_id in self._mock_hazard_zones:
                del self._mock_hazard_zones[zone_id]
            return
            
        try:
            client.delete_item(
                TableName=self.settings.dynamodb_hazard_zones_table,
                Key={'zone_id': {'S': zone_id}}
            )
        except Exception as e:
            logger.error(f"DynamoDB clear_hazard_zone error: {e}")

    def save_hospital(self, hospital_id, name, lat, lon, beds_available, phone, specialties):
        item = {
            "hospital_id": hospital_id,
            "name": name,
            "lat": float(lat),
            "lon": float(lon),
            "beds_available": int(beds_available),
            "phone": phone,
            "specialties": specialties
        }
        
        if self.use_mock:
            self._mock_hospitals[hospital_id] = item
            return
            
        client = self._get_client('dynamodb')
        if self.use_mock:
            self._mock_hospitals[hospital_id] = item
            return
            
        try:
            dynamo_item = {
                'hospital_id': {'S': hospital_id},
                'name': {'S': name},
                'lat': {'N': str(lat)},
                'lon': {'N': str(lon)},
                'beds_available': {'N': str(beds_available)},
                'phone': {'S': phone},
                'specialties': {'SS': specialties}
            }
            client.put_item(
                TableName=self.settings.dynamodb_hospitals_table,
                Item=dynamo_item
            )
        except Exception as e:
            logger.error(f"DynamoDB save_hospital error: {e}")

    def get_all_hospitals(self):
        if self.use_mock:
            return list(self._mock_hospitals.values())
            
        client = self._get_client('dynamodb')
        if self.use_mock:
            return list(self._mock_hospitals.values())
            
        try:
            response = client.scan(TableName=self.settings.dynamodb_hospitals_table)
            results = []
            for item in response.get('Items', []):
                results.append({
                    'hospital_id': item['hospital_id']['S'],
                    'name': item.get('name', {}).get('S', ''),
                    'lat': float(item.get('lat', {}).get('N', 0)),
                    'lon': float(item.get('lon', {}).get('N', 0)),
                    'beds_available': int(item.get('beds_available', {}).get('N', 0)),
                    'phone': item.get('phone', {}).get('S', ''),
                    'specialties': item.get('specialties', {}).get('SS', [])
                })
            return results
        except Exception as e:
            logger.error(f"DynamoDB get_all_hospitals error: {e}")
            return []

    def update_hospital_beds(self, hospital_id, beds):
        if self.use_mock:
            if hospital_id in self._mock_hospitals:
                self._mock_hospitals[hospital_id]['beds_available'] = beds
            return
            
        client = self._get_client('dynamodb')
        if self.use_mock:
            if hospital_id in self._mock_hospitals:
                self._mock_hospitals[hospital_id]['beds_available'] = beds
            return
            
        try:
            client.update_item(
                TableName=self.settings.dynamodb_hospitals_table,
                Key={'hospital_id': {'S': hospital_id}},
                UpdateExpression="SET beds_available = :b",
                ExpressionAttributeValues={':b': {'N': str(beds)}}
            )
        except Exception as e:
            logger.error(f"DynamoDB update_hospital_beds error: {e}")

    def upload_image(self, file_bytes, key):
        if self.use_mock:
            return f"https://mock-s3-bucket.s3.amazonaws.com/{key}"
            
        client = self._get_client('s3')
        if self.use_mock:
            return f"https://mock-s3-bucket.s3.amazonaws.com/{key}"
            
        try:
            client.put_object(
                Bucket=self.settings.s3_bucket_name,
                Key=key,
                Body=file_bytes,
                ContentType='image/jpeg'
            )
            return f"https://{self.settings.s3_bucket_name}.s3.{self.settings.aws_region}.amazonaws.com/{key}"
        except Exception as e:
            logger.error(f"S3 upload error: {e}")
            return f"https://mock-s3-bucket.s3.amazonaws.com/{key}"

    def broadcast_emergency(self, subject, message):
        if self.use_mock:
            logger.info(f"[MOCK SNS BROADCAST] Subject: {subject} | Message: {message}")
            return
            
        client = self._get_client('sns')
        if self.use_mock:
            logger.info(f"[MOCK SNS BROADCAST] Subject: {subject} | Message: {message}")
            return
            
        try:
            client.publish(
                TopicArn=self.settings.sns_topic_arn,
                Subject=subject,
                Message=message
            )
        except Exception as e:
            logger.error(f"SNS broadcast error: {e}")

    def send_hospital_alert(self, hospital_phone, message):
        if self.use_mock:
            logger.info(f"[MOCK SNS SMS] To: {hospital_phone} | Message: {message}")
            return
            
        client = self._get_client('sns')
        if self.use_mock:
            logger.info(f"[MOCK SNS SMS] To: {hospital_phone} | Message: {message}")
            return
            
        try:
            client.publish(
                PhoneNumber=hospital_phone,
                Message=message
            )
        except Exception as e:
            logger.error(f"SNS SMS error: {e}")

    def save_unit(self, unit_id: str, unit_type: str, lat: float, lon: float, status: str = "ACTIVE", name: str = "") -> dict:
        if self.use_mock:
            self._mock_units[unit_id] = {
                "unit_id": unit_id,
                "unit_type": unit_type,
                "lat": lat,
                "lon": lon,
                "status": status,
                "name": name,
                "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }
            return self._mock_units[unit_id]
        return {}

    def get_all_units(self) -> list[dict]:
        if self.use_mock:
            return list(self._mock_units.values())
        return []

@lru_cache()
def get_aws_service():
    return AWSService()
