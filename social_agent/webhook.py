"""Webhook Meta (Facebook Messenger + Instagram).

Alefaso: `flask --app social_agent.webhook run --port 8000`
Ary apetraho ao amin'ny Meta App ny URL `https://<domain>/webhook`.
"""

import hashlib
import hmac
import logging
import os
import threading

import requests
from flask import Flask, abort, request

from .agent import reply

log = logging.getLogger(__name__)
app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("META_VERIFY_TOKEN", "")
APP_SECRET = os.environ.get("META_APP_SECRET", "")
PAGE_TOKEN = os.environ.get("META_PAGE_ACCESS_TOKEN", "")
GRAPH_URL = f"https://graph.facebook.com/{os.environ.get('META_GRAPH_VERSION', 'v21.0')}/me/messages"
MAX_CHARS = 2000  # fetran'ny Messenger isaky ny hafatra


@app.get("/webhook")
def verify():
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge", "")
    abort(403)


@app.post("/webhook")
def receive():
    signature = request.headers.get("X-Hub-Signature-256", "")
    expected = "sha256=" + hmac.new(APP_SECRET.encode(), request.get_data(), hashlib.sha256).hexdigest()
    if not APP_SECRET or not hmac.compare_digest(signature, expected):
        abort(403)

    payload = request.get_json(silent=True) or {}
    platform = "instagram" if payload.get("object") == "instagram" else "messenger"
    for entry in payload.get("entry", []):
        for event in entry.get("messaging", []):
            message = event.get("message") or {}
            text = message.get("text")
            if not text or message.get("is_echo"):
                continue
            sender_id = event["sender"]["id"]
            # Mamaly haingana an'i Meta (< 20s), ny agent mandeha ao ambadika
            threading.Thread(target=_handle, args=(platform, sender_id, text), daemon=True).start()
    return "EVENT_RECEIVED"


def _handle(platform: str, sender_id: str, text: str) -> None:
    try:
        answer = reply(platform, sender_id, text)
    except Exception:
        log.exception("Tsy nahavita namaly ny agent")
        return
    if answer:
        send_text(sender_id, answer)


def send_text(recipient_id: str, text: str) -> None:
    for start in range(0, len(text), MAX_CHARS):
        resp = requests.post(
            GRAPH_URL,
            params={"access_token": PAGE_TOKEN},
            json={
                "recipient": {"id": recipient_id},
                "messaging_type": "RESPONSE",
                "message": {"text": text[start : start + MAX_CHARS]},
            },
            timeout=15,
        )
        if not resp.ok:
            log.error("Graph API %s: %s", resp.status_code, resp.text)
            return
