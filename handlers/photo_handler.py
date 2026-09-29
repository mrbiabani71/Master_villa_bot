from aiogram import types
import os
from datetime import datetime

from utils.image_search import process_user_photo

USER_PHOTO_DIR = "user_photos"

async def handle_user_photo(message: types.Message):
    # ساخت پوشه اگر وجود نداشت
    if not os.path.exists(USER_PHOTO_DIR):
        os.makedirs(USER_PHOTO_DIR)

    # دانلود عکس
    photo = message.photo[-1]
    file_id = photo.file_id
    file = await message.bot.get_file(file_id)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = f"{USER_PHOTO_DIR}/{message.from_user.id}_{timestamp}.jpg"

    await message.bot.download_file(file.file_path, file_path)

    # ارسال پیام به کاربر
    await message.reply("عکس دریافت شد، در حال بررسی... 🔍")

    # پردازش عکس
    await process_user_photo(message, file_path)