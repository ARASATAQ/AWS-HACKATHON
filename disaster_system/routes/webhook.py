from fastapi import APIRouter, Request, Query, HTTPException
import logging, uuid
from datetime import datetime, timezone
from config import get_settings
from services.aws_service import get_aws_service
from services.vision_service import analyze_disaster_image
from services.whatsapp_service import (
    send_text_message, send_interactive_buttons, download_media
)
from services.maps_service import find_nearest_shelter, generate_safe_route_url

router = APIRouter(tags=["WhatsApp Webhook"])
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory session state: phone → last known location
# Fixes the lat=0/lon=0 bug on image messages that arrive after a location pin
# ---------------------------------------------------------------------------
_location_cache: dict[str, dict] = {}   # { "+919…": {"lat": …, "lon": …} }


@router.get("/webhook")
async def verify_webhook(
    mode: str = Query(None, alias="hub.mode"),
    verify_token: str = Query(None, alias="hub.verify_token"),
    challenge: int = Query(None, alias="hub.challenge"),
):
    settings = get_settings()
    if mode == "subscribe" and verify_token == settings.meta_verify_token:
        return challenge
    raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/webhook")
async def process_webhook(request: Request):
    payload = await request.json()
    if isinstance(payload, str):
        import json
        payload = json.loads(payload)
    aws = get_aws_service()

    try:
        entries = payload.get("entry", []) if isinstance(payload, dict) else []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for change in entry.get("changes", []):
                if not isinstance(change, dict):
                    continue
                value = change.get("value", {})
                if not isinstance(value, dict):
                    continue
                for message in value.get("messages", []):
                    if not isinstance(message, dict):
                        continue

                    phone    = message.get("from")
                    msg_type = message.get("type")

                    if not phone or not msg_type:
                        continue

                    # ----------------------------------------------------------
                    # Text messages
                    # ----------------------------------------------------------
                    if msg_type == "text":
                        text = message.get("text", {}).get("body", "").strip().lower()

                        if text == "safe":
                            aws.update_citizen_status(phone, "SAFE")
                            send_text_message(
                                phone,
                                "✅ Glad you are safe! Follow local authorities for updates. Stay alert for further advisories.",
                            )

                        elif text == "help":
                            aws.update_citizen_status(phone, "IN_DANGER")
                            send_text_message(
                                phone,
                                "🆘 Emergency teams have been alerted! Please share your WhatsApp Location Pin immediately so we can locate you.",
                            )
                            send_interactive_buttons(
                                phone,
                                "Choose an action:",
                                [{"id": "btn_share_location", "title": "📍 Share Location"}],
                            )

                        else:
                            send_text_message(
                                phone,
                                "Welcome to the NOVA-S Emergency Response System.\n"
                                "Reply 'HELP' if you are in danger.\n"
                                "Reply 'SAFE' if you are secure.\n"
                                "Send your 📍 Location pin for emergency assistance.",
                            )

                    # ----------------------------------------------------------
                    # Location messages — cache the coordinates for this phone
                    # ----------------------------------------------------------
                    elif msg_type == "location":
                        lat = message.get("location", {}).get("latitude")
                        lon = message.get("location", {}).get("longitude")

                        if lat is not None and lon is not None:
                            # Store in session cache
                            _location_cache[phone] = {"lat": lat, "lon": lon}

                        aws.save_citizen(
                            phone=phone, name="Citizen",
                            lat=lat or 0.0, lon=lon or 0.0,
                            status="IN_DANGER",
                        )

                        incident_id = str(uuid.uuid4())
                        aws.save_incident(
                            incident_id=incident_id, phone=phone,
                            lat=lat or 0.0, lon=lon or 0.0,
                            hazard_type="UNKNOWN", severity_score=0,
                            severity_level="PENDING",
                            visual_findings="Awaiting photo",
                            image_url="", status="PENDING",
                            recommended_dispatch="", immediate_life_threat=False,
                        )

                        shelter     = find_nearest_shelter(lat or 0.0, lon or 0.0)
                        shelter_msg = ""
                        if shelter:
                            route_url   = generate_safe_route_url(lat, lon, shelter.get("lat"), shelter.get("lon"))
                            shelter_msg = f"\nNearest shelter: {shelter.get('name')}\n🗺️ Safe Route: {route_url}"

                        send_text_message(
                            phone,
                            f"📍 Location received.{shelter_msg}\n\n"
                            "Please send a photo of the situation so our AI can assess the severity.",
                        )

                    # ----------------------------------------------------------
                    # Image messages — use cached location if available
                    # ----------------------------------------------------------
                    elif msg_type == "image":
                        media_id = message.get("image", {}).get("id")

                        # Resolve coordinates from cache or fallback to 0,0
                        cached_loc = _location_cache.get(phone, {})
                        img_lat    = cached_loc.get("lat", 0.0)
                        img_lon    = cached_loc.get("lon", 0.0)

                        image_bytes = download_media(media_id) if media_id else None
                        incident_id = str(uuid.uuid4())
                        timestamp   = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

                        if image_bytes:
                            image_url = aws.upload_image(f"{phone}_{timestamp}.jpg", image_bytes)
                            analysis  = analyze_disaster_image(image_bytes)
                        else:
                            image_url = ""
                            analysis  = {
                                "detected_hazard":    "UNKNOWN",
                                "severity_level":     "CRITICAL",
                                "severity_score":     5,
                                "visual_findings":    "Mock analysis: Severe structural damage and flooding observed",
                                "recommended_dispatch": "AIRLIFT",
                                "immediate_life_threat": True,
                            }

                        aws.save_incident(
                            incident_id=incident_id,
                            phone=phone,
                            lat=img_lat,
                            lon=img_lon,
                            hazard_type=analysis.get("detected_hazard", "UNKNOWN"),
                            severity_score=analysis.get("severity_score", 0),
                            severity_level=analysis.get("severity_level", "PENDING"),
                            visual_findings=analysis.get("visual_findings", ""),
                            image_url=image_url,
                            status="PENDING",
                            recommended_dispatch=analysis.get("recommended_dispatch", ""),
                            immediate_life_threat=analysis.get("severity_level") == "CRITICAL",
                        )

                        if analysis.get("severity_level") == "CRITICAL":
                            aws.broadcast_emergency(
                                subject="CRITICAL: Emergency Photo Triage",
                                message=(
                                    f"Critical incident from {phone}. "
                                    f"{analysis.get('visual_findings', '')}"
                                ),
                            )

                        send_text_message(
                            phone,
                            f"🤖 Analysis Complete.\n"
                            f"Hazard: {analysis.get('detected_hazard', 'UNKNOWN')}\n"
                            f"Severity: {analysis.get('severity_level')}\n"
                            f"{analysis.get('visual_findings')}\n\n"
                            "First responders have been notified.",
                        )

    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)

    return {"status": "ok"}
