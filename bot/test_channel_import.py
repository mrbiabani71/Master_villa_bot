"""
Quick smoke-test for the SQLite channel-import path.
Runs against a temporary in-memory database — does NOT touch bot.db.
No Telegram, no API server, no network required.

Usage:  python3 bot/test_channel_import.py
"""
import sys
import os
import sqlite3
import unittest
from unittest.mock import patch

# Make bot/ importable without installing anything
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Patch database.get_connection to use an in-memory SQLite DB ───────────────

_mem_conn: sqlite3.Connection | None = None

def _in_memory_connection() -> sqlite3.Connection:
    global _mem_conn
    if _mem_conn is None:
        _mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
        _mem_conn.row_factory = sqlite3.Row
    return _mem_conn

# Apply the patch before importing database so init_db() runs against :memory:
import database as _db_module
_db_module.get_connection = _in_memory_connection   # type: ignore[assignment]

import database
database.init_db()   # creates tables + migrations in :memory:

from smart_import.models import VillaData, ImportResult
from smart_import.importer import import_villa_from_channel


# ── Helper ────────────────────────────────────────────────────────────────────

def _make_data(**kwargs) -> VillaData:
    defaults = dict(
        city="نوشهر",
        area_type="جنگلی",
        price=3_500_000_000,
        land_size=250.0,
        building_size=120.0,
        bedrooms=3,
        master_bedrooms=1,
        has_pool=1,
        has_jacuzzi=0,
        has_roof_garden=0,
        has_parking=1,
        has_storage=0,
        documents=["سند تک برگ"],
        description="ویلای دوبلکس با نمای مدرن",
        photos=["file_id_1", "file_id_2"],
        telegram_message_id=42001,
        telegram_media_group_id="group_abc",
        original_caption="ویلا نوشهر ۳خ",
        region="منطقه جنگلی",
        villa_type="دوبلکس",
        facade="مدرن",
        utilities=["آب", "برق"],
        location_status="مشرف به جنگل",
        community_status="داخل شهرک",
    )
    defaults.update(kwargs)
    return VillaData(**defaults)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestChannelImportSQLite(unittest.TestCase):

    def setUp(self):
        # Clear villas table between tests
        conn = _in_memory_connection()
        conn.execute("DELETE FROM villas")
        conn.commit()

    # ── insert ────────────────────────────────────────────────────────────────

    def test_create_new_villa(self):
        """A new channel post creates a villa row in SQLite."""
        data = _make_data()
        result = import_villa_from_channel(data)

        self.assertTrue(result.success, f"expected success, got error: {result.error}")
        self.assertEqual(result.mode, "create")
        self.assertIsNotNone(result.villa_id)
        self.assertIsNotNone(result.villa_code)

        row = database.get_villa_by_id(result.villa_id)
        self.assertIsNotNone(row)
        self.assertEqual(row["city"], "نوشهر")
        self.assertEqual(row["price"], 3_500_000_000)
        self.assertEqual(row["telegram_message_id"], 42001)
        self.assertEqual(row["telegram_media_group_id"], "group_abc")
        self.assertEqual(row["photos"], "file_id_1,file_id_2")
        self.assertEqual(row["region"], "منطقه جنگلی")
        self.assertEqual(row["villa_type"], "دوبلکس")
        self.assertEqual(row["location_status"], "مشرف به جنگل")
        self.assertEqual(row["community_status"], "داخل شهرک")
        self.assertEqual(row["status"], "published")

    def test_villa_code_auto_assigned(self):
        """villa_code is auto-generated (MV-NNNN) when not provided by parser."""
        data = _make_data(villa_code=None)
        result = import_villa_from_channel(data)

        self.assertTrue(result.success)
        self.assertTrue(result.villa_code.startswith("MV-"), result.villa_code)

    def test_villa_code_explicit(self):
        """If parser already has a villa_code it is preserved."""
        data = _make_data(villa_code="MV-9999")
        result = import_villa_from_channel(data)

        self.assertTrue(result.success)
        self.assertEqual(result.villa_code, "MV-9999")

    # ── idempotent update ─────────────────────────────────────────────────────

    def test_reimport_same_message_updates_not_duplicates(self):
        """Re-importing the same telegram_message_id updates the row, not inserts a new one."""
        data = _make_data()
        r1 = import_villa_from_channel(data)
        self.assertTrue(r1.success)
        self.assertEqual(r1.mode, "create")

        # Edit the caption — same message_id, new price
        data2 = _make_data(price=4_000_000_000)
        r2 = import_villa_from_channel(data2)
        self.assertTrue(r2.success)
        self.assertEqual(r2.mode, "update")
        self.assertEqual(r2.villa_id, r1.villa_id,
                         "update must reuse the same row id")
        self.assertEqual(r2.villa_code, r1.villa_code,
                         "villa_code must not change on update")

        # Only one row in DB
        conn = _in_memory_connection()
        count = conn.execute("SELECT COUNT(*) FROM villas WHERE telegram_message_id=42001").fetchone()[0]
        self.assertEqual(count, 1, "expected exactly 1 row after re-import")

        # Price was updated
        row = database.get_villa_by_id(r1.villa_id)
        self.assertEqual(row["price"], 4_000_000_000)

    def test_update_preserves_villa_code(self):
        """The villa_code assigned on create is not changed during an update."""
        data = _make_data(villa_code=None)
        r1 = import_villa_from_channel(data)
        original_code = r1.villa_code

        data2 = _make_data(villa_code=None, city="آمل")
        r2 = import_villa_from_channel(data2)
        self.assertEqual(r2.villa_code, original_code)

        row = database.get_villa_by_id(r1.villa_id)
        self.assertEqual(row["city"], "آمل")        # updated
        self.assertEqual(row["villa_code"], original_code)  # preserved

    # ── no message_id ─────────────────────────────────────────────────────────

    def test_no_telegram_message_id_always_creates(self):
        """Posts with no telegram_message_id always create a new row."""
        data1 = _make_data(telegram_message_id=None, villa_code=None)
        data2 = _make_data(telegram_message_id=None, villa_code=None)
        r1 = import_villa_from_channel(data1)
        r2 = import_villa_from_channel(data2)

        self.assertEqual(r1.mode, "create")
        self.assertEqual(r2.mode, "create")
        self.assertNotEqual(r1.villa_id, r2.villa_id)

    # ── photos stored as comma-joined string ──────────────────────────────────

    def test_photos_stored_as_comma_string(self):
        data = _make_data(photos=["A", "B", "C"])
        result = import_villa_from_channel(data)
        row = database.get_villa_by_id(result.villa_id)
        self.assertEqual(row["photos"], "A,B,C")

    def test_empty_photos(self):
        data = _make_data(photos=[])
        result = import_villa_from_channel(data)
        row = database.get_villa_by_id(result.villa_id)
        self.assertIn(row["photos"], (None, ""))

    # ── boolean amenities ─────────────────────────────────────────────────────

    def test_boolean_amenities_stored(self):
        data = _make_data(has_pool=1, has_jacuzzi=1, has_roof_garden=0,
                          has_parking=1, has_storage=0)
        result = import_villa_from_channel(data)
        row = database.get_villa_by_id(result.villa_id)
        self.assertEqual(row["has_pool"], 1)
        self.assertEqual(row["has_jacuzzi"], 1)
        self.assertEqual(row["has_roof_garden"], 0)
        self.assertEqual(row["has_parking"], 1)
        self.assertEqual(row["has_storage"], 0)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestChannelImportSQLite)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
