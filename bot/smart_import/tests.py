"""
Smart Import — comprehensive validation suite.

Run from the bot/ directory:
    python3 -m smart_import.tests

Sections
────────
A  Price formats          (میلیارد / میلیون / decimal / no label / plain int)
B  Bedroom formats        (Persian words / digits / master bedrooms / edge cases)
C  Area formats           (land & building — keyword variants / units)
D  Villa code detection   (standard / lowercase / mid-text / auto-generate)
E  Missing optional fields (price absent / city absent / both absent / bare post)
F  Unknown lines → description  (real free-form lines, none discarded)
G  Boolean feature flags  (all 5 flags, combinations, same-line extraction)
H  Document types         (multiple docs / keyword variants)
I  Full real-world posts  (10 complete listings, mixed formats)
J  Database insertion     (fields verified round-trip in DB)
K  Duplicate code handling (same code twice / re-import same text)
L  Auto-code generation   (sequential, unique, permanent format)
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import init_db, get_villa_by_code, get_connection
from smart_import.parser import parse_villa_text
from smart_import.importer import import_villa

# ── ANSI helpers ──────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

_pass = _fail = 0
_section_pass = _section_fail = 0


def ok(label: str, detail: str = "") -> None:
    global _pass, _section_pass
    _pass += 1; _section_pass += 1
    print(f"  {GREEN}✓{RESET} {label}" + (f"  {YELLOW}({detail}){RESET}" if detail else ""))


def fail(label: str, detail: str = "") -> None:
    global _fail, _section_fail
    _fail += 1; _section_fail += 1
    print(f"  {RED}✗ FAIL{RESET} {label}" + (f"  → {detail}" if detail else ""))


def section(title: str) -> None:
    global _section_pass, _section_fail
    _section_pass = _section_fail = 0
    pad = max(1, 54 - len(title))
    print(f"\n{BOLD}{CYAN}── {title} {'─' * pad}{RESET}")


def section_done() -> None:
    c = _section_pass + _section_fail
    status = f"{GREEN}all {c} passed{RESET}" if not _section_fail else \
             f"{GREEN}{_section_pass} passed{RESET}  {RED}{_section_fail} failed{RESET}"
    print(f"     {status}")


def eq(label, got, expected):
    (ok if got == expected else fail)(label, f"got {got!r}, expected {expected!r}")


def not_none(label, got):
    (ok if got is not None else fail)(label, "got None" if got is None else repr(got))


def is_none(label, got):
    (ok if got is None else fail)(label, f"expected None, got {got!r}")


def contains(label, haystack: str, needle: str):
    (ok if needle in haystack else fail)(label,
        f"{needle!r} not in {haystack!r}" if needle not in haystack else f"…{needle}…")


def true(label, cond: bool, detail: str = ""):
    (ok if cond else fail)(label, detail)


def false(label, cond: bool, detail: str = ""):
    (ok if not cond else fail)(label, detail or "expected False")


# ─────────────────────────────────────────────────────────────────────────────
#  Test data — all villa codes use MV-8xx range to avoid collisions
# ─────────────────────────────────────────────────────────────────────────────

_TEST_CODE_PREFIX = "MV-8"   # all fixture codes start with this


def _cleanup():
    """Remove all test fixtures so the suite is fully repeatable."""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM villas WHERE villa_code LIKE 'MV-8%'"
        )
        conn.commit()
    print(f"  {YELLOW}(test fixtures cleaned — MV-8xx range){RESET}")


# ═════════════════════════════════════════════════════════════════════════════
#  A  PRICE FORMATS
# ═════════════════════════════════════════════════════════════════════════════

def test_prices():
    section("A  Price Formats")

    cases = [
        # (description, text_snippet,  expected_price)
        ("Persian digits + میلیارد",
         "📍 نور\nقیمت ۱۵ میلیارد",               15_000_000_000.0),
        ("Western digits + میلیارد",
         "📍 آمل\nقیمت 15 میلیارد",                15_000_000_000.0),
        ("Decimal Persian + میلیارد",
         "آمل\nقیمت ۱۲.۵ میلیارد",                12_500_000_000.0),
        ("Decimal Western + میلیارد",
         "آمل\nقیمت 12.5 میلیارد",                12_500_000_000.0),
        ("Persian digits + میلیون",
         "نور\nقیمت ۸۵۰ میلیون",                  850_000_000.0),
        ("Western digits + میلیون",
         "نور\nقیمت 850 میلیون",                   850_000_000.0),
        ("No قیمت label — plain میلیارد",
         "آمل\n18 میلیارد",                         18_000_000_000.0),
        ("No قیمت label — Persian میلیارد",
         "آمل\n۱۸ میلیارد",                         18_000_000_000.0),
        ("No قیمت label — میلیون",
         "نور\n1200 میلیون",                        1_200_000_000.0),
        ("Price missing → None",
         "MV-899\nآمل\n200 زمین",                  None),
    ]

    for desc, text, expected in cases:
        d = parse_villa_text(text)
        eq(desc, d.price, expected)

    section_done()


# ═════════════════════════════════════════════════════════════════════════════
#  B  BEDROOM / MASTER BEDROOM FORMATS
# ═════════════════════════════════════════════════════════════════════════════

def test_bedrooms():
    section("B  Bedroom & Master Bedroom Formats")

    # (text,  expected_bedrooms,  expected_master_bedrooms)
    cases = [
        ("Persian word bed + Persian word master",
         "سه خواب دو مستر",    3, 2),
        ("Persian word bed only",
         "دو خواب",             2, None),
        ("Western digit bed + Western digit master",
         "4 خواب 2 مستر",      4, 2),
        ("Western digit bed only",
         "3 خواب",              3, None),
        ("Persian digit bed",
         "۳ خواب",              3, None),
        ("Persian digit bed + master",
         "۴ خواب ۲ مستر",      4, 2),
        ("One bedroom Persian",
         "یک خواب",             1, None),
        ("Five bed three master",
         "پنج خواب سه مستر",   5, 3),
        ("No bedroom line → both None",
         "آمل\nقیمت 5 میلیارد", None, None),
        ("Master without bedroom",
         "دو مستر",             None, 2),
    ]

    for desc, text, exp_bed, exp_master in cases:
        d = parse_villa_text(text)
        eq(f"{desc} — bedrooms",        d.bedrooms,        exp_bed)
        eq(f"{desc} — master_bedrooms", d.master_bedrooms, exp_master)

    section_done()


# ═════════════════════════════════════════════════════════════════════════════
#  C  AREA FORMATS  (land & building)
# ═════════════════════════════════════════════════════════════════════════════

def test_areas():
    section("C  Land & Building Area Formats")

    land_cases = [
        ("number before زمین",    "300 زمین",          300.0),
        ("number after زمین",     "زمین 250",           250.0),
        ("متراژ زمین + number",   "متراژ زمین ۱۸۰",   180.0),
        ("number + متر زمین",     "200 متر زمین",      200.0),
        ("Persian digit زمین",    "۳۵۰ زمین",          350.0),
        ("No land line → None",   "آمل\nقیمت 5 میلیارد", None),
    ]

    for desc, text, expected in land_cases:
        d = parse_villa_text(text)
        eq(f"land — {desc}", d.land_size, expected)

    bld_cases = [
        ("number before بنا",    "150 بنا",           150.0),
        ("number after بنا",     "بنا 120",            120.0),
        ("زیربنا variant",       "زیربنا ۱۴۰ متر",   140.0),
        ("Persian digit بنا",    "۲۰۰ بنا",           200.0),
        ("No building → None",   "آمل\nقیمت 5 میلیارد", None),
    ]

    for desc, text, expected in bld_cases:
        d = parse_villa_text(text)
        eq(f"building — {desc}", d.building_size, expected)

    section_done()


# ═════════════════════════════════════════════════════════════════════════════
#  D  VILLA CODE DETECTION
# ═════════════════════════════════════════════════════════════════════════════

def test_villa_codes():
    section("D  Villa Code Detection")

    eq("Standard MV-XXX on first line",
       parse_villa_text("MV-801\nآمل\nقیمت 5 میلیارد").villa_code, "MV-801")

    eq("Lowercase mv-xxx → normalised uppercase",
       parse_villa_text("mv-802\nآمل\nقیمت 5 میلیارد").villa_code, "MV-802")

    eq("Code buried mid-text",
       parse_villa_text("آمل\nMV-803\nقیمت 5 میلیارد").villa_code, "MV-803")

    eq("Code on last line",
       parse_villa_text("آمل\nقیمت 5 میلیارد\nMV-804").villa_code, "MV-804")

    eq("Code with extra spaces",
       parse_villa_text("  MV-805  \nآمل\nقیمت 5 میلیارد").villa_code, "MV-805")

    is_none("No code in text → None (auto-assign later)",
            parse_villa_text("آمل\nقیمت 5 میلیارد").villa_code)

    is_none("Fake pattern MV- without digits → no match",
            parse_villa_text("آمل\nMV-\nقیمت 5 میلیارد").villa_code)

    section_done()


# ═════════════════════════════════════════════════════════════════════════════
#  E  MISSING OPTIONAL FIELDS
# ═════════════════════════════════════════════════════════════════════════════

def test_missing_fields():
    section("E  Missing Optional Fields")

    # Price absent — parser still returns VillaData with price=None
    d = parse_villa_text("MV-810\nآمل\n200 زمین\n150 بنا\nسه خواب")
    is_none("price absent → None",        d.price)
    eq("city still extracted",            d.city, "آمل")
    eq("land still extracted",            d.land_size, 200.0)

    # City absent
    d = parse_villa_text("MV-811\n200 زمین\nسه خواب\nقیمت 8 میلیارد")
    is_none("city absent → None",         d.city)
    is_none("area_type absent → None",    d.area_type)
    eq("price still extracted",           d.price, 8_000_000_000.0)

    # Both city and price absent
    d = parse_villa_text("MV-812\n300 زمین\n200 بنا\nچهار خواب")
    is_none("city+price both absent",     d.city)
    is_none("price stays None",           d.price)
    eq("bedrooms still extracted",        d.bedrooms, 4)

    # Only code (everything else absent)
    d = parse_villa_text("MV-813")
    eq("code-only: villa_code",           d.villa_code, "MV-813")
    is_none("code-only: city None",       d.city)
    is_none("code-only: price None",      d.price)
    is_none("code-only: land None",       d.land_size)
    is_none("code-only: bedrooms None",   d.bedrooms)
    eq("code-only: description empty",    d.description, "")

    # Bare minimal: city + price only
    d = parse_villa_text("نور\nقیمت 5 میلیارد")
    eq("bare minimal: city",              d.city, "نور")
    eq("bare minimal: price",             d.price, 5_000_000_000.0)
    is_none("bare minimal: land None",    d.land_size)
    is_none("bare minimal: bedrooms None",d.bedrooms)

    section_done()


# ═════════════════════════════════════════════════════════════════════════════
#  F  UNKNOWN LINES → DESCRIPTION
# ═════════════════════════════════════════════════════════════════════════════

def test_unknown_lines():
    section("F  Unknown Lines Preserved in Description")

    text = """MV-820
