import re
import logging
import asyncio
import uuid
import random
import os
from pathlib import Path
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    CallbackContext,
)
from concurrent.futures import ThreadPoolExecutor, as_completed
import pickle

# -----------------------------
# Logging and Directories 📊📂
# -----------------------------
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Use Render-compatible paths
BASE_DIR = Path(__file__).parent
LOGS_DIR = BASE_DIR / "logs"
SAVE_DIR = BASE_DIR / "Generated_Results"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
SAVE_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------------
# Bot Token and Admin Settings 🤖👑
# -----------------------------
TOKEN = os.getenv("TOKEN", "8298937133:AAGAHGesQKCpwfnU1kTuBnjQ96kDVA_HWfM")
ADMIN_ID = int(os.getenv("ADMIN_ID", 6675722513))
ALLOWED_USERS = set()  # Users must redeem a key to access

# -----------------------------
# Global Variables for Keys, Pause Status, and Command Cancellation 🔐⏸️
# -----------------------------
keys = {}  # Stores keys: key-string or user_id -> expiration datetime
used_keys = set()  # Tracks keys that have been redeemed (or expired)
paused_users = set()  # Set of user IDs whose key is paused
DATA_FILE = "bot_data.pkl"
generation_history = {}  # {user_id: {"username": str, "generated_count": int, "total_lines": int}}

# This dict stores the latest command ID for each user to allow cancellation
current_commands = {}  # {user_id: uuid.UUID}

# -----------------------------
# Keywords Categories 💡
# -----------------------------
KEYWORDS_CATEGORIES = {
    "🪖Garena": {
        "💀 CODM ACCOUNT": "garena.com",
        "💀 CODM": "sso.garena.com",
        "💀 NORMAL_COD_SITE": "100082.connect.garena.com",
        "💀 HIDDEN_COD_SITE": "authgop.garena.com/universal/oauth",
        "💀 PREMIUM_COD_SITE": "authgop.garena.com/oauth/login",
        "💀 PALDO_COD_SITE": "auth.garena.com/ui/login",
        "💀 PREMIUM_SITE (2)": "auth.garena.com/oauth/login",
        "💀 PREMIUM_SITE (3)": "sso.garena.com/universal/login",
        "💀 PREMIUM_SITE (4)": "sso.garena.com/ui/register",
        "💀100055": "100055.connect.garena.com",
        "💀100080": "100080.connect.garena.com",
        "💀100054": "100054.connect.garena.com",
        "💀100072": "100072.connect.garena.com",
        "🔥🎮 Free Fire (Garena)": "ff.garena.com",
        "🏆🎖️ Arena of Valor (Garena)": "account.aov.garena.com",
    },
    "🛡️Mobilelegends": {
        "⚔️🏆MLBB_SITE": "mtacc.mobilelegends.com",
        "⚔️🏆HIDDEN_MLBB_SITE": "play.mobilelegends.com",
        "⚔️🏆MLBB_PREMIUM": "m.mobilelegends.com",
        "⚔️🏆REALMLBB_SITE": "mobilelegends.com",
    },
    "🌐Social Media": {
        "📘👥 Facebook": "facebook.com",
        "💬📲 WhatsApp": "whatsapp.com",
        "🎵🎶 TikTok": "tiktok.com",
        "🕊️❌ Twitter (Now X)": "twitter.com",
        "📱💙 Telegram": "web.telegram.org",
        "💬🐼 WeChat": "wechat.com",
        "🎧🗣️ Discord": "discord.com",
        "📱📸 Instagram": "instagram.com",
    },
    "🎬Cinema": {
        "🎬🍿 Netflix": "netflix.com",
        "🎬📺 YouTube": "youtube.com",
        "🎬🎭 Bilibili": "bilibili.com",
    },
    "🗃️Email Account": {
        "📩📜 COMBO_LIST_BY_JIAN(2)": "outlook.com",
        "📩📜 COMBO_LIST_BY_JIAN(3)": "hotmail.com",
        "📂📑 COMBOLIST_TXT": "google.com",
        "💎📜 HQ_COMBO_LIST": "yahoo.com",
    },
    "🎮Online Games": {
        "🏰🎮 Supercell": "supercell.com",
        "👾🔫 Blood Strikes": "bloodstrike.com",
        "🎱🏆 8Ball Pool": "miniclip.com",
        "🕹️🏗️ Roblox": "roblox.com",
        "👾🌍 Minecraft": "minecraft.net",
        "🎯⚔️ Riot Games": "auth.riotgames.com",
        "🕹️🌎 Genshin Impact/HoYoverse": "account.hoyoverse.com",
        "🏀🎮 2K Games": "accounts.2k.com",
        "⚔️🐉 World of Warcraft": "us.battle.net/wow",
        "🔫🏹 PUBG": "accounts.pubg.com",
        "🚁🔫 Warframe": "warframe.com",
        "🏹🛡️ Final Fantasy XIV": "secure.square-enix.com",
        "🛸🌌 Star Wars: The Old Republic": "swtor.com",
        "🚢⚓ Wargaming (World of Tanks, World of Warships)": "wargaming.net",
    }
}

# -----------------------------
# Regex Patterns for Accounts 📧
# -----------------------------
EMAIL_PATTERN = re.compile(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})[|:]([^\s]+)")
USERNAME_PATTERN = re.compile(r"([a-zA-Z0-9_]{6,})[|:]([^\s]+)")

# -----------------------------
# Thread Pool for Performance 🚀
# -----------------------------
executor = ThreadPoolExecutor(max_workers=5)

