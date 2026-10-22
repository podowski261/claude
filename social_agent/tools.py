"""Ireo tools azon'ny agent ampiasaina.

Ny tools mikasika ny mpanjifa (kaomandy, sns.) dia voafetra ho an'ilay olona miresaka ihany:
ny `platform` sy `user_id` dia avy amin'ny webhook fa tsy avy amin'ny modèle.
"""

import json
import os
import sqlite3

from anthropic import beta_tool

from . import db

MAX_ROWS = 50

# SQL mamoaka ny kaomandin'ilay mpanjifa miresaka. Ampifanaraho amin'ny base-nareo ao amin'ny .env.
# Paramètres azo ampiasaina: :platform, :user_id, :phone_intl, :phone_plus, :phone_local
DEFAULT_ORDERS_SQL = (
    "SELECT o.id, o.status, o.total, o.created_at, o.delivery_address, "
    "group_concat(oi.quantity || ' x ' || p.name, ', ') AS items "
    "FROM customers c JOIN orders o ON o.customer_id = c.id "
    "LEFT JOIN order_items oi ON oi.order_id = o.id "
    "LEFT JOIN products p ON p.id = oi.product_id "
    "WHERE (c.platform = :platform AND c.platform_user_id = :user_id) "
    "   OR (:platform = 'whatsapp' AND c.phone IN (:phone_intl, :phone_plus, :phone_local)) "
    "GROUP BY o.id ORDER BY o.created_at DESC"
)
ORDERS_SQL = os.environ.get("CUSTOMER_ORDERS_SQL", DEFAULT_ORDERS_SQL)


def _rows_to_json(rows: list[sqlite3.Row]) -> str:
    data = [dict(r) for r in rows[:MAX_ROWS]]
    out = {"rows": data, "count": len(data)}
    if len(rows) > MAX_ROWS:
        out["truncated"] = True
    return json.dumps(out, ensure_ascii=False, default=str)


def build_tools(platform: str, user_id: str) -> list:
    """Mamorona ny tools mifatotra amin'ilay mpanjifa miresaka."""

    @beta_tool
    def query_database(query: str) -> str:
        """Manatanteraka fangatahana SQL SELECT (SQLite) amin'ny base an'ny fivarotana:
        vokatra, stock, vidiny, sokajy, FAQ, sns. Jereo ao amin'ny prompt ny schéma.

        Tsy azo atao ny manova data, ary ireo tables voatanisa ao amin'ny schéma ihany no azo vakiana.
        Ampiasao `LIKE '%...%'` rehefa mitady anarana, satria mety tsy mitovy tsara ny soratra.

        Args:
            query: Fangatahana SELECT iray monja.
        """
        try:
            with db.readonly_connection(restrict_tables=True) as conn:
                return _rows_to_json(conn.execute(query).fetchmany(MAX_ROWS + 1))
        except sqlite3.Error as e:
            return f"Error: {e}. Schéma azo vakiana:\n{db.describe_schema()}"

    @beta_tool
    def get_my_orders() -> str:
        """Mamoaka ny kaomandin'ilay mpanjifa miresaka izao (statut, total, entana)."""
        params = {"platform": platform, "user_id": user_id, **db.phone_variants(user_id)}
        try:
            with db.readonly_connection() as conn:
                rows = conn.execute(ORDERS_SQL, params).fetchall()
        except sqlite3.Error as e:
            return f"Error: tsy azo jerena ny kaomandy ({e})."
        if not rows:
            return json.dumps({"rows": [], "note": "Tsy misy kaomandy mifandray amin'ity kaonty/laharana ity."})
        return _rows_to_json(rows)

    @beta_tool
    def escalate_to_human(reason: str) -> str:
        """Mampandre olona ao amin'ny ekipa mba handray ny resaka (fitarainana, famerenam-bola,
        kaomandy vonona hamarinina, fangatahana tsy hain'ny agent, na raha mangataka olona ilay mpanjifa).

        Args:
            reason: Fehintenin'ny olana na ny kaomandy ho an'ny ekipa (vokatra, isa, adiresy, laharana...).
        """
        db.set_needs_human(platform, user_id, reason)
        return "Voaray. Hiditra amin'ny resaka ny ekipa; tsy hamaly ho azy intsony ny agent."

    return [query_database, get_my_orders, escalate_to_human]
