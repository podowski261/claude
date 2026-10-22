"""Ny agent: mandray hafatra iray avy amin'ny mpanjifa, mamerina valiny."""

import functools
import logging
import os
import threading
from collections import defaultdict

import anthropic

from . import db
from .tools import build_tools

log = logging.getLogger(__name__)

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
BUSINESS_NAME = os.environ.get("BUSINESS_NAME", "ny fivarotanay")
BUSINESS_INFO_FILE = os.environ.get("BUSINESS_INFO_FILE", "business_info.md")

PROMPT_TEMPLATE = """Ianao no mpanampy (service client) an'i {business} amin'ny tambajotra sosialy
(Facebook Messenger, Instagram, WhatsApp).

Fomba fiasa:
- Valio amin'ny fiteny ampiasain'ny mpanjifa (malagasy, frantsay, anglisy...).
- Hafatra fohy sy mazava mifanaraka amin'ny chat: andalana vitsivitsy, tsy misy Markdown na lohateny.
- Aza mamorona vidiny, stock, na statut kaomandy: jereo amin'ny `query_database` foana ary
  ampiasao ny valiny azo. Raha 0 ny stock dia lazao fa tsy misy amin'izao ary manolora safidy hafa.
- Ny kaomandin'ilay olona miresaka ihany no azonao jerena (`get_my_orders`). Aza manome
  mombamomba olon-kafa mihitsy.
- Raha te hanao kaomandy ilay mpanjifa: angony ny vokatra, ny isa, ny adiresy ary ny laharana
  finday, avereno amboarina aminy, dia ampiasao `escalate_to_human` miaraka amin'ireo antsipiriany
  ireo mba hamarinin'ny ekipa. Tsy afaka mandray vola na manamarina kaomandy irery ianao.
- Ampiasao koa `escalate_to_human` raha misy fitarainana, famerenam-bola, olana momba ny
  fandoavam-bola, na raha mangataka olona ilay mpanjifa.
- Ny hafatra manomboka amin'ny "[Mpiasa]" dia nosoratan'ny mpiasa: tohizo ny resaka mifanaraka aminy.

Schéma an'ny base (SQLite):
{schema}

Fampahalalana momba ny fivarotana:
{info}
"""

FALLBACK_REPLY = "Miala tsiny, misy olana kely ara-teknika. Hamaly anao tsy ho ela ny ekipanay."

_client = anthropic.Anthropic()
# Hafatra iray isaky ny mpanjifa no karakaraina indray mandeha, mba tsy hifanindry ny valiny
_user_locks: defaultdict[tuple[str, str], threading.Lock] = defaultdict(threading.Lock)


@functools.cache
def system_prompt() -> str:
    try:
        with open(BUSINESS_INFO_FILE, encoding="utf-8") as f:
            info = f.read().strip()
    except FileNotFoundError:
        info = "(tsy misy)"
    return PROMPT_TEMPLATE.format(business=BUSINESS_NAME, schema=db.describe_schema(), info=info)


def reply(platform: str, user_id: str, text: str, display_name: str | None = None) -> str | None:
    """Mamerina ny valiny halefa, na `None` raha efa olona no mitantana ilay resaka."""
    with _user_locks[(platform, user_id)]:
        db.save_message(platform, user_id, "user", text, display_name)
        if db.needs_human(platform, user_id):
            return None
        return _run_agent(platform, user_id)


def _run_agent(platform: str, user_id: str) -> str | None:
    runner = _client.beta.messages.tool_runner(
        model=MODEL,
        max_tokens=16000,
        system=[{"type": "text", "text": system_prompt(), "cache_control": {"type": "ephemeral"}}],
        tools=build_tools(platform, user_id),
        messages=db.load_history(platform, user_id),
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