# -----------------------------
# Data Loading & Saving Functions 💾
# -----------------------------
def load_data():
    global keys, ALLOWED_USERS, generation_history
    try:
        with open(DATA_FILE, "rb") as f:
            data = pickle.load(f)
            keys = data.get("keys", {})
            ALLOWED_USERS = data.get("allowed_users", set())
            generation_history = data.get("generation_history", {})
    except FileNotFoundError:
        logging.warning("Data file not found. Starting with empty data. 🚧")
    except Exception as e:
        logging.error(f"Error loading data: {e}")

def save_data():
    try:
        with open(DATA_FILE, "wb") as f:
            pickle.dump({"keys": keys, "allowed_users": ALLOWED_USERS, "generation_history": generation_history}, f)
        logging.info("Data saved successfully. 💾")
    except Exception as e:
        logging.error(f"Error saving data: {e}")

def load_existing_accounts():
    saved_accounts = set()
    for file_path in SAVE_DIR.rglob("*.txt"):
        try:
            with file_path.open("r", errors="ignore") as f:
                saved_accounts.update(line.strip() for line in f)
        except Exception as e:
            logging.error(f"Error reading {file_path}: {e}")
    return saved_accounts

# -----------------------------
# Email Validation Function
# -----------------------------
def validate_emails_in_file(file_name):
    file_path = SAVE_DIR / file_name
    if not file_path.exists():
        return None, None, None
    with file_path.open("r", errors="ignore") as f:
        lines = f.readlines()
    valid_count = 0
    invalid_count = 0
    invalid_emails = []
    email_validator_pattern = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split(":")
        if parts:
            email = parts[0].strip()
            if email_validator_pattern.match(email):
                valid_count += 1
            else:
                invalid_count += 1
                invalid_emails.append(email)
    return valid_count, invalid_count, invalid_emails

# -----------------------------
# User and Key Validation Functions 🔍
# -----------------------------
def is_user_allowed(user_id):
    return user_id == ADMIN_ID or user_id in ALLOWED_USERS

def is_key_valid(user_id):
    if user_id in paused_users:
        return False
    if user_id == ADMIN_ID:
        return True
    if user_id in ALLOWED_USERS:
        if user_id in keys:
            expiration_time = keys[user_id]
            if datetime.now() < expiration_time:
                return True
            else:
                del keys[user_id]
                ALLOWED_USERS.remove(user_id)
                if user_id in generation_history:
                    del generation_history[user_id]
                save_data()
                return False
        else:
            ALLOWED_USERS.remove(user_id)
            if user_id in generation_history:
                del generation_history[user_id]
            save_data()
            return False
    return False

# -----------------------------
# Helper: Generate Custom Key (Format: 143-626-716)
# -----------------------------
def generate_custom_key():
    part1 = random.randint(100, 999)
    part2 = random.randint(100, 999)
    part3 = random.randint(100, 999)
    return f"{part1}-{part2}-{part3}"

# -----------------------------
# Decorators 🛡️
# -----------------------------
def check_key(func):
    async def wrapper(update: Update, context: CallbackContext):
        user = update.effective_user
        if not is_user_allowed(user.id) and not is_key_valid(user.id):
            custom_message = (
                "✨ WELCOME, PREMIUM USER!✨\n\n"
                "🔐 Access Denied!\n"
                "You need a Valid Access Key to unlock this bot's features.\n\n"
                "📩 Buy Your Key From: @ItsMeKuichiro\n\n"
                "✨ Why You Need a Key:\n"
                "🚀 Unlimited & Fast Searches\n"
                "🔒 Complete Privacy & Safety\n"
                "📆 Frequent Database Updates\n"
                "💡 24/7 Efficient Performance\n\n"
                "📌 Have a Key? Use /redeem <YourKey> to get started!"
            )
            if update.effective_message:
                await update.effective_message.reply_text(custom_message, parse_mode="Markdown")
            elif update.callback_query:
                await update.callback_query.answer(custom_message, show_alert=True)
            return
        return await func(update, context)
    return wrapper

def admin_only(func):
    async def wrapper(update: Update, context: CallbackContext):
        user = update.effective_user
        if user.id != ADMIN_ID:
            await update.effective_message.reply_text("❌ You don't have permission to use this command. 🚫")
            return
        return await func(update, context)
    return wrapper

# -----------------------------
# Admin Pause/Resume Functions ⏸️▶️
# -----------------------------
async def admin_pause_key(update: Update, context: CallbackContext):
    await update.effective_message.reply_text("⏸️ Please send the user ID to PAUSE the key.", parse_mode="Markdown")
    context.user_data["admin_action"] = "pause"

async def admin_resume_key(update: Update, context: CallbackContext):
    await update.effective_message.reply_text("▶️ Please send the user ID to RESUME the key.", parse_mode="Markdown")
    context.user_data["admin_action"] = "resume"

# -----------------------------
# Help Menu Command
# -----------------------------
@check_key
async def menu_help(update: Update, context: CallbackContext):
    help_text = (
        "🤖 **Bot Help Menu**\n\n"
        "• **🔍 Generate Txt:** Select a predefined keyword from our categories.\n"
        "• **✍️ Custom Keyword:** Enter your own custom keyword.\n"
        "• **🔑 Check Key Time:** View the expiration time of your access key.\n"
        "• **🔄 Start Again:** Restart the account generation process.\n"
        "• **💰 Price Of Key:** See the pricing for keys.\n\n"
        "Additional commands:\n"
        "• **/keywordsleft <keyword>**: Returns the number of available lines for the given keyword (e.g., `/keywordsleft garena.com`).\n\n"
        "For further assistance, please contact @ItsMeKuichiro"
    )
    await update.effective_message.reply_text(help_text, parse_mode="Markdown")

