"""
ValyutaX — O'zbekiston Markaziy banki (CBU) va xalqaro kurslar asosida
ishlaydigan valyuta Telegram boti.

Imkoniyatlar:
    - Joriy rasmiy kursni ko'rsatish (USD/EUR/RUB/GBP va h.k.)
    - Erkin matn orqali konvertatsiya: "100 USD" yoki "100 USD EUR"
    - Kurs tarixi grafigi (bot ishlagan kunlar bo'yicha to'planadi)
    - Kunlik bildirishnoma: kurs o'zgargan kunlari obunachilarga xabar

Ishga tushirish:
    export BOT_TOKEN="..."       # @BotFather dan olinadi
    python bot.py
"""

import logging
import os
import re
import time
from datetime import date, time as dt_time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from zoneinfo import ZoneInfo

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import db
import rates
from charts import render_history_chart

LOGS_DIR = Path(__file__).resolve().parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(LOGS_DIR / "bot.log", maxBytes=2_000_000, backupCount=3),
    ],
)
logger = logging.getLogger(__name__)

START_TIME = time.time()

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "")
TRACKED_CURRENCIES = [
    code.strip().upper()
    for code in os.environ.get(
        "TRACKED_CURRENCIES", "USD,EUR,RUB,GBP,CNY,KZT,TRY,JPY,AED,CHF"
    ).split(",")
    if code.strip()
]
QUICK_AMOUNTS = [100, 500, 1000, 5000]
NOTIFY_HOUR = int(os.environ.get("NOTIFY_HOUR", "9"))
WEBAPP_URL = os.environ.get("WEBAPP_URL", "").strip()
TASHKENT_TZ = ZoneInfo("Asia/Tashkent")

AMOUNT_CCY_RE = re.compile(
    r"^\s*([\d]+(?:[.,]\d+)?)\s*([A-Za-z]{3})(?:\s+([A-Za-z]{3}))?\s*$"
)


MENU_RATE = "💵 Joriy kurs"
MENU_CONVERT = "🔄 Konvertatsiya"
MENU_HISTORY = "📈 Tarix/Grafik"
MENU_SUB = "🔔 Bildirishnoma"
BOTTOM_MENU_TEXTS = [MENU_RATE, MENU_CONVERT, MENU_HISTORY, MENU_SUB]


def bottom_menu_keyboard() -> ReplyKeyboardMarkup:
    rows = [[MENU_RATE, MENU_CONVERT], [MENU_HISTORY, MENU_SUB]]
    if WEBAPP_URL:
        rows.append([KeyboardButton("🌐 Web ilova", web_app=WebAppInfo(url=WEBAPP_URL))])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💵 Joriy kurs", callback_data="rate")],
            [InlineKeyboardButton("🔄 Konvertatsiya", callback_data="convert_hint")],
            [InlineKeyboardButton("📈 Tarix/Grafik", callback_data="history")],
            [InlineKeyboardButton("🔔 Bildirishnoma", callback_data="sub_toggle")],
        ]
    )


def currency_picker_keyboard(prefix: str) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(code, callback_data=f"{prefix}:{code}")
        for code in TRACKED_CURRENCIES
    ]
    rows = [buttons[i : i + 3] for i in range(0, len(buttons), 3)]
    rows.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def quick_amount_keyboard(code: str) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(f"{amount:,} {code}", callback_data=f"conv:{code}:{amount}")
        for amount in QUICK_AMOUNTS
    ]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="convert_hint")])
    return InlineKeyboardMarkup(rows)


def format_rate_message() -> str:
    try:
        cbu = rates.fetch_cbu_rates()
    except rates.RateFetchError as exc:
        return f"⚠️ Kurslarni olishda xatolik: {exc}"

    lines = ["💵 <b>Bugungi rasmiy kurs (CBU)</b>\n"]
    for code in TRACKED_CURRENCIES:
        info = cbu.get(code)
        if not info:
            continue
        arrow = "▲" if info["diff"] > 0 else ("▼" if info["diff"] < 0 else "•")
        lines.append(
            f"{code}: <b>{info['rate']:,.2f}</b> so'm  {arrow} {info['diff']:+.2f}"
        )
    if cbu:
        any_code = TRACKED_CURRENCIES[0] if TRACKED_CURRENCIES else next(iter(cbu))
        info = cbu.get(any_code)
        if info and info.get("date"):
            lines.append(f"\n<i>Sana: {info['date']}</i>")
    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Assalomu alaykum! ValyutaX botiga xush kelibsiz.\n"
        "Rasmiy (CBU) va xalqaro valyuta kurslarini shu yerdan kuzatishingiz mumkin.\n\n"
        "Konvertatsiya uchun shunchaki yozing: <code>100 USD</code> yoki <code>100 USD EUR</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=bottom_menu_keyboard(),
    )