آمل
350 زمین
220 بنا
چهار خواب دو مستر
سند تک برگ
قیمت 18 میلیارد
دسترسی عالی به جاده اصلی
فاصله ۵ دقیقه‌ای از دریا
بازسازی کامل در سال ۱۴۰۲
آشپزخانه اوپن با کابینت‌های MDF
کف سرامیک ایتالیایی در تمام اتاق‌ها
تراس بزرگ با دید رو به جنگل"""

    d = parse_villa_text(text)
    # Known fields consumed
    eq("code",          d.villa_code,   "MV-820")
    eq("city",          d.city,         "آمل")
    eq("area_type",     d.area_type,    "جنگلی")
    eq("land",          d.land_size,    350.0)
    eq("building",      d.building_size,220.0)
    eq("bedrooms",      d.bedrooms,     4)
    eq("master",        d.master_bedrooms, 2)
    eq("price",         d.price,        18_000_000_000.0)

    # All 6 free-form lines must survive in description
    for line in [
        "دسترسی عالی به جاده اصلی",
        "فاصله ۵ دقیقه‌ای از دریا",
        "بازسازی کامل در سال ۱۴۰۲",
        "آشپزخانه اوپن با کابینت‌های MDF",
        "کف سرامیک ایتالیایی در تمام اتاق‌ها",
        "تراس بزرگ با دید رو به جنگل",
    ]:
        contains(f"unknown line preserved: {line[:20]}…", d.description, line)

    # Zero unknown lines — description should be empty (only known fields)
    d2 = parse_villa_text("MV-821\nآمل\nقیمت 5 میلیارد")
    eq("no unknowns → description empty", d2.description, "")

    # Single unknown line
    d3 = parse_villa_text("MV-822\nنور\nقیمت 3 میلیارد\nیک خط ناشناخته")
    eq("single unknown line in description",
       d3.description, "یک خط ناشناخته")

    section_done()


# ═════════════════════════════════════════════════════════════════════════════
#  G  BOOLEAN FEATURE FLAGS
# ═════════════════════════════════════════════════════════════════════════════

def test_feature_flags():
    section("G  Boolean Feature Flags")

    # All 5 flags on separate lines
    d = parse_villa_text("""آمل
