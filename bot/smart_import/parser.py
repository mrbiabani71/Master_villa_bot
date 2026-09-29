"""
Source-independent parser for Persian property text.

Input  : raw multi-line Persian string
Output : VillaData (no DB, no Telegram, no I/O)

Parsing strategy
----------------
Each non-empty line is tested against a priority chain of matchers.
The first matcher that fires claims the line; unmatched lines are
collected and appended to VillaData.description.

A single line may carry multiple pieces of info (e.g. bedroom +
master-bedroom); those are extracted in a single matcher call.

Non-exclusive matchers (boolean features, community/location status,
utilities) run on every line regardless of whether another matcher
already claimed it, since one line can carry multiple facts.
"""
from __future__ import annotations

import re
from .models import VillaData

# ── City → area_type table ────────────────────────────────────────────────────

CITY_AREA_MAP: dict[str, str] = {
    "محمودآباد": "ساحلی",
    "سرخرود":    "ساحلی",
    "ایزدشهر":   "ساحلی",
    "بابلسر":    "ساحلی",
    "فریدونکنار": "ساحلی",
    "عباس‌آباد": "ساحلی",
    "رامسر":     "ساحلی",
    "تنکابن":    "ساحلی",
    "چالوس":     "ساحلی",
    "نوشهر":     "ساحلی",
    "نور":       "جنگلی",
    "آمل":       "جنگلی",
    "چمستان":    "جنگلی",
    "کلاردشت":   "جنگلی",
    "رویان":     "جنگلی",
}

# ── Persian / Arabic digit normalisation ─────────────────────────────────────

_DIGIT_TABLE = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)

def _to_latin(text: str) -> str:
    return text.translate(_DIGIT_TABLE)

def _first_float(text: str) -> float | None:
    """Extract the first numeric value (int or decimal) from text."""
    m = re.search(r"[\d.]+", _to_latin(text))
    if not m:
        return None
    try:
        return float(m.group())
    except ValueError:
        return None

# ── Persian cardinal words → int ─────────────────────────────────────────────

_WORD_NUM: dict[str, int] = {
    "یک":   1, "دو":   2, "سه":   3, "چهار": 4, "پنج":  5,
    "شش":   6, "هفت":  7, "هشت":  8, "نه":   9, "ده":  10,
}

def _word_to_int(text: str) -> int | None:
    """Return the first Persian number word found in text, or digit if no word."""
    text = text.strip()
    # Longer words first to avoid "یک" matching inside "بیست‌ویک"
    for word in sorted(_WORD_NUM, key=len, reverse=True):
        if word in text:
            return _WORD_NUM[word]
    n = _first_float(text)
    return int(n) if n is not None else None

# ── Matcher helpers ───────────────────────────────────────────────────────────

def _match_villa_code(line: str) -> str | None:
    """MV-<digits>  anywhere in line."""
    m = re.search(r"\bMV-\d+\b", line, re.IGNORECASE)
    return m.group().upper() if m else None

def _match_city(line: str) -> tuple[str, str] | None:
    """Return (city, area_type) if city name found in line."""
    stripped = line.strip()
    for city, area in CITY_AREA_MAP.items():
        if city in stripped:
            return city, area
    return None

def _match_region(line: str) -> str | None:
    """
    Lines containing 'منطقه' — return the full line as the region description.
    e.g. "منطقه: شهرک دریایی" → "منطقه: شهرک دریایی"
    """
    if "منطقه" not in line:
        return None
    return line.strip()

def _match_villa_type(line: str) -> str | None:
    """
    Detect villa structural type.
    e.g. "ویلا دوبلکس", "یک طبقه", "نوساز", "کلنگی"
    """
    stripped = line.strip()
    villa_types = [
        "تریبلکس", "دوبلکس",
        "سه طبقه", "دو طبقه", "یک طبقه",
        "کلنگی", "نوساز", "بازسازی شده", "ویلایی",
    ]
    for vt in villa_types:
        if vt in stripped:
            return vt
    return None

def _match_facade(line: str) -> str | None:
    """
    Lines mentioning facade type — contains 'نما' (but not 'ویو' which is 'view').
    e.g. "نمای مدرن", "نما: سنگ و چوب"
    """
    stripped = line.strip()
    # "نمای" (facade's) and "نما" (facade) but exclude ویو-type lines
    if "نما" not in stripped:
        return None
    if "ویو" in stripped:
        return None
    return stripped

