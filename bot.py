#!/usr/bin/env python3
"""
==============================================
  TELEGRAM LICENSE BOT — BUTTON EDITION
  HWID + Expiry + Inline Button Controls
==============================================
  pip install python-telegram-bot
  python3 bot.py
"""

import random
import string
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, ConversationHandler, filters
)

# ─── CONFIG ───────────────────────────────────────────
BOT_TOKEN  = "8636526459:AAGt18m9Wx778WDSs01sDAyUtQ_BMJQPTwg"
CHANNEL_ID = "@newchannel900"       # or numeric: -1001234567890
ADMIN_IDS  = [1339904459]          # your Telegram user ID(s)
# ──────────────────────────────────────────────────────

# Conversation states
(
    WAIT_GENKEY_DAYS,
    WAIT_GENKEYS_COUNT,
    WAIT_GENKEYS_DAYS,
    WAIT_ADDKEY_NAME,
    WAIT_ADDKEY_DAYS,
    WAIT_CHECKKEY,
    WAIT_REVOKEKEY,
    WAIT_DELETEKEY,
    WAIT_RESETDEVICE,
    WAIT_EXTENDKEY_NAME,
    WAIT_EXTENDKEY_DAYS,
) = range(11)

key_db = {}


# ══════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════

def is_admin(update: Update) -> bool:
    uid = update.effective_user.id if update.effective_user else None
    return uid in ADMIN_IDS


def make_key() -> str:
    chars = string.ascii_uppercase + string.digits
    return "-".join("".join(random.choices(chars, k=4)) for _ in range(4))


def key_status(record: dict) -> str:
    expiry = record["expiry"]
    if expiry == "revoked":
        return "⛔ Revoked"
    try:
        exp = datetime.strptime(expiry, "%Y-%m-%d")
        days_left = (exp - datetime.now()).days
        if days_left < 0:
            return "❌ Expired"
        elif days_left <= 7:
            return f"⚠️ {days_left}d left"
        else:
            return f"✅ {days_left}d left"
    except Exception:
        return "❓ Unknown"


# ══════════════════════════════════════════════════════
#  DATABASE (Pinned Channel Message)
# ══════════════════════════════════════════════════════

async def load_keys(app):
    global key_db
    chat = await app.bot.get_chat(CHANNEL_ID)
    pinned = chat.pinned_message
    if not pinned or not pinned.text:
        key_db = {}
        return
    key_db = {}
    for line in pinned.text.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(":", 2)
        if len(parts) == 3:
            key_db[parts[0].strip()] = {
                "hwid":   parts[1].strip(),
                "expiry": parts[2].strip()
            }


async def save_keys(app):
    chat = await app.bot.get_chat(CHANNEL_ID)
    pinned = chat.pinned_message
    lines = [f"{k}:{v['hwid']}:{v['expiry']}" for k, v in key_db.items()]
    content = "\n".join(lines) if lines else "# No keys yet"
    if pinned:
        await app.bot.edit_message_text(
            chat_id=CHANNEL_ID,
            message_id=pinned.message_id,
            text=content
        )


# ══════════════════════════════════════════════════════
#  MENUS
# ══════════════════════════════════════════════════════

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔑 Gen Key",     callback_data="menu_genkey"),
            InlineKeyboardButton("🔑🔑 Gen Keys",  callback_data="menu_genkeys"),
        ],
        [
            InlineKeyboardButton("➕ Add Key",     callback_data="menu_addkey"),
            InlineKeyboardButton("🔍 Check Key",   callback_data="menu_checkkey"),
        ],
        [
            InlineKeyboardButton("⛔ Revoke Key",  callback_data="menu_revokekey"),
            InlineKeyboardButton("🗑️ Delete Key",  callback_data="menu_deletekey"),
        ],
        [
            InlineKeyboardButton("📅 Extend Key",  callback_data="menu_extendkey"),
            InlineKeyboardButton("🔄 Reset Device",callback_data="menu_resetdevice"),
        ],
        [
            InlineKeyboardButton("📋 List Keys",   callback_data="menu_listkeys"),
        ],
    ])