استخر
جکوزی
روف گاردن
پارکینگ
انباری
قیمت 10 میلیارد""")
    eq("has_pool",        d.has_pool,       1)
    eq("has_jacuzzi",     d.has_jacuzzi,    1)
    eq("has_roof_garden", d.has_roof_garden,1)
    eq("has_parking",     d.has_parking,    1)
    eq("has_storage",     d.has_storage,    1)

    # Flags absent
    d2 = parse_villa_text("آمل\nقیمت 5 میلیارد")
    eq("no flags: has_pool=0",        d2.has_pool,       0)
    eq("no flags: has_jacuzzi=0",     d2.has_jacuzzi,    0)
    eq("no flags: has_roof_garden=0", d2.has_roof_garden,0)
    eq("no flags: has_parking=0",     d2.has_parking,    0)
    eq("no flags: has_storage=0",     d2.has_storage,    0)

    # Mixed: pool + parking only
    d3 = parse_villa_text("آمل\nاستخر\nپارکینگ\nقیمت 8 میلیارد")
    eq("mixed: has_pool=1",    d3.has_pool,   1)
    eq("mixed: has_parking=1", d3.has_parking,1)
    eq("mixed: has_jacuzzi=0", d3.has_jacuzzi,0)
    eq("mixed: has_storage=0", d3.has_storage,0)

    # Hyphenated روف‌گاردن variant
    d4 = parse_villa_text("آمل\nروف‌گاردن\nقیمت 7 میلیارد")
    eq("روف‌گاردن hyphenated variant", d4.has_roof_garden, 1)

    section_done()


# ═════════════════════════════════════════════════════════════════════════════
#  H  DOCUMENT TYPES
# ═════════════════════════════════════════════════════════════════════════════

def test_documents():
    section("H  Document Types")

    # Single document
    d = parse_villa_text("آمل\nسند تک برگ\nقیمت 5 میلیارد")
    true("single doc in list",  "سند تک برگ" in d.documents)
    eq("doc list length",        len(d.documents), 1)

    # Multiple documents
    d2 = parse_villa_text("آمل\nپروانه ساخت\nسند تک برگ\nقیمت 5 میلیارد")
    true("doc 1: پروانه ساخت",  "پروانه ساخت" in d2.documents)
    true("doc 2: سند تک برگ",   "سند تک برگ"  in d2.documents)
    eq("two docs in list",        len(d2.documents), 2)

    # قولنامه
    d3 = parse_villa_text("آمل\nقولنامه\nقیمت 3 میلیارد")
    true("قولنامه detected",     "قولنامه" in d3.documents)

    # منگوله
    d4 = parse_villa_text("آمل\nسند منگوله‌دار\nقیمت 4 میلیارد")
    true("منگوله keyword",        any("منگوله" in doc for doc in d4.documents))

    # No document → empty list
    d5 = parse_villa_text("آمل\nقیمت 5 میلیارد")
    eq("no doc → empty list",    d5.documents, [])

    section_done()


# ═════════════════════════════════════════════════════════════════════════════
#  I  FULL REAL-WORLD POSTS  (10 complete listings)
# ═════════════════════════════════════════════════════════════════════════════

FULL_POSTS = [
    # ── 1 ──────────────────────────────────────────────────────────────────
    ("I-1: Forest villa, full template, Persian digits",
     """MV-830
