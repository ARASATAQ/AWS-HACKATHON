import logging
import requests
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

def send_text_message(to: str, body: str) -> dict:
    if not settings.meta_whatsapp_token:
        logger.warning("WhatsApp token is empty, sending mock response.")
        return {"status": "mock", "message": body}
    
    url = f"https://graph.facebook.com/{settings.meta_api_version}/{settings.meta_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.meta_whatsapp_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body}
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send text message: {e}")
        return {"status": "error", "error": str(e)}

def send_interactive_buttons(to: str, body_text: str, buttons: list[dict]) -> dict:
    if not settings.meta_whatsapp_token:
        logger.warning("WhatsApp token is empty, sending mock response.")
        return {"status": "mock"}
        
    url = f"https://graph.facebook.com/{settings.meta_api_version}/{settings.meta_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.meta_whatsapp_token}",
        "Content-Type": "application/json"
    }
    
    interactive_buttons = []
    for btn in buttons[:3]:
        interactive_buttons.append({
            "type": "reply",
            "reply": {
                "id": btn.get("id"),
                "title": btn.get("title")
            }
        })
        
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": body_text
            },
            "action": {
                "buttons": interactive_buttons
            }
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send interactive buttons: {e}")
        return {"status": "error", "error": str(e)}

def send_location_request(to: str) -> dict:
    body = "Please share your live location pin so we can assist you."
    return send_text_message(to, body)

def send_emergency_alert(to: str, hazard_type: str, area: str) -> dict:
    body = f"⚠️ EMERGENCY: {hazard_type} alert in {area}. Reply 'SAFE' if okay or 'HELP' if you require assistance."
    return send_text_message(to, body)

def download_media(media_id: str) -> bytes:
    if not settings.meta_whatsapp_token:
        logger.warning("WhatsApp token is empty, cannot download media.")
        return None
        
    url = f"https://graph.facebook.com/{settings.meta_api_version}/{media_id}"
    headers = {
        "Authorization": f"Bearer {settings.meta_whatsapp_token}"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        media_url = response.json().get("url")
        
        if not media_url:
            logger.error("No media URL found in response.")
            return None
            
        media_response = requests.get(media_url, headers=headers)
        media_response.raise_for_status()
        return media_response.content
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download media: {e}")
        return None

def send_rescue_dispatched(to: str) -> dict:
    body = "🚨 Rescue unit dispatched to your location. Stay where you are and keep your phone accessible."
    return send_text_message(to, body)

def send_safe_route(to: str, shelter_name: str, route_url: str) -> dict:
    body = f"📍 Location recorded.\nNearest safe haven: {shelter_name}\n🗺️ Safe Route: {route_url}\n📸 Please send a photo of your surroundings so our AI can assess the severity."
    return send_text_message(to, body)

def send_analysis_result(to: str, visual_findings: str, severity_level: str) -> dict:
    body = f"🤖 Photo analyzed by Emergency AI:\n{visual_findings}\nSeverity: {severity_level}\nFirst responders have been notified."
    return send_text_message(to, body)
