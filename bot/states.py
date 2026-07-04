# ── Admin: villa registration states ──────────────────────────────────────────
(
    CITY,
    AREA_TYPE,
    PRICE,
    LAND_SIZE,
    BUILDING_SIZE,
    BEDROOMS,
    VILLA_TYPE,
    FEATURES,
    DOCUMENT_TYPE,
    PHOTOS,
    VIDEO,
    LOCATION,
    DESCRIPTION,
    CONFIRM,
) = range(14)

# ── User: villa browsing states ────────────────────────────────────────────────
BROWSE_AREA, BROWSE_CITY, BROWSE_BUDGET = range(14, 17)

# ── User: visit request states ─────────────────────────────────────────────────
VISIT_NAME, VISIT_PHONE = range(17, 19)

# ── User: consultation request states ──────────────────────────────────────────
CONSULT_NAME, CONSULT_PHONE, CONSULT_REGION, CONSULT_BUDGET, CONSULT_CONFIRM = range(19, 24)

# ── Admin: Smart Import states ──────────────────────────────────────────────────
SI_WAITING_TEXT, SI_PREVIEW, SI_EDIT_FIELD, SI_EDIT_VALUE, SI_PHOTOS = range(24, 29)

# ── Feature metadata ───────────────────────────────────────────────────────────
FEATURE_KEYS = ["has_pool", "has_jacuzzi", "has_roof_garden", "has_parking", "has_storage"]
FEATURE_LABELS = ["استخر", "جکوزی", "روف گاردن", "پارکینگ", "انباری"]
FEATURE_QUESTIONS = [
    "آیا ویلا استخر دارد؟ 🏊",
    "آیا ویلا جکوزی دارد؟ 🛁",
    "آیا ویلا روف گاردن دارد؟ 🌿",
    "آیا ویلا پارکینگ دارد؟ 🚗",
    "آیا ویلا انباری دارد؟ 📦",
]