آمل
۲۱۰ زمین
۱۶۰ بنا
سه خواب دو مستر
پروانه ساخت
سند تک برگ
شهرک خصوصی
قیمت ۱۵ میلیارد""",
     dict(villa_code="MV-830", city="آمل", area_type="جنگلی",
          land_size=210.0, building_size=160.0,
          bedrooms=3, master_bedrooms=2,
          price=15_000_000_000.0,
          docs=["پروانه ساخت", "سند تک برگ"])),

    # ── 2 ──────────────────────────────────────────────────────────────────
    ("I-2: Coastal villa, Western digits, feature flags",
     """MV-831
محمودآباد
350 زمین
200 بنا
4 خواب 2 مستر
سند تک برگ
استخر
جکوزی
پارکینگ
قیمت 22 میلیارد""",
     dict(villa_code="MV-831", city="محمودآباد", area_type="ساحلی",
          land_size=350.0, building_size=200.0,
          bedrooms=4, master_bedrooms=2,
          price=22_000_000_000.0,
          has_pool=1, has_jacuzzi=1, has_parking=1)),

    # ── 3 ──────────────────────────────────────────────────────────────────
    ("I-3: No villa code, minimal info, auto-assign expected",
     """سرخرود
120 زمین
90 بنا
دو خواب
قولنامه
قیمت 850 میلیون
انباری""",
     dict(villa_code=None, city="سرخرود", area_type="ساحلی",
          land_size=120.0, building_size=90.0,
          bedrooms=2, master_bedrooms=None,
          price=850_000_000.0, has_storage=1)),

    # ── 4 ──────────────────────────────────────────────────────────────────
    ("I-4: Decimal price, rooftop garden, ایزدشهر",
     """MV-832
