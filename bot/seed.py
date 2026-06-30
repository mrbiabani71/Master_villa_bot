"""
Run once to populate the database with sample villas for testing.
Usage:  python seed.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from database import get_connection, init_db

SAMPLE_VILLAS = [
    {
        "villa_code":    "MV-1001",
        "city":          "محمودآباد",
        "area_type":     "ساحلی",
        "price":         6_500_000_000,
        "land_size":     500,
        "building_size": 220,
        "bedrooms":      3,
        "is_townhouse":  0,
        "has_pool":      1,
        "has_jacuzzi":   0,
        "has_roof_garden": 0,
        "has_parking":   1,
        "has_storage":   1,
        "document_type": "سند تک‌برگ",
        "description":   (
            "ویلای ساحلی لوکس با دسترسی مستقیم به دریا. محوطه‌سازی زیبا با باغچه و فضای سبز فراوان. "
            "کاملاً مبله و آماده سکونت. فاصله تا ساحل ۱۵۰ متر. نمای مدرن و سیستم گرمایش از کف."
        ),
        "latitude":  36.6376,
        "longitude": 52.2586,
        "photos":    "",
        "video":     "",
        "status":    "active",
    },
    {
        "villa_code":    "MV-1002",
        "city":          "محمودآباد",
        "area_type":     "ساحلی",
        "price":         8_200_000_000,
        "land_size":     320,
        "building_size": 150,
        "bedrooms":      2,
        "is_townhouse":  1,
        "has_pool":      0,
        "has_jacuzzi":   0,
        "has_roof_garden": 0,
        "has_parking":   1,
        "has_storage":   1,
        "document_type": "سند منگوله‌دار",
        "description":   (
            "ویلای شهرکی با امنیت ۲۴ ساعته و نگهبانی. نزدیک به ساحل و مراکز خرید. "
            "مناسب برای سرمایه‌گذاری یا استفاده تفریحی. سند معتبر."
        ),
        "latitude":  None,
        "longitude": None,
        "photos":    "",
        "video":     "",
        "status":    "active",
    },
    {
        "villa_code":    "MV-1003",
        "city":          "نور",
        "area_type":     "جنگلی",
        "price":         12_000_000_000,
        "land_size":     800,
        "building_size": 300,
        "bedrooms":      4,
        "is_townhouse":  0,
        "has_pool":      1,
        "has_jacuzzi":   1,
        "has_roof_garden": 1,
        "has_parking":   1,
        "has_storage":   1,
        "document_type": "سند تک‌برگ",
        "description":   (
            "ویلای جنگلی ویژه با چشم‌انداز فوق‌العاده. دارای جکوزی، استخر آب گرم، روف گاردن اختصاصی "
            "با دید به جنگل. هوای پاک و طبیعت بکر. سیستم هوشمند خانه. آشپزخانه اپن مدرن."
        ),
        "latitude":  36.5673,
        "longitude": 51.9854,
        "photos":    "",
        "video":     "",
        "status":    "active",
    },
    {
        "villa_code":    "MV-1004",
        "city":          "سرخرود",
        "area_type":     "ساحلی",
        "price":         5_500_000_000,
        "land_size":     270,
        "building_size": 120,
        "bedrooms":      2,
        "is_townhouse":  1,
        "has_pool":      0,
        "has_jacuzzi":   0,
        "has_roof_garden": 0,
        "has_parking":   1,
        "has_storage":   0,
        "document_type": "قولنامه",
        "description":   (
            "ویلای اقتصادی با موقعیت ممتاز در سرخرود. مناسب برای خانواده‌های جوان. "
            "فاصله تا دریا ۵ دقیقه پیاده. در حال حاضر اجاره داده نشده."
        ),
        "latitude":  None,
        "longitude": None,
        "photos":    "",
        "video":     "",
        "status":    "active",
    },
    {
        "villa_code":    "MV-1005",
        "city":          "نور",
        "area_type":     "جنگلی",
        "price":         18_000_000_000,
        "land_size":     1200,
        "building_size": 450,
        "bedrooms":      5,
        "is_townhouse":  0,
        "has_pool":      1,
        "has_jacuzzi":   1,
        "has_roof_garden": 1,
        "has_parking":   1,
        "has_storage":   1,
        "document_type": "سند تک‌برگ",
        "description":   (
            "ویلای اکازیون فوق لوکس در قلب جنگل نور. با تمام امکانات مدرن: استخر اینفینیتی، "
            "سالن سینمای خصوصی، گیم روم، سونا خشک و بخار، زمین بازی کودکان. "
            "مناسب برای سرمایه‌گذاری کلان یا اقامت دائم."
        ),
        "latitude":  36.5800,
        "longitude": 52.0100,
        "photos":    "",
        "video":     "",
        "status":    "active",
    },
]


def seed() -> None:
    init_db()
    inserted = 0
    skipped = 0

    with get_connection() as conn:
        for v in SAMPLE_VILLAS:
            try:
                conn.execute(
                    """
                    INSERT INTO villas (
                        villa_code, city, area_type, price,
                        land_size, building_size, bedrooms,
                        is_townhouse, has_pool, has_jacuzzi,
                        has_roof_garden, has_parking, has_storage,
                        document_type, description,
                        latitude, longitude,
                        photos, video, status,
                        created_at, updated_at
                    ) VALUES (
                        :villa_code, :city, :area_type, :price,
                        :land_size, :building_size, :bedrooms,
                        :is_townhouse, :has_pool, :has_jacuzzi,
                        :has_roof_garden, :has_parking, :has_storage,
                        :document_type, :description,
                        :latitude, :longitude,
                        :photos, :video, :status,
                        datetime('now'), datetime('now')
                    )
                    """,
                    v,
                )
                inserted += 1
                print(f"  ✅ Inserted {v['villa_code']} — {v['city']} {v['area_type']}")
            except Exception as e:
                if "UNIQUE constraint" in str(e):
                    skipped += 1
                    print(f"  ⏭  Skipped {v['villa_code']} (already exists)")
                else:
                    print(f"  ❌ Error inserting {v['villa_code']}: {e}")
        conn.commit()

    print(f"\nDone: {inserted} inserted, {skipped} skipped.")


if __name__ == "__main__":
    seed()
