# Agent service client: Facebook, Instagram, WhatsApp + base SQLite

Agent mampiasa ny Claude API mamaly ny hafatry ny mpanjifa ao amin'ny pejy Facebook (Messenger),
Instagram ary WhatsApp. Mijery ny base `.sqlite` an'ny logiciel Infinity StockFlow izy
(vokatra misy, stock, vidiny, kaomandy) mba hanomezana valiny marina, ary mitazona ny resaka feno.

## Ny fomba fiasany

```
Mpanjifa (Messenger / Instagram / WhatsApp)
        │
        ▼
Meta (webhook)  ──►  https://bot.infinity-stockflow.store/webhook   (cloudflared tunnel)
                              │
                              ▼  server-nareo (izay misy ny base)
                     social_agent (gunicorn :8000)
                       ├─ Claude API  (mamaly, mifidy tools)
                       ├─ DB_PATH          → base an'ny logiciel (vakiana fotsiny)
                       └─ HISTORY_DB_PATH  → tantaran'ny resaka
```

Rakitra SQLite ny base, ka **tsy maintsy mandeha ao amin'ilay server misy ny base ihany ny agent**.
Ny cloudflared tunnel efa misy no hampidirana ny hafatra avy amin'i Meta ao amin'ny agent
(sous-domaine vaovao `bot.infinity-stockflow.store`). Tsy mila manokatra port ianareo.

| Rakitra | Anjara asa |
|---|---|
| `social_agent/agent.py` | Prompt sy fihodinan'ny agent, tantaran'ny resaka |
| `social_agent/tools.py` | Tools: `query_database`, `get_my_orders`, `escalate_to_human` |
| `social_agent/db.py` | Base vakiana fotsiny + base tantaran'ny resaka |
| `social_agent/channels.py` | Fandefasana hafatra amin'ny Messenger / Instagram / WhatsApp |
| `social_agent/webhook.py` | Webhook Meta + API ho an'ny ekipa (`/admin/...`) |
| `business_info.md` | Fampahalalana momba ny fivarotana (fandoavam-bola, fandefasana...) |
| `deploy/` | Service systemd sy config cloudflared |
| `seed_db.py`, `chat_cli.py` | Base ohatra sy fanandramana ao amin'ny terminal |

## Ampifanaraho amin'ny base-nareo

1. **`SQL_ALLOWED_TABLES`**: ireo tables azon'ny agent vakiana (vokatra, sokajy, stock...).
   Mamaky ny schéma-n'ireo tables ireo ho azy ny agent, ka tsy mila manova code ianareo.
   **Aza ampidirina** ny tables misy mombamomba ny mpanjifa (anarana, finday...).
2. **`CUSTOMER_ORDERS_SQL`** (tsy voatery): SQL mamoaka ny kaomandin'ilay olona miresaka.
   Ho an'ny WhatsApp dia azo ampitahaina amin'ny laharana finday:
   `:phone_local` (0341234567), `:phone_plus` (+261341234567), `:phone_intl` (261341234567).
3. **`business_info.md`**: soraty ao ny fandoavam-bola, ny fandefasana, ny ora fisokafana...

## Fametrahana ao amin'ny server

```bash
sudo mkdir -p /opt/social-agent && sudo chown $USER /opt/social-agent
git clone -b claude/jolly-rubin-9lhzo7 https://github.com/podowski261/claude /opt/social-agent
cd /opt/social-agent
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # fenoy (DB_PATH, ANTHROPIC_API_KEY, token Meta, ADMIN_TOKEN)

# Andrana ao amin'ny terminal aloha:
set -a; . ./.env; set +a
.venv/bin/python chat_cli.py

# Service:
sudo cp deploy/social-agent.service /etc/systemd/system/
sudo systemctl enable --now social-agent
curl http://localhost:8000/health
```

Avy eo, ampio ao amin'ny config cloudflared ny règle ao amin'ny `deploy/cloudflared-ingress.yml`
(`bot.infinity-stockflow.store → http://localhost:8000`), ary avereno alefa ny cloudflared.
Tokony hamaly `ok` ny `https://bot.infinity-stockflow.store/health`.

