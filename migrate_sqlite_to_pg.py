"""
One-time migration: SQLite (bot/bot.db) → PostgreSQL (DATABASE_URL)

Rules:
  - Compare by villa_code.
  - villa_code not in PG  → INSERT as new villa.
  - villa_code already in PG → patch only NULL/empty PG fields from SQLite;
    never overwrite existing PG data or channel-only fields.
  - Produces a report at the end; makes no changes without explicit confirmation
    (pass --run to actually write, default is dry-run).

Usage:
  python3 migrate_sqlite_to_pg.py          # dry-run (safe, no DB writes)
  python3 migrate_sqlite_to_pg.py --run    # execute the migration
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from dataclasses import dataclass, field
from typing import Any

import psycopg2
import psycopg2.extras

# ── Config ────────────────────────────────────────────────────────────────────

SQLITE_PATH = os.path.join(os.path.dirname(__file__), "bot", "bot.db")
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Fields that exist in SQLite and map directly to PostgreSQL columns.
# Order matters only for the INSERT statement.
MIGRATED_FIELDS: list[str] = [
    "villa_code",
    "city",
    "area_type",
    "price",
    "land_size",
    "building_size",
    "bedrooms",
    "master_bedrooms",
    "is_townhouse",
    "has_pool",
    "has_jacuzzi",
    "has_roof_garden",
    "has_parking",
    "has_storage",
    "document_type",
    "description",
    "latitude",
    "longitude",
    "photos",
    "video",
    "status",
]

# These PG-only fields are never touched by this migration.
CHANNEL_ONLY_FIELDS = {
    "telegram_message_id",
    "telegram_media_group_id",
    "original_caption",
    "region",
    "villa_type",
    "facade",
    "utilities",
    "location_status",
    "community_status",
}

# Text fields: NULL *or* empty string counts as "missing".
TEXT_FIELDS = {
    "city", "area_type", "document_type", "description",
    "photos", "video", "status",
}


# ── Report ────────────────────────────────────────────────────────────────────

@dataclass
class Report:
    inserted: list[str] = field(default_factory=list)
    updated: list[tuple[str, list[str]]] = field(default_factory=list)   # (code, [fields])
    skipped: list[str] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)

    def print(self) -> None:
        print("\n" + "=" * 60)
        print("MIGRATION REPORT")
        print("=" * 60)

        print(f"\n✅ INSERTED ({len(self.inserted)} villas — new to PostgreSQL):")
        if self.inserted:
            for code in self.inserted:
                print(f"   {code}")
        else:
            print("   (none)")

        print(f"\n🔄 PATCHED ({len(self.updated)} villas — missing fields filled):")
        if self.updated:
            for code, fields in self.updated:
                print(f"   {code}: {', '.join(fields)}")
        else:
            print("   (none)")

        print(f"\n⏭  SKIPPED ({len(self.skipped)} villas — PG already complete):")
        if self.skipped:
            for code in self.skipped:
                print(f"   {code}")
        else:
            print("   (none)")

        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for code, err in self.errors:
                print(f"   {code}: {err}")

        total = len(self.inserted) + len(self.updated) + len(self.skipped)
        print(f"\nSUMMARY: {total} SQLite villas processed")
        print(f"  Inserted (new):        {len(self.inserted)}")
        print(f"  Patched (fields only): {len(self.updated)}")
        print(f"  Skipped (complete):    {len(self.skipped)}")
        print(f"  Duplicates avoided:    {len(self.updated) + len(self.skipped)}")
        print(f"  Errors:                {len(self.errors)}")
        print("=" * 60 + "\n")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_missing(value: Any, field_name: str) -> bool:
    """Return True when a PG value is considered absent/empty."""
    if value is None:
        return True
    if field_name in TEXT_FIELDS and str(value).strip() == "":
        return True
    return False


def _load_sqlite_villas() -> list[dict]:
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM villas ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _load_pg_villas(pg: psycopg2.extensions.connection) -> dict[str, dict]:
    """Return {villa_code: row_dict} for all PG villas."""
    with pg.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM villas")
        return {row["villa_code"]: dict(row) for row in cur.fetchall()}


# ── Core logic ────────────────────────────────────────────────────────────────

def migrate(dry_run: bool) -> Report:
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL environment variable is not set.", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(SQLITE_PATH):
        print(f"ERROR: SQLite file not found at {SQLITE_PATH}", file=sys.stderr)
        sys.exit(1)

    mode_label = "DRY-RUN" if dry_run else "LIVE"
    print(f"\n[{mode_label}] Loading SQLite villas from {SQLITE_PATH} …")
    sqlite_villas = _load_sqlite_villas()
    print(f"[{mode_label}] {len(sqlite_villas)} villas found in SQLite.")

    pg = psycopg2.connect(DATABASE_URL)
    pg.autocommit = False

    print(f"[{mode_label}] Loading PostgreSQL villas …")
    pg_villas = _load_pg_villas(pg)
    print(f"[{mode_label}] {len(pg_villas)} villas found in PostgreSQL.")

    report = Report()

    for sv in sqlite_villas:
        code = sv["villa_code"]
        try:
            if code not in pg_villas:
                # ── INSERT ────────────────────────────────────────────────────
                row = {f: sv.get(f) for f in MIGRATED_FIELDS}
                if not dry_run:
                    cols = ", ".join(row.keys())
                    placeholders = ", ".join(f"%({k})s" for k in row.keys())
                    with pg.cursor() as cur:
                        cur.execute(
                            f"INSERT INTO villas ({cols}) VALUES ({placeholders})",
                            row,
                        )
                report.inserted.append(code)
                print(f"  [INSERT] {code}")

            else:
                # ── PATCH missing fields only ─────────────────────────────────
                pg_row = pg_villas[code]
                patch: dict[str, Any] = {}

                for f in MIGRATED_FIELDS:
                    if f == "villa_code":
                        continue  # never update the key
                    if f in CHANNEL_ONLY_FIELDS:
                        continue  # never overwrite channel metadata
                    pg_val = pg_row.get(f)
                    sq_val = sv.get(f)
                    if _is_missing(pg_val, f) and sq_val is not None:
                        # For text fields: also skip empty SQLite values
                        if f in TEXT_FIELDS and str(sq_val).strip() == "":
                            continue
                        patch[f] = sq_val

                if patch:
                    if not dry_run:
                        set_clause = ", ".join(f"{k} = %({k})s" for k in patch)
                        patch["_code"] = code
                        with pg.cursor() as cur:
                            cur.execute(
                                f"UPDATE villas SET {set_clause} WHERE villa_code = %(_code)s",
                                patch,
                            )
                    report.updated.append((code, list(patch.keys())))
                    print(f"  [PATCH]  {code} → {list(patch.keys())}")
                else:
                    report.skipped.append(code)
                    print(f"  [SKIP]   {code} (PG already complete)")

        except Exception as exc:
            report.errors.append((code, str(exc)))
            print(f"  [ERROR]  {code}: {exc}", file=sys.stderr)
            pg.rollback()

    if not dry_run and not report.errors:
        pg.commit()
        print(f"\n[LIVE] Transaction committed.")
    elif not dry_run and report.errors:
        pg.rollback()
        print(f"\n[LIVE] ⚠️  Errors occurred — transaction rolled back. Fix errors and re-run.", file=sys.stderr)
    else:
        pg.rollback()  # dry-run: nothing to commit
        print(f"\n[DRY-RUN] No changes written.")

    pg.close()
    return report


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate villas from SQLite to PostgreSQL.")
    parser.add_argument(
        "--run",
        action="store_true",
        default=False,
        help="Actually write changes (default is dry-run).",
    )
    args = parser.parse_args()

    dry_run = not args.run

    if dry_run:
        print(
            "\n⚠️  DRY-RUN MODE — no changes will be written to the database.\n"
            "    Review the plan below, then re-run with --run to execute.\n"
        )
    else:
        print(
            "\n🚀 LIVE MODE — changes will be written to PostgreSQL.\n"
        )

    report = migrate(dry_run=dry_run)
    report.print()

    if report.errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
