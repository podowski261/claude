"""Hanandramana ny agent ao amin'ny terminal, tsy mila Facebook.

    python chat_cli.py            # miresaka amin'ny maha "demo-user" (manana kaomandy ohatra)
    python chat_cli.py olona-hafa
"""

import sys

from social_agent import db
from social_agent.agent import reply

if __name__ == "__main__":
    user_id = sys.argv[1] if len(sys.argv) > 1 else "demo-user"
    print("Soraty ny hafatrao (Ctrl+C hivoahana, /reset hamerina ny agent).")
    while True:
        try:
            text = input("\nIanao> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text == "/reset":
            db.set_needs_human("cli", user_id, "", value=False)
            print("(Mamaly ho azy indray ny agent)")
            continue
        if text:
            answer = reply("cli", user_id, text)
            print(f"\nAgent> {answer}" if answer else "\n(Olona ao amin'ny ekipa no mitantana ity resaka ity)")
