from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = "8951313123:AAE0TtJKGsr7UHOMgQlGfzRIZjlJQmt5Zhw" 


menu = [
    ["🏡 مشاهده ویلاها"],
    ["📄 دریافت کاتالوگ"],
    ["🎥 ویدیوها"],
    ["💰 قیمت روز"],
    ["📞 مشاوره رایگان"]
]

keyboard = ReplyKeyboardMarkup(menu, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام 👋 به ربات Master Villa خوش اومدی\nیکی از گزینه‌های زیر رو انتخاب کن:",
        reply_markup=keyboard
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "🏡 مشاهده ویلاها":
        await update.message.reply_text("در حال حاضر جدیدترین ویلاها در حال آماده‌سازی هستند 🏡")

    elif text == "📄 دریافت کاتالوگ":
        await update.message.reply_text("کاتالوگ به زودی ارسال می‌شود 📄")

    elif text == "🎥 ویدیوها":
        await update.message.reply_text("ویدیوهای ویلاها به زودی اضافه می‌شود 🎥")

    elif text == "💰 قیمت روز":
        await update.message.reply_text("برای دریافت قیمت روز با مشاور تماس بگیر 📞")

    elif text == "📞 مشاوره رایگان":
        await update.message.reply_text(
            "برای مشاوره رایگان لطفاً نام و شماره تماس خود را ارسال کنید 📞"
        )

    else:
        await update.message.reply_text("لطفاً از منو استفاده کن 👇")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

app.run_polling()