ایزدشهر
250 زمین
140 بنا
سه خواب یک مستر
سند منگوله‌دار
روف گاردن
قیمت 18.5 میلیارد
کنار دریا، دید آزاد""",
     dict(villa_code="MV-832", city="ایزدشهر", area_type="ساحلی",
          land_size=250.0, building_size=140.0,
          bedrooms=3, master_bedrooms=1,
          price=18_500_000_000.0, has_roof_garden=1,
          desc_contains=["کنار دریا"])),

    # ── 5 ──────────────────────────────────────────────────────────────────
    ("I-5: چمستان forest, میلیون price, زیربنا keyword",
     """MV-833
چمستان
200 زمین
زیربنا ۱۳۰
دو خواب
پروانه ساخت
قیمت 1200 میلیون""",
     dict(villa_code="MV-833", city="چمستان", area_type="جنگلی",
          land_size=200.0, building_size=130.0,
          bedrooms=2, master_bedrooms=None,
          price=1_200_000_000.0)),

    # ── 6 ──────────────────────────────────────────────────────────────────
    ("I-6: نور, large villa, many unknowns preserved",
     """MV-834
نور
500 زمین
300 بنا
پنج خواب سه مستر
سند تک برگ
استخر
سونا خشک و بخار
سیستم هوشمند خانه
محوطه‌سازی لاکچری
قیمت 45 میلیارد""",
     dict(villa_code="MV-834", city="نور", area_type="جنگلی",
          land_size=500.0, building_size=300.0,
          bedrooms=5, master_bedrooms=3,
          price=45_000_000_000.0, has_pool=1,
          desc_contains=["سونا خشک و بخار", "سیستم هوشمند خانه"])),

    # ── 7 ──────────────────────────────────────────────────────────────────
    ("I-7: بابلسر, digit bedrooms, price without label",
     """MV-835
