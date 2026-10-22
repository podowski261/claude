"""Hanandramana ny agent ao amin'ny terminal, tsy mila Facebook na WhatsApp.

    python chat_cli.py                          # "demo-user" (manana kaomandy ohatra)
    python chat_cli.py whatsapp 261340000000    # mody WhatsApp, laharana mifanaraka amin'ny mpanjifa ohatra
"""

import sys

from social_agent import db
from social_agent.agent import reply

if __name__ == "__main__":
    platform, user_id = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("cli", "demo-user")
    print("Soraty ny hafatrao (Ctrl+C hivoahana, /reset hamerina ny agent).")
    while True:
        try:
            text = input("\nIanao> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text == "/reset":
            db.set_needs_human(platform, user_id, "", value=False)
            print("(Mamaly ho azy indray ny agent)")
            continue
        if text:
            answer = reply(platform, user_id, text)
            print(f"\nAgent> {answer}" if answer else "\n(Olona ao amin'ny ekipa no mitantana ity resaka ity)")
