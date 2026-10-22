"""Webhook Meta (Facebook Messenger, Instagram, WhatsApp) + API kely ho an'ny ekipa.

Alefaso: `gunicorn -w 1 --threads 8 -b 127.0.0.1:8000 social_agent.webhook:app`
Ary apetraho ao amin'ny Meta App ny URL `https://<domain>/webhook`.
"""

import hashlib
import hmac
import logging
import os
import threading

from flask import Flask, abort, jsonify, request

from . import channels, db
from .agent import reply

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)
app = Flask(__name__)

VERIFY_TOKEN = os.environ.get("META_VERIFY_TOKEN", "")
APP_SECRET = os.environ.get("META_APP_SECRET", "")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")


@app.get("/health")
def health():
    return "ok"


@app.get("/webhook")
def verify():
    if (
        VERIFY_TOKEN
        and request.args.get("hub.mode") == "subscribe"
        and request.args.get("hub.verify_token") == VERIFY_TOKEN
    ):
        return request.args.get("hub.challenge", "")
    abort(403)


@app.post("/webhook")
def receive():
    signature = request.headers.get("X-Hub-Signature-256", "")
    expected = "sha256=" + hmac.new(APP_SECRET.encode(), request.get_data(), hashlib.sha256).hexdigest()
    if not APP_SECRET or not hmac.compare_digest(signature, expected):
        abort(403)

    payload = request.get_json(silent=True) or {}
    if payload.get("object") == "whatsapp_business_account":
        incoming = _parse_whatsapp(payload)
    else:
        incoming = _parse_messenger(payload)

    for platform, sender_id, text, name, event_id in incoming:
        if event_id and not db.mark_event_processed(event_id):
            continue
        # Mamaly haingana an'i Meta, ny agent mandeha ao ambadika
        threading.Thread(target=_handle, args=(platform, sender_id, text, name, event_id), daemon=True).start()
    return "EVENT_RECEIVED"


def _parse_messenger(payload: dict):
    platform = "instagram" if payload.get("object") == "instagram" else "messenger"
    for entry in payload.get("entry", []):
        for event in entry.get("messaging", []):
            message = event.get("message") or {}
            if message.get("is_echo"):
                continue
            text = message.get("text") or _attachment_note(message.get("attachments"))
            if text:
                yield platform, event["sender"]["id"], text, None, message.get("mid")


def _parse_whatsapp(payload: dict):
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value") or {}
            names = {c.get("wa_id"): (c.get("profile") or {}).get("name") for c in value.get("contacts", [])}
            for message in value.get("messages", []):
                kind = message.get("type")
                if kind == "text":
                    text = message["text"]["body"]
                elif kind == "interactive":
                    inter = message.get("interactive") or {}
                    text = (inter.get("button_reply") or inter.get("list_reply") or {}).get("title")
                elif kind == "button":
                    text = (message.get("button") or {}).get("text")
                else:
                    text = _attachment_note([{"type": kind}])
                if text:
                    yield "whatsapp", message["from"], text, names.get(message["from"]), message.get("id")


def _attachment_note(attachments) -> str | None:
    if not attachments:
        return None
    kinds = ", ".join(a.get("type", "fichier") for a in attachments)
    return f"(Nandefa {kinds} ilay mpanjifa, tsy hitan'ny agent ny ao anatiny.)"


def _handle(platform: str, sender_id: str, text: str, name: str | None, event_id: str | None) -> None:
    if platform == "whatsapp" and event_id:
        try:
            channels.mark_whatsapp_read(event_id)
        except Exception:
            log.warning("Tsy voamarika ho voavaky ny hafatra WhatsApp")
    try:
        answer = reply(platform, sender_id, text, name)
    except Exception:
        log.exception("Tsy nahavita namaly ny agent")
        return
    if answer:
        channels.send_text(platform, sender_id, answer)


# ---------------------------------------------------------------------------
# API ho an'ny ekipa: jerena ny resaka, mamaly tanana, mamerina ny agent.
# Header: `Authorization: Bearer <ADMIN_TOKEN>`


def _require_admin():
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not ADMIN_TOKEN or not hmac.compare_digest(token, ADMIN_TOKEN):
        abort(401)


@app.get("/admin/conversations")
def admin_conversations():
    _require_admin()
    return jsonify(db.list_conversations(only_handoff=request.args.get("handoff") == "1"))


@app.get("/admin/conversations/<platform>/<user_id>")
def admin_transcript(platform: str, user_id: str):
    _require_admin()
    return jsonify(db.get_transcript(platform, user_id))


@app.post("/admin/conversations/<platform>/<user_id>/send")
def admin_send(platform: str, user_id: str):
    """Mpiasa mamaly mivantana; ny agent dia mijanona mandra-pamerina azy."""
    _require_admin()
    text = ((request.get_json(silent=True) or {}).get("text") or "").strip()
    if not text:
        abort(400)
    if not channels.send_text(platform, user_id, text):
        abort(502)
    db.save_message(platform, user_id, "staff", text)
    db.set_needs_human(platform, user_id, "Mpiasa no mamaly")
    return jsonify({"sent": True})


@app.post("/admin/conversations/<platform>/<user_id>/release")
def admin_release(platform: str, user_id: str):
    """Averina amin'ny agent ny resaka."""
    _require_admin()
    db.set_needs_human(platform, user_id, "", value=False)
    return jsonify({"released": True})
