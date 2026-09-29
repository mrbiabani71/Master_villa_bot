import sqlite3

DB_PATH = "bot/bot.db"


def _connect():
    return sqlite3.connect(DB_PATH)


# ─────────────────────────────────────────────
#  جستجو ویلاها
# ─────────────────────────────────────────────

def admin_search_villas(code=None, city=None, max_price=None):
    conn = _connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    query = "SELECT * FROM villas WHERE 1=1"
    params = []

    if code:
        query += " AND villa_code LIKE ?"
        params.append(f"%{code}%")

    if city:
        query += " AND city LIKE ?"
        params.append(f"%{city}%")

    if max_price:
        query += " AND price <= ?"
        params.append(max_price)

    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    return [dict(r) for r in rows]


# ─────────────────────────────────────────────
#  گرفتن یک ویلا با ID
# ─────────────────────────────────────────────

def get_villa_by_id(villa_id: int):
    conn = _connect()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM villas WHERE id = ?", (villa_id,))
    row = cur.fetchone()
    conn.close()

    return dict(row) if row else None


# ─────────────────────────────────────────────
#  حذف ویلا
# ─────────────────────────────────────────────

def delete_villa(villa_id: int) -> bool:
    conn = _connect()
    cur = conn.cursor()

    cur.execute("DELETE FROM villas WHERE id = ?", (villa_id,))
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()

    return ok


# ─────────────────────────────────────────────
#  تغییر وضعیت ویلا
# ─────────────────────────────────────────────

def set_villa_status(villa_id: int, status: str) -> bool:
    conn = _connect()
    cur = conn.cursor()

    cur.execute(
        "UPDATE villas SET status = ?, updated_at = datetime('now') WHERE id = ?",
        (status, villa_id),
    )
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()

    return ok