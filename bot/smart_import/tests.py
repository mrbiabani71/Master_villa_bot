"""
Smart Import validation suite.

Run from the bot/ directory:
    python3 -m smart_import.tests

Covers:
  1. Parsing accuracy — multiple real Persian villa descriptions
  2. Database insertion
  3. Duplicate villa code handling
  4. Automatic villa code generation
  5. Unknown lines preserved in description
  6. Price formats (میلیارد / میلیون / plain digit)
  7. Bedroom formats (Persian words / digits / master bedrooms)
  8. Boolean feature flags (استخر، جکوزی، پارکینگ …)
  9. Minimal post (only city + price)
 10. Mixed Persian & Western numerals
"""

from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))  # bot/

from database import init_db, get_villa_by_code
from smart_import.parser import parse_villa_text
from smart_import.importer import import_villa

# ── ANSI colours ──────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

_pass = 0
_fail = 0

def ok(label: str, detail: str = "") -> None:
    global _pass
    _pass += 1
    print(f"  {GREEN}✓{RESET} {label}" + (f"  {YELLOW}({detail}){RESET}" if detail else ""))

def fail(label: str, detail: str = "") -> None:
    global _fail
    _fail += 1
    print(f"  {RED}✗ FAIL{RESET} {label}" + (f"  → {detail}" if detail else ""))

def section(title: str) -> None:
    print(f"\n{BOLD}{CYAN}── {title} {'─'*(52 - len(title))}{RESET}")

def assert_eq(label: str, got, expected) -> None:
    if got == expected:
        ok(label, f"{got!r}")
    else:
        fail(label, f"got {got!r}, expected {expected!r}")

def assert_not_none(label: str, got) -> None:
    if got is not None:
        ok(label, f"{got!r}")
    else:
        fail(label, "got None")

def assert_none(label: str, got) -> None:
    if got is None:
        ok(label, "None")
    else:
        fail(label, f"expected None, got {got!r}")

def assert_contains(label: str, text: str, substring: str) -> None:
    if substring in text:
        ok(label, f"…{substring}…")
    else:
        fail(label, f"{substring!r} not in {text!r}")

