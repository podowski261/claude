"""Mamorona base SQLite ohatra (`shop.sqlite`) hanandramana ny agent.

Raha efa manana base ianao, aza ampiasaina ity: ampifanaraho fotsiny ny anaran'ny
tables/colonnes ao amin'ny `social_agent/tools.py`.
"""

import os
import sqlite3

DB_PATH = os.environ.get("DB_PATH", "shop.sqlite")

SCHEMA = """
CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE products (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT,
    price REAL NOT NULL, stock INTEGER NOT NULL DEFAULT 0,
    category_id INTEGER REFERENCES categories(id)
);
CREATE TABLE faq (id INTEGER PRIMARY KEY, question TEXT NOT NULL, answer TEXT NOT NULL, tags TEXT);
CREATE TABLE shipping_zones (id INTEGER PRIMARY KEY, zone TEXT NOT NULL, price REAL NOT NULL, delay_days TEXT);
CREATE TABLE customers (
    id INTEGER PRIMARY KEY, name TEXT, phone TEXT,
    platform TEXT NOT NULL, platform_user_id TEXT NOT NULL,
    UNIQUE (platform, platform_user_id)
);
CREATE TABLE orders (
    id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id),
    status TEXT NOT NULL, total REAL NOT NULL, delivery_address TEXT, created_at TEXT NOT NULL
);
CREATE TABLE order_items (
    order_id INTEGER NOT NULL REFERENCES orders(id), product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL
);
"""

DATA = """
INSERT INTO categories VALUES (1, 'Akanjo'), (2, 'Kiraro'), (3, 'Kojakoja');
INSERT INTO products VALUES
 (1, 'T-shirt landy fotsy', 'T-shirt 100% landy, habe S-XL', 25000, 40, 1),
 (2, 'Jean bleu', 'Pataloha jean slim, habe 28-36', 65000, 12, 1),
 (3, 'Kiraro baskety mainty', 'Baskety maivana, habe 38-44', 89000, 0, 2),
 (4, 'Sandaly hoditra', 'Sandaly hoditra vita gasy', 45000, 8, 2),
 (5, 'Kitapo lamba', 'Kitapo rafia sy lamba, vita tanana', 30000, 20, 3);
INSERT INTO faq (question, answer, tags) VALUES
 ('Ahoana no fandoavam-bola?', 'MVola, Orange Money, Airtel Money, na vola rehefa tonga ny entana (Antananarivo ihany).', 'paiement vola mvola'),
 ('Firy andro ny fandefasana?', 'Antananarivo: 24-48 ora. Faritany: 3-5 andro amin''ny alalan''ny kaoperativa.', 'livraison fandefasana'),
 ('Azo averina ve ny entana?', 'Eny, ao anatin''ny 7 andro raha mbola vaovao sy misy ny tikety.', 'retour fiverenana echange'),
 ('Ahoana no anaovana kaomandy?', 'Alefaso eto ny anaran''ny vokatra, ny habe, ny adiresy ary ny laharana finday.', 'commande kaomandy');
INSERT INTO shipping_zones (zone, price, delay_days) VALUES
 ('Antananarivo', 3000, '1-2'), ('Toamasina', 10000, '3-4'), ('Mahajanga', 12000, '3-5');
INSERT INTO customers VALUES (1, 'Rakoto', '0340000000', 'cli', 'demo-user');
INSERT INTO orders VALUES (1, 1, 'en cours de livraison', 90000, 'Analakely, Antananarivo', '2026-10-20');
INSERT INTO order_items VALUES (1, 1, 1), (1, 2, 1);
"""

if __name__ == "__main__":
    if os.path.exists(DB_PATH):
        raise SystemExit(f"{DB_PATH} efa misy; fafao aloha raha te hamorona vaovao.")
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA + DATA)
    print(f"Voaforona: {DB_PATH}")