# Recognised land/building formats (flexible spacing, Persian/English digits):
#   land:      "220 زمین" | "220 متر زمین" | "زمین 220" | "متراژ زمین 220"
#   building:  "130 بنا"  | "130 متر بنا"  | "بنا 130"  | "زیربنا 130" | "130 متر زیربنا"
#
# "زیربنا" already contains "بنا" as a trailing substring, so a single set of
# "بنا"-based patterns covers both keyword variants without special-casing.
#
# Number-after-keyword is tried first so combined lines like "زمین 300 بنا 250"
# resolve each figure to the number immediately following its own keyword,
# rather than falling through to the number-before-keyword fallback.

_LAND_KEYWORD_THEN_NUMBER = re.compile(r"زمین\D{0,10}(\d+(?:\.\d+)?)")
_NUMBER_THEN_LAND_KEYWORD = re.compile(r"(\d+(?:\.\d+)?)\D{0,10}زمین")

_BUILDING_KEYWORD_THEN_NUMBER = re.compile(r"بنا\D{0,10}(\d+(?:\.\d+)?)")
_NUMBER_THEN_BUILDING_KEYWORD = re.compile(r"(\d+(?:\.\d+)?)\D{0,10}بنا")


def _match_land(line: str) -> float | None:
    """
    Lines like '220 زمین', '220 متر زمین', 'زمین 220', 'متراژ زمین 220', or
    emoji-prefixed '📐 220'. For combined lines ('زمین 300 بنا 250') the number
    immediately following 'زمین' is the land figure.
    """
    text = _to_latin(line)
    if "زمین" not in text and not text.startswith("📐"):
        return None

    m = _LAND_KEYWORD_THEN_NUMBER.search(text)
    if m:
        return float(m.group(1))
    m = _NUMBER_THEN_LAND_KEYWORD.search(text)
    if m:
        return float(m.group(1))
    if text.startswith("📐"):
        return _first_float(text)
    return None


def _match_building(line: str) -> float | None:
    """
    Lines like '130 بنا', '130 متر بنا', 'بنا 130', 'زیربنا 130',
    '130 متر زیربنا', or emoji-prefixed '🏠 130'. For combined lines
    ('زمین 300 بنا 250') the number immediately following 'بنا' (or
    'زیربنا', which contains 'بنا') is the building figure.
    """
    text = _to_latin(line)
    if "بنا" not in text and not text.startswith("🏠"):
        return None

    m = _BUILDING_KEYWORD_THEN_NUMBER.search(text)
    if m:
        return float(m.group(1))
    m = _NUMBER_THEN_BUILDING_KEYWORD.search(text)
    if m:
        return float(m.group(1))
    if text.startswith("🏠"):
        return _first_float(text)
    return None

def _match_bedrooms(line: str) -> dict | None:
    """
    Lines like 'سه خواب دو مستر', '3 خواب', 'دو مستر'.
    Returns dict with any of: bedrooms, master_bedrooms.
    """
    has_kh = "خواب" in line
    has_ms = "مستر" in line
    if not has_kh and not has_ms:
        return None

    result: dict[str, int] = {}

    if has_kh:
        # Text before خواب holds the count
        before_kh = line.split("خواب")[0]
        n = _word_to_int(before_kh)
        if n is not None:
            result["bedrooms"] = n

    if has_ms:
        # If both keywords: count is between خواب and مستر
        if has_kh:
            after_kh = line.split("خواب", 1)[1]
            before_ms = after_kh.split("مستر")[0]
        else:
            before_ms = line.split("مستر")[0]
        n = _word_to_int(before_ms)
        if n is not None:
            result["master_bedrooms"] = n

    return result if result else None

