# ── User: villa browsing states ────────────────────────────────────────────────
BROWSE_AREA, BROWSE_CITY, BROWSE_BUDGET = range(14, 17)

# ── User: visit request states ─────────────────────────────────────────────────
VISIT_NAME, VISIT_PHONE = range(17, 19)

# ── User: consultation request states ──────────────────────────────────────────
CONSULT_NAME, CONSULT_PHONE, CONSULT_REGION, CONSULT_BUDGET, CONSULT_CONFIRM = range(19, 24)

# ── Admin: Smart Import states ──────────────────────────────────────────────────
SI_WAITING_TEXT, SI_PREVIEW, SI_EDIT_FIELD, SI_EDIT_VALUE, SI_PHOTOS = range(24, 29)

# ── Admin: Edit Villa states ─────────────────────────────────────────────────────
EV_WAITING_CODE, EV_PREVIEW, EV_EDIT_FIELD, EV_EDIT_VALUE, EV_PHOTOS = range(29, 34)

# ── Admin: Manage Villas states ───────────────────────────────────────────────────
MV_SEARCH, MV_CONFIRM_DELETE = range(34, 36)

# ── User: advanced villa search states ─────────────────────────────────────────
ADV_REGION, ADV_CITY, ADV_PRICE, ADV_FILTERS = range(36, 40)

# ── User: search menu (smart vs category) state ─────────────────────────────────
SEARCH_MENU = 40

# ── User: smart search (rule-based parser) states ────────────────────────────────
SMART_TEXT, SMART_ASK_REGION, SMART_ASK_PRICE = range(41, 44)

# ── User: notification preferences states ─────────────────────────────────────
NP_REGION, NP_PRICE, NP_TYPE = range(44, 47)
