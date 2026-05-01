# database.py
import os
import sqlite3
from contextlib import contextmanager
from typing import Any, List, Optional

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - optional in some local environments
    psycopg = None
    dict_row = None


DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
IS_POSTGRES = DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")


def _default_db_path() -> str:
    data_dir = os.getenv("DATA_DIR") or "."
    return os.path.join(data_dir, "prices.db")


DB_NAME = os.getenv("DB_PATH", _default_db_path())


@contextmanager
def get_db():
    """Context manager for safe database connections with auto-close."""
    if IS_POSTGRES:
        if psycopg is None:
            raise RuntimeError("DATABASE_URL is set but psycopg is not installed.")
        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    else:
        conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        conn.row_factory = sqlite3.Row

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _fetchall_dicts(rows) -> List[dict]:
    return [dict(row) for row in rows]


def init_db():
    with get_db() as conn:
        cursor = conn.cursor()

        if IS_POSTGRES:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id           BIGSERIAL PRIMARY KEY,
                    url          TEXT NOT NULL,
                    platform     TEXT NOT NULL DEFAULT 'flipkart',
                    product_name TEXT,
                    email        TEXT NOT NULL,
                    price        INTEGER NOT NULL,
                    target_price INTEGER,
                    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_logins (
                    email         TEXT PRIMARY KEY,
                    provider      TEXT,
                    last_login_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    password      TEXT,
                    picture       TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alert_log (
                    id      BIGSERIAL PRIMARY KEY,
                    url     TEXT NOT NULL,
                    email   TEXT NOT NULL,
                    price   INTEGER NOT NULL,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS platform TEXT NOT NULL DEFAULT 'flipkart'")
            cursor.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS product_name TEXT")
            cursor.execute("ALTER TABLE user_logins ADD COLUMN IF NOT EXISTS password TEXT")
            cursor.execute("ALTER TABLE user_logins ADD COLUMN IF NOT EXISTS picture TEXT")
            return

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                url          TEXT NOT NULL,
                platform     TEXT NOT NULL DEFAULT 'flipkart',
                product_name TEXT,
                email        TEXT NOT NULL,
                price        INTEGER NOT NULL,
                target_price INTEGER,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        existing = {row[1] for row in cursor.execute("PRAGMA table_info(products)")}
        if "platform" not in existing:
            cursor.execute("ALTER TABLE products ADD COLUMN platform TEXT NOT NULL DEFAULT 'flipkart'")
        if "product_name" not in existing:
            cursor.execute("ALTER TABLE products ADD COLUMN product_name TEXT")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_logins (
                email         TEXT PRIMARY KEY,
                provider      TEXT,
                last_login_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                password      TEXT,
                picture       TEXT
            )
        """)

        login_cols = {row[1] for row in cursor.execute("PRAGMA table_info(user_logins)")}
        if "password" not in login_cols:
            cursor.execute("ALTER TABLE user_logins ADD COLUMN password TEXT")
        if "picture" not in login_cols:
            cursor.execute("ALTER TABLE user_logins ADD COLUMN picture TEXT")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                url        TEXT NOT NULL,
                email      TEXT NOT NULL,
                price      INTEGER NOT NULL,
                sent_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


def insert_price(url: str, email: str, price: int, target_price: Optional[int],
                 platform: str = "flipkart", product_name: str = None):
    with get_db() as conn:
        if IS_POSTGRES:
            conn.execute(
                """
                INSERT INTO products (url, email, price, target_price, platform, product_name)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (url, email, price, target_price, platform, product_name),
            )
        else:
            conn.execute(
                """
                INSERT INTO products (url, email, price, target_price, platform, product_name)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (url, email, price, target_price, platform, product_name),
            )


def get_last_price(url: str) -> Optional[int]:
    with get_db() as conn:
        if IS_POSTGRES:
            row = conn.execute(
                "SELECT price FROM products WHERE url=%s ORDER BY created_at DESC LIMIT 1",
                (url,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT price FROM products WHERE url=? ORDER BY created_at DESC LIMIT 1",
                (url,),
            ).fetchone()
        return row["price"] if row else None


def get_price_history(url: str, email: str, limit: int = 30) -> List[dict]:
    """Return price history for a specific product."""
    with get_db() as conn:
        if IS_POSTGRES:
            rows = conn.execute(
                """
                SELECT price, created_at FROM products
                WHERE url=%s AND email=%s
                ORDER BY created_at DESC LIMIT %s
                """,
                (url, email, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT price, created_at FROM products
                WHERE url=? AND email=?
                ORDER BY created_at DESC LIMIT ?
                """,
                (url, email, limit),
            ).fetchall()
        return _fetchall_dicts(rows)


def get_tracked_products_by_email(email: str) -> List[dict]:
    with get_db() as conn:
        if IS_POSTGRES:
            rows = conn.execute(
                """
                SELECT url, platform, product_name, price, target_price, created_at
                FROM products
                WHERE email = %s
                  AND id IN (
                      SELECT MAX(id) FROM products
                      WHERE email = %s
                      GROUP BY url
                  )
                ORDER BY created_at DESC
                """,
                (email, email),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT url, platform, product_name, price, target_price, created_at
                FROM products
                WHERE email = ?
                  AND id IN (
                      SELECT MAX(id) FROM products
                      WHERE email = ?
                      GROUP BY url
                  )
                ORDER BY created_at DESC
                """,
                (email, email),
            ).fetchall()
        return _fetchall_dicts(rows)


def get_price_rows_by_email(email: str, limit: int = 300) -> List[dict]:
    """Return raw historical rows for analytics charts."""
    with get_db() as conn:
        if IS_POSTGRES:
            rows = conn.execute(
                """
                SELECT url, platform, product_name, price, target_price, created_at
                FROM products
                WHERE email = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (email, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT url, platform, product_name, price, target_price, created_at
                FROM products
                WHERE email = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (email, limit),
            ).fetchall()
        return _fetchall_dicts(rows)


def get_all_tracked_products() -> List[dict]:
    """Return one latest record per (url, email) pair for the scheduler."""
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT url, email, target_price, platform, product_name
            FROM products
            WHERE id IN (
                SELECT MAX(id) FROM products
                GROUP BY url, email
            )
            """
        ).fetchall()
        return _fetchall_dicts(rows)


def upsert_user_login(email: str, provider: str, password: str = None, picture: str = None):
    with get_db() as conn:
        if IS_POSTGRES:
            placeholder = "%s"
        else:
            placeholder = "?"

        if password and picture:
            conn.execute(
                f"""
                INSERT INTO user_logins (email, provider, last_login_at, password, picture)
                VALUES ({placeholder}, {placeholder}, CURRENT_TIMESTAMP, {placeholder}, {placeholder})
                ON CONFLICT(email) DO UPDATE SET
                    provider = excluded.provider,
                    last_login_at = CURRENT_TIMESTAMP,
                    password = excluded.password,
                    picture = excluded.picture
                """,
                (email, provider, password, picture),
            )
        elif password:
            conn.execute(
                f"""
                INSERT INTO user_logins (email, provider, last_login_at, password)
                VALUES ({placeholder}, {placeholder}, CURRENT_TIMESTAMP, {placeholder})
                ON CONFLICT(email) DO UPDATE SET
                    provider = excluded.provider,
                    last_login_at = CURRENT_TIMESTAMP,
                    password = excluded.password
                """,
                (email, provider, password),
            )
        elif picture:
            conn.execute(
                f"""
                INSERT INTO user_logins (email, provider, last_login_at, picture)
                VALUES ({placeholder}, {placeholder}, CURRENT_TIMESTAMP, {placeholder})
                ON CONFLICT(email) DO UPDATE SET
                    provider = excluded.provider,
                    last_login_at = CURRENT_TIMESTAMP,
                    picture = excluded.picture
                """,
                (email, provider, picture),
            )
        else:
            conn.execute(
                f"""
                INSERT INTO user_logins (email, provider, last_login_at)
                VALUES ({placeholder}, {placeholder}, CURRENT_TIMESTAMP)
                ON CONFLICT(email) DO UPDATE SET
                    provider = excluded.provider,
                    last_login_at = CURRENT_TIMESTAMP
                """,
                (email, provider),
            )


def get_user_data(email: str) -> Optional[dict]:
    with get_db() as conn:
        if IS_POSTGRES:
            row = conn.execute(
                "SELECT provider, password, picture FROM user_logins WHERE email=%s",
                (email,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT provider, password, picture FROM user_logins WHERE email=?",
                (email,),
            ).fetchone()
        return dict(row) if row else None


def update_user_picture(email: str, picture: str):
    with get_db() as conn:
        if IS_POSTGRES:
            conn.execute("UPDATE user_logins SET picture=%s WHERE email=%s", (picture, email))
        else:
            conn.execute("UPDATE user_logins SET picture=? WHERE email=?", (picture, email))


def get_user_password(email: str) -> Optional[str]:
    with get_db() as conn:
        if IS_POSTGRES:
            row = conn.execute("SELECT password FROM user_logins WHERE email=%s", (email,)).fetchone()
        else:
            row = conn.execute("SELECT password FROM user_logins WHERE email=?", (email,)).fetchone()
        return row["password"] if row else None


def update_user_password(email: str, hashed_password: str):
    with get_db() as conn:
        if IS_POSTGRES:
            conn.execute("UPDATE user_logins SET password=%s WHERE email=%s", (hashed_password, email))
        else:
            conn.execute("UPDATE user_logins SET password=? WHERE email=?", (hashed_password, email))


def delete_tracked_product(email: str, url: str):
    with get_db() as conn:
        if IS_POSTGRES:
            conn.execute("DELETE FROM products WHERE email=%s AND url=%s", (email, url))
        else:
            conn.execute("DELETE FROM products WHERE email=? AND url=?", (email, url))


def get_trusted_users_count() -> int:
    with get_db() as conn:
        row = conn.execute("SELECT COUNT(*) AS total FROM user_logins").fetchone()
        return row["total"] if row else 0


def log_alert_sent(url: str, email: str, price: int):
    with get_db() as conn:
        if IS_POSTGRES:
            conn.execute(
                "INSERT INTO alert_log (url, email, price) VALUES (%s, %s, %s)",
                (url, email, price),
            )
        else:
            conn.execute(
                "INSERT INTO alert_log (url, email, price) VALUES (?, ?, ?)",
                (url, email, price),
            )


def was_alert_sent_recently(url: str, email: str, hours: int = 24) -> bool:
    """Prevent duplicate alerts within the given window."""
    with get_db() as conn:
        if IS_POSTGRES:
            row = conn.execute(
                """
                SELECT 1
                FROM alert_log
                WHERE url=%s AND email=%s
                  AND sent_at > CURRENT_TIMESTAMP - (%s * INTERVAL '1 hour')
                LIMIT 1
                """,
                (url, email, hours),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT 1 FROM alert_log
                WHERE url=? AND email=?
                  AND sent_at > datetime('now', ? || ' hours')
                LIMIT 1
                """,
                (url, email, f"-{hours}"),
            ).fetchone()
        return row is not None


# Backward-compatible alias
get_all_products = get_all_tracked_products