def _match_price(line: str) -> float | None:
    """
    Lines like 'قیمت 15 میلیارد', '800 میلیون', '1500000000'.
    Must contain قیمت OR میلیارد/میلیون to be claimed.
    """
    has_label  = "قیمت" in line
    has_milyard = "میلیارد" in line
    has_million = "میلیون" in line

    if not (has_label or has_milyard or has_million):
        return None

    text = _to_latin(line.replace("قیمت", "").strip())
    multiplier = 1
    if has_milyard:
        text = text.replace("میلیارد", "").strip()
        multiplier = 1_000_000_000
    elif has_million:
        text = text.replace("میلیون", "").strip()
        multiplier = 1_000_000

    n = _first_float(text)
    return n * multiplier if n is not None else None

# Document keywords — lines containing any of these are treated as document info
_DOC_KEYWORDS = [
    "سند", "پروانه", "قولنامه", "وقفی", "منگوله", "تک برگ", "تک‌برگ",
    "شخصی‌سازی", "شخصی سازی", "ملکی", "بنچاق",
]

def _match_document(line: str) -> bool:
    return any(kw in line for kw in _DOC_KEYWORDS)

# Feature keywords — boolean DB flags
_BOOL_FEATURES: list[tuple[str, str]] = [
    ("استخر",     "has_pool"),
    ("جکوزی",    "has_jacuzzi"),
    ("روف گاردن", "has_roof_garden"),
    ("روف‌گاردن", "has_roof_garden"),
    ("پارکینگ",  "has_parking"),
    ("انباری",   "has_storage"),
]

# Display-only features — matched but stored as text features, not DB booleans
_DISPLAY_FEATURE_KEYWORDS = [
    "شهرک", "دربند", "ویو دریا", "ویو جنگل", "محوطه سازی",
    "باربیکیو", "سونا", "آسانسور", "نگهبانی", "سیستم هوشمند",
    "اتوماسیون", "سقف کاذب", "کمد دیواری",
]

def _match_bool_features(line: str) -> dict[str, int] | None:
    flags: dict[str, int] = {}
    for kw, col in _BOOL_FEATURES:
        if kw in line:
            flags[col] = 1
    return flags if flags else None

def _match_display_feature(line: str) -> bool:
    return any(kw in line for kw in _DISPLAY_FEATURE_KEYWORDS)

# ── New non-exclusive matchers ────────────────────────────────────────────────

_LOCATION_STATUS_KEYWORDS = [
    "کنار دریا", "مشرف به دریا", "رو به دریا", "لب دریا",
    "کنار جنگل", "مشرف به جنگل", "داخل جنگل",
    "کنار رودخانه", "کنار تالاب",
    "کوهستانی", "ییلاقی",
]

def _match_location_status(line: str) -> str | None:
    """
    Detailed geographical position of the villa.
    Returns the matched keyword phrase, or the part after 'موقعیت:'.
    """
    stripped = line.strip()

    # Explicit label: "موقعیت: ساحلی" or "موقعیت ملک: …"
    if "موقعیت" in stripped:
        # Extract text after the colon / label
        for sep in (":", "ملک", "جغرافیایی"):
            if sep in stripped:
                after = stripped.split(sep, 1)[-1].strip()
                if after:
                    return after
        # No separator — return the whole line
        return stripped

    for kw in _LOCATION_STATUS_KEYWORDS:
        if kw in stripped:
            return kw

    return None

_COMMUNITY_STATUS_KEYWORDS = [
    # Negative / non-gated forms MUST come before the generic positive "شهرکی"
    # to prevent "غیرشهرکی" from being misclassified as "داخل شهرک".
    ("غیرشهرکی",   "خارج شهرک"),
    ("غیر شهرکی",  "خارج شهرک"),
    ("خارج شهرک",   "خارج شهرک"),
    ("بیرون شهرک",  "خارج شهرک"),
    ("بدون شهرک",   "خارج شهرک"),
    ("داخل شهرک",   "داخل شهرک"),
    ("درون شهرک",   "داخل شهرک"),
    ("شهرکی",       "داخل شهرک"),   # generic — must stay after negative forms
    ("خارج بافت",   "خارج از بافت"),
    ("داخل بافت",   "داخل بافت"),
]

def _match_community_status(line: str) -> str | None:
    """Community / gated-community status."""
    stripped = line.strip()
    for kw, normalized in _COMMUNITY_STATUS_KEYWORDS:
        if kw in stripped:
            return normalized
    return None

