import os
from db.connection import get_db
from utils.image_hash import get_image_hash, compare_hash

ADMIN_ID = 123456789   # آیدی مدیر را اینجا قرار بده

async def process_user_photo(message, user_photo_path):
    db = get_db()
    cursor = db.cursor()

    # هش عکس کاربر
    user_hash = get_image_hash(user_photo_path)

    # گرفتن عکس‌های ویلاها
    cursor.execute("SELECT villa_id, photo_path FROM villa_photos")
    villas = cursor.fetchall()

    best_match = None
    best_score = 999

    # مقایسه هش‌ها
    for villa_id, photo_path in villas:
        villa_hash = get_image_hash(photo_path)
        score = compare_hash(user_hash, villa_hash)

        if score < best_score:
            best_score = score
            best_match = villa_id

    # اگر شباهت بالا بود → ویلا پیدا شده
    if best_score < 20:
        await message.reply(f"ویلا پیدا شد! 🏡\nشناسه ویلا: {best_match}")
        return

    # اگر پیدا نشد → ارسال به مدیر
    await message.reply("این ویلا در آرشیو ما نیست. عکس برای مدیر ارسال شد.")

    await message.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=open(user_photo_path, "rb"),
        caption=f"عکس جدید از کاربر {message.from_user.id}"
    )