# -----------------------------
# Updated /keywordsleft Command
# -----------------------------
@check_key
async def keywords_left(update: Update, context: CallbackContext):
    message = update.effective_message
    if len(context.args) != 1:
        await message.reply_text("Usage: /keywordsleft <keyword>", parse_mode="Markdown")
        return
    search_keyword = context.args[0].lower()
    total = 0
    for file_path in LOGS_DIR.rglob("*.txt"):
        try:
            with file_path.open("r", errors="ignore") as f:
                for line in f:
                    if search_keyword in line.lower():
                        total += 1
        except Exception as e:
            logging.error(f"Error reading {file_path}: {e}")
    deducted = 0
    for file_path in SAVE_DIR.rglob("*.txt"):
        try:
            with file_path.open("r", errors="ignore") as f:
                for line in f:
                    if search_keyword in line.lower():
                        deducted += 1
        except Exception as e:
            logging.error(f"Error reading {file_path}: {e}")
    available = total - deducted
    await message.reply_text(f"Keyword `{search_keyword}` appears in {available} available lines.", parse_mode="Markdown")

# -----------------------------
# New: Report Appeal Feature
# -----------------------------
async def report_appeal_prompt(update: Update, context: CallbackContext):
    query = update.callback_query
    context.user_data["state"] = "awaiting_report"
    await query.message.reply_text("🚨 Please describe the issue you encountered with the bot:", parse_mode="Markdown")

# -----------------------------
# New: Admin Send Message Feature
# -----------------------------
@admin_only
async def admin_send_message_prompt(update: Update, context: CallbackContext):
    await update.effective_message.reply_text("📨 Please provide the target user's ID or username:", parse_mode="Markdown")
    context.user_data["state"] = "awaiting_send_message_target"

# -----------------------------
# New: Admin Announcement Feature
# -----------------------------
@admin_only
async def admin_announcement_prompt(update: Update, context: CallbackContext):
    await update.effective_message.reply_text("📢 Please provide the announcement message to broadcast to all users:", parse_mode="Markdown")
    context.user_data["state"] = "awaiting_announcement"

# -----------------------------
# New: Email Validator Prompt
# -----------------------------
@check_key
async def email_validator_prompt(update: Update, context: CallbackContext):
    await update.effective_message.reply_text("📧 Please send the filename (e.g. Results.txt) from the Generated Results folder to validate email accounts:", parse_mode="Markdown")
    context.user_data["state"] = "awaiting_email_validator_filename"