بابلسر
180 زمین
120 بنا
3 خواب 1 مستر
سند شخصی
6 میلیارد""",
     dict(villa_code="MV-835", city="بابلسر", area_type="ساحلی",
          land_size=180.0, building_size=120.0,
          bedrooms=3, master_bedrooms=1,
          price=6_000_000_000.0)),

    # ── 8 ──────────────────────────────────────────────────────────────────
    ("I-8: کلاردشت, all 5 feature flags, mixed digits",
     """MV-836
کلاردشت
۴۰۰ زمین
250 بنا
چهار خواب دو مستر
سند تک برگ
استخر
جکوزی
روف‌گاردن
پارکینگ
انباری
قیمت ۳۵ میلیارد""",
     dict(villa_code="MV-836", city="کلاردشت", area_type="جنگلی",
          land_size=400.0, building_size=250.0,
          bedrooms=4, master_bedrooms=2,
          price=35_000_000_000.0,
          has_pool=1, has_jacuzzi=1, has_roof_garden=1,
          has_parking=1, has_storage=1)),

    # ── 9 ──────────────────────────────────────────────────────────────────
    ("I-9: رامسر, price missing, description from unknowns",
     """MV-837
رامسر
300 زمین
180 بنا
سه خواب
پروانه ساخت
مجاور پارک جنگلی
ویو کوه از تراس""",
     dict(villa_code="MV-837", city="رامسر", area_type="ساحلی",
          land_size=300.0, building_size=180.0,
          bedrooms=3, price=None,
          desc_contains=["مجاور پارک جنگلی", "ویو کوه از تراس"])),

    # ── 10 ─────────────────────────────────────────────────────────────────
    ("I-10: Bare minimal — city + price, everything else None",
     """نور
قیمت 5 میلیارد""",
     dict(villa_code=None, city="نور", area_type="جنگلی",
          land_size=None, building_size=None,
          bedrooms=None, master_bedrooms=None,
          price=5_000_000_000.0)),
]


def test_full_posts():
    section("I  Full Real-World Posts (10 listings)")

    for title, text, expected in FULL_POSTS:
        d = parse_villa_text(text)
        print(f"\n  {BOLD}» {title}{RESET}")
        for field, exp_val in expected.items():
            if field == "docs":
                for doc in exp_val:
                    true(f"  doc '{doc}'", doc in d.documents)
            elif field == "desc_contains":
                for phrase in exp_val:
                    contains(f"  desc has '{phrase[:20]}'", d.description, phrase)
            else:
                got = getattr(d, field, "MISSING")
                eq(f"  {field}", got, exp_val)

    section_done()


# ═════════════════════════════════════════════════════════════════════════════
#  J  DATABASE INSERTION — round-trip field verification
# ═════════════════════════════════════════════════════════════════════════════

def test_db_insertion():
    section("J  Database Insertion — Round-Trip Verification")

    # --- J1: full post ---
    text_j1 = """MV-840