def back_button():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu_back")]
    ])


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, text=None):
    msg = text or "👋 *License Manager*\n\nChoose an action:"
    if update.callback_query:
        await update.callback_query.edit_message_text(
            msg, parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            msg, parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )


# ══════════════════════════════════════════════════════
#  /start
# ══════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("⛔ Unauthorized.")
        return ConversationHandler.END
    await show_main_menu(update, context)
    return ConversationHandler.END


# ══════════════════════════════════════════════════════
#  VERIFICATION — called by shell script
# ══════════════════════════════════════════════════════

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/check KEY HWID — used by shell script only"""
    if len(context.args) < 2:
        await update.message.reply_text("ERROR")
        return

    key  = context.args[0].strip()
    hwid = context.args[1].strip()

    await load_keys(context.application)

    if key not in key_db:
        await update.message.reply_text("INVALID_KEY")
        return

    record      = key_db[key]
    expiry      = record["expiry"]
    stored_hwid = record["hwid"]

    if expiry == "revoked":
        await update.message.reply_text("REVOKED")
        return

    try:
        if datetime.now() > datetime.strptime(expiry, "%Y-%m-%d"):
            await update.message.reply_text("EXPIRED")
            return
    except ValueError:
        await update.message.reply_text("ERROR")
        return

    if stored_hwid in ("", "pending"):
        key_db[key]["hwid"] = hwid
        await save_keys(context.application)
        await update.message.reply_text("OK")
    elif stored_hwid == hwid:
        await update.message.reply_text("OK")
    else:
        await update.message.reply_text("HWID_MISMATCH")


# ══════════════════════════════════════════════════════
#  BUTTON ROUTER
# ══════════════════════════════════════════════════════

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(update):
        await query.edit_message_text("⛔ Unauthorized.")
        return ConversationHandler.END

    data = query.data

    # ── Back ──────────────────────────────────────────
    if data == "menu_back":
        await show_main_menu(update, context)
        return ConversationHandler.END

    # ── List Keys ─────────────────────────────────────
    elif data == "menu_listkeys":
        await load_keys(context.application)
        if not key_db:
            await query.edit_message_text("📋 No keys in database.", reply_markup=back_button())
            return ConversationHandler.END
        lines = []
        for k, v in key_db.items():
            status = key_status(v)
            hwid   = (v["hwid"][:8] + "...") if v["hwid"] else "pending"
            lines.append(f"`{k}`\n  {status} | {hwid}")
        await query.edit_message_text(
            f"📋 *All Keys ({len(key_db)})*\n\n" + "\n\n".join(lines),
            parse_mode="Markdown", reply_markup=back_button()
        )
        return ConversationHandler.END

    # ── Prompts that need text input ──────────────────
    prompts = {
        "menu_genkey":      (WAIT_GENKEY_DAYS,    "🔑 *Generate Key*\n\nHow many days should the key be valid?\n\nType a number (e.g. `30`):"),
        "menu_genkeys":     (WAIT_GENKEYS_COUNT,   "🔑🔑 *Generate Multiple Keys*\n\nHow many keys? (max 20)\n\nType a number (e.g. `5`):"),
        "menu_addkey":      (WAIT_ADDKEY_NAME,     "➕ *Add Custom Key*\n\nType the key name you want to add:"),
        "menu_checkkey":    (WAIT_CHECKKEY,        "🔍 *Check Key*\n\nType the key to inspect:"),
        "menu_revokekey":   (WAIT_REVOKEKEY,       "⛔ *Revoke Key*\n\nType the key to revoke:"),
        "menu_deletekey":   (WAIT_DELETEKEY,       "🗑️ *Delete Key*\n\nType the key to permanently delete:"),
        "menu_resetdevice": (WAIT_RESETDEVICE,     "🔄 *Reset Device*\n\nType the key to reset HWID for:"),
        "menu_extendkey":   (WAIT_EXTENDKEY_NAME,  "📅 *Extend Key*\n\nType the key to extend:"),
    }

    if data in prompts:
        state, prompt = prompts[data]
        await query.edit_message_text(prompt, parse_mode="Markdown", reply_markup=back_button())
        return state

    # ── Day confirm buttons ────────────────────────────
    elif data.startswith("days_"):
        parts  = data.split("_")
        action = parts[1]
        days   = int(parts[2])
        key    = context.user_data.get("pending_key", "")
        expiry = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")

        await load_keys(context.application)

        if action == "genkey":
            new_key = make_key()
            while new_key in key_db:
                new_key = make_key()
            key_db[new_key] = {"hwid": "", "expiry": expiry}
            await save_keys(context.application)
            await query.edit_message_text(
                f"✅ *Key Generated*\n\n`{new_key}`\n\n📅 Expires: `{expiry}` ({days} days)\n📱 Device: Not activated",
                parse_mode="Markdown", reply_markup=back_button()
            )

        elif action == "addkey":
            key_db[key] = {"hwid": "", "expiry": expiry}
            await save_keys(context.application)
            await query.edit_message_text(
                f"✅ Key `{key}` added\n📅 Expires: `{expiry}`",
                parse_mode="Markdown", reply_markup=back_button()
            )

        elif action == "extend":
            if key in key_db:
                current = key_db[key]["expiry"]
                if current == "revoked":
                    await query.edit_message_text("❌ Key is revoked.", reply_markup=back_button())
                else:
                    try:
                        base = datetime.strptime(current, "%Y-%m-%d")
                        if base < datetime.now():
                            base = datetime.now()
                        new_exp = (base + timedelta(days=days)).strftime("%Y-%m-%d")
                        key_db[key]["expiry"] = new_exp
                        await save_keys(context.application)
                        await query.edit_message_text(
                            f"📅 Extended `{key}`\nNew expiry: `{new_exp}`",
                            parse_mode="Markdown", reply_markup=back_button()
                        )
                    except Exception:
                        await query.edit_message_text("❌ Error extending.", reply_markup=back_button())

        return ConversationHandler.END

    return ConversationHandler.END


# ══════════════════════════════════════════════════════
#  CONFIRM CALLBACKS
# ══════════════════════════════════════════════════════

async def confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(update):
        return

    data = query.data
    await load_keys(context.application)

    if data.startswith("confirm_revoke_"):
        key = data.replace("confirm_revoke_", "")
        if key in key_db:
            key_db[key]["expiry"] = "revoked"
            await save_keys(context.application)
            await query.edit_message_text(
                f"⛔ Key `{key}` revoked.", parse_mode="Markdown", reply_markup=back_button()
            )

    elif data.startswith("confirm_delete_"):
        key = data.replace("confirm_delete_", "")
        if key in key_db:
            del key_db[key]
            await save_keys(context.application)
            await query.edit_message_text(
                f"🗑️ Key `{key}` deleted.", parse_mode="Markdown", reply_markup=back_button()
            )

    elif data.startswith("confirm_reset_"):
        key = data.replace("confirm_reset_", "")
        if key in key_db:
            key_db[key]["hwid"] = ""
            await save_keys(context.application)
            await query.edit_message_text(
                f"🔄 Device reset for `{key}`.\nCan now activate on a new device.",
                parse_mode="Markdown", reply_markup=back_button()
            )


# ══════════════════════════════════════════════════════
#  TEXT INPUT HANDLERS
# ══════════════════════════════════════════════════════

async def genkey_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        days = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Enter a valid number.", reply_markup=back_button())
        return ConversationHandler.END
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(f"✅ Confirm ({days} days)", callback_data=f"days_genkey_{days}"),
        InlineKeyboardButton("❌ Cancel", callback_data="menu_back"),
    ]])
    await update.message.reply_text(
        f"Generate 1 key valid for *{days} days*?",
        parse_mode="Markdown", reply_markup=kb
    )
    return ConversationHandler.END


async def genkeys_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["genkeys_count"] = min(int(update.message.text.strip()), 20)
    except ValueError:
        await update.message.reply_text("❌ Enter a valid number.")
        return ConversationHandler.END
    await update.message.reply_text(
        "How many days should each key be valid?\n\nType a number (e.g. `30`):",
        parse_mode="Markdown", reply_markup=back_button()
    )
    return WAIT_GENKEYS_DAYS


async def genkeys_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        days  = int(update.message.text.strip())
        count = context.user_data.get("genkeys_count", 1)
    except ValueError:
        await update.message.reply_text("❌ Enter a valid number.")
        return ConversationHandler.END
    await load_keys(context.application)
    expiry   = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    new_keys = []
    for _ in range(count):
        k = make_key()
        while k in key_db:
            k = make_key()
        key_db[k] = {"hwid": "", "expiry": expiry}
        new_keys.append(k)
    await save_keys(context.application)
    keys_text = "\n".join(f"`{k}`" for k in new_keys)
    await update.message.reply_text(
        f"✅ *{count} Keys Generated*\n📅 Expires: `{expiry}` ({days} days)\n\n{keys_text}",
        parse_mode="Markdown", reply_markup=back_button()
    )
    return ConversationHandler.END


async def addkey_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = update.message.text.strip().upper()
    context.user_data["pending_key"] = key
    await update.message.reply_text(
        f"Key: `{key}`\n\nHow many days valid? (e.g. `30`)",
        parse_mode="Markdown", reply_markup=back_button()
    )
    return WAIT_ADDKEY_DAYS


async def addkey_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        days = int(update.message.text.strip())
        key  = context.user_data.get("pending_key", "")
    except ValueError:
        await update.message.reply_text("❌ Enter a valid number.")
        return ConversationHandler.END
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(f"✅ Add {key} ({days}d)", callback_data=f"days_addkey_{days}"),
        InlineKeyboardButton("❌ Cancel", callback_data="menu_back"),
    ]])
    await update.message.reply_text(
        f"Add key `{key}` valid for *{days} days*?",
        parse_mode="Markdown", reply_markup=kb
    )
    return ConversationHandler.END


async def do_checkkey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = update.message.text.strip().upper()
    await load_keys(context.application)
    if key not in key_db:
        await update.message.reply_text("❌ Key not found.", reply_markup=back_button())
        return ConversationHandler.END
    r    = key_db[key]
    hwid = r["hwid"] or "Not activated"
    await update.message.reply_text(
        f"🔍 *Key Details*\n\n"
        f"🔑 Key:    `{key}`\n"
        f"📊 Status: {key_status(r)}\n"
        f"📱 HWID:   `{hwid}`\n"
        f"📅 Expiry: `{r['expiry']}`",
        parse_mode="Markdown", reply_markup=back_button()
    )
    return ConversationHandler.END


async def do_revokekey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = update.message.text.strip().upper()
    await load_keys(context.application)
    if key not in key_db:
        await update.message.reply_text("❌ Key not found.", reply_markup=back_button())
        return ConversationHandler.END
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⛔ Yes, Revoke", callback_data=f"confirm_revoke_{key}"),
        InlineKeyboardButton("❌ Cancel",       callback_data="menu_back"),
    ]])
    await update.message.reply_text(
        f"Revoke key `{key}`? This cannot be undone.",
        parse_mode="Markdown", reply_markup=kb
    )
    return ConversationHandler.END


async def do_deletekey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = update.message.text.strip().upper()
    await load_keys(context.application)
    if key not in key_db:
        await update.message.reply_text("❌ Key not found.", reply_markup=back_button())
        return ConversationHandler.END
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🗑️ Yes, Delete", callback_data=f"confirm_delete_{key}"),
        InlineKeyboardButton("❌ Cancel",       callback_data="menu_back"),
    ]])
    await update.message.reply_text(
        f"Permanently delete key `{key}`?",
        parse_mode="Markdown", reply_markup=kb
    )
    return ConversationHandler.END


async def do_resetdevice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = update.message.text.strip().upper()
    await load_keys(context.application)
    if key not in key_db:
        await update.message.reply_text("❌ Key not found.", reply_markup=back_button())
        return ConversationHandler.END
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔄 Yes, Reset", callback_data=f"confirm_reset_{key}"),
        InlineKeyboardButton("❌ Cancel",     callback_data="menu_back"),
    ]])
    await update.message.reply_text(
        f"Reset HWID for `{key}`? User can activate on a new device.",
        parse_mode="Markdown", reply_markup=kb
    )
    return ConversationHandler.END


async def extendkey_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = update.message.text.strip().upper()
    await load_keys(context.application)
    if key not in key_db:
        await update.message.reply_text("❌ Key not found.", reply_markup=back_button())
        return ConversationHandler.END
    context.user_data["pending_key"] = key
    r = key_db[key]
    await update.message.reply_text(
        f"Key: `{key}` — Current expiry: `{r['expiry']}`\n\nHow many days to add?",
        parse_mode="Markdown", reply_markup=back_button()
    )
    return WAIT_EXTENDKEY_DAYS


async def extendkey_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        days = int(update.message.text.strip())
        key  = context.user_data.get("pending_key", "")
    except ValueError:
        await update.message.reply_text("❌ Enter a valid number.")
        return ConversationHandler.END
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(f"📅 Add {days} days", callback_data=f"days_extend_{days}"),
        InlineKeyboardButton("❌ Cancel",            callback_data="menu_back"),
    ]])
    await update.message.reply_text(
        f"Add *{days} days* to key `{key}`?",
        parse_mode="Markdown", reply_markup=kb
    )
    return ConversationHandler.END


# ══════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🤖 Bot starting...")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Shell script verification — keep as /check
    app.add_handler(CommandHandler("check", check))

    # Confirm action callbacks
    app.add_handler(CallbackQueryHandler(confirm_callback, pattern="^confirm_"))

    # Main conversation handler
    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(menu_callback, pattern="^menu_"),
            CallbackQueryHandler(menu_callback, pattern="^days_"),
        ],
        states={
            WAIT_GENKEY_DAYS:    [MessageHandler(filters.TEXT & ~filters.COMMAND, genkey_days)],
            WAIT_GENKEYS_COUNT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, genkeys_count)],
            WAIT_GENKEYS_DAYS:   [MessageHandler(filters.TEXT & ~filters.COMMAND, genkeys_days)],
            WAIT_ADDKEY_NAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, addkey_name)],
            WAIT_ADDKEY_DAYS:    [MessageHandler(filters.TEXT & ~filters.COMMAND, addkey_days)],
            WAIT_CHECKKEY:       [MessageHandler(filters.TEXT & ~filters.COMMAND, do_checkkey)],
            WAIT_REVOKEKEY:      [MessageHandler(filters.TEXT & ~filters.COMMAND, do_revokekey)],
            WAIT_DELETEKEY:      [MessageHandler(filters.TEXT & ~filters.COMMAND, do_deletekey)],
            WAIT_RESETDEVICE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, do_resetdevice)],
            WAIT_EXTENDKEY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, extendkey_name)],
            WAIT_EXTENDKEY_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, extendkey_days)],
        },
        fallbacks=[
            CommandHandler("start", start),
            CallbackQueryHandler(menu_callback, pattern="^menu_back$"),
        ],
        per_message=False,
    )

    app.add_handler(conv)

    print("✅ Bot running. Send /start in Telegram.")
    app.run_polling()