async def bottom_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text

    if text == MENU_RATE:
        await update.message.reply_text(
            format_rate_message(), parse_mode=ParseMode.HTML, reply_markup=main_menu_keyboard()
        )
    elif text == MENU_CONVERT:
        await update.message.reply_text(
            "🔄 Tez konvertatsiya uchun valyutani tanlang, yoki istalgan vaqt "
            "<code>100 USD</code> / <code>100 USD EUR</code> deb yozing:",
            parse_mode=ParseMode.HTML,
            reply_markup=currency_picker_keyboard("convccy"),
        )
    elif text == MENU_HISTORY:
        await update.message.reply_text(
            "Qaysi valyuta tarixini ko'rmoqchisiz?", reply_markup=currency_picker_keyboard("history")
        )
    elif text == MENU_SUB:
        chat_id = update.effective_chat.id
        if db.is_subscribed(chat_id):
            db.remove_subscriber(chat_id)
            reply = "🔕 Bildirishnoma o'chirildi."
        else:
            user = update.effective_user
            db.add_subscriber(chat_id, user.id, user.username)
            reply = "🔔 Bildirishnoma yoqildi. Kurs o'zgargan kunlari xabar beramiz."
        await update.message.reply_text(reply)


async def kurs_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        format_rate_message(), parse_mode=ParseMode.HTML, reply_markup=main_menu_keyboard()
    )


async def obuna_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    db.add_subscriber(chat.id, user.id, user.username)
    await update.message.reply_text("🔔 Kurs o'zgarishi haqida kunlik bildirishnomaga obuna bo'ldingiz.")


async def bekor_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db.remove_subscriber(update.effective_chat.id)
    await update.message.reply_text("🔕 Obuna bekor qilindi.")


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "menu":
        await query.message.edit_text(
            "Kerakli bo'limni tanlang:", reply_markup=main_menu_keyboard()
        )
    elif data == "rate":
        await query.message.edit_text(
            format_rate_message(), parse_mode=ParseMode.HTML, reply_markup=main_menu_keyboard()
        )
    elif data == "convert_hint":
        await query.message.edit_text(
            "🔄 Tez konvertatsiya uchun valyutani tanlang, yoki istalgan vaqt "
            "<code>100 USD</code> / <code>100 USD EUR</code> deb yozing:",
            parse_mode=ParseMode.HTML,
            reply_markup=currency_picker_keyboard("convccy"),
        )
    elif data.startswith("convccy:"):
        code = data.split(":", 1)[1]
        await query.message.edit_text(
            f"{code} dan qancha miqdorni so'mga aylantiramiz?",
            reply_markup=quick_amount_keyboard(code),
        )
    elif data.startswith("conv:"):
        _, code, amount_raw = data.split(":")
        amount = float(amount_raw)
        db.log_usage(code)
        try:
            result, target = rates.convert(amount, code, None)
            text = f"{amount:,.0f} {code} = <b>{result:,.2f} {target}</b>"
        except rates.RateFetchError as exc:
            text = f"⚠️ {exc}"
        await query.message.reply_text(text, parse_mode=ParseMode.HTML)
    elif data == "history":
        await query.message.edit_text(
            "Qaysi valyuta tarixini ko'rmoqchisiz?", reply_markup=currency_picker_keyboard("history")
        )
    elif data.startswith("history:"):
        code = data.split(":", 1)[1]
        db.log_usage(code)
        await send_history_chart(query.message.chat_id, code, context)
    elif data == "sub_toggle":
        chat_id = query.message.chat_id
        if db.is_subscribed(chat_id):
            db.remove_subscriber(chat_id)
            text = "🔕 Bildirishnoma o'chirildi."
        else:
            user = update.effective_user
            db.add_subscriber(chat_id, user.id, user.username)
            text = "🔔 Bildirishnoma yoqildi. Kurs o'zgargan kunlari xabar beramiz."
        await query.message.edit_text(text, reply_markup=main_menu_keyboard())


