# Agent service client (SQLite + tambajotra sosialy)

Agent mampiasa ny Claude API mamaly ny hafatry ny mpanjifa ao amin'ny Facebook Messenger sy
Instagram, ary mijery ny base `.sqlite` (vokatra, stock, FAQ, kaomandy) mba hanomezana valiny marina.

## Fandrafetana

| Rakitra | Anjara asa |
|---|---|
| `social_agent/agent.py` | Prompt sy fihodinan'ny agent (`tool_runner`), tantaran'ny resaka |
| `social_agent/tools.py` | Tools: `search_products`, `search_faq`, `get_my_orders`, `run_readonly_sql`, `escalate_to_human` |
| `social_agent/db.py` | Connexion SQLite vakiana fotsiny + tantaran'ny resaka |
| `social_agent/webhook.py` | Webhook Meta (Messenger / Instagram) |
| `seed_db.py` | Mamorona base ohatra `shop.sqlite` |
| `chat_cli.py` | Manandrana ao amin'ny terminal |

## Fiarovana

- Ny base dia sokafana amin'ny `mode=ro` + `PRAGMA query_only` + authorizer: tsy afaka manova data ny agent.
- `run_readonly_sql` dia tsy mahavaky afa-tsy ny tables ao amin'ny `SQL_ALLOWED_TABLES`.
- `get_my_orders` dia mamoaka ny kaomandin'ilay olona miresaka ihany (ny ID avy amin'ny webhook, fa tsy avy amin'ny modèle).
- Ny webhook dia manamarina ny sonia `X-Hub-Signature-256`.
- Rehefa antsoina ny `escalate_to_human`, tsy mamaly ho azy intsony ny agent amin'io resaka io
  (`conversations.needs_human = 1`); avereno ho `0` rehefa vita ny ekipa.

## Fampiasana

```bash
pip install -r requirements.txt
cp .env.example .env    # fenoy ny ANTHROPIC_API_KEY sy ny token Meta
set -a; . ./.env; set +a

python seed_db.py       # base ohatra (na apetraho ao amin'ny DB_PATH ny base-nao)
python chat_cli.py      # andramo: "Misy kiraro ve?", "Aiza ny kaomandiko?"
```

Webhook:

```bash
flask --app social_agent.webhook run --port 8000
```

Ao amin'ny Meta for Developers: Webhooks → Callback URL `https://<domain>/webhook`, Verify token = `META_VERIFY_TOKEN`,
misoratra anarana amin'ny `messages` (Page sy Instagram).

## Base efa misy anao

Raha tsy mitovy amin'ny `seed_db.py` ny tables-nao, ovay ny SQL ao amin'ny `social_agent/tools.py`
(`search_products`, `search_faq`, `get_my_orders`) ary ny `SQL_ALLOWED_TABLES`.
Ny tables `conversations` sy `chat_messages` dia foronina ho azy ao amin'ilay base ihany.