آمل
210 زمین
160 بنا
سه خواب دو مستر
پروانه ساخت
سند تک برگ
استخر
قیمت 15 میلیارد
ویلای لوکس نزدیک جنگل"""
    r = import_villa(parse_villa_text(text_j1))
    true("J1 insert success",          r.success, r.error or "")
    eq("J1 assigned code",             r.villa_code, "MV-840")
    not_none("J1 villa_id",            r.villa_id)

    row = get_villa_by_code("MV-840")
    not_none("J1 row exists in DB",    row)
    eq("J1 DB city",                   row["city"],            "آمل")
    eq("J1 DB area_type",              row["area_type"],       "جنگلی")
    eq("J1 DB land_size",              row["land_size"],       210.0)
    eq("J1 DB building_size",          row["building_size"],   160.0)
    eq("J1 DB bedrooms",               row["bedrooms"],        3)
    eq("J1 DB master_bedrooms",        row["master_bedrooms"], 2)
    eq("J1 DB price",                  row["price"],           15_000_000_000.0)
    eq("J1 DB has_pool",               row["has_pool"],        1)
    eq("J1 DB has_jacuzzi",            row["has_jacuzzi"],     0)
    contains("J1 DB document_type",    row["document_type"],   "پروانه ساخت")
    contains("J1 DB document_type",    row["document_type"],   "سند تک برگ")
    contains("J1 DB description",      row["description"],     "ویلای لوکس نزدیک جنگل")
    eq("J1 DB status",                 row["status"],          "active")

    # --- J2: feature flags round-trip ---
    text_j2 = """MV-841
