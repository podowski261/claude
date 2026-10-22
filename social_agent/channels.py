"""Fandefasana hafatra amin'ny Messenger / Instagram / WhatsApp (Meta Graph API)."""

import logging
import os

import requests

log = logging.getLogger(__name__)

GRAPH = f"https://graph.facebook.com/{os.environ.get('META_GRAPH_VERSION', 'v21.0')}"
PAGE_TOKEN = os.environ.get("META_PAGE_ACCESS_TOKEN", "")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")

# Fetran'ny halavan'ny hafatra iray isaky ny sehatra
MAX_CHARS = {"messenger": 2000, "instagram": 1000, "whatsapp": 4096}


def _chunks(text: str, size: int) -> list[str]:
    """Manapaka ny lahatsoratra lava, raha azo atao eo amin'ny fiafaran'andalana."""
    parts = []
    while len(text) > size:
        cut = text.rfind("\n", 0, size)
        cut = cut if cut > size // 2 else size
        parts.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    if text:
        parts.append(text)
    return parts


def send_text(platform: str, recipient_id: str, text: str) -> bool:
    for part in _chunks(text, MAX_CHARS.get(platform, 1000)):
        if platform == "whatsapp":
            resp = requests.post(
                f"{GRAPH}/{WHATSAPP_PHONE_NUMBER_ID}/messages",
                headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": recipient_id,
                    "type": "text",
                    "text": {"body": part},
                },
                timeout=15,
            )
        elif platform in ("messenger", "instagram"):
            resp = requests.post(
                f"{GRAPH}/me/messages",
                params={"access_token": PAGE_TOKEN},
                json={
                    "recipient": {"id": recipient_id},
                    "messaging_type": "RESPONSE",
                    "message": {"text": part},
                },
                timeout=15,
            )
        else:
            log.info("[%s → %s] %s", platform, recipient_id, part)
            continue
        if not resp.ok:
            log.error("Graph API %s (%s): %s", resp.status_code, platform, resp.text)
            return False
    return True


def mark_whatsapp_read(message_id: str) -> None:
    """Asehoy ho voavaky (✓✓ manga) ny hafatra WhatsApp."""
    requests.post(
        f"{GRAPH}/{WHATSAPP_PHONE_NUMBER_ID}/messages",
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"},
        json={"messaging_product": "whatsapp", "status": "read", "message_id": message_id},
        timeout=10,
    )
