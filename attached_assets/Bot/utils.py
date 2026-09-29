def fmt_price(price) -> str:
    """Return a human-readable Farsi price string.

    Examples:
        18_000_000_000  →  18 میلیارد تومان
         6_500_000_000  →  6.5 میلیارد تومان
           780_000_000  →  780 میلیون تومان
    """
    if price is None:
        return "—"
    price = int(price)
    if price >= 1_000_000_000:
        val = price / 1_000_000_000
        label = f"{int(val)}" if val == int(val) else f"{val:.1f}"
        return f"{label} میلیارد تومان"
    if price >= 1_000_000:
        val = price / 1_000_000
        label = f"{int(val)}" if val == int(val) else f"{round(val)}"
        return f"{label} میلیون تومان"
    return f"{price:,} تومان"


def price_category(price) -> str:
    """Return the price tier label matching the business category thresholds.

    Thresholds:
        < 7 B   →  🟢 اقتصادی
        < 10 B  →  🔵 متوسط
        < 15 B  →  🟣 نیمه لوکس
        ≥ 15 B  →  🔴 لوکس
    """
    if price is None:
        return ""
    price = int(price)
    if price < 7_000_000_000:
        return "🟢 اقتصادی"
    if price < 10_000_000_000:
        return "🔵 متوسط"
    if price < 15_000_000_000:
        return "🟣 نیمه لوکس"
    return "🔴 لوکس"
