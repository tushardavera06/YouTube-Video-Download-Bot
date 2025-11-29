from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import os, json, time, shutil
from datetime import datetime

# ====== Paths & constants ======
DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
SERVICES_FILE = os.path.join(DATA_DIR, "services.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
LOG_FILE = os.path.join(DATA_DIR, "logs.txt")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")

# yaha apna Telegram user id daalo (owner)
ADMINS = [2136583087]

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)


# ====== Generic helpers ======
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ====== Config & roles ======
def get_config():
    cfg = load_json(CONFIG_FILE, {})
    if "roles" not in cfg:
        cfg["roles"] = {}
    if "messages" not in cfg:
        cfg["messages"] = {}
    save_config(cfg)
    return cfg


def save_config(cfg):
    save_json(CONFIG_FILE, cfg)


def get_role(user_id: int) -> str:
    uid = str(user_id)
    cfg = get_config()
    roles = cfg.get("roles", {})
    if user_id in ADMINS or uid in [str(x) for x in ADMINS]:
        return "owner"
    return roles.get(uid, "none")


def set_role(user_id: int, role: str):
    uid = str(user_id)
    cfg = get_config()
    roles = cfg.setdefault("roles", {})
    if role == "none":
        roles.pop(uid, None)
    else:
        roles[uid] = role
    save_config(cfg)


def is_admin_id(user_id: int) -> bool:
    return get_role(user_id) in ["owner", "admin", "mod"]


def admin_filter(_, __, message):
    if not message.from_user:
        return False
    return is_admin_id(message.from_user.id)


admin_only = filters.create(admin_filter)


# ====== Users ======
def load_users():
    return load_json(USERS_FILE, {})


def save_users(data):
    save_json(USERS_FILE, data)


def register_user(user):
    if user is None:
        return
    data = load_users()
    uid = str(user.id)
    if uid not in data:
        data[uid] = {
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "username": user.username or "",
            "language": getattr(user, "language_code", "") or "",
            "joined_at": now_str(),
            "last_active": now_str(),
            "total_downloads": 0,
            "total_mb": 0,
            "blocked": False,
        }
    else:
        data[uid]["last_active"] = now_str()
        data[uid]["first_name"] = user.first_name or ""
        data[uid]["last_name"] = user.last_name or ""
        data[uid]["username"] = user.username or ""
    save_users(data)


def add_download_stat(user_id: int, file_size_bytes: int):
    data = load_users()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {
            "first_name": "",
            "last_name": "",
            "username": "",
            "language": "",
            "joined_at": now_str(),
            "last_active": now_str(),
            "total_downloads": 0,
            "total_mb": 0,
            "blocked": False,
        }
    data[uid]["total_downloads"] += 1
    data[uid]["total_mb"] += round(file_size_bytes / (1024 * 1024))
    data[uid]["last_active"] = now_str()
    save_users(data)


def is_blocked(user_id: int) -> bool:
    data = load_users()
    return data.get(str(user_id), {}).get("blocked", False)


# simple in-memory rate limit
RATE_LIMIT = {}
MAX_REQ_PER_MIN = 10
WINDOW_SEC = 60


def is_rate_limited(user_id: int) -> bool:
    now = time.time()
    lst = RATE_LIMIT.get(user_id, [])
    lst = [t for t in lst if now - t < WINDOW_SEC]
    lst.append(now)
    RATE_LIMIT[user_id] = lst
    return len(lst) > MAX_REQ_PER_MIN


# ====== Services ======
def load_services():
    return load_json(SERVICES_FILE, {})


def save_services(data):
    save_json(SERVICES_FILE, data)


# ====== Messages helpers ======
def get_message(key: str, default: str) -> str:
    cfg = get_config()
    msgs = cfg.setdefault("messages", {})
    return msgs.get(key, default)


def set_message(key: str, value: str):
    cfg = get_config()
    msgs = cfg.setdefault("messages", {})
    msgs[key] = value
    save_config(cfg)


# ====== Admin commands ======

@Client.on_message(filters.command("admins") & admin_only)
async def cmd_admins(client, message):
    cfg = get_config()
    roles = cfg.get("roles", {})
    text = "🛡 **Admins & Mods**\n\n"
    text += "Owner(s):\n"
    for x in ADMINS:
        text += f" • `{x}` (owner)\n"
    if roles:
        text += "\nRoles:\n"
        for uid, r in roles.items():
            text += f" • `{uid}` → {r}\n"
    await message.reply(text)