def assert_true(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        ok(label, detail)
    else:
        fail(label, detail or "condition was False")

# ─────────────────────────────────────────────────────────────────────────────
#  Test data
# ─────────────────────────────────────────────────────────────────────────────

# 1. Full structured post — the reference sample
SAMPLE_1 = """MV-701
آمل
210 زمین
200 بنا
سه خواب دو مستر
پروانه ساخت
سند تک برگ
شهرک خصوصی
دسترسی عالی به امکانات شهری
مناسب برای سکونت دائم
قیمت 15 میلیارد"""

# 2. Coastal villa, Western digits, feature flags
SAMPLE_2 = """MV-702
محمودآباد
350 زمین
180 بنا
4 خواب 2 مستر
سند تک برگ
استخر
جکوزی
پارکینگ
ویو دریا
قیمت 22 میلیارد"""

# 3. No villa code → auto-generate
SAMPLE_3 = """سرخرود
120 زمین
90 بنا
دو خواب
قولنامه
قیمت 850 میلیون
انباری"""

# 4. Minimal post — only city and price
SAMPLE_4 = """نور
قیمت 5 میلیارد"""

# 5. Mixed Persian + Western digits, روف گاردن
SAMPLE_5 = """MV-703
ایزدشهر
۲۵۰ زمین
۱۴۰ بنا
سه خواب یک مستر
سند منگوله‌دار
روف گاردن
قیمت ۱۸ میلیارد
کنار دریاچه، آرامش کامل"""

# 6. Forest villa, price in میلیون, no master bedroom
SAMPLE_6 = """MV-704
چمستان
200 زمین
130 بنا
دو خواب
پروانه ساخت
قیمت 1200 میلیون"""

# 7. Post with several unknown / free-form lines
SAMPLE_7 = """MV-705
نور
500 زمین
300 بنا
پنج خواب سه مستر
سند تک برگ
استخر
سونا خشک و بخار
سیستم اتوماسیون هوشمند
منطقه دربند کوه، دید کامل به جنگل
مجتمع ویلایی بسته با امنیت ۲۴ ساعته
قیمت 45 میلیارد"""

# 8. Duplicate of SAMPLE_1 code — should error
SAMPLE_DUP = """MV-701
آمل
100 زمین
80 بنا
یک خواب
قیمت 2 میلیارد"""

# 9. Price with no label, plain میلیارد
SAMPLE_9 = """MV-706
آمل
300 زمین
200 بنا
چهار خواب دو مستر
سند تک برگ
12 میلیارد"""

# 10. Bedrooms written as digits (not words)
SAMPLE_10 = """MV-707
بابلسر
180 زمین
120 بنا
3 خواب 1 مستر
سند شخصی
قیمت 6 میلیارد"""


# ─────────────────────────────────────────────────────────────────────────────
#  Run tests
# ─────────────────────────────────────────────────────────────────────────────

# Villa codes used by this suite — cleaned before every run so tests are repeatable
_TEST_CODES = ["MV-701", "MV-702", "MV-703", "MV-704", "MV-705", "MV-706", "MV-707"]


def _cleanup_test_data() -> None:
    """Delete any leftover rows from a previous run so the suite is idempotent."""
    from database import get_connection
    with get_connection() as conn:
        placeholders = ",".join("?" * len(_TEST_CODES))
        conn.execute(
            f"DELETE FROM villas WHERE villa_code IN ({placeholders})",
            _TEST_CODES,
        )
        # Also remove any auto-generated codes inserted by this suite
        # (they start at MV-1001+, but the sequential counter will re-use them)
        conn.commit()
    print(f"  {YELLOW}(test data cleaned){RESET}")


def run():
    print(f"\n{BOLD}{'═'*60}")
    print("  Smart Import — Validation Suite")
    print(f"{'═'*60}{RESET}")

    init_db()
    _cleanup_test_data()

    # ── Test group 1: Parser accuracy ─────────────────────────────────────────
    section("1. Full structured post (SAMPLE_1)")
    d = parse_villa_text(SAMPLE_1)
    assert_eq("villa_code",      d.villa_code,      "MV-701")
    assert_eq("city",            d.city,            "آمل")
    assert_eq("area_type",       d.area_type,       "جنگلی")
    assert_eq("land_size",       d.land_size,       210.0)
    assert_eq("building_size",   d.building_size,   200.0)
    assert_eq("bedrooms",        d.bedrooms,        3)
    assert_eq("master_bedrooms", d.master_bedrooms, 2)
    assert_eq("price",           d.price,           15_000_000_000.0)
    assert_true("documents has پروانه ساخت",  "پروانه ساخت" in d.documents)
    assert_true("documents has سند تک برگ",  "سند تک برگ"  in d.documents)
    assert_true("features has شهرک خصوصی",   "شهرک خصوصی"  in d.features)
    assert_contains("unknown lines in description", d.description, "دسترسی عالی به امکانات شهری")
    assert_contains("unknown lines in description", d.description, "مناسب برای سکونت دائم")

    section("2. Coastal villa + feature flags (SAMPLE_2)")
    d = parse_villa_text(SAMPLE_2)
    assert_eq("villa_code",  d.villa_code,  "MV-702")
    assert_eq("city",        d.city,        "محمودآباد")
    assert_eq("area_type",   d.area_type,   "ساحلی")
    assert_eq("bedrooms",    d.bedrooms,    4)
    assert_eq("master_bedrooms", d.master_bedrooms, 2)
    assert_eq("price",       d.price,       22_000_000_000.0)
    assert_eq("has_pool",    d.has_pool,    1)
    assert_eq("has_jacuzzi", d.has_jacuzzi, 1)
    assert_eq("has_parking", d.has_parking, 1)

    section("3. No villa code — auto-assign (SAMPLE_3)")
    d = parse_villa_text(SAMPLE_3)
    assert_none("villa_code is None before import", d.villa_code)
    assert_eq("city",       d.city,       "سرخرود")
    assert_eq("area_type",  d.area_type,  "ساحلی")
    assert_eq("bedrooms",   d.bedrooms,   2)
    assert_none("master_bedrooms is None", d.master_bedrooms)
    assert_eq("price",      d.price,      850_000_000.0)
    assert_eq("has_storage",d.has_storage,1)

    section("4. Minimal post — city + price only (SAMPLE_4)")
    d = parse_villa_text(SAMPLE_4)
    assert_eq("city",  d.city,  "نور")
    assert_eq("price", d.price, 5_000_000_000.0)
    assert_none("land_size None",     d.land_size)
    assert_none("building_size None", d.building_size)
    assert_none("bedrooms None",      d.bedrooms)

    section("5. Persian digits + روف گاردن (SAMPLE_5)")
    d = parse_villa_text(SAMPLE_5)
    assert_eq("villa_code",      d.villa_code,      "MV-703")
    assert_eq("city",            d.city,            "ایزدشهر")
    assert_eq("area_type",       d.area_type,       "ساحلی")
    assert_eq("land_size",       d.land_size,       250.0)
    assert_eq("building_size",   d.building_size,   140.0)
    assert_eq("bedrooms",        d.bedrooms,        3)
    assert_eq("master_bedrooms", d.master_bedrooms, 1)
    assert_eq("price",           d.price,           18_000_000_000.0)
    assert_eq("has_roof_garden", d.has_roof_garden, 1)
    assert_contains("unknown line in description", d.description, "کنار دریاچه")

    section("6. Price in میلیون, no master bedroom (SAMPLE_6)")
    d = parse_villa_text(SAMPLE_6)
    assert_eq("price",           d.price,           1_200_000_000.0)
    assert_none("master_bedrooms None", d.master_bedrooms)
    assert_eq("bedrooms",        d.bedrooms,        2)

    section("7. Multiple unknown/free-form lines (SAMPLE_7)")
    d = parse_villa_text(SAMPLE_7)
    assert_eq("bedrooms",        d.bedrooms,        5)
    assert_eq("master_bedrooms", d.master_bedrooms, 3)
    assert_eq("price",           d.price,           45_000_000_000.0)
    assert_contains("free-form line 1 in description", d.description, "سونا خشک و بخار")
    assert_contains("free-form line 2 in description", d.description, "سیستم اتوماسیون هوشمند")
    assert_contains("free-form line 3 in description", d.description, "منطقه دربند کوه")
    assert_contains("free-form line 4 in description", d.description, "مجتمع ویلایی بسته")

    section("8. Price without قیمت label (plain میلیارد) (SAMPLE_9)")
    d = parse_villa_text(SAMPLE_9)
    assert_eq("price", d.price, 12_000_000_000.0)

    section("9. Digit-only bedrooms (SAMPLE_10)")
    d = parse_villa_text(SAMPLE_10)
    assert_eq("bedrooms",        d.bedrooms,        3)
    assert_eq("master_bedrooms", d.master_bedrooms, 1)
    assert_eq("city",            d.city,            "بابلسر")
    assert_eq("area_type",       d.area_type,       "ساحلی")

    # ── Test group 2: Database insertion ──────────────────────────────────────
    section("10. DB insertion — SAMPLE_1 (MV-701)")
    r = import_villa(parse_villa_text(SAMPLE_1))
    assert_true("success",        r.success, r.error or "")
    assert_eq("assigned code",    r.villa_code, "MV-701")
    assert_not_none("villa_id",   r.villa_id)
    row = get_villa_by_code("MV-701")
    assert_not_none("row in DB",       row)
    assert_eq("DB city",               row["city"],            "آمل")
    assert_eq("DB price",              row["price"],           15_000_000_000.0)
    assert_eq("DB master_bedrooms",    row["master_bedrooms"], 2)
    assert_contains("DB document_type","پروانه ساخت" in row["document_type"] and
                                       "سند تک برگ"  in row["document_type"] and "✓" or "✗", "✓")
    assert_contains("DB description",  row["description"], "دسترسی عالی")

    section("11. DB insertion — SAMPLE_2 (MV-702, coastal with flags)")
    r = import_villa(parse_villa_text(SAMPLE_2))
    assert_true("success",     r.success, r.error or "")
    row = get_villa_by_code("MV-702")
    assert_eq("DB has_pool",    row["has_pool"],    1)
    assert_eq("DB has_jacuzzi", row["has_jacuzzi"], 1)
    assert_eq("DB has_parking", row["has_parking"], 1)

    section("12. DB insertion — SAMPLE_3 (auto villa code)")
    d3 = parse_villa_text(SAMPLE_3)
    r3 = import_villa(d3)
    assert_true("success",             r3.success, r3.error or "")
    assert_not_none("auto-code assigned", r3.villa_code)
    assert_true("code starts with MV-", r3.villa_code.startswith("MV-"))
    row3 = get_villa_by_code(r3.villa_code)
    assert_not_none("row in DB",   row3)
    assert_eq("DB city",           row3["city"],       "سرخرود")
    assert_eq("DB price",          row3["price"],      850_000_000.0)
    assert_eq("DB has_storage",    row3["has_storage"],1)
    print(f"  {YELLOW}↳ Auto-generated code: {r3.villa_code}{RESET}")

    section("13. DB insertion — SAMPLE_7 (many unknown lines)")
    r7 = import_villa(parse_villa_text(SAMPLE_7))
    assert_true("success", r7.success, r7.error or "")
    row7 = get_villa_by_code("MV-705")
    assert_contains("DB description has free-form lines",
                    row7["description"], "سونا خشک و بخار")

    section("14. Duplicate villa code handling")
    r_dup = import_villa(parse_villa_text(SAMPLE_DUP))
    assert_true("success is False",        not r_dup.success)
    assert_not_none("error message set",   r_dup.error)
    assert_contains("error mentions code", r_dup.error, "MV-701")
    print(f"  {YELLOW}↳ Error: {r_dup.error}{RESET}")

    section("15. Auto-code is permanent (sequential, unique)")
    codes_before = set()
    for code_suffix in ["MV-706", "MV-707"]:
        row = get_villa_by_code(code_suffix)
        if row:
            codes_before.add(code_suffix)

    r9  = import_villa(parse_villa_text(SAMPLE_9))
    r10 = import_villa(parse_villa_text(SAMPLE_10))

    assert_true("r9 success",  r9.success,  r9.error or "")
    assert_true("r10 success", r10.success, r10.error or "")
    assert_true("codes are different", r9.villa_code != r10.villa_code,
                f"{r9.villa_code} vs {r10.villa_code}")
    assert_true("r9 code MV-706 or later",
                r9.villa_code.startswith("MV-"), r9.villa_code)
    print(f"  {YELLOW}↳ r9  → {r9.villa_code}{RESET}")
    print(f"  {YELLOW}↳ r10 → {r10.villa_code}{RESET}")

    # ── Summary ───────────────────────────────────────────────────────────────
    total = _pass + _fail
    print(f"\n{BOLD}{'═'*60}")
    if _fail == 0:
        print(f"  {GREEN}All {total} checks passed ✓{RESET}")
    else:
        print(f"  {GREEN}{_pass} passed{RESET}  {RED}{_fail} failed ✗{RESET}  of {total} total")
    print(f"{BOLD}{'═'*60}{RESET}\n")

    sys.exit(0 if _fail == 0 else 1)


if __name__ == "__main__":
    run()
