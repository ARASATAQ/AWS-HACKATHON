import json
import logging
import base64
import random
from services.aws_service import get_aws_service
from config import get_settings

logger = logging.getLogger(__name__)

def analyze_disaster_image(image_bytes: bytes, image_media_type: str = 'image/jpeg') -> dict:
    aws_svc = get_aws_service()
    settings = get_settings()
    client = aws_svc._get_client('bedrock-runtime')
    
    if aws_svc.use_mock or client is None:
        logger.info("Using mock Bedrock response.")
        hazards = ["FLOOD", "EARTHQUAKE", "TSUNAMI", "HEATWAVE"]
        hazard = random.choice(hazards)
        severity = random.randint(3, 5)
        level = "CRITICAL" if severity == 5 else "MODERATE"
        return {
            "detected_hazard": hazard,
            "severity_score": severity,
            "severity_level": level,
            "visual_findings": "Mock visual findings indicating significant disaster impact.",
            "immediate_life_threat": severity >= 4,
            "recommended_dispatch": "BOAT" if hazard in ["FLOOD", "TSUNAMI"] else "AIRLIFT"
        }

    try:
        encoded_image = base64.b64encode(image_bytes).decode('utf-8')
        prompt = """
        Analyze this disaster image against 4 hazard archetypes:
        - Flood: Water depth estimation (tire-level, waist-level, roof-level), current speed, submerged vehicles
        - Earthquake: Structural debris, wall fissures, collapsed roofs, trapped victims
        - Tsunami: Massive inundation, structural washaways, heavy debris fields
        - Extreme Heat/Drought: Wildfire proximity, arid ground fissures, thermal collapse

        Output MUST be in strict JSON format matching this schema with no markdown formatting or extra text:
        {
          "detected_hazard": "FLOOD | EARTHQUAKE | TSUNAMI | HEATWAVE | UNKNOWN",
          "severity_score": 1-5,
          "severity_level": "LOW | MODERATE | CRITICAL",
          "visual_findings": "Detailed description...",
          "immediate_life_threat": true or false,
          "recommended_dispatch": "BOAT | MEDICAL | AMBULANCE | AIRLIFT"
        }
        """

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": image_media_type,
                                "data": encoded_image
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        }

        response = client.invoke_model(
            modelId=settings.bedrock_model_id or "anthropic.claude-3-haiku-20240307-v1:0",
            body=json.dumps(request_body)
        )
        
        response_body = json.loads(response.get('body').read())
        output_text = response_body.get('content', [{}])[0].get('text', '')
        
        # Clean potential markdown wrapping
        output_text = output_text.strip()
        if output_text.startswith("```json"):
            output_text = output_text[7:]
        if output_text.endswith("```"):
            output_text = output_text[:-3]
            
        result = json.loads(output_text.strip())
        
        # Validate required fields
        required_keys = ["detected_hazard", "severity_score", "severity_level", "visual_findings", "immediate_life_threat", "recommended_dispatch"]
        for key in required_keys:
            if key not in result:
                raise ValueError(f"Missing required key: {key}")
                
        return result
        
    except Exception as e:
        logger.error(f"Error calling Bedrock or parsing response: {e}")
        return {
            "detected_hazard": "UNKNOWN",
            "severity_score": 1,
            "severity_level": "LOW",
            "visual_findings": "Failed to analyze image.",
            "immediate_life_threat": False,
            "recommended_dispatch": "MEDICAL"
        }
