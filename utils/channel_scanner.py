from aiogram import Bot
from db.connection import get_db
import os

VILLA_PHOTO_DIR = "villa_photos"


async def scan_channel_photos(bot: Bot, channel_id: int):
    db = get_db()
    cursor = db.cursor()

    # ساخت پوشه عکس‌های ویلا اگر وجود نداشت
    if not os.path.exists(VILLA_PHOTO_DIR):
        os.makedirs(VILLA_PHOTO_DIR)

    # خواندن پیام‌های کانال
    async for msg in bot.get_chat_history(channel_id, limit=500):
        # فقط پیام‌هایی که عکس دارند
        if not msg.photo:
            continue

        # اولین عکس = نمای اصلی ویلا
        photo = msg.photo[-1]
        file = await bot.get_file(photo.file_id)

        # استخراج شناسه ویلا از کپشن
        if msg.caption:
            try:
                villa_id = int(msg.caption.strip().split()[0])
            except:
                continue
        else:
            continue

        # مسیر ذخیره‌سازی عکس
        file_path = f"{VILLA_PHOTO_DIR}/{villa_id}.jpg"

        # دانلود عکس
        await bot.download_file(file.file_path, file_path)

        # ثبت در دیتابیس
        cursor.execute(
            "INSERT INTO villa_photos (villa_id, photo_path) VALUES (?, ?)",
            (villa_id, file_path)
        )
        db.commit()