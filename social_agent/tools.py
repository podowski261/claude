"""Ireo tools azon'ny agent ampiasaina.

Ny tools mikasika ny mpanjifa (kaomandy, sns.) dia voafetra ho an'ilay olona miresaka ihany:
ny `platform` sy `user_id` dia avy amin'ny webhook fa tsy avy amin'ny modèle.
"""

import json
import sqlite3

from anthropic import beta_tool

from . import db

MAX_ROWS = 50


def _rows_to_json(rows: list[sqlite3.Row]) -> str:
    data = [dict(r) for r in rows[:MAX_ROWS]]
    out = {"rows": data, "count": len(data)}
    if len(rows) > MAX_ROWS:
        out["truncated"] = True
    return json.dumps(out, ensure_ascii=False, default=str)


def build_tools(platform: str, user_id: str) -> list:
    """Mamorona ny tools mifatotra amin'ilay mpanjifa miresaka."""

    @beta_tool
    def search_products(query: str, max_price: float | None = None) -> str:
        """Mitady vokatra amin'ny anarana na famaritana (stock sy vidiny tafiditra).

        Args:
            query: Teny hotadiavina, ohatra "kiraro", "t-shirt mena".
            max_price: Vidiny ambony indrindra (Ariary), tsy voatery.
        """
        sql = (
            "SELECT p.id, p.name, p.description, p.price, p.stock, c.name AS category "
            "FROM products p LEFT JOIN categories c ON c.id = p.category_id "
            "WHERE (p.name LIKE ? OR p.description LIKE ? OR c.name LIKE ?)"
        )
        like = f"%{query}%"
        params: list = [like, like, like]
        if max_price is not None:
            sql += " AND p.price <= ?"
            params.append(max_price)
        with db.readonly_connection() as conn:
            return _rows_to_json(conn.execute(sql + " ORDER BY p.name", params).fetchall())

    @beta_tool
    def search_faq(query: str) -> str:
        """Mitady valiny ao amin'ny FAQ (fandoavam-bola, fandefasana, fiverenana entana, ora fisokafana...).

        Args:
            query: Teny fanalahidy hotadiavina.
        """
        like = f"%{query}%"
        with db.readonly_connection() as conn:
            rows = conn.execute(
                "SELECT question, answer FROM faq WHERE question LIKE ? OR answer LIKE ? OR tags LIKE ?",
                (like, like, like),
            ).fetchall()
        return _rows_to_json(rows)

    @beta_tool
    def get_my_orders() -> str:
        """Mamoaka ny kaomandin'ilay mpanjifa miresaka izao (statut, total, entana)."""
        with db.readonly_connection() as conn:
            rows = conn.execute(
                "SELECT o.id, o.status, o.total, o.created_at, o.delivery_address, "
                "group_concat(oi.quantity || ' x ' || p.name, ', ') AS items "
                "FROM customers c JOIN orders o ON o.customer_id = c.id "
                "LEFT JOIN order_items oi ON oi.order_id = o.id "
                "LEFT JOIN products p ON p.id = oi.product_id "
                "WHERE c.platform = ? AND c.platform_user_id = ? "
                "GROUP BY o.id ORDER BY o.created_at DESC",
                (platform, user_id),
            ).fetchall()
        if not rows:
            return json.dumps({"rows": [], "note": "Tsy misy kaomandy mifandray amin'ity kaonty ity."})
        return _rows_to_json(rows)

    @beta_tool
    def run_readonly_sql(query: str) -> str:
        """Manatanteraka fangatahana SQL SELECT (SQLite) amin'ny tables ankapobeny ihany.

        Ampiasao rehefa tsy ampy ireo tools hafa. Tsy azo atao ny manova data, ary
        tsy azo vakiana ny tables misy mombamomba ny mpanjifa.

        Args:
            query: Fangatahana SELECT iray monja.
        """
        try:
            with db.readonly_connection(restrict_tables=True) as conn:
                return _rows_to_json(conn.execute(query).fetchmany(MAX_ROWS + 1))
        except sqlite3.Error as e:
            return f"Error: {e}. Schéma azo vakiana:\n{db.describe_schema()}"

    @beta_tool
    def escalate_to_human(reason: str) -> str:
        """Mampandre olona ao amin'ny ekipa mba handray ny resaka (fitarainana, famerenam-bola,
        fangatahana tsy hain'ny agent, na raha mangataka olona ilay mpanjifa).

        Args:
            reason: Fehintenin'ny olana ho an'ny ekipa.
        """
        db.set_needs_human(platform, user_id, reason)
        return "Voaray. Hiditra amin'ny resaka ny ekipa; tsy hamaly ho azy intsony ny agent."

    return [search_products, search_faq, get_my_orders, run_readonly_sql, escalate_to_human]
