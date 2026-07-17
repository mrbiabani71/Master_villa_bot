import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "bot.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _add_column_if_missing(
    conn: sqlite3.Connection, table: str, column: str, definition: str
) -> None:
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    except sqlite3.OperationalError:
        pass


def init_db() -> None:
    with get_connection() as conn:
        conn.execute("PRAGMA journal_mode=WAL;")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS villas (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                villa_code    TEXT UNIQUE NOT NULL,
                city          TEXT,
                area_type     TEXT,
                price         REAL,
                land_size     REAL,
                building_size REAL,
                bedrooms      INTEGER,
                is_townhouse  INTEGER NOT NULL DEFAULT 0,
                has_pool      INTEGER NOT NULL DEFAULT 0,
                document_type TEXT,
                description   TEXT,
                latitude      REAL,
                longitude     REAL,
                photos        TEXT,
                video         TEXT,
                status        TEXT NOT NULL DEFAULT 'published',
                created_at    TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)

        _add_column_if_missing(conn, "villas", "has_jacuzzi",      "INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(conn, "villas", "has_roof_garden",  "INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(conn, "villas", "has_parking",      "INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(conn, "villas", "has_storage",      "INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(conn, "villas", "master_bedrooms",  "INTEGER DEFAULT 0")
        _add_column_if_missing(conn, "villas", "updated_at",       "TEXT DEFAULT (datetime('now'))")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS visit_requests (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                villa_code   TEXT NOT NULL,
                user_id      INTEGER NOT NULL,
                name         TEXT NOT NULL,
                phone        TEXT NOT NULL,
                area_type    TEXT DEFAULT '',
                request_type TEXT DEFAULT 'visit',
                status       TEXT DEFAULT 'pending',
                created_at   TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)

        # Safe migrations for existing rows
        _add_column_if_missing(conn, "visit_requests", "area_type",    "TEXT DEFAULT ''")
        _add_column_if_missing(conn, "visit_requests", "request_type", "TEXT DEFAULT 'visit'")
        _add_column_if_missing(conn, "visit_requests", "status",       "TEXT DEFAULT 'pending'")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                villa_id   INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(user_id, villa_id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS compare_list (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                villa_id   INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(user_id, villa_id)
            )
        """)

        conn.commit()


# ── Villa queries ──────────────────────────────────────────────────────────────

def get_next_villa_code() -> str:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT MAX(CAST(SUBSTR(villa_code, 4) AS INTEGER)) AS max_num FROM villas"
        ).fetchone()
        next_num = (row["max_num"] or 1000) + 1
        return f"MV-{next_num}"


def insert_villa(data: dict) -> int:
    photos_str = ",".join(data.get("photos") or [])
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO villas (
                villa_code, city, area_type, price,
                land_size, building_size, bedrooms, master_bedrooms,
                is_townhouse, has_pool, has_jacuzzi,
                has_roof_garden, has_parking, has_storage,
                document_type, description,
                latitude, longitude,
                photos, video, status,
                created_at, updated_at
            ) VALUES (
                :villa_code, :city, :area_type, :price,
                :land_size, :building_size, :bedrooms, :master_bedrooms,
                :is_townhouse, :has_pool, :has_jacuzzi,
                :has_roof_garden, :has_parking, :has_storage,
                :document_type, :description,
                :latitude, :longitude,
                :photos_str, :video, 'published',
                datetime('now'), datetime('now')
            )
            """,
            {**data, "photos_str": photos_str, "master_bedrooms": data.get("master_bedrooms") or 0},
        )
        conn.commit()
        return cursor.lastrowid


def get_villa_by_id(villa_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM villas WHERE id = ?", (villa_id,)
        ).fetchone()
        return dict(row) if row else None


def get_villa_by_code(villa_code: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM villas WHERE villa_code = ?", (villa_code,)
        ).fetchone()
        return dict(row) if row else None


def search_villas(
    area_type: str,
    min_price: float,
    max_price: float | None,
    city: str | None = None,
) -> list[dict]:
    query = """
        SELECT * FROM villas
        WHERE status = 'published'
          AND area_type = ?
          AND price >= ?
    """
    params: list = [area_type, min_price]
    if city:
        query += " AND city = ?"
        params.append(city)
    if max_price is not None:
        query += " AND price <= ?"
        params.append(max_price)
    query += " ORDER BY price ASC, created_at DESC"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


# ── Visit request queries ──────────────────────────────────────────────────────

def insert_visit_request(
    villa_code: str,
    user_id: int,
    name: str,
    phone: str,
    area_type: str = "",
    request_type: str = "visit",
) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO visit_requests
                (villa_code, user_id, name, phone, area_type, request_type, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', datetime('now'))
            """,
            (villa_code, user_id, name, phone, area_type, request_type),
        )
        conn.commit()
        return cursor.lastrowid


def get_requests(
    page: int,
    page_size: int = 1,
    status_filter: str | None = None,
    type_filter: str | None = None,
) -> list[dict]:
    conditions = []
    params: list = []

    if status_filter:
        conditions.append("r.status = ?")
        params.append(status_filter)
    if type_filter:
        conditions.append("r.request_type = ?")
        params.append(type_filter)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    query = f"""
        SELECT
            r.id, r.villa_code, r.user_id, r.name, r.phone,
            r.area_type, r.request_type, r.status, r.created_at,
            v.price, v.city AS villa_city
        FROM visit_requests r
        LEFT JOIN villas v ON r.villa_code = v.villa_code
        {where}
        ORDER BY r.created_at DESC, r.id DESC
        LIMIT ? OFFSET ?
    """
    params += [page_size, page * page_size]

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def get_requests_count(
    status_filter: str | None = None,
    type_filter: str | None = None,
) -> int:
    conditions = []
    params: list = []

    if status_filter:
        conditions.append("status = ?")
        params.append(status_filter)
    if type_filter:
        conditions.append("request_type = ?")
        params.append(type_filter)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    with get_connection() as conn:
        row = conn.execute(
            f"SELECT COUNT(*) AS cnt FROM visit_requests {where}", params
        ).fetchone()
        return row["cnt"]


def mark_request_contacted(req_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE visit_requests SET status = 'contacted' WHERE id = ?", (req_id,)
        )
        conn.commit()


def delete_request(req_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM visit_requests WHERE id = ?", (req_id,))
        conn.commit()


# ── Favorites queries ──────────────────────────────────────────────────────────

def add_favorite(user_id: int, villa_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO favorites (user_id, villa_id) VALUES (?, ?)",
            (user_id, villa_id),
        )
        conn.commit()


def remove_favorite(user_id: int, villa_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM favorites WHERE user_id = ? AND villa_id = ?",
            (user_id, villa_id),
        )
        conn.commit()


def is_favorite(user_id: int, villa_id: int) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM favorites WHERE user_id = ? AND villa_id = ?",
            (user_id, villa_id),
        ).fetchone()
        return row is not None


def get_user_favorites(user_id: int) -> list[int]:
    """Return villa_ids saved by user, most recently added first."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT villa_id FROM favorites WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [row["villa_id"] for row in rows]


# ── Compare queries ────────────────────────────────────────────────────────────

def add_compare(user_id: int, villa_id: int) -> bool:
    """Add villa to compare list. Returns False if already at 3-villa limit."""
    with get_connection() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM compare_list WHERE user_id = ?",
            (user_id,),
        ).fetchone()[0]
        if count >= 3:
            return False
        conn.execute(
            "INSERT OR IGNORE INTO compare_list (user_id, villa_id) VALUES (?, ?)",
            (user_id, villa_id),
        )
        conn.commit()
        return True


def remove_compare(user_id: int, villa_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM compare_list WHERE user_id = ? AND villa_id = ?",
            (user_id, villa_id),
        )
        conn.commit()


def is_in_compare(user_id: int, villa_id: int) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM compare_list WHERE user_id = ? AND villa_id = ?",
            (user_id, villa_id),
        ).fetchone()
        return row is not None


def get_user_compare(user_id: int) -> list[int]:
    """Return villa_ids in compare list, oldest first."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT villa_id FROM compare_list WHERE user_id = ? ORDER BY created_at ASC",
            (user_id,),
        ).fetchall()
        return [row["villa_id"] for row in rows]


def clear_compare(user_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM compare_list WHERE user_id = ?", (user_id,))
        conn.commit()