# -----------------------------
# Main Menu and Other Bot Commands 🎉
# -----------------------------
@check_key
async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    current_commands[user.id] = uuid.uuid4()
    message = update.effective_message
    keyboard = [
        [InlineKeyboardButton("🔍 Choose Keyword", callback_data="choose_keyword"),
         InlineKeyboardButton("✍️ Custom Keyword", callback_data="custom_keyword")],
        [InlineKeyboardButton("🔑 Check Key Time", callback_data="check_key_time"),
         InlineKeyboardButton("🔄 Start Again", callback_data="start_again")],
        [InlineKeyboardButton("🆘 Help", callback_data="menu_help"),
         InlineKeyboardButton("❌ Exit", callback_data="exit")],
        [InlineKeyboardButton("🔗 Join Here", callback_data="join_here"),
         InlineKeyboardButton("👨‍💻 Developer", callback_data="developer"),
         InlineKeyboardButton("❓ What Bot Can Do", callback_data="what_bot_can_do")],
        [InlineKeyboardButton("💰 Price Of Key", callback_data="price_of_key")],
        [InlineKeyboardButton("🚨 Report Appeal", callback_data="report_appeal")],
        [InlineKeyboardButton("📧 Email Validator", callback_data="email_validator")]
    ]
    if user.id == ADMIN_ID:
        keyboard.insert(0, [InlineKeyboardButton("🛠️ Admin Panel", callback_data="admin_panel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await message.reply_text("🤖 **Welcome to Premium Generator Bot!**\nChoose an option below: 🚀", reply_markup=reply_markup, parse_mode="Markdown")

@check_key
async def check_key_time(update: Update, context: CallbackContext):
    message = update.effective_message
    user = update.effective_user
    if user.id in keys:
        expiration_time = keys[user.id]
        time_remaining = expiration_time - datetime.now()
        days = time_remaining.days
        hours, remainder = divmod(time_remaining.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        await message.reply_text(f"🔐 KEY ACCEPTED!\n════════════════════════\n📅 EXPIRATION TIME:\n⏳ {days} DAYS | {hours} HOURS | {minutes} MINUTES | {seconds} SECONDS\n════════════════════════", parse_mode="Markdown")
    else:
        await message.reply_text("❌ **No active key found for your user ID.**", parse_mode="Markdown")

# -----------------------------
# /genkey Command (Admin Only) with Custom Key Format 🔑
# -----------------------------
@admin_only
async def genkey(update: Update, context: CallbackContext):
    message = update.effective_message
    if len(context.args) < 1:
        await message.reply_text("❌ Usage: /genkey <duration> (e.g., /genkey 1hours) ⏰")
        return
    duration_str = " ".join(context.args)
    try:
        duration = parse_duration(duration_str)
    except ValueError as e:
        await message.reply_text(f"❌ Invalid duration: {e} 🚫")
        return
    expiration_time = datetime.now() + duration
    custom_key = generate_custom_key()
    keys[custom_key] = expiration_time
    save_data()
    expiration_str = expiration_time.strftime("%Y-%m-%d %H:%M:%S")
    await message.reply_text(f"✅ Key generated: `{custom_key}`\nExpires at: `{expiration_str}` 🔐", parse_mode="Markdown")

# -----------------------------
# Extend and Deduct Key Commands (Admin Only) ⏳
# -----------------------------
@admin_only
async def extendkey(update: Update, context: CallbackContext):
    message = update.effective_message
    if len(context.args) != 2:
        await message.reply_text("❌ Usage: /extendkey <user_id> <duration> ⏰")
        return
    try:
        user_id_to_extend = int(context.args[0])
        duration_str = context.args[1]
        duration = parse_duration(duration_str)
    except ValueError:
        await message.reply_text("❌ Invalid user ID or duration format. 🚫")
        return
    if user_id_to_extend in keys:
        expiration_time = keys[user_id_to_extend]
        keys[user_id_to_extend] = expiration_time + duration
        new_expiration_time = expiration_time + duration
        new_expiration_str = new_expiration_time.strftime("%Y-%m-%d %H:%M:%S")
        await message.reply_text(f"✅ Key for User {user_id_to_extend} extended.\nNew expiration: `{new_expiration_str}` ⏳", parse_mode="Markdown")
    else:
        await message.reply_text(f"❌ No active key found for User {user_id_to_extend}.", parse_mode="Markdown")
    save_data()

@admin_only
async def deductkey(update: Update, context: CallbackContext):
    message = update.effective_message
    if len(context.args) != 2:
        await message.reply_text("❌ Usage: /deductkey <user_id> <duration> ⏰", parse_mode="Markdown")
        return
    try:
        user_id_to_deduct = int(context.args[0])
        duration_str = context.args[1]
        duration = parse_duration(duration_str)
    except ValueError:
        await message.reply_text("❌ Invalid user ID or duration format. 🚫", parse_mode="Markdown")
        return
    if user_id_to_deduct in keys:
        expiration_time = keys[user_id_to_deduct]
        keys[user_id_to_deduct] = expiration_time - duration
        new_expiration_time = expiration_time - duration
        new_expiration_str = new_expiration_time.strftime("%Y-%m-%d %H:%M:%S")
        await message.reply_text(f"✅ Key for User {user_id_to_deduct} reduced.\nNew expiration: `{new_expiration_str}` ⏳", parse_mode="Markdown")
    else:
        await message.reply_text(f"❌ No active key found for User {user_id_to_deduct}.", parse_mode="Markdown")
    save_data()

# -----------------------------
# /history Command (Admin Only) 📊
# -----------------------------
@admin_only
async def history(update: Update, context: CallbackContext):
    message = update.effective_message
    if len(context.args) != 1:
        await message.reply_text("❌ Usage: /history <user_id> 🔍", parse_mode="Markdown")
        return
    try:
        target_user = int(context.args[0])
    except ValueError:
        await message.reply_text("❌ Invalid user_id. Please enter a number. 🚫", parse_mode="Markdown")
        return
    if target_user in generation_history:
        data = generation_history[target_user]
        username = data.get("username", "N/A").replace("_", "\\_")
        generated_count = data.get("generated_count", 0)
        total_lines = data.get("total_lines", 0)
        msg = f"📊 **Generation History for User {target_user} (@{username}):**\n• Generated Count: `{generated_count}`\n• Total Lines Generated: `{total_lines}`"
        await message.reply_text(msg, parse_mode="Markdown")
    else:
        await message.reply_text("❌ No history found for that user. 📭", parse_mode="Markdown")

# -----------------------------
# Admin Panel Menu (Admin Only) with Additional Buttons ⏸️▶️
# -----------------------------
@admin_only
async def admin_panel(update: Update, context: CallbackContext):
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton("👥 List Users", callback_data="list_users"),
         InlineKeyboardButton("📊 Generation History", callback_data="generation_history")],
        [InlineKeyboardButton("⏱️ Deduct Key Time", callback_data="deduct_key_time"),
         InlineKeyboardButton("➕ Extend Key Time", callback_data="extend_key_time")],
        [InlineKeyboardButton("❌ Revoke User", callback_data="revoke_user")],
        [InlineKeyboardButton("⏸️ Pause Key", callback_data="pause_key"),
         InlineKeyboardButton("▶️ Resume Key", callback_data="resume_key")],
        [InlineKeyboardButton("📨 Send Message", callback_data="send_message")],
        [InlineKeyboardButton("📢 Announcement", callback_data="announcement")],
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("🛠️ **Admin Panel**\nChoose an admin command:", reply_markup=reply_markup, parse_mode="Markdown")

# -----------------------------
# Keyword Selection and Account Generation 💎
# -----------------------------
@check_key
async def choose_keyword(update: Update, context: CallbackContext):
    user = update.effective_user
    current_commands[user.id] = uuid.uuid4()
    query = update.callback_query
    keyboard = []
    row = []
    for category in KEYWORDS_CATEGORIES.keys():
        button = InlineKeyboardButton(category, callback_data=f"cat_{category}")
        row.append(button)
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("✍️ Custom Keyword", callback_data="custom_keyword")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("📌 **Select a category:**", reply_markup=reply_markup, parse_mode="Markdown")

async def show_keywords_for_category(update: Update, context: CallbackContext, category):
    user = update.effective_user
    current_commands[user.id] = uuid.uuid4()
    query = update.callback_query
    keywords = KEYWORDS_CATEGORIES.get(category, {})
    keyboard = []
    row = []
    for name, keyword in keywords.items():
        button = InlineKeyboardButton(name, callback_data=f"kw_{keyword}")
        row.append(button)
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"📌 **Select a keyword from {category}:**", reply_markup=reply_markup, parse_mode="Markdown")

@check_key
async def handle_keyword_selection(update: Update, context: CallbackContext):
    user = update.effective_user
    current_commands[user.id] = uuid.uuid4()
    query = update.callback_query
    data = query.data
    if data == "custom_keyword_confirm":
        keyword = context.user_data.get("custom_keyword")
    else:
        keyword = data.split("_", 1)[1]
    context.user_data["keyword"] = keyword
    context.user_data["state"] = "awaiting_number"
    await query.answer()
    await query.edit_message_text("✅ SELECTION SAVED!\n──────────────\nSEND THE NUMBER OF ACCOUNTS YOU WANT (e.g., `100`)\n", parse_mode="Markdown")

@check_key
async def handle_user_input(update: Update, context: CallbackContext):
    user = update.effective_user
    current_commands[user.id] = uuid.uuid4()
    message = update.effective_message
    state = context.user_data.get("state")
    
    # Handle admin actions
    if user.id == ADMIN_ID and context.user_data.get("admin_action") in ["pause", "resume"]:
        try:
            target_user = int(message.text)
            if context.user_data["admin_action"] == "pause":
                paused_users.add(target_user)
                await message.reply_text(f"⏸️ User {target_user}'s key has been paused.", parse_mode="Markdown")
            elif context.user_data["admin_action"] == "resume":
                if target_user in paused_users:
                    paused_users.remove(target_user)
                    await message.reply_text(f"▶️ User {target_user}'s key has been resumed.", parse_mode="Markdown")
                else:
                    await message.reply_text("User is not paused.", parse_mode="Markdown")
            context.user_data["admin_action"] = None
            return
        except ValueError:
            await message.reply_text("❌ Please send a valid user ID number.", parse_mode="Markdown")
            return

    # Handle send message target
    if state == "awaiting_send_message_target":
        target = message.text.strip()
        context.user_data["target"] = target
        context.user_data["state"] = "awaiting_send_message_content"
        await message.reply_text("📨 Please type the message you want to send to the user:", parse_mode="Markdown")
        return
    
    # Handle send message content
    elif state == "awaiting_send_message_content":
        message_to_send = message.text.strip()
        target = context.user_data.get("target")
        try:
            if target.startswith("@"):
                target = target
            else:
                try:
                    target = int(target)
                except ValueError:
                    target = target
            chat = await context.bot.get_chat(target)
            await context.bot.send_message(chat_id=chat.id, text=message_to_send)
            await message.reply_text(f"✅ Message successfully sent to {chat.username or chat.id}.", parse_mode="Markdown")
        except Exception as e:
            await message.reply_text(f"❌ Failed to send message: {e}", parse_mode="Markdown")
        context.user_data["state"] = None
        return

    # Handle announcement
    if state == "awaiting_announcement":
        announcement_text = message.text.strip()
        count = 0
        for user_id in ALLOWED_USERS:
            try:
                await context.bot.send_message(chat_id=user_id, text=f"📢 Announcement:\n\n{announcement_text}")
                count += 1
            except Exception as e:
                logging.error(f"Error sending announcement to {user_id}: {e}")
        await message.reply_text(f"✅ Announcement sent to {count} users.", parse_mode="Markdown")
        context.user_data["state"] = None
        return

    # Handle email validator
    if state == "awaiting_email_validator_filename":
        file_name = message.text.strip()
        valid_count, invalid_count, invalid_emails = validate_emails_in_file(file_name)
        if valid_count is None:
            await message.reply_text("❌ File not found. Please check the filename and try again.", parse_mode="Markdown")
        else:
            reply = f"✅ Email Validation Complete!\nValid Emails: {valid_count}\nInvalid Emails: {invalid_count}"
            if invalid_emails and len(invalid_emails) <= 10:
                reply += "\nInvalid: " + ", ".join(invalid_emails)
            await message.reply_text(reply, parse_mode="Markdown")
        context.user_data["state"] = None
        return

    # Handle account generation flow
    if state == "awaiting_number":
        try:
            num_accounts = int(message.text)
            if num_accounts <= 0:
                raise ValueError
            context.user_data["num_accounts"] = num_accounts
            context.user_data["state"] = "awaiting_filename"
            await message.reply_text("✅ NUMBER RECEIVED!\n────────────────────────\nSEND THE FILENAME TO CONTINUE.\n💾 (e.g., `Results.txt`)\n───────────────────────", parse_mode="Markdown")
        except ValueError:
            await message.reply_text("❌ Invalid number. Please send a valid number. 🚫", parse_mode="Markdown")
    elif state == "awaiting_filename":
        filename = message.text.strip()
        context.user_data["filename"] = filename
        context.user_data["state"] = None
        await generate_accounts(update, context)
    elif state == "awaiting_custom_keyword":
        custom_keyword = message.text.strip()
        context.user_data["custom_keyword"] = custom_keyword
        keyboard = [[InlineKeyboardButton("✅ Confirm", callback_data="custom_keyword_confirm")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await message.reply_text(f"You entered: `{custom_keyword}`\nConfirm?", reply_markup=reply_markup, parse_mode="Markdown")
        context.user_data["state"] = None

@check_key
async def generate_accounts(update: Update, context: CallbackContext):
    user = update.effective_user
    command_id = uuid.uuid4()
    current_commands[user.id] = command_id
    message = update.effective_message
    keyword = context.user_data.get("keyword")
    num_accounts = context.user_data.get("num_accounts")
    filename = context.user_data.get("filename")
    file_path = SAVE_DIR / filename
    
    await message.reply_text("🔍🚀 SEARCH IN PROGRESS...\n⏳ HOLD ON! WE'RE FINDING THE ACCOUNTS YOU NEED.", parse_mode="Markdown")
    
    saved_accounts = load_existing_accounts()
    loop = asyncio.get_running_loop()
    
    try:
        extracted_results = await loop.run_in_executor(
            executor, extract_accounts_fast, keyword, num_accounts, saved_accounts, command_id, user.id
        )
        
        if extracted_results is None:
            await message.reply_text("⚠️ Previous command was canceled. New command will take over.", parse_mode="Markdown")
            return

        # Write results to file
        content_to_write = "\n".join(extracted_results)
        file_path.write_text(content_to_write)
        
        # Wait before sending results
        await asyncio.sleep(2)
        
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        total_lines = len(extracted_results)
        summary_message = f"""
✅ SEARCH COMPLETE! ✅  
════════════════════════  
🪪NAME: `{filename}`  
🗓️DATE & TIME: `{current_datetime}`  
🔎TOTAL LINES: `{total_lines}`  
════════════════════════  
🥳THANKS FOR USING THE BOT!   
🖥️DEVELOPER: @ItsMeKuichiro  
        """
        
        # Send file and summary
        with open(file_path, "rb") as document:
            await message.reply_document(document=document, filename=filename)
        
        await message.reply_text(summary_message, parse_mode="Markdown")
        
        # Show option to choose again
        keyboard = [[InlineKeyboardButton("🔙 Choose Again Keyword", callback_data="choose_keyword")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await message.reply_text("Select a new keyword:", reply_markup=reply_markup)
        
        # Update generation history
        username = user.username if user.username else "N/A"
        update_generation_history(user.id, username, total_lines)
        
    except Exception as e:
        await message.reply_text(f"❌ Error during account generation: {e}", parse_mode="Markdown")
        logging.exception("Error in generate_accounts:")

def extract_accounts_fast(keyword, num_lines, saved_accounts, command_id, user_id):
    """Extract accounts from files matching the keyword"""
    file_paths = list(SAVE_DIR.rglob("*.txt")) + list(LOGS_DIR.rglob("*.txt"))
    file_paths = sorted(file_paths, key=lambda p: p.stat().st_mtime, reverse=True)
    results = set()

    def process_file(file_path):
        if current_commands.get(user_id) != command_id:
            return None
        local_results = set()
        try:
            with file_path.open("r", errors="ignore") as f:
                for line in f:
                    if current_commands.get(user_id) != command_id:
                        return None
                    if keyword.lower() in line.lower():
                        match = EMAIL_PATTERN.search(line) or USERNAME_PATTERN.search(line)
                        if match:
                            account = f"{match.group(1)}:{match.group(2)}"
                            if account not in saved_accounts and account not in local_results:
                                local_results.add(account)
                                if len(local_results) >= num_lines:
                                    break
            return list(local_results)
        except Exception as e:
            logging.error(f"Error reading {file_path}: {e}")
            return []

    # Process files in parallel
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(process_file, fp): fp for fp in file_paths}
        for future in as_completed(futures):
            if current_commands.get(user_id) != command_id:
                return None
            local_result = future.result()
            if local_result:
                results.update(local_result)
            if len(results) >= num_lines:
                break
    
    return list(results)[:num_lines]

def parse_duration(duration_str):
    """Parse duration string like '1days 2hours' into timedelta"""
    pattern = re.compile(r"(?:(\d+)\s*days?)?\s*(?:(\d+)\s*hours?)?\s*(?:(\d+)\s*minutes?)?\s*(?:(\d+)\s*seconds?)?", re.IGNORECASE)
    match = pattern.fullmatch(duration_str.strip())
    if not match:
        raise ValueError("Invalid duration format. Use formats like '1days', '1hours', '1minutes', etc.")
    days = int(match.group(1)) if match.group(1) else 0
    hours = int(match.group(2)) if match.group(2) else 0
    minutes = int(match.group(3)) if match.group(3) else 0
    seconds = int(match.group(4)) if match.group(4) else 0
    if all(v == 0 for v in [days, hours, minutes, seconds]):
        raise ValueError("Duration must have at least one nonzero value.")
    return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)

def redeem_key(key, user_id):
    """Redeem a key for a user"""
    if key in keys:
        expiration_time = keys[key]
        if datetime.now() < expiration_time:
            keys[user_id] = expiration_time
            ALLOWED_USERS.add(user_id)
            used_keys.add(key)
            del keys[key]
            save_data()
            return "success"
        else:
            used_keys.add(key)
            del keys[key]
            save_data()
            return "wrong_key"
    else:
        if key in used_keys:
            return "already_redeemed"
        else:
            return "wrong_key"

async def redeem(update: Update, context: CallbackContext):
    """Handle /redeem command"""
    message = update.effective_message
    user = update.effective_user
    key = context.args[0] if context.args else None
    if not key:
        await message.reply_text("❌ Please provide a key using /redeem <YourKey>.", parse_mode="Markdown")
        return
    
    result = redeem_key(key, user.id)
    if result == "success":
        expiry_date = keys[user.id].strftime('%Y-%m-%d %H:%M:%S')
        username = user.username if user.username else "N/A"
        username = username.replace("_", "\\_")
        await message.reply_text(
            f"🎉 REDEMPTION SUCCESSFUL! ✅\n───────────────────────\n👤 USERNAME: @{username}\n⏳ ACCESS EXPIRES: {expiry_date}\n───────────────────────\nYOU NOW HAVE ACCESS TO THE BOT! 🚀 Type /start to continue.",
            parse_mode="Markdown"
        )
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🎉 Successful Redeem by {username} (ID: {user.id})")
    elif result == "already_redeemed":
        await message.reply_text(
            "⚠️ Error: Key Already Redeemed!\n"
            "🔑 The key you are trying to redeem has been used before.\n"
            "💡 Please ensure you enter a valid key.\n"
            "📲 For a new key, contact @ItsMeKuichiro",
            parse_mode="Markdown"
        )
    elif result == "wrong_key":
        await message.reply_text(
            "🚫 Wrong Key Entered!\n"
            "❗ This key is not valid or has already expired.\n"
            "🔍 Please make sure to redeem the correct key.\n"
            "📲 Contact @ItsMeKuichiro to purchase a key.",
            parse_mode="Markdown"
        )
    save_data()

@admin_only
async def revoke(update: Update, context: CallbackContext):
    """Revoke a user's access"""
    message = update.effective_message
    if context.args:
        user_id_to_revoke = int(context.args[0])
        ALLOWED_USERS.discard(user_id_to_revoke)
        if user_id_to_revoke in keys:
            del keys[user_id_to_revoke]
        await message.reply_text(f"✅ User {user_id_to_revoke} revoked.", parse_mode="Markdown")
        save_data()
    else:
        await message.reply_text("❌ Please specify a user ID to revoke. 🚫", parse_mode="Markdown")

@admin_only
async def list_users(update: Update, context: CallbackContext):
    """List all active users"""
    query = update.callback_query
    all_users = ALLOWED_USERS.union({ADMIN_ID})
    active_users = set()
    for user_id in all_users:
        if user_id == ADMIN_ID or is_key_valid(user_id):
            active_users.add(user_id)
    
    user_list = "📋 **ACTIVE USERS (Active Keys Only):**\n════════════════════════\n"
    for user_id in active_users:
        try:
            user = await context.bot.get_chat(user_id)
            username = user.username if user.username else "N/A"
            full_name = f"{user.first_name} {user.last_name}" if user.last_name else user.first_name
            username = username.replace("_", "\\_")
            full_name = full_name.replace("_", "\\_")
        except Exception as e:
            username = "N/A"
            full_name = "N/A"
            logging.error(f"Error getting chat for user {user_id}: {e}")
        
        expiration_str = keys[user_id].strftime("%Y-%m-%d %H:%M:%S") if user_id in keys else "N/A"
        user_list += (
            f"👤 User ID: `{user_id}`\n"
            f"🔗 Username: @{username}\n"
            f"📝 Name: {full_name}\n"
            f"⏳ Key Expiration: `{expiration_str}`\n"
            "─────────────────────────\n"
        )
    
    if not user_list.strip():
        user_list = "❌ **No Active Users Found.**"
    
    await query.message.reply_text(user_list, parse_mode="Markdown")

@admin_only
async def generation_history_command(update: Update, context: CallbackContext):
    """Show generation history for all users"""
    query = update.callback_query
    report = "📊 **GENERATION HISTORY REPORT:**\n══════════════════════\n"
    if not generation_history:
        report += "❌ **No generation history found.**"
    else:
        for user_id, data in generation_history.items():
            username = data.get("username", "N/A").replace("_", "\\_")
            generated_count = data.get("generated_count", 0)
            total_lines = data.get("total_lines", 0)
            report += f"👤 User ID: `{user_id}`\n🔗 Username: @{username}\n📈 Generated Count: `{generated_count}`\n📝 Total Lines Generated: `{total_lines}`\n─────────────────────────────\n"
    await query.message.reply_text(report, parse_mode="Markdown")

@admin_only
async def deduct_key_time(update: Update, context: CallbackContext):
    """Prompt for deduct key time"""
    await update.callback_query.message.reply_text("Please send the user ID and the duration to deduct in the format: `/deductkey <user_id> <duration>`", parse_mode="Markdown")

@admin_only
async def extend_key_time(update: Update, context: CallbackContext):
    """Prompt for extend key time"""
    await update.callback_query.message.reply_text("Please send the user ID and the duration to extend in the format: `/extendkey <user_id> <duration>`", parse_mode="Markdown")

def update_generation_history(user_id, username, total_lines):
    """Update generation history for a user"""
    if user_id in generation_history:
        generation_history[user_id]["generated_count"] += 1
        generation_history[user_id]["total_lines"] += total_lines
    else:
        generation_history[user_id] = {"username": username, "generated_count": 1, "total_lines": total_lines}
    save_data()

@admin_only
async def price_of_key(update: Update, context: CallbackContext):
    """Show key pricing"""
    query = update.callback_query
    price_message = (
        "🔥𝙿𝚁𝙸𝙲𝙴 𝙾𝙵 𝙺𝙴𝚈 🔥\n"
        "────────────\n"
        "✅  𝟐𝟓𝟎 - 𝑳𝒊𝒇𝒆𝒕𝒊𝒎𝒆\n"
        "✅ 𝟐𝟎𝟎 - 𝟑𝟎 𝐃𝐚𝐲𝐬\n"
        "✅ 𝟏𝟎𝟎 - 𝟕 𝐃𝐚𝐲𝐬\n"
        "✅ 𝟓𝟎   - 𝟑 𝐃𝐚𝐲𝐬\n"
        "────────────\n"
        "☎️ 𝙲𝙾𝙽𝚃𝙰𝙲𝚃 - @ItsMeKuichiro\n"
        "𝚃𝙾 𝙰𝚅𝙰𝙸𝙻 𝙺𝙴𝚈 🗝️"
    )
    await query.edit_message_text(price_message, parse_mode="Markdown")

async def button(update: Update, context: CallbackContext):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    user = query.from_user
    
    # Check if user has valid access
    if not is_user_allowed(user.id):
        await query.answer("🚫 Access Denied!\n❌ Your key has expired or is paused.\n🔑 Please redeem a valid key to continue.", show_alert=True)
        return
    if not is_key_valid(user.id):
        await query.answer("⛔ Invalid Key!\n❌ Your key is no longer valid or is paused.\n🔑 Please redeem a new key to regain access.", show_alert=True)
        return

    # Handle different button actions
    if query.data == "choose_keyword":
        await choose_keyword(update, context)
    elif query.data.startswith("cat_"):
        category = query.data.split("_", 1)[1]
        await show_keywords_for_category(update, context, category)
    elif query.data == "custom_keyword":
        context.user_data["state"] = "awaiting_custom_keyword"
        await query.message.reply_text("✍️ Enter your custom keyword: 💬", parse_mode="Markdown")
    elif query.data == "custom_keyword_confirm":
        await handle_keyword_selection(update, context)
    elif query.data.startswith("kw_"):
        await handle_keyword_selection(update, context)
    elif query.data == "start_again":
        await start(update, context)
    elif query.data == "check_key_time":
        await check_key_time(update, context)
    elif query.data == "exit":
        await query.message.edit_text("👋 Goodbye! 👋", parse_mode="Markdown")
    elif query.data == "main_menu":
        await start(update, context)
    elif query.data == "list_users":
        await list_users(update, context)
    elif query.data == "generation_history":
        await generation_history_command(update, context)
    elif query.data == "deduct_key_time":
        await deduct_key_time(update, context)
    elif query.data == "extend_key_time":
        await extend_key_time(update, context)
    elif query.data == "menu_help":
        await menu_help(update, context)
    elif query.data == "admin_panel":
        await admin_panel(update, context)
    elif query.data == "pause_key":
        await admin_pause_key(update, context)
    elif query.data == "resume_key":
        await admin_resume_key(update, context)
    elif query.data == "join_here":
        keyboard = [
            [InlineKeyboardButton("📣 Telegram Channel", url="https://t.me/KuichiroMain")],
            [InlineKeyboardButton("💬 Telegram Discussion", url="https://t.me/KuichiroMainGroup")],
            [InlineKeyboardButton("🛒 Proof of Buying", url="https://t.me/ItsMeKuichiro")],
            [InlineKeyboardButton("💬 Feedback", url="https://t.me/KuichiroMainGroup")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Join our community: 🤝", reply_markup=reply_markup)
    elif query.data == "developer":
        await query.message.edit_text("👨‍💻 **Developer Info**\n\nThis bot was developed by @ItsMeKuichiro 💻", parse_mode="Markdown")
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Return to main menu:", reply_markup=reply_markup)
    elif query.data == "what_bot_can_do":
        message_text = (
            "🤖 **What This Bot Can Do:**\n\n"
            "• Generate premium accounts based on selected keywords. 💎\n"
            "• Allow custom keyword searches. 🔍\n"
            "• Manage key validity and access control. 🔐\n"
            "• Show generation history (admin only). 📊\n"
            "• Provide various Telegram community links. 🔗\n"
            "• And more features as updated by the developer. 🚀"
        )
        await query.message.edit_text(message_text, parse_mode="Markdown")
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Return to main menu:", reply_markup=reply_markup)
    elif query.data == "price_of_key":
        await price_of_key(update, context)
    elif query.data == "revoke_user":
        await query.edit_message_text("Please use the command `/revoke <user_id>` to revoke a user. 🚫", parse_mode="Markdown")
    elif query.data == "report_appeal":
        await report_appeal_prompt(update, context)
    elif query.data == "send_message":
        await admin_send_message_prompt(update, context)
    elif query.data == "announcement":
        await admin_announcement_prompt(update, context)
    elif query.data == "email_validator":
        await email_validator_prompt(update, context)
    else:
        await query.answer("Unrecognized command. 🚫")

async def error_handler(update: Update, context: CallbackContext):
    """Handle errors"""
    logging.error(msg="Exception while handling an update:", exc_info=context.error)
    try:
        await context.bot.send_message(ADMIN_ID, text=f"Exception:\n{context.error}")
    except:
        pass  # Ignore errors when sending error messages

def main():
    """Main function to start the bot"""
    # Load existing data
    load_data()
    
    # Create application
    app = Application.builder().token(TOKEN).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("genkey", genkey))
    app.add_handler(CommandHandler("redeem", redeem))
    app.add_handler(CommandHandler("revoke", revoke))
    app.add_handler(CommandHandler("extendkey", extendkey))
    app.add_handler(CommandHandler("deductkey", deductkey))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("keywordsleft", keywords_left))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_input))
    app.add_handler(CallbackQueryHandler(button))
    app.add_error_handler(error_handler)

    # Start the bot
    logging.info("Starting bot...")
    app.run_polling()

if __name__ == "__main__":
    main()