Ny user ao amin'ny service (`www-data`) dia tsy maintsy afaka mamaky ny `DB_PATH` sy manoratra ao amin'ny `HISTORY_DB_PATH`.
Raha WAL no ampiasain'ny base an'ny logiciel, tsy maintsy afaka mamaky koa ny rakitra `-wal` sy `-shm` izy.

## Fampifandraisana amin'ny Meta

Ao amin'ny [Meta for Developers](https://developers.facebook.com/), App iray (karazana *Business*):

**Facebook Page / Instagram**
1. Ampio ny produit *Messenger* (sy *Instagram* raha ilaina), ampifandraiso ny pejy.
2. Mamorona *Page Access Token* → `META_PAGE_ACCESS_TOKEN`.
3. Webhooks: Callback URL `https://bot.infinity-stockflow.store/webhook`, Verify token = `META_VERIFY_TOKEN`,
   misoratra amin'ny `messages`.

**WhatsApp**
1. Ampio ny produit *WhatsApp*, ampifandraiso ny laharana WhatsApp Business.
2. Raiso ny *Phone number ID* → `WHATSAPP_PHONE_NUMBER_ID`.
3. Mamorona *System User* ao amin'ny Business Manager misy token maharitra
   (`whatsapp_business_messaging`) → `WHATSAPP_ACCESS_TOKEN`.
4. Webhooks (WhatsApp Business Account): URL sy Verify token mitovy amin'ny etsy ambony, misoratra amin'ny `messages`.

`META_APP_SECRET` = *App Secret* (Settings → Basic): amin'ity no hamarinina fa avy amin'i Meta tokoa ny hafatra.

> Raha ampiasaina amin'ny WhatsApp Cloud API ny laharana dia tsy azo ampiasaina amin'ny application
> WhatsApp Business finday intsony izy, raha tsy mampiasa ny *coexistence* an'i Meta ianareo.
> Ny API `/admin/...` etsy ambany no ahafahan'ny ekipa mamaly tanana.
> Rehefa mihoatra ny 24 ora tsy nisy hafatra avy amin'ny mpanjifa dia *template* voamarina ihany no azo alefa
> amin'ny WhatsApp. Ity agent ity tsy mamaly afa-tsy hafatra vao avy amin'ny mpanjifa, ka tsy voakasik'izany.

## Ny ekipa sy ny resaka

- Rehefa misy fitarainana, kaomandy vonona hamarinina, na mangataka olona ny mpanjifa dia mampiasa
  `escalate_to_human` ny agent, ary **mijanona tsy mamaly ho azy** amin'io resaka io.
- API ho an'ny ekipa (header `Authorization: Bearer <ADMIN_TOKEN>`):

```bash
B=https://bot.infinity-stockflow.store; H="Authorization: Bearer $ADMIN_TOKEN"
curl -H "$H" "$B/admin/conversations?handoff=1"                     # resaka miandry olona
curl -H "$H" "$B/admin/conversations/whatsapp/261341234567"         # resaka feno
curl -H "$H" -X POST -H 'Content-Type: application/json' \
     -d '{"text":"Salama, voaray ny kaomandinao"}' \
     "$B/admin/conversations/whatsapp/261341234567/send"            # mamaly tanana
curl -H "$H" -X POST "$B/admin/conversations/whatsapp/261341234567/release"  # averina amin'ny agent
```

## Fiarovana

- Sokafana amin'ny `mode=ro`, `PRAGMA query_only` ary authorizer ny base an'ny logiciel, ka tsy afaka manova data ny agent.
- Ireo tables ao amin'ny `SQL_ALLOWED_TABLES` ihany no hitan'ny `query_database`.
- Ny kaomandin'ilay olona miresaka ihany no hitan'ny `get_my_orders`, ary avy amin'ny webhook no ahafantarana azy fa tsy avy amin'ny modèle.
- Hamarinina amin'ny `X-Hub-Signature-256` ny hafatra rehetra avy amin'i Meta. Ny hafatra efa voaray dia tsy karakaraina indroa.