async def send_history_chart(chat_id: int, code: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    history = db.get_rate_history(code, days=30)
    if len(history) < 2:
        await context.bot.send_message(
            chat_id,
            f"📈 {code} uchun tarix hali to'planmoqda — bot har kuni bitta nuqta qo'shadi, "
            "bir necha kundan so'ng qayta urinib ko'ring.",
            reply_markup=main_menu_keyboard(),
        )
        return

    chart = render_history_chart(code, history)
    await context.bot.send_photo(
        chat_id, photo=chart, caption=f"📈 {code}/UZS — so'nggi {len(history)} kun",
        reply_markup=main_menu_keyboard(),
    )


async def convert_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    match = AMOUNT_CCY_RE.match(update.message.text or "")
    if not match:
        return

    amount_raw, from_code, to_code = match.groups()
    amount = float(amount_raw.replace(",", "."))
    db.log_usage(from_code.upper())

    try:
        result, target = rates.convert(amount, from_code, to_code)
    except rates.RateFetchError as exc:
        await update.message.reply_text(f"⚠️ {exc}")
        return

    await update.message.reply_text(
        f"{amount:,.2f} {from_code.upper()} = <b>{result:,.2f} {target}</b>",
        parse_mode=ParseMode.HTML,
    )


def _format_ago(timestamp: float | None) -> str:
    if timestamp is None:
        return "hali yo'q"
    seconds = int(time.time() - timestamp)
    if seconds < 60:
        return f"{seconds} soniya oldin"
    if seconds < 3600:
        return f"{seconds // 60} daqiqa oldin"
    return f"{seconds // 3600} soat oldin"


async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uptime_seconds = int(time.time() - START_TIME)
    lines = [
        "🩺 <b>Holat</b>",
        f"Ishlash vaqti: {uptime_seconds // 3600}s {(uptime_seconds % 3600) // 60}d",
        f"CBU so'nggi muvaffaqiyatli olish: {_format_ago(rates.last_success['cbu'])}",
        f"Xalqaro API so'nggi muvaffaqiyatli olish: {_format_ago(rates.last_success['intl'])}",
    ]
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    if not ADMIN_CHAT_ID or chat_id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔️ Bu buyruq faqat admin uchun.")
        return

    top = db.get_top_currencies(5)
    top_lines = "\n".join(f"  {code}: {count} so'rov" for code, count in top) or "  ma'lumot yo'q"

    lines = [
        "📊 <b>Admin panel</b>",
        f"Obunachilar: {db.get_subscriber_count()}",
        "Eng ko'p so'ralgan valyutalar:",
        top_lines,
        f"\nCBU so'nggi olish: {_format_ago(rates.last_success['cbu'])}",
        f"Xalqaro API so'nggi olish: {_format_ago(rates.last_success['intl'])}",
    ]
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Kutilmagan xatolik", exc_info=context.error)
    if isinstance(update, Update) and update.effective_chat:
        try:
            await context.bot.send_message(
                update.effective_chat.id,
                "⚠️ Xatolik yuz berdi, birozdan so'ng qayta urinib ko'ring.",
            )
        except Exception:  # noqa: BLE001 — xabar yuborishning o'zi ham xato bersa, faqat log qilamiz
            logger.warning("Xato haqida xabar yuborib bo'lmadi")


async def daily_digest_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        cbu = rates.fetch_cbu_rates(force=True)
    except rates.RateFetchError as exc:
        logger.warning("Kunlik job: kurslarni olib bo'lmadi: %s", exc)
        return

    today = date.today().isoformat()
    changed_lines = []

    for code in TRACKED_CURRENCIES:
        info = cbu.get(code)
        if not info:
            continue

        db.save_rate_snapshot(today, code, info["rate"])

        previous = db.get_last_notified(code)
        if previous is None or abs(info["rate"] - previous) > 0.005:
            arrow = "▲" if previous is not None and info["rate"] > previous else (
                "▼" if previous is not None and info["rate"] < previous else "•"
            )
            changed_lines.append(f"{code}: {info['rate']:,.2f} so'm {arrow}")
        db.set_last_notified(code, info["rate"])

    if not changed_lines:
        return

    subscribers = db.list_subscribers()
    if not subscribers:
        return

    text = "🔔 <b>Kurs yangilandi</b>\n\n" + "\n".join(changed_lines)
    for chat_id in subscribers:
        try:
            await context.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)
        except Exception as exc:  # noqa: BLE001 — bitta chatdagi xato boshqalarga ta'sir qilmasin
            logger.warning("Bildirishnoma yuborilmadi (chat_id=%s): %s", chat_id, exc)


def build_app() -> Application:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN muhit o'zgaruvchisi berilmagan")

    db.init_db()
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("kurs", kurs_command))
    application.add_handler(CommandHandler("obuna", obuna_command))
    application.add_handler(CommandHandler("bekor", bekor_command))
    application.add_handler(CommandHandler("health", health_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CallbackQueryHandler(menu_callback))
    application.add_handler(
        MessageHandler(filters.Text(BOTTOM_MENU_TEXTS), bottom_menu_handler)
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Regex(AMOUNT_CCY_RE), convert_text_handler)
    )
    application.add_error_handler(error_handler)

    application.job_queue.run_daily(
        daily_digest_job, time=dt_time(hour=NOTIFY_HOUR, minute=0, tzinfo=TASHKENT_TZ)
    )

    return application


if __name__ == "__main__":
    app = build_app()
    logger.info("ValyutaX bot ishga tushdi...")
    app.run_polling()