محمودآباد
استخر
جکوزی
روف گاردن
پارکینگ
انباری
قیمت 20 میلیارد"""
    r2 = import_villa(parse_villa_text(text_j2))
    true("J2 insert success",          r2.success, r2.error or "")
    row2 = get_villa_by_code("MV-841")
    eq("J2 DB has_pool",       row2["has_pool"],       1)
    eq("J2 DB has_jacuzzi",    row2["has_jacuzzi"],    1)
    eq("J2 DB has_roof_garden",row2["has_roof_garden"],1)
    eq("J2 DB has_parking",    row2["has_parking"],    1)
    eq("J2 DB has_storage",    row2["has_storage"],    1)

    # --- J3: price in میلیون ---
    text_j3 = "MV-842\nنور\n800 میلیون"
    r3 = import_villa(parse_villa_text(text_j3))
    true("J3 insert success",          r3.success, r3.error or "")
    eq("J3 DB price (میلیون)",        get_villa_by_code("MV-842")["price"], 800_000_000.0)

    # --- J4: nullable fields stored correctly ---
    text_j4 = "MV-843\nنور\nقیمت 3 میلیارد"
    r4 = import_villa(parse_villa_text(text_j4))
    true("J4 insert success",          r4.success, r4.error or "")
    row4 = get_villa_by_code("MV-843")
    true("J4 DB land_size is None or 0",   row4["land_size"]    is None)
    true("J4 DB building_size is None or 0", row4["building_size"] is None)
    true("J4 DB bedrooms is None or 0",    row4["bedrooms"]     is None)
    true("J4 DB master_bedrooms=0",        row4["master_bedrooms"] in (0, None))

    section_done()


# ═════════════════════════════════════════════════════════════════════════════
#  K  DUPLICATE HANDLING
# ═════════════════════════════════════════════════════════════════════════════

def test_duplicates():
    section("K  Duplicate Code Handling")

    base_text = "MV-850\nآمل\nقیمت 10 میلیارد"

    # First insert — must succeed
    r1 = import_villa(parse_villa_text(base_text))
    true("first insert succeeds",           r1.success, r1.error or "")
    eq("first insert: correct code",        r1.villa_code, "MV-850")

    # Second insert — same code → must fail
    r2 = import_villa(parse_villa_text(base_text))
    false("second insert fails (duplicate)", r2.success)
    not_none("error message populated",      r2.error)
    contains("error mentions the code",      r2.error, "MV-850")
    is_none("no villa_id on failure",        r2.villa_id)
    print(f"    {YELLOW}↳ Duplicate error: {r2.error}{RESET}")

    # Different text, same code — still rejected
    r3 = import_villa(parse_villa_text("MV-850\nنور\nقیمت 99 میلیارد"))
    false("different text, same code → rejected", r3.success)

    # Different code — must succeed
    r4 = import_villa(parse_villa_text("MV-851\nآمل\nقیمت 10 میلیارد"))
    true("different code → accepted",        r4.success, r4.error or "")

    # importer mode field is set correctly
    eq("create mode label on success",       r1.mode, "create")
    eq("create mode label on failure",       r2.mode, "create")

    section_done()


# ═════════════════════════════════════════════════════════════════════════════
#  L  AUTO-CODE GENERATION
# ═════════════════════════════════════════════════════════════════════════════

def test_auto_codes():
    section("L  Auto-Code Generation")

    no_code_texts = [
        "آمل\n200 زمین\nقیمت 5 میلیارد",
        "نور\n150 زمین\nقیمت 3 میلیارد",
        "محمودآباد\n300 زمین\nقیمت 12 میلیارد",
    ]

    assigned: list[str] = []
    for i, text in enumerate(no_code_texts, 1):
        d = parse_villa_text(text)
        is_none(f"auto-{i}: parser returns villa_code=None", d.villa_code)
        r = import_villa(d)
        true(f"auto-{i}: insert succeeds",        r.success, r.error or "")
        not_none(f"auto-{i}: code assigned",       r.villa_code)
        true(f"auto-{i}: code starts MV-",         r.villa_code.startswith("MV-"))
        true(f"auto-{i}: numeric suffix",
             r.villa_code.split("-")[1].isdigit())
        assigned.append(r.villa_code)
        print(f"    {YELLOW}↳ auto-{i} → {r.villa_code}{RESET}")

    # All three must be unique
    eq("all 3 auto-codes unique",  len(set(assigned)), 3)

    # Codes are strictly increasing
    nums = [int(c.split("-")[1]) for c in assigned]
    true("auto-codes are sequential",  nums == sorted(nums),
         f"{nums}")

    # Re-importing same text with explicit MV code still works
    r_explicit = import_villa(parse_villa_text("MV-860\nنور\nقیمت 1 میلیارد"))
    true("explicit code after auto-codes works", r_explicit.success, r_explicit.error or "")
    eq("explicit code preserved",               r_explicit.villa_code, "MV-860")

    # Auto-code does NOT conflict with explicit codes already in DB
    next_auto_d = parse_villa_text("چمستان\nقیمت 2 میلیارد")
    r_next = import_villa(next_auto_d)
    true("auto after explicit: success",        r_next.success, r_next.error or "")
    true("auto after explicit: not MV-860",     r_next.villa_code != "MV-860")
    print(f"    {YELLOW}↳ next auto after explicit → {r_next.villa_code}{RESET}")

    section_done()


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═════════════════════════════════════════════════════════════════════════════

def run():
    print(f"\n{BOLD}{'═' * 62}")
    print("  Smart Import — Comprehensive Validation Suite")
    print(f"{'═' * 62}{RESET}")

    init_db()
    _cleanup()

    test_prices()
    test_bedrooms()
    test_areas()
    test_villa_codes()
    test_missing_fields()
    test_unknown_lines()
    test_feature_flags()
    test_documents()
    test_full_posts()
    test_db_insertion()
    test_duplicates()
    test_auto_codes()

    total = _pass + _fail
    print(f"\n{BOLD}{'═' * 62}")
    if _fail == 0:
        print(f"  {GREEN}✓  All {total} checks passed{RESET}")
    else:
        pct = int(_pass / total * 100) if total else 0
        print(f"  {GREEN}{_pass} passed{RESET}  {RED}{_fail} failed{RESET}"
              f"  of {total} total  ({pct}%)")

        print(f"\n  {RED}Failed checks:{RESET}")
        # Re-run in quiet mode is not needed — fails printed inline above
    print(f"{BOLD}{'═' * 62}{RESET}\n")

    sys.exit(0 if _fail == 0 else 1)


if __name__ == "__main__":
    run()