@Client.on_message(filters.command("addadmin") & filters.user(ADMINS))
async def cmd_addadmin(client, message):
    if len(message.command) < 2:
        return await message.reply("Use: /addadmin user_id")
    try:
        uid = int(message.command[1])
    except Exception:
        return await message.reply("Galat user_id")
    set_role(uid, "admin")
    await message.reply(f"✅ {uid} ko admin bana diya.")


@Client.on_message(filters.command("addmod") & filters.user(ADMINS))
async def cmd_addmod(client, message):
    if len(message.command) < 2:
        return await message.reply("Use: /addmod user_id")
    try:
        uid = int(message.command[1])
    except Exception:
        return await message.reply("Galat user_id")
    set_role(uid, "mod")
    await message.reply(f"✅ {uid} ko moderator bana diya.")


@Client.on_message(filters.command("removeadmin") & filters.user(ADMINS))
async def cmd_removeadmin(client, message):
    if len(message.command) < 2:
        return await message.reply("Use: /removeadmin user_id")
    try:
        uid = int(message.command[1])
    except Exception:
        return await message.reply("Galat user_id")
    set_role(uid, "none")
    await message.reply(f"✅ {uid} se admin/mod role hata diya.")


# users stats

@Client.on_message(filters.command("users") & admin_only)
async def cmd_users(client, message):
    data = load_users()
    total = len(data)
    blocked = sum(1 for u in data.values() if u.get("blocked"))
    total_downloads = sum(u.get("total_downloads", 0) for u in data.values())
    total_mb = sum(u.get("total_mb", 0) for u in data.values())
    text = (
        "👥 **Users Stats**\n\n"
        f"• Total Users: `{total}`\n"
        f"• Blocked Users: `{blocked}`\n"
        f"• Total Downloads: `{total_downloads}`\n"
        f"• Total Data: `{total_mb}` MB\n"
    )
    await message.reply(text)


def format_user(uid, info):
    name = (info.get("first_name", "") + " " + info.get("last_name", "")).strip() or "—"
    uname = f"@{info['username']}" if info.get("username") else "—"
    text = (
        f"🧾 **User Details**\n\n"
        f"ID: `{uid}`\n"
        f"Name: {name}\n"
        f"Username: {uname}\n"
        f"Language: `{info.get('language', '—')}`\n\n"
        f"Joined: `{info.get('joined_at', '—')}`\n"
        f"Last Active: `{info.get('last_active', '—')}`\n\n"
        f"Total Downloads: `{info.get('total_downloads', 0)}`\n"
        f"Total MB: `{info.get('total_mb', 0)}` MB\n"
        f"Blocked: `{info.get('blocked', False)}`\n"
    )
    return text


@Client.on_message(filters.command("user") & admin_only)
async def cmd_user(client, message):
    data = load_users()
    if len(message.command) > 1:
        uid = message.command[1]
    elif message.reply_to_message and message.reply_to_message.from_user:
        uid = str(message.reply_to_message.from_user.id)
    else:
        return await message.reply("Use: `/user user_id` ya reply karke `/user` likho.")
    if uid not in data:
        return await message.reply("❌ User record nahi mila.")
    await message.reply(format_user(uid, data[uid]))


@Client.on_message(filters.command("export_users") & admin_only)
async def cmd_export_users(client, message):
    if not os.path.exists(USERS_FILE):
        return await message.reply("Users file nahi mili.")
    await message.reply_document(USERS_FILE, caption="📁 users.json")


# services

@Client.on_message(filters.command("addservice") & admin_only)
async def cmd_addservice(client, message):
    if len(message.command) < 2:
        return await message.reply("Use: `/addservice 🔍 | Name | key | note`")
    try:
        raw = message.text.split(" ", 1)[1]
        parts = [x.strip() for x in raw.split("|")]
        if len(parts) < 3:
            raise ValueError
        emoji, name, key = parts[0], parts[1], parts[2]
        note = parts[3] if len(parts) > 3 else ""
    except Exception:
        return await message.reply("Format galat hai. Example:\n`/addservice 🔍 | Number Lookup | num_lookup | test`")
    data = load_services()
    data[key] = {
        "emoji": emoji,
        "name": name,
        "note": note,
        "created_at": now_str(),
    }
    save_services(data)
    await message.reply(f"✅ Service added:\n{emoji} **{name}**\nKey: `{key}`")


@Client.on_message(filters.command("services") & admin_only)
async def cmd_services(client, message):
    data = load_services()
    if not data:
        return await message.reply("ℹ️ Abhi tak koi service add nahi hai.")
    text = "🧾 **All Services:**\n\n"
    for key, s in data.items():
        text += f"{s.get('emoji','•')} **{s.get('name','?')}** — `{key}`\n"
    await message.reply(text)


