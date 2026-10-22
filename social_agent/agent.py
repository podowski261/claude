"""Ny agent: mandray hafatra iray avy amin'ny mpanjifa, mamerina valiny."""

import logging
import os

import anthropic

from . import db
from .tools import build_tools

log = logging.getLogger(__name__)

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
BUSINESS_NAME = os.environ.get("BUSINESS_NAME", "ny fivarotanay")

SYSTEM_PROMPT = f"""Ianao no mpanampy (service client) an'i {BUSINESS_NAME} amin'ny tambajotra sosialy
(Facebook Messenger, Instagram, WhatsApp).

Fomba fiasa:
- Valio amin'ny fiteny ampiasain'ny mpanjifa (malagasy, frantsay, anglisy...).
- Hafatra fohy sy mazava mifanaraka amin'ny chat: andalana vitsivitsy, tsy misy Markdown na lohateny.
- Aza mamorona vidiny, stock, na statut kaomandy: jereo amin'ny tools foana ary ampiasao ny valiny azo.
- Raha tsy hita ny vokatra, lazao izany ary manolora safidy mitovitovy raha misy.
- Ny kaomandin'ilay olona miresaka ihany no azonao jerena (`get_my_orders`). Aza manome
  mombamomba olon-kafa mihitsy.
- Ampiasao `escalate_to_human` raha misy fitarainana, fangatahana famerenam-bola, olana
  momba ny fandoavam-bola, na raha mangataka olona ilay mpanjifa. Lazao azy avy eo fa
  hiresaka aminy tsy ho ela ny ekipa.
- Tsy afaka mandray kaomandy na mandray vola ianao: tarihina any amin'ny fomba ao amin'ny FAQ.
"""

FALLBACK_REPLY = "Miala tsiny, misy olana kely ara-teknika. Hamaly anao tsy ho ela ny ekipanay."

_client = anthropic.Anthropic()


def reply(platform: str, user_id: str, text: str) -> str | None:
    """Mamerina ny valiny halefa, na `None` raha efa olona no mitantana ilay resaka."""
    db.save_message(platform, user_id, "user", text)
    if db.needs_human(platform, user_id):
        return None

    messages = db.load_history(platform, user_id)
    runner = _client.beta.messages.tool_runner(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        tools=build_tools(platform, user_id),
        messages=messages,
        output_config={"effort": "medium"},
        # Raha mandà ny modèle noho ny politika fiarovana, alefa any amin'ny modèle hafa ilay fangatahana
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )

    try:
        final = None
        for message in runner:
            final = message
    except anthropic.RateLimitError:
        log.warning("Rate limit tamin'ny Claude API")
        return FALLBACK_REPLY
    except anthropic.APIStatusError as e:
        log.error("Claude API error %s: %s", e.status_code, e.message)
        return FALLBACK_REPLY
    except anthropic.APIConnectionError:
        log.error("Tsy tafiditra tamin'ny Claude API")
        return FALLBACK_REPLY

    if final is None or final.stop_reason == "refusal":
        db.set_needs_human(platform, user_id, "Tsy namaly ny agent (refusal)")
        return FALLBACK_REPLY

    answer = "".join(b.text for b in final.content if b.type == "text").strip()
    if not answer:
        return None
    db.save_message(platform, user_id, "assistant", answer)
    return answer