def _match_utility_line(line: str) -> bool:
    """
    Infrastructure / utility connection lines.
    Requires 'انشعاب' OR two of {برق, آب, گاز} to avoid false positives.
    """
    if "انشعاب" in line:
        return True
    infra = ["برق", "آب", "گاز"]
    count = sum(1 for kw in infra if kw in line)
    return count >= 2

# ── Main parse function ───────────────────────────────────────────────────────

def parse_villa_text(text: str) -> VillaData:
    """
    Parse a raw Persian villa listing into a VillaData object.

    Lines are processed top-to-bottom; each is tried against the
    matcher priority chain.  Unrecognised lines are appended to
    VillaData.description separated by newlines.

    Non-exclusive matchers (bool features, community/location status,
    utilities) run on every line and do not prevent other matchers.

    This function is pure: no I/O, no DB, no Telegram.
    """
    data = VillaData(raw_text=text)
    unknown_lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        claimed = False

        # 1. Villa code
        if data.villa_code is None:
            code = _match_villa_code(line)
            if code:
                data.villa_code = code
                claimed = True

        # 2. City (only first match)
        if not claimed and data.city is None:
            city_match = _match_city(line)
            if city_match:
                data.city, data.area_type = city_match
                claimed = True

        # 3. Region (منطقه) — exclusive; only if city didn't claim this line
        if not claimed and data.region is None:
            region = _match_region(line)
            if region:
                data.region = region
                claimed = True

        # 4. Villa type — exclusive
        if not claimed and data.villa_type is None:
            vt = _match_villa_type(line)
            if vt:
                data.villa_type = vt
                claimed = True

        # 5. Facade — exclusive
        if not claimed and data.facade is None:
            fcd = _match_facade(line)
            if fcd:
                data.facade = fcd
                claimed = True

        # 6. Land area (non-exclusive: may share a line with building)
        if data.land_size is None:
            land = _match_land(line)
            if land is not None:
                data.land_size = land
                claimed = True

        # 7. Building area (non-exclusive: may share a line with land)
        if data.building_size is None:
            bld = _match_building(line)
            if bld is not None:
                data.building_size = bld
                claimed = True

        # 8. Bedrooms / master bedrooms
        if not claimed:
            rooms = _match_bedrooms(line)
            if rooms:
                if "bedrooms" in rooms and data.bedrooms is None:
                    data.bedrooms = rooms["bedrooms"]
                if "master_bedrooms" in rooms and data.master_bedrooms is None:
                    data.master_bedrooms = rooms["master_bedrooms"]
                claimed = True

        # 9. Price
        if not claimed and data.price is None:
            price = _match_price(line)
            if price is not None:
                data.price = price
                claimed = True

        # ── Non-exclusive matchers ─────────────────────────────────────────────
        # These run on every line (regardless of claimed) because one line can
        # contain multiple facts.

        # 10. Boolean feature flags (has_pool, etc.)
        bool_flags = _match_bool_features(line)
        if bool_flags:
            for col, val in bool_flags.items():
                setattr(data, col, val)
            claimed = True

        # 11. Community status (داخل/خارج شهرک)
        comm = _match_community_status(line)
        if comm and data.community_status is None:
            data.community_status = comm
            claimed = True

        # 12. Location status (کنار دریا, مشرف به جنگل, …)
        loc = _match_location_status(line)
        if loc and data.location_status is None:
            data.location_status = loc
            claimed = True

        # 13. Utility connections (انشعاب, برق+آب+گاز)
        if _match_utility_line(line):
            data.utilities.append(line.strip())
            claimed = True

        # ── Exclusive tail matchers ────────────────────────────────────────────

        # 14. Document info
        if not claimed and _match_document(line):
            data.documents.append(line)
            claimed = True

        # 15. Display-only features
        if not claimed and _match_display_feature(line):
            data.features.append(line)
            claimed = True

        # 16. Unknown — collect for description
        if not claimed:
            unknown_lines.append(line)

    # Build description: explicit text + display features + unmatched lines.
    # Display features are informational and must be preserved here too.
    parts: list[str] = []
    if data.description:
        parts.append(data.description)
    if data.features:
        parts.extend(data.features)
    if unknown_lines:
        parts.extend(unknown_lines)
    data.description = "\n".join(parts).strip()

    return data