@Client.on_message(filters.command("delservice") & admin_only)
async def cmd_delservice(client, message):
    if len(message.command) < 2:
        return await message.reply("Use: /delservice key")
    key = message.command[1]
    data = load_services()
    if key not in data:
        return await message.reply("❌ Service nahi mili.")
    s = data.pop(key)
    save_services(data)
    await message.reply(f"🗑 Deleted: {s.get('emoji','')} {s.get('name','')} (`{key}`)")


# stats

@Client.on_message(filters.command("stats") & admin_only)
async def cmd_stats(client, message):
    users = load_users()
    total = len(users)
    today = datetime.now().strftime("%Y-%m-%d")
    today_new = sum(1 for u in users.values() if u.get("joined_at", "").startswith(today))
    total_downloads = sum(u.get("total_downloads", 0) for u in users.values())
    total_mb = sum(u.get("total_mb", 0) for u in users.values())
    text = (
        "📊 **Bot Stats**\n\n"
        f"• Total Users: `{total}`\n"
        f"• New Today: `{today_new}`\n"
        f"• Total Downloads: `{total_downloads}`\n"
        f"• Total Data: `{total_mb}` MB\n"
    )
    await message.reply(text)


@Client.on_message(filters.command("topusers") & admin_only)
async def cmd_topusers(client, message):
    users = load_users()
    ranked = sorted(users.items(), key=lambda kv: kv[1].get("total_downloads", 0), reverse=True)[:10]
    if not ranked:
        return await message.reply("No data.")
    text = "🏆 **Top Users (Downloads)**\n\n"
    for uid, info in ranked:
        text += f"• `{uid}` → {info.get('total_downloads', 0)} downloads\n"
    await message.reply(text)


# security block/unblock

@Client.on_message(filters.command("block") & admin_only)
async def cmd_block(client, message):
    if len(message.command) < 2:
        return await message.reply("Use: /block user_id")
    uid = message.command[1]
    data = load_users()
    if uid not in data:
        return await message.reply("User record nahi mila.")
    data[uid]["blocked"] = True
    save_users(data)
    await message.reply(f"🚫 User `{uid}` blocked.")


@Client.on_message(filters.command("unblock") & admin_only)
async def cmd_unblock(client, message):
    if len(message.command) < 2:
        return await message.reply("Use: /unblock user_id")
    uid = message.command[1]
    data = load_users()
    if uid not in data:
        return await message.reply("User record nahi mila.")
    data[uid]["blocked"] = False
    save_users(data)
    await message.reply(f"✅ User `{uid}` unblocked.")


# debug / tools

@Client.on_message(filters.command("ping") & admin_only)
async def cmd_ping(client, message):
    start = time.time()
    m = await message.reply("Pinging...")
    ms = int((time.time() - start) * 1000)
    await m.edit(f"🏓 Pong: `{ms} ms`")


@Client.on_message(filters.command("server") & admin_only)
async def cmd_server(client, message):
    total_users = len(load_users())
    text = (
        "🖥 **Server Info (basic)**\n\n"
        f"• Tracked users: `{total_users}`\n"
        f"• Time: `{now_str()}`\n"
    )
    await message.reply(text)


@Client.on_message(filters.command("logs") & admin_only)
async def cmd_logs(client, message):
    if not os.path.exists(LOG_FILE):
        return await message.reply("Log file nahi mili.")
    await message.reply_document(LOG_FILE, caption="📄 logs.txt")


# custom messages

@Client.on_message(filters.command("setmsg") & filters.user(ADMINS))
async def cmd_setmsg(client, message):
    if len(message.command) < 2:
        return await message.reply("Use: `/setmsg key | text`")
    try:
        raw = message.text.split(" ", 1)[1]
        key, val = [x.strip() for x in raw.split("|", 1)]
    except Exception:
        return await message.reply("Format galat hai.\nExample:\n`/setmsg start | Welcome to my bot`")
    set_message(key, val)
    await message.reply(f"✅ Message `{key}` update ho gaya.")


# backup

@Client.on_message(filters.command("backupnow") & admin_only)
async def cmd_backupnow(client, message):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = os.path.join(BACKUP_DIR, f"backup_{ts}")
    os.makedirs(folder_name, exist_ok=True)
    for f in [USERS_FILE, SERVICES_FILE, CONFIG_FILE, LOG_FILE]:
        if os.path.exists(f):
            shutil.copy(f, folder_name)
    zip_path = folder_name + ".zip"
    shutil.make_archive(folder_name, "zip", folder_name)
    await message.reply_document(zip_path, caption="📦 Backup: users, services, config, logs")
