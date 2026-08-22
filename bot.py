import telebot
import requests
import json
import os
import re
import signal
import threading
from datetime import datetime
import time
from uuid import uuid4
from html import escape
from pymongo import MongoClient, ReturnDocument

# ─────────────────────────────────────────────────────────────
#  CONFIG FILE  (all settings live here – editable at runtime)
# RydenX─────────────────────────────────────────────────────────────
CONFIG_FILE = "config.json"
MONGODB_URI = os.getenv("MONGODB_URI")
if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI secret is required to start the bot.")

mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
mongo_client.admin.command("ping")
try:
    mongo_db = mongo_client.get_default_database()
except Exception:
    mongo_db = None
mongo_db = mongo_db or mongo_client["telegram_smm_bot"]
settings_collection = mongo_db["settings"]
users_collection = mongo_db["users"]
orders_collection = mongo_db["orders"]
gift_codes_collection = mongo_db["gift_codes"]
services_collection = mongo_db["services"]
wallet_reservations_collection = mongo_db["wallet_reservations"]
wallet_ledger_collection = mongo_db["wallet_ledger"]

wallet_reservations_collection.create_index(
    [("reservation_id", 1)], unique=True, name="unique_reservation_id"
)
wallet_ledger_collection.create_index(
    [("reservation_id", 1), ("event", 1)],
    unique=True,
    name="unique_reservation_event",
)

DEFAULT_CONFIG = {
    "bot_token":          os.getenv("BOT_TOKEN", ""),
    "smm_panel_url":      "https://indiansmm.store/api/v2",
    "smm_api_key":        os.getenv("9abc9233d182a83ddc1c12bff50d75b16e3fe449", ""),

    # Rates
    "provider_rate_reactions": 10,
    "provider_rate_views":     100,
    "provider_rate_members":   1,
    "markup_percentage":   50.0,
    "referral_reward_inr":  25.0,
    "daily_bonus_inr":      10.0,

    # Service IDs
    "service_id_reactions": 476,
    "service_id_views":     500,
    "service_id_members":   470,

    # Logs channel (username without @ or chat_id as string)
    "logs_channel": "-1004434715037",

    # Force-join channels
    "channels": [
        {"name": "🌺 MAIN", "username": "-1004357091931", "url": "https://t.me/+JSco8U0Ej6c2Zjk1"},
        {"name": "🤖 JOIN", "username": "-1004490909992", "url": "https://t.me/+gaYXF8qAdTdiMWU1"}
    ],

    "qr_code_url": "https://t.me/bobbyQr/2",
    "main_menu_photo_file_id": "",
    "payment_contact": "@BOBBY_2606",
    "bot_username": "Bobby SMM Bot"
}


def load_config():
    data = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
    stored = settings_collection.find_one({"_id": "app"}) or {}
    stored.pop("_id", None)

    config = DEFAULT_CONFIG.copy()
    config.update(data)

    # Never let stale MongoDB values overwrite the currently configured channels.
    # The active force-join list must come from the live config file/defaults only.
    stored.pop("channels", None)
    config.update(stored)

    # Secrets supplied through the environment always take precedence over
    # values that may have been present in an imported config file.
    for key, env_key in (("bot_token", "BOT_TOKEN"), ("smm_api_key", "SMM_API_KEY")):
        if os.getenv(env_key):
            config[key] = os.environ[env_key]
    save_config(config)
    return config


def save_config(cfg):
    settings_collection.replace_one({"_id": "app"}, {"_id": "app", **cfg}, upsert=True)


cfg = load_config()


DEFAULT_SERVICES = [
    {
        "_id": "reactions",
        "name": "👍 Order Reactions",
        "provider_service_id": 476,
        "category": "Reactions",
        "min": 10,
        "max": 2147483647,
        "price": 10,
        "enabled": True,
    },
    {
        "_id": "views",
        "name": "👀 Order Views",
        "provider_service_id": 500,
        "category": "Views",
        "min": 10,
        "max": 2147483647,
        "price": 100,
        "enabled": True,
    },
    {
        "_id": "members",
        "name": "👥 Order Members",
        "provider_service_id": 470,
        "category": "Members",
        "min": 10,
        "max": 2147483647,
        "price": 1,
        "enabled": True,
    },
]


def ensure_default_services():
    """Seed only the original three services on a new services collection."""
    if services_collection.count_documents({}) != 0:
        return
    rates = {
        "reactions": cfg["provider_rate_reactions"],
        "views": cfg["provider_rate_views"],
        "members": cfg["provider_rate_members"],
    }
    for service in DEFAULT_SERVICES:
        seeded = service.copy()
        seeded["provider_service_id"] = cfg[f"service_id_{service['_id']}"]
        seeded["price"] = rates[service["_id"]]
        seeded["provider_rate"] = float(rates[service["_id"]])
        services_collection.insert_one(seeded)


ensure_default_services()

# ─────────────────────────────────────────────────────────────
#  BOT INIT
# ─────────────────────────────────────────────────────────────
if not cfg["bot_token"]:
    raise RuntimeError("BOT_TOKEN secret or a persisted bot_token setting is required.")
bot = telebot.TeleBot(cfg["bot_token"], parse_mode="HTML")


def shutdown_handler(signum, frame):
    print(f"[SHUTDOWN] Received signal {signum}. Stopping polling gracefully.")
    try:
        bot.stop_polling()
    except Exception:
        pass
    raise SystemExit(0)


signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)

# ─────────────────────────────────────────────────────────────
#  IN-MEMORY USER DATA
# ─────────────────────────────────────────────────────────────
user_balances        = {}   # {user_id: float}
user_last_bonus      = {}   # {user_id: date}
user_referrals       = {}   # {user_id: {"referrer": int, "rewarded": bool}}
users                = set()
gift_codes           = {}   # {code: INR amount}
banned_users         = set()
user_redeemed_codes  = {}   # {user_id: set of codes}
user_orders          = {}   # {user_id: [order_dict]}
user_state           = {}   # FSM state per user
wallet_balance_lock  = threading.RLock()


def parse_admin_ids():
    raw = os.getenv("ADMIN_IDS", "")
    ids = set()
    for value in raw.replace(",", " ").split():
        try:
            ids.add(int(value))
        except ValueError:
            print(f"[ADMIN_IDS] Ignoring invalid admin ID: {value}")
    return ids


ADMIN_IDS = parse_admin_ids()
if not ADMIN_IDS:
    raise RuntimeError("ADMIN_IDS must contain at least one Telegram user ID.")


def primary_admin_id():
    return min(ADMIN_IDS) if ADMIN_IDS else None


def persist_user(user_id):
    user_id = int(user_id)
    users_collection.update_one(
        {"_id": user_id},
        {"$set": {
            "balance": float(user_balances.get(user_id, 0)),
            "last_bonus": (
                user_last_bonus[user_id].isoformat()
                if user_id in user_last_bonus else None
            ),
            "referral": user_referrals.get(user_id),
            "redeemed_codes": sorted(user_redeemed_codes.get(user_id, set())),
            "banned": user_id in banned_users,
        }},
        upsert=True,
    )


def wallet_atomic_debit(user_id, amount, session=None):
    """Reduce a user's balance only when the account has enough funds."""
    user_id = int(user_id)
    amount = float(amount)
    if amount < 0:
        raise ValueError("Wallet debit amount cannot be negative.")
    if amount == 0:
        return users_collection.find_one({"_id": user_id}, session=session) or {"_id": user_id, "balance": 0}
    return users_collection.find_one_and_update(
        {"_id": user_id, "balance": {"$gte": amount}},
        {"$inc": {"balance": -amount}},
        return_document=ReturnDocument.AFTER,
        session=session,
    )


def wallet_hold(user_id, amount, order_id=None, reservation_id=None):
    """Atomically reserve available INR and create its durable ledger entry."""
    user_id = int(user_id)
    amount = float(amount)
    if amount <= 0:
        raise ValueError("Wallet reservation amount must be positive.")

    reservation_id = reservation_id or uuid4().hex
    now = datetime.now().isoformat()
    with wallet_balance_lock:
        with mongo_client.start_session() as session:
            with session.start_transaction():
                existing = wallet_reservations_collection.find_one(
                    {"_id": reservation_id}, session=session
                )
                if existing:
                    if (
                        existing["user_id"] != user_id or
                        float(existing["amount"]) != amount
                    ):
                        raise ValueError("Reservation ID is already in use.")
                    current_user = users_collection.find_one(
                        {"_id": user_id}, session=session
                    ) or {}
                    return {
                        "reservation_id": reservation_id,
                        "amount": amount,
                        "status": existing["status"],
                        "balance": float(current_user.get("balance", 0)),
                    }

                updated_user = wallet_atomic_debit(user_id, amount, session=session)
                if not updated_user:
                    return None

                wallet_reservations_collection.insert_one(
                    {
                        "_id": reservation_id,
                        "reservation_id": reservation_id,
                        "user_id": user_id,
                        "amount": amount,
                        "order_id": order_id,
                        "status": "pending",
                        "created_at": now,
                        "updated_at": now,
                    },
                    session=session,
                )
                wallet_ledger_collection.insert_one(
                    {
                        "_id": f"{reservation_id}:hold",
                        "reservation_id": reservation_id,
                        "order_id": order_id,
                        "user_id": user_id,
                        "event": "hold",
                        "amount": -amount,
                        "created_at": now,
                    },
                    session=session,
                )

        user_balances[user_id] = float(updated_user["balance"])
        send_log(
            f"💰 <b>Wallet debited</b>\n"
            f"User: <code>{user_id}</code>\n"
            f"Amount: ₹{amount:.2f}\n"
            f"Reservation: <code>{reservation_id}</code>"
        )
    return {
        "reservation_id": reservation_id,
        "amount": amount,
        "balance": float(updated_user["balance"]),
    }


def wallet_settle(reservation_id, order_id):
    """Settle a pending reservation exactly once; retries are harmless."""
    now = datetime.now().isoformat()
    with mongo_client.start_session() as session:
        with session.start_transaction():
            reservation = wallet_reservations_collection.find_one_and_update(
                {"_id": reservation_id, "status": "pending"},
                {
                    "$set": {
                        "status": "settled",
                        "order_id": order_id,
                        "updated_at": now,
                    }
                },
                return_document=ReturnDocument.AFTER,
                session=session,
            )
            if reservation:
                wallet_ledger_collection.insert_one(
                    {
                        "_id": f"{reservation_id}:settle",
                        "reservation_id": reservation_id,
                        "order_id": order_id,
                        "user_id": reservation["user_id"],
                        "event": "settle",
                        "amount": 0,
                        "created_at": now,
                    },
                    session=session,
                )
                return True

            existing = wallet_reservations_collection.find_one(
                {"_id": reservation_id}, session=session
            )
            return bool(existing and existing.get("status") == "settled")


def wallet_release(reservation_id, order_id=None):
    """Release a pending reservation exactly once; retries are harmless."""
    now = datetime.now().isoformat()
    with wallet_balance_lock:
        with mongo_client.start_session() as session:
            with session.start_transaction():
                reservation = wallet_reservations_collection.find_one_and_update(
                    {"_id": reservation_id, "status": "pending"},
                    {
                        "$set": {
                            "status": "released",
                            "order_id": order_id,
                            "updated_at": now,
                        }
                    },
                    return_document=ReturnDocument.AFTER,
                    session=session,
                )
                if reservation:
                    updated_user = users_collection.find_one_and_update(
                        {"_id": reservation["user_id"]},
                        {"$inc": {"balance": reservation["amount"]}},
                        return_document=ReturnDocument.AFTER,
                        session=session,
                    )
                    if not updated_user:
                        raise RuntimeError("Wallet user disappeared during release.")
                    wallet_ledger_collection.insert_one(
                        {
                            "_id": f"{reservation_id}:release",
                            "reservation_id": reservation_id,
                            "order_id": order_id,
                            "user_id": reservation["user_id"],
                            "event": "release",
                            "amount": reservation["amount"],
                            "created_at": now,
                        },
                        session=session,
                    )
                    user_balances[reservation["user_id"]] = float(updated_user["balance"])
                    send_log(
                        f"💰 <b>Wallet credited</b>\n"
                        f"User: <code>{reservation['user_id']}</code>\n"
                        f"Amount: ₹{float(reservation['amount']):.2f}\n"
                        f"Reservation: <code>{reservation_id}</code>"
                    )
                    return True

                existing = wallet_reservations_collection.find_one(
                    {"_id": reservation_id}, session=session
                )
                return bool(existing and existing.get("status") == "released")


def wallet_mark_pending(reservation_id, reason):
    """Record an ambiguous provider outcome without changing the hold."""
    wallet_reservations_collection.update_one(
        {"_id": reservation_id, "status": "pending"},
        {
            "$set": {
                "provider_state": "pending",
                "pending_reason": reason,
                "updated_at": datetime.now().isoformat(),
            }
        },
    )


def wallet_mark_request_attempted(reservation_id, provider_request_id):
    """Durably record that a provider request was dispatched so retries never re-submit."""
    now = datetime.now().isoformat()
    return wallet_reservations_collection.find_one_and_update(
        {"_id": reservation_id, "status": "pending", "provider_request_id": {"$exists": False}},
        {"$set": {
            "provider_request_id": provider_request_id,
            "provider_state": "requested",
            "updated_at": now,
        }},
        return_document=ReturnDocument.AFTER,
    )


def wallet_retry_status(reservation_id):
    """Check a pending reservation without ever re-submitting to the provider."""
    reservation = wallet_reservations_collection.find_one({"_id": reservation_id})
    if not reservation:
        return {"status": "not_found"}
    status = reservation.get("status")
    if status == "settled":
        return {"status": "settled", "order_id": reservation.get("order_id")}
    if status == "released":
        return {"status": "released"}
    return {
        "status": "pending",
        "provider_request_id": reservation.get("provider_request_id"),
        "reason": reservation.get("pending_reason"),
    }


def pending_reservation_markup(reservation_id):
    mk = telebot.types.InlineKeyboardMarkup()
    mk.add(telebot.types.InlineKeyboardButton(
        "🔄 Retry", callback_data=f"retry_res:{reservation_id}"
    ))
    return mk


def persist_order(user_id, order):
    orders_collection.insert_one({"user_id": int(user_id), **order})


def persist_gift_code(code, amount):
    gift_codes_collection.replace_one(
        {"_id": code},
        {"_id": code, "amount": float(amount), "points": float(amount)},
        upsert=True,
    )


def delete_gift_code(code):
    gift_codes_collection.delete_one({"_id": code})


def load_persistent_state():
    for document in users_collection.find({}):
        user_id = int(document["_id"])
        users.add(user_id)
        user_balances[user_id] = float(document.get("balance", 0))
        if document.get("last_bonus"):
            user_last_bonus[user_id] = datetime.strptime(
                document["last_bonus"], "%Y-%m-%d"
            ).date()
        if document.get("referral"):
            user_referrals[user_id] = document["referral"]
        user_redeemed_codes[user_id] = set(document.get("redeemed_codes", []))
        if document.get("banned"):
            banned_users.add(user_id)

    for document in orders_collection.find({}).sort("_id", 1):
        user_orders.setdefault(int(document["user_id"]), []).append(
            {key: value for key, value in document.items()
             if key not in {"_id", "user_id"}}
        )

    for document in gift_codes_collection.find({}):
        gift_codes[document["_id"]] = float(document.get("amount", document.get("points", 0)))


load_persistent_state()

MAIN_COMMANDS = [
    "👍 Order Reactions", "👀 Order Views", "👥 Order Members",
    "💰 Check Balance", "🎁 Claim Bonus", "➕ Add Funds",
    "📢 Refer & Earn", "🔳 GiftCode", "💬 Feedback", "🔎 Search Service",
    "� Services", "�🖲 Track Order", "📜 Order History"
]

# ─────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────
def _safe_float(value, default=0.0):
    if value is None or value is False or value == "":
        return default
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def is_admin(uid):
    return int(uid) in ADMIN_IDS


def get_enabled_services():
    return list(services_collection.find({"enabled": True}).sort([("category", 1), ("name", 1)]))


def get_provider_rate(service):
    for field in ("rate", "cost"):
        legacy_rate = _safe_float(service.get(field), 0.0)
        if legacy_rate > 0:
            return legacy_rate

    provider_rate = _safe_float(service.get("provider_rate"), 0.0)
    if provider_rate > 0:
        return provider_rate
    return _safe_float(service.get("price"), 0.0)


def calculate_default_selling_price(provider_rate):
    provider_rate = _safe_float(provider_rate, 0.0)
    markup = _safe_float(cfg.get("markup_percentage"), 0.0)
    return provider_rate + (provider_rate * markup / 100.0)


def get_selling_rate(service):
    override = _safe_float(service.get("selling_price"), 0.0)
    if override > 0:
        return override
    legacy_override = _safe_float(service.get("selling_rate"), 0.0)
    if legacy_override > 0:
        return legacy_override
    return calculate_default_selling_price(get_provider_rate(service))


def format_selling_price(price):
    return f"{float(price):.2f}".rstrip("0").rstrip(".")


def ensure_custom_selling_prices():
    for service in services_collection.find({}):
        if _safe_float(service.get("selling_price"), 0.0) > 0:
            continue
        default_price = get_selling_rate(service)
        if default_price > 0:
            services_collection.update_one(
                {"_id": service["_id"]},
                {"$set": {"selling_price": default_price}}
            )


ensure_custom_selling_prices()


def get_order_charge(service, quantity):
    return float(quantity) / 1000.0 * get_selling_rate(service)


def get_enabled_service_by_name(name):
    if not name:
        return None
    return services_collection.find_one({"name": name, "enabled": True})


def get_service_by_id(service_id, enabled_only=False):
    query = {"_id": service_id}
    if enabled_only:
        query["enabled"] = True
    return services_collection.find_one(query)


def is_main_command(text):
    return text in MAIN_COMMANDS or get_enabled_service_by_name(text) is not None


def send_log(text, disable_preview=True):
    """Send message to logs channel if configured."""
    ch = cfg.get("logs_channel", "").strip()
    if not ch:
        return
    try:
        # Accept @username or numeric chat_id
        target = ch if ch.startswith("-") else ("@" + ch.lstrip("@"))
        bot.send_message(target, text, disable_web_page_preview=disable_preview)
    except Exception as e:
        print(f"[LOG CHANNEL ERROR] {e}")


def normalize_channel_target(value):
    if value is None:
        return None
    target = str(value).strip()
    if not target:
        return None
    target = target.replace("https://t.me/", "").replace("t.me/", "")
    if target.startswith("+"):
        target = target[1:]
    if target.startswith("@"):
        target = target[1:]
    if re.fullmatch(r"-?\d+", target):
        return int(target)
    return "@" + target


def user_has_joined_all_channels(user_id):
    if is_admin(user_id):
        return True

    for ch in cfg.get("channels", []):
        channel_name = ch.get("name") or ch.get("username") or "channel"
        target_value = ch.get("username") or ch.get("chat_id") or ch.get("id")
        target = normalize_channel_target(target_value)
        if target is None:
            print(f"[CHANNEL CONFIG ERROR] channel={channel_name} target={target_value!r} user={user_id} error=missing_channel_target")
            return False

        try:
            bot.get_chat(target)
        except Exception as e:
            print(f"[CHANNEL CHECK ERROR] channel={channel_name} target={target} user={user_id} error_type={type(e).__name__} error={e}")
            return False

        try:
            member = bot.get_chat_member(target, user_id)
        except Exception as e:
            print(f"[CHANNEL CHECK ERROR] channel={channel_name} target={target} user={user_id} error_type={type(e).__name__} error={e}")
            return False

        status = getattr(member, "status", None)
        if status in ("member", "administrator", "creator", "restricted"):
            continue
        if status is None and getattr(member, "is_member", False):
            continue
        return False

    return True


def reload_cfg():
    global cfg
    cfg = load_config()


# ─────────────────────────────────────────────────────────────
#  SAFE WRAPPERS
# ─────────────────────────────────────────────────────────────
def safe_handler(func):
    def wrapper(message, *args, **kwargs):
        try:
            if not hasattr(message, 'text') and message.content_type != 'photo':
                bot.send_message(message.chat.id, "❌ Please send a text message.")
                return
            return func(message, *args, **kwargs)
        except Exception as e:
            print(f"[HANDLER ERROR] {func.__name__}: {e}")
            send_log(f"⚠️ <b>Bot error</b>\nHandler: <code>{func.__name__}</code>\nError type: <code>{type(e).__name__}</code>")
            try:
                bot.send_message(message.chat.id, "❌ Something went wrong. Please try again.")
            except Exception:
                pass
    return wrapper


def safe_callback(func):
    def wrapper(call, *args, **kwargs):
        try:
            return func(call, *args, **kwargs)
        except Exception as e:
            print(f"[CALLBACK ERROR] {func.__name__}: {e}")
            send_log(f"⚠️ <b>Bot error</b>\nCallback: <code>{func.__name__}</code>\nError type: <code>{type(e).__name__}</code>")
            try:
                bot.answer_callback_query(call.id, "❌ Something went wrong.")
            except Exception:
                pass
    return wrapper


def require_not_banned(func):
    def wrapper(message, *args, **kwargs):
        try:
            if message.chat.id in banned_users:
                bot.send_message(message.chat.id, "🚫 You are banned from using this bot.")
                return
            if is_main_command(message.text):
                user_state.pop(message.chat.id, None)
            return func(message, *args, **kwargs)
        except Exception as e:
            print(f"[BAN WRAPPER ERROR]: {e}")
    return wrapper


# ─────────────────────────────────────────────────────────────
#  KEYBOARDS  – USER RydenX
# ─────────────────────────────────────────────────────────────
def join_menu():
    markup = telebot.types.InlineKeyboardMarkup()
    channels = cfg["channels"]
    # Row 1 – first channel alone
    if channels:
        markup.add(telebot.types.InlineKeyboardButton(channels[0]["name"], url=channels[0]["url"]))
    # Pair remaining channels 2-per-row
    for i in range(1, len(channels), 2):
        row_btns = [telebot.types.InlineKeyboardButton(channels[i]["name"], url=channels[i]["url"])]
        if i + 1 < len(channels):
            row_btns.append(telebot.types.InlineKeyboardButton(channels[i+1]["name"], url=channels[i+1]["url"]))
        markup.row(*row_btns)
    markup.add(telebot.types.InlineKeyboardButton("✅ Joined", callback_data="joined"))
    return markup


def main_menu():
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        telebot.types.InlineKeyboardButton("🛒 ORDER SERVICES", callback_data="svc_catalog_home"),
        telebot.types.InlineKeyboardButton("📦 MY ORDERS", callback_data="main_menu_my_orders"),
    )
    markup.add(
        telebot.types.InlineKeyboardButton("💳 ADD FUNDS", callback_data="main_menu_add_funds"),
        telebot.types.InlineKeyboardButton("💰 WALLET", callback_data="main_menu_check_balance"),
    )
    markup.add(
        telebot.types.InlineKeyboardButton("👥 REFER & EARN", callback_data="main_menu_refer"),
        telebot.types.InlineKeyboardButton("📞 SUPPORT", callback_data="main_menu_support"),
    )
    markup.add(telebot.types.InlineKeyboardButton("ℹ️ HELP", callback_data="main_menu_help"))
    return markup


def main_menu_caption(user_id, first_name=None):
    name = escape(str(first_name or "there").strip() or "there")
    balance = float(user_balances.get(user_id, 0))
    return (
        f"👋 Welcome, {name}!\n\n"
        "🚀 <b>Bobby SMM Panel</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"💰 Wallet Balance: ₹{balance:.2f}\n"
        "⚡ Fast Delivery • Best Rates • 24/7 Support\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "🛍️ Choose an option below:"
    )


def send_main_menu(chat_id, first_name=None):
    caption = main_menu_caption(chat_id, first_name)
    photo_file_id = str(cfg.get("main_menu_photo_file_id") or "").strip()
    if photo_file_id:
        try:
            return bot.send_photo(chat_id, photo_file_id, caption=caption, reply_markup=main_menu())
        except Exception as exc:
            print(f"[MAIN MENU PHOTO ERROR] {type(exc).__name__}: {exc}")
    return bot.send_message(chat_id, caption, reply_markup=main_menu())


def make_dummy_message(chat_id, text):
    class ChatProxy:
        id = chat_id

    class MessageProxy:
        def __init__(self, chat_id_value, text_value):
            self.chat = ChatProxy()
            self.chat.id = chat_id_value
            self.text = text_value

    return MessageProxy(chat_id, text)


def trigger_main_menu_action(call, action_text):
    message = make_dummy_message(call.message.chat.id, action_text)
    if action_text == "📦 My Orders":
        my_orders(message)
    elif action_text == "💰 Check Balance":
        check_balance(message)
    elif action_text == "➕ Add Funds":
        add_funds(message)
    elif action_text == "📢 Refer & Earn":
        refer_earn(message)
    elif action_text == "🔎 Search Service":
        search_service(message)
    elif action_text == "📞 Support":
        bot.send_message(
            call.message.chat.id,
            f"📞 <b>Support</b>\n\nFor assistance, contact {escape(str(cfg.get('payment_contact') or primary_admin_id()))}.",
            reply_markup=main_menu(),
        )
    elif action_text == "ℹ️ Help":
        bot.send_message(
            call.message.chat.id,
            "ℹ️ <b>Help</b>\n\nChoose a service, enter the required link and quantity, then confirm your order.\n\nUse Wallet to check your balance or Add Funds to recharge.",
            reply_markup=main_menu(),
        )


def get_service_platform(service):
    platform = str(service.get("platform") or "").strip()
    if platform:
        return platform

    category = str(service.get("category") or "General").strip() or "General"
    return category.split(None, 1)[0]


def format_service_platform(platform):
    icons = {
        "instagram": "📸",
        "youtube": "▶️",
        "telegram": "✈️",
        "facebook": "👍",
        "twitter": "🐦",
        "twitter/x": "🐦",
        "x": "🐦",
        "tiktok": "🎵",
    }
    icon = icons.get(str(platform).strip().lower())
    return f"{icon} {platform}" if icon else str(platform)


ALLOWED_USER_SERVICE_CATEGORIES = {
    "Instagram": ("Instagram Followers", "Instagram Likes", "Instagram Views", "Instagram Comments", "Instagram Story Views", "Instagram Reels Views", "Instagram Saves", "Instagram Shares"),
    "YouTube": ("YouTube Subscribers", "YouTube Likes", "YouTube Views", "YouTube Comments"),
    "Telegram": ("Telegram Members", "Telegram Views", "Telegram Reactions", "Telegram Comments"),
    "Facebook": ("Facebook Followers", "Facebook Likes", "Facebook Views", "Facebook Comments"),
    "Twitter/X": ("Twitter Followers", "Twitter Likes", "Twitter Views", "Twitter Retweets", "Twitter Comments"),
    "TikTok": ("TikTok Followers", "TikTok Likes", "TikTok Views", "TikTok Comments"),
}

PLATFORM_ALIASES = {
    "instagram": "Instagram",
    "insta": "Instagram",
    "ig": "Instagram",
    "youtube": "YouTube",
    "yt": "YouTube",
    "telegram": "Telegram",
    "tg": "Telegram",
    "facebook": "Facebook",
    "fb": "Facebook",
    "twitter": "Twitter/X",
    "twitter/x": "Twitter/X",
    "x": "Twitter/X",
    "tiktok": "TikTok",
}

SERVICE_TYPE_ALIASES = (
    ("Story Views", ("story views?",)),
    ("Reels Views", ("reels? views?", "shorts? views?")),
    ("Subscribers", ("subscribers?", "subs?")),
    ("Followers", ("followers?", "fans?")),
    ("Retweets", ("retweets?", "reposts?")),
    ("Comments", ("comments?",)),
    ("Reactions", ("reactions?",)),
    ("Members", ("members?",)),
    ("Likes", ("likes?",)),
    ("Views", ("views?",)),
    ("Saves", ("saves?", "bookmarks?")),
    ("Shares", ("shares?",)),
)


def find_platform(text):
    normalized = str(text or "").lower().replace("tiktok", "tik tok")
    for alias in sorted(PLATFORM_ALIASES, key=len, reverse=True):
        if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", normalized):
            return PLATFORM_ALIASES[alias]
    return None


def find_service_type(text):
    normalized = str(text or "").lower()
    for display_type, patterns in SERVICE_TYPE_ALIASES:
        if any(re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", normalized) for pattern in patterns):
            return display_type
    return None

def get_user_catalog_service_parts(service):
    """Return normalized catalog parts from provider platform, category, and name."""
    raw_platform = str(service.get("platform") or "")
    raw_category = str(service.get("category") or "")
    raw_name = str(service.get("name") or "")
    platform = find_platform(raw_platform)
    if not platform:
        platform = find_platform(f"{raw_category} {raw_name}")
    if not platform:
        return None

    category = find_service_type(f"{raw_category} {raw_name}")
    if category not in ALLOWED_USER_SERVICE_CATEGORIES[platform]:
        return None
    return platform, category


def is_user_catalog_service(service):
    return bool(service and service.get("enabled") and get_user_catalog_service_parts(service))


def get_enabled_services_by_platform_category():
    services = list(services_collection.find({"enabled": True}).sort([("category", 1), ("name", 1)]))
    grouped = {}
    for service in services:
        parts = get_user_catalog_service_parts(service)
        if not parts:
            continue
        platform, category = parts
        grouped.setdefault(platform, {}).setdefault(category, []).append(service)
    return grouped


def get_platform_name_from_id(platform_id):
    platforms = sorted(get_enabled_services_by_platform_category(), key=lambda text: text.lower())
    try:
        platform_id = int(platform_id)
    except (TypeError, ValueError):
        return None
    if 0 <= platform_id < len(platforms):
        return platforms[platform_id]
    return None


def get_category_name_from_id(platform, category_id):
    categories = sorted(
        get_enabled_services_by_platform_category().get(platform, {}),
        key=lambda text: text.lower()
    )
    try:
        category_id = int(category_id)
    except (TypeError, ValueError):
        return None
    if 0 <= category_id < len(categories):
        return categories[category_id]
    return None


def service_catalog_home_markup(page=0, page_size=6):
    grouped = get_enabled_services_by_platform_category()
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    platforms = sorted(grouped, key=lambda text: text.lower())
    if not platforms:
        markup.add(telebot.types.InlineKeyboardButton("🏠 Home", callback_data="svc_catalog_home"))
        return markup

    total_pages = max(1, (len(platforms) + page_size - 1) // page_size)
    page = max(0, min(page, total_pages - 1))
    start = page * page_size
    end = start + page_size
    for platform_id, platform in enumerate(platforms[start:end], start=start):
        service_count = sum(len(services) for services in grouped[platform].values())
        markup.add(telebot.types.InlineKeyboardButton(
            f"{format_service_platform(platform)} ({service_count})",
            callback_data=f"svc_catalog_platform:{platform_id}"
        ))

    if total_pages > 1:
        nav_row = []
        nav_row.append(telebot.types.InlineKeyboardButton(
            "⬅️ Previous" if page > 0 else "⬅️ Previous",
            callback_data=f"svc_catalog_home_page:{page - 1}" if page > 0 else "svc_catalog_home_disabled"
        ))
        nav_row.append(telebot.types.InlineKeyboardButton(
            "➡️ Next" if page + 1 < total_pages else "➡️ Next",
            callback_data=f"svc_catalog_home_page:{page + 1}" if page + 1 < total_pages else "svc_catalog_home_disabled"
        ))
        markup.row(*nav_row)

    markup.add(telebot.types.InlineKeyboardButton("🏠 Home", callback_data="svc_catalog_home"))
    return markup


def service_catalog_platform_markup(platform, page=0, page_size=6):
    grouped = get_enabled_services_by_platform_category().get(platform, {})
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    categories = sorted(grouped, key=lambda text: text.lower())
    total_pages = max(1, (len(categories) + page_size - 1) // page_size)
    page = max(0, min(page, total_pages - 1))
    start = page * page_size
    end = start + page_size
    platform_id = sorted(
        get_enabled_services_by_platform_category(), key=lambda text: text.lower()
    ).index(platform)
    for category_id, category in enumerate(categories[start:end], start=start):
        service_count = len(grouped[category])
        category_price = min(get_selling_rate(service) for service in grouped[category])
        markup.add(telebot.types.InlineKeyboardButton(
            f"{format_service_platform(platform)} {category} — ₹{format_selling_price(category_price)}/1K ({service_count})",
            callback_data=f"svc_catalog_category:{platform_id}:{category_id}"
        ))

    if total_pages > 1:
        nav_row = []
        nav_row.append(telebot.types.InlineKeyboardButton(
            "⬅️ Previous" if page > 0 else "⬅️ Previous",
            callback_data=f"svc_catalog_platform_page:{platform_id}:{page - 1}" if page > 0 else "svc_catalog_page_disabled"
        ))
        nav_row.append(telebot.types.InlineKeyboardButton(
            "➡️ Next" if page + 1 < total_pages else "➡️ Next",
            callback_data=f"svc_catalog_platform_page:{platform_id}:{page + 1}" if page + 1 < total_pages else "svc_catalog_page_disabled"
        ))
        markup.row(*nav_row)

    markup.add(telebot.types.InlineKeyboardButton("⬅️ Back", callback_data="svc_catalog_home"))
    return markup


def service_catalog_category_markup(platform, category, page=0, page_size=6):
    grouped = get_enabled_services_by_platform_category().get(platform, {})
    services = grouped.get(category, [])
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    total_pages = max(1, (len(services) + page_size - 1) // page_size)
    page = max(0, min(page, total_pages - 1))
    start = page * page_size
    end = start + page_size
    platform_id = sorted(
        get_enabled_services_by_platform_category(), key=lambda text: text.lower()
    ).index(platform)
    categories = sorted(grouped, key=lambda text: text.lower())
    category_id = categories.index(category)
    for service in services[start:end]:
        markup.add(telebot.types.InlineKeyboardButton(
            f"{service['name']} — ₹{get_selling_rate(service):.2f}/1K",
            callback_data=f"svc_catalog_service:{service['_id']}"
        ))

    if total_pages > 1:
        nav_row = []
        nav_row.append(telebot.types.InlineKeyboardButton(
            "⬅️ Previous",
            callback_data=f"svc_catalog_category_page:{platform_id}:{category_id}:{page - 1}" if page > 0 else "svc_catalog_page_disabled"
        ))
        nav_row.append(telebot.types.InlineKeyboardButton(
            "➡️ Next",
            callback_data=f"svc_catalog_category_page:{platform_id}:{category_id}:{page + 1}" if page + 1 < total_pages else "svc_catalog_page_disabled"
        ))
        markup.row(*nav_row)

    markup.add(telebot.types.InlineKeyboardButton("⬅️ Back", callback_data=f"svc_catalog_platform:{platform_id}"))
    markup.add(telebot.types.InlineKeyboardButton("🏠 Home", callback_data="svc_catalog_home"))
    return markup


def service_catalog_details_markup(service_id, platform, category):
    platform_id = sorted(
        get_enabled_services_by_platform_category(), key=lambda text: text.lower()
    ).index(platform)
    categories = sorted(
        get_enabled_services_by_platform_category().get(platform, {}),
        key=lambda text: text.lower()
    )
    category_id = categories.index(category)
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    markup.add(telebot.types.InlineKeyboardButton(
        "🛒 Order Now",
        callback_data=f"svc_catalog_order_now:{service_id}"
    ))
    markup.add(telebot.types.InlineKeyboardButton(
        "⬅️ Back",
        callback_data=f"svc_catalog_category:{platform_id}:{category_id}"
    ))
    markup.add(telebot.types.InlineKeyboardButton("🏠 Home", callback_data="svc_catalog_home"))
    return markup


def send_service_catalog_home(message):
    grouped = get_enabled_services_by_platform_category()
    if not grouped:
        bot.send_message(
            message.chat.id,
            "🛍 <b>Services</b>\n\nNo enabled services are available right now.",
            reply_markup=main_menu()
        )
        return

    lines = ["🛍 <b>Order Services</b>", "📂 <b>Categories / Platforms</b>"]
    text = "\n".join(lines)
    bot.send_message(message.chat.id, text, reply_markup=service_catalog_home_markup())


@bot.message_handler(func=lambda m: m.text == "🛍 Services")
@safe_handler
@require_not_banned
def service_catalog_entry(message):
    send_service_catalog_home(message)


@bot.callback_query_handler(func=lambda c: c.data == "svc_catalog_home")
@safe_callback
def service_catalog_home_callback(call):
    text = "🛍 <b>Order Services</b>\n\n📂 <b>Categories / Platforms</b>"
    try:
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=service_catalog_home_markup()
        )
    except Exception as exc:
        if "message is not modified" not in str(exc).lower():
            raise
        bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda c: c.data.startswith("svc_catalog_home_page:"))
@safe_callback
def service_catalog_home_page_callback(call):
    try:
        page = int(call.data.split(":", 1)[1])
    except (TypeError, ValueError):
        page = 0
    bot.edit_message_text(
        "🛍 <b>Order Services</b>\n\n📂 <b>Categories / Platforms</b>",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=service_catalog_home_markup(page=page)
    )


@bot.callback_query_handler(func=lambda c: c.data == "svc_catalog_home_disabled")
@safe_callback
def service_catalog_home_disabled_callback(call):
    bot.answer_callback_query(call.id, "No more platforms to show.")


@bot.callback_query_handler(func=lambda c: c.data.startswith("svc_catalog_platform:"))
@safe_callback
def service_catalog_platform_callback(call):
    platform_id = call.data.split(":", 1)[1]
    platform = get_platform_name_from_id(platform_id)
    if platform is None:
        bot.answer_callback_query(call.id, "❌ Invalid platform.")
        return

    grouped = get_enabled_services_by_platform_category()
    if not grouped.get(platform):
        bot.answer_callback_query(call.id, "❌ No categories in this platform.")
        return

    bot.edit_message_text(
        f"📂 <b>{escape(platform)}</b>\n\nSelect a category:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=service_catalog_platform_markup(platform)
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("svc_catalog_platform_page:"))
@safe_callback
def service_catalog_platform_page_callback(call):
    try:
        _, platform_id, page_str = call.data.split(":", 2)
        page = int(page_str)
    except (TypeError, ValueError):
        bot.answer_callback_query(call.id, "❌ Invalid platform page.")
        return

    platform = get_platform_name_from_id(platform_id)
    if platform is None:
        bot.answer_callback_query(call.id, "❌ Invalid platform.")
        return

    bot.edit_message_text(
        f"📂 <b>{escape(platform)}</b>\n\nSelect a category:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=service_catalog_platform_markup(platform, page=page)
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("svc_catalog_category:"))
@safe_callback
def service_catalog_category_callback(call):
    try:
        _, platform_id, category_id = call.data.split(":", 2)
    except ValueError:
        bot.answer_callback_query(call.id, "❌ Invalid category.")
        return

    platform = get_platform_name_from_id(platform_id)
    category = get_category_name_from_id(platform, category_id) if platform else None
    if platform is None or category is None:
        bot.answer_callback_query(call.id, "❌ Invalid category.")
        return

    services = get_enabled_services_by_platform_category().get(platform, {}).get(category, [])
    if not services:
        bot.answer_callback_query(call.id, "❌ No services in this category.")
        return

    text = f"📂 <b>{escape(platform)}</b>\n📁 <b>{escape(category)}</b>\n\nSelect a service:"
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=service_catalog_category_markup(platform, category)
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("svc_catalog_category_page:"))
@safe_callback
def service_catalog_category_page_callback(call):
    try:
        _, platform_id, category_id, page_str = call.data.split(":", 3)
        page = int(page_str)
    except (TypeError, ValueError):
        bot.answer_callback_query(call.id, "❌ Invalid category page.")
        return

    platform = get_platform_name_from_id(platform_id)
    category = get_category_name_from_id(platform, category_id) if platform else None
    if platform is None or category is None:
        bot.answer_callback_query(call.id, "❌ Invalid category.")
        return

    services = get_enabled_services_by_platform_category().get(platform, {}).get(category, [])
    if not services:
        bot.answer_callback_query(call.id, "❌ No services in this category.")
        return
    text = f"📂 <b>{escape(platform)}</b>\n📁 <b>{escape(category)}</b>\n\nSelect a service:"
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=service_catalog_category_markup(platform, category, page=page)
    )


@bot.callback_query_handler(func=lambda c: c.data == "svc_catalog_page_disabled")
@safe_callback
def service_catalog_page_disabled_callback(call):
    bot.answer_callback_query(call.id, "No more services to show.")


@bot.callback_query_handler(func=lambda c: c.data.startswith("svc_catalog_service:"))
@safe_callback
def service_catalog_service_callback(call):
    service_id = call.data.split(":", 1)[1]
    service = get_service_by_id(service_id, enabled_only=True)
    if not is_user_catalog_service(service):
        bot.answer_callback_query(call.id, "❌ This service is no longer available.")
        return

    platform, category = get_user_catalog_service_parts(service)
    lines = [
        f"📦 <b>{escape(str(service['name']))}</b>",
        f"Category: <b>{escape(category)}</b>",
        f"Min: <b>{service.get('min', 'N/A')}</b>",
        f"Max: <b>{service.get('max', 'N/A')}</b>",
        f"💰 Price: <b>₹{get_selling_rate(service):.2f}</b> / 1000",
    ]
    description = str(service.get("description") or "").strip()
    if description:
        lines.append("")
        lines.append(f"Description: <i>{escape(description)}</i>")

    bot.edit_message_text(
        "\n".join(lines),
        call.message.chat.id,
        call.message.message_id,
        reply_markup=service_catalog_details_markup(service_id, platform, category)
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("svc_catalog_order_now:"))
@safe_callback
def service_catalog_order_now_callback(call):
    service_id = call.data.split(":", 1)[1]
    service = get_service_by_id(service_id, enabled_only=True)
    if not is_user_catalog_service(service):
        bot.answer_callback_query(call.id, "❌ This service is no longer available.")
        return

    user_id = call.message.chat.id
    user_state[user_id] = {
        "action": "catalog_order",
        "service_id": service_id,
        "service_name": service["name"],
        "service_min": service["min"],
        "service_max": service["max"],
        "selling_rate": get_selling_rate(service),
        "step": "awaiting_link",
        "link": "",
        "quantity": None,
    }
    bot.answer_callback_query(call.id)
    bot.send_message(
        user_id,
        f"📦 <b>{escape(str(service['name']))}</b>\n\nSend the required link or username for this order:"
    )


@bot.message_handler(func=lambda m: (
    user_state.get(m.chat.id) is not None and
    user_state.get(m.chat.id, {}).get("action") == "catalog_order"
))
@safe_handler
def handle_catalog_order(message):
    user_id = message.chat.id
    state = user_state.get(user_id)
    if not state:
        return

    if message.content_type != "text":
        bot.send_message(user_id, "❌ Please send text only.")
        return

    if state.get("step") == "awaiting_link":
        link = message.text.strip()
        if not link:
            bot.send_message(user_id, "❌ Please provide a valid link or username.")
            return
        state["link"] = link
        state["step"] = "awaiting_quantity"
        bot.send_message(
            user_id,
            f"📏 Enter the quantity for <b>{escape(str(state['service_name']))}</b>\n"
            f"Min: <b>{state['service_min']}</b> | Max: <b>{state['service_max']}</b>"
        )
        return

    if state.get("step") == "awaiting_quantity":
        text = message.text.strip()
        if not text.isdigit():
            bot.send_message(user_id, "❌ Please enter a number only.")
            return
        quantity = int(text)
        service = get_service_by_id(state["service_id"], enabled_only=True)
        if not service:
            user_state.pop(user_id, None)
            bot.send_message(user_id, "❌ This service is no longer available.")
            return

        if quantity < state["service_min"]:
            bot.send_message(user_id, f"❌ Minimum order quantity is {state['service_min']}.")
            return
        if quantity > state["service_max"]:
            bot.send_message(user_id, f"❌ Maximum order quantity is {state['service_max']}.")
            return

        state["quantity"] = quantity
        state["step"] = "summary"
        current_price = quantity / 1000.0 * state["selling_rate"]
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            telebot.types.InlineKeyboardButton("✅ Confirm", callback_data="svc_catalog_confirm_order"),
            telebot.types.InlineKeyboardButton("❌ Cancel", callback_data="svc_catalog_cancel_order"),
        )
        markup.add(
            telebot.types.InlineKeyboardButton("⬅️ Back", callback_data="svc_catalog_back_order"),
            telebot.types.InlineKeyboardButton("🏠 Home", callback_data="svc_catalog_home"),
        )
        bot.send_message(
            user_id,
            "🧾 <b>Order Summary</b>\n\n"
            f"Service: <b>{escape(str(service['name']))}</b>\n"
            f"Link/Username: <code>{escape(str(state['link']))}</code>\n"
            f"Quantity: <b>{quantity}</b>\n"
            f"Current price: <b>₹{current_price:.2f}</b>\n\n"
            "Please confirm this order.",
            reply_markup=markup,
            disable_web_page_preview=True,
        )
        return

    if state.get("step") == "summary":
        bot.send_message(user_id, "⚠️ Please confirm, cancel, or go back from the order summary.")


@bot.callback_query_handler(func=lambda c: c.data == "svc_catalog_cancel_order")
@safe_callback
def service_catalog_cancel_order_callback(call):
    user_state.pop(call.message.chat.id, None)
    bot.edit_message_text(
        "❌ Order cancelled.",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=main_menu()
    )


@bot.callback_query_handler(func=lambda c: c.data == "svc_catalog_back_order")
@safe_callback
def service_catalog_back_order_callback(call):
    state = user_state.get(call.message.chat.id)
    if not state or state.get("action") != "catalog_order":
        bot.answer_callback_query(call.id, "❌ No active order to edit.")
        return
    state["step"] = "awaiting_quantity"
    bot.edit_message_text(
        f"📏 Enter the quantity for <b>{escape(str(state['service_name']))}</b>\n"
        f"Min: <b>{state['service_min']}</b> | Max: <b>{state['service_max']}</b>",
        call.message.chat.id,
        call.message.message_id,
    )


@bot.callback_query_handler(func=lambda c: c.data == "svc_catalog_confirm_order")
@safe_callback
def service_catalog_confirm_order_callback(call):
    user_id = call.message.chat.id
    state = user_state.get(user_id)
    if not state or state.get("action") != "catalog_order":
        bot.answer_callback_query(call.id, "❌ No active order to confirm.")
        return

    service = get_service_by_id(state["service_id"], enabled_only=True)
    if not service:
        user_state.pop(user_id, None)
        bot.answer_callback_query(call.id, "❌ This service is no longer available.")
        return

    quantity = state.get("quantity")
    link = state.get("link")
    if quantity is None or not link:
        bot.answer_callback_query(call.id, "❌ The order is incomplete.")
        return

    state["action"] = "order"
    state["service_id"] = service["_id"]
    state["service_name"] = service["name"]
    state["service_min"] = service["min"]
    state["service_max"] = service["max"]
    state["selling_rate"] = get_selling_rate(service)
    state["step"] = "awaiting_quantity"
    state["url"] = link

    # Reuse the existing order placement logic after quantity validation.
    result = place_order_for_user(user_id, state, service, link, quantity)
    if result is False:
        return
    user_state.pop(user_id, None)
    bot.answer_callback_query(call.id, "✅ Order confirmed.")


@safe_handler
def process_order_quantity(message):
    reload_cfg()
    user_id = message.chat.id
    state   = user_state.get(user_id)
    if not state or state.get("step") != "awaiting_quantity":
        return
    if message.content_type != 'text' or not message.text.strip().isdigit():
        bot.send_message(user_id, "❌ Please enter numbers only.")
        return
    quantity = int(message.text.strip())
    if quantity < state["service_min"]:
        bot.send_message(user_id, f"❌ Minimum order quantity is {state['service_min']}.")
        return
    if quantity > state["service_max"]:
        bot.send_message(user_id, f"❌ Maximum order quantity is {state['service_max']}.")
        return

    service = get_service_by_id(state["service_id"], enabled_only=True)
    if not service:
        user_state.pop(user_id, None)
        bot.send_message(user_id, "❌ This service is no longer enabled.")
        return

    url = state["url"]
    if not url:
        bot.send_message(user_id, "❌ Missing link or username. Please try again.")
        return

    place_order_for_user(user_id, state, service, url, quantity)


def place_order_for_user(user_id, state, service, url, quantity):
    selling_rate = state.get("selling_rate", get_selling_rate(service))
    charged_amount = quantity / 1000.0 * selling_rate
    try:
        reservation = wallet_hold(user_id, charged_amount)
    except Exception:
        bot.send_message(user_id, "❌ Unable to reserve ₹ balance right now. Please try again.")
        user_state.pop(user_id, None)
        return False
    if not reservation:
        current_user = users_collection.find_one({"_id": user_id}) or {}
        available = float(current_user.get("balance", user_balances.get(user_id, 0)))
        user_balances[user_id] = available
        bot.send_message(
            user_id,
            f"❌ Insufficient ₹ balance. You need <b>₹{charged_amount:.2f}</b> "
            f"but have <b>₹{available:.2f}</b>."
        )
        user_state.pop(user_id, None)
        return False

    reservation_id = reservation["reservation_id"]
    user_state.pop(user_id, None)

    provider_request_id = uuid4().hex
    if not wallet_mark_request_attempted(reservation_id, provider_request_id):
        bot.send_message(
            user_id,
            f"⚠️ This reservation already has a pending provider request.\n"
            f"Reservation ID: <code>{reservation_id}</code>\n"
            f"Use Retry to check its status.",
            reply_markup=pending_reservation_markup(reservation_id)
        )
        return False

    order_data = {
        "key":      cfg["smm_api_key"],
        "action":   "add",
        "service":  service["provider_service_id"],
        "link":     url,
        "quantity": quantity
    }
    try:
        provider_response = requests.post(
            cfg["smm_panel_url"], data=order_data, timeout=15
        )
    except requests.RequestException:
        wallet_mark_pending(reservation_id, "timeout_or_connection")
        bot.send_message(
            user_id,
            f"⚠️ Provider response is pending. Your <b>₹{charged_amount:.2f}</b> "
            f"remains reserved.\nReservation ID: <code>{reservation_id}</code>",
            reply_markup=pending_reservation_markup(reservation_id)
        )
        return False

    try:
        response = provider_response.json()
    except (AttributeError, TypeError, ValueError):
        wallet_mark_pending(reservation_id, "malformed_or_truncated_response")
        bot.send_message(
            user_id,
            f"⚠️ Provider response could not be verified. Your <b>₹{charged_amount:.2f}</b> "
            f"remains reserved.\nReservation ID: <code>{reservation_id}</code>",
            reply_markup=pending_reservation_markup(reservation_id)
        )
        return False

    if not isinstance(response, dict):
        wallet_mark_pending(reservation_id, "malformed_or_truncated_response")
        bot.send_message(
            user_id,
            f"⚠️ Provider response could not be verified. Your <b>₹{charged_amount:.2f}</b> "
            f"remains reserved.\nReservation ID: <code>{reservation_id}</code>",
            reply_markup=pending_reservation_markup(reservation_id)
        )
        return False

    raw_order_id = response.get("order")
    has_order_id = (
        isinstance(raw_order_id, (str, int)) and
        not isinstance(raw_order_id, bool) and
        bool(str(raw_order_id).strip())
    )
    raw_error = response.get("error")
    has_explicit_error = isinstance(raw_error, str) and bool(raw_error.strip())
    if has_order_id and not has_explicit_error:
        order_id = raw_order_id
        if not wallet_settle(reservation_id, order_id):
            wallet_mark_pending(reservation_id, "settlement_conflict")
            bot.send_message(
                user_id,
                f"⚠️ Order result could not be finalized. Your <b>₹{charged_amount:.2f}</b> "
                f"remains reserved.\nReservation ID: <code>{reservation_id}</code>",
                reply_markup=pending_reservation_markup(reservation_id)
            )
            return False
    elif has_explicit_error and not has_order_id:
        wallet_release(reservation_id, order_id=None)
        send_log(
            f"❌ <b>Order failed</b>\n"
            f"User ID: <code>{user_id}</code>\n"
            f"Service: <b>{escape(str(service['name']))}</b>\n"
            f"Quantity: {quantity}\n"
            f"Charged: ₹{charged_amount:.2f}\n"
            f"Status: failed"
        )
        bot.send_message(
            user_id,
            f"❌ Order failed. ₹ balance released.\nError: {raw_error}"
        )
        return False
    else:
        wallet_mark_pending(reservation_id, "ambiguous_provider_response")
        bot.send_message(
            user_id,
            f"⚠️ Provider response was ambiguous. Your <b>₹{charged_amount:.2f}</b> "
            f"remains reserved.\nReservation ID: <code>{reservation_id}</code>",
            reply_markup=pending_reservation_markup(reservation_id)
        )
        return False

    if "order" in response:
        ts       = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        order_details = {
            "order_id":    order_id,
            "service_type": service["name"],
            "service_name": service["name"],
            "reservation_id": reservation_id,
            "link":        url,
            "quantity":    quantity,
            "charged_amount": charged_amount,
            "provider_rate": get_provider_rate(service),
            "selling_rate": selling_rate,
            "timestamp":   ts
        }
        user_orders.setdefault(user_id, []).append(order_details)
        persist_order(user_id, order_details)
        send_log(
            f"🛒 <b>Order placed</b>\n"
            f"User ID: <code>{user_id}</code>\n"
            f"Order ID: <code>{order_id}</code>\n"
            f"Service: <b>{escape(str(service['name']))}</b>\n"
            f"Quantity: {quantity}\n"
            f"Charged: ₹{charged_amount:.2f}\n"
            f"Status: placed"
        )
        bot.send_message(user_id,
            f"✅ 𝗢𝗥𝗗𝗘𝗥 𝗣𝗟𝗔𝗖𝗘𝗗 🦋\n"
            f"Service: {service['name']}\n"
            f"Quantity: {quantity}\n"
            f"Order ID: <code>{order_id}</code>\n"
            f"Estimated time: 2-3 hours"
        )

        return True

    return False


# ─────────────────────────────────────────────────────────────
#  KEYBOARDS  – ADMIN PANEL
# ─────────────────────────────────────────────────────────────
def admin_panel_markup():
    mk = telebot.types.InlineKeyboardMarkup(row_width=2)
    mk.add(
        telebot.types.InlineKeyboardButton("📊 Stats",            callback_data="ap_stats"),
        telebot.types.InlineKeyboardButton("📢 Broadcast",        callback_data="ap_broadcast"),
    )
    mk.add(
        telebot.types.InlineKeyboardButton("🧰 Manage Services",  callback_data="ap_services"),
        telebot.types.InlineKeyboardButton("🔄 Sync Services",    callback_data="ap_sync_services"),
    )
    mk.add(
        telebot.types.InlineKeyboardButton("🎁 Create GiftCode",  callback_data="ap_giftcode_create"),
        telebot.types.InlineKeyboardButton("🗑 Delete GiftCode",  callback_data="ap_giftcode_delete"),
    )
    mk.add(
        telebot.types.InlineKeyboardButton("➕ Add Balance",       callback_data="ap_add_balance"),
        telebot.types.InlineKeyboardButton("➖ Remove Balance",    callback_data="ap_remove_balance"),
    )
    mk.add(
        telebot.types.InlineKeyboardButton("💰 Check User Bal",   callback_data="ap_check_balance"),
        telebot.types.InlineKeyboardButton("🚫 Ban User",         callback_data="ap_ban"),
    )
    mk.add(
        telebot.types.InlineKeyboardButton("✅ Unban User",       callback_data="ap_unban"),
        telebot.types.InlineKeyboardButton("📋 List Banned",      callback_data="ap_list_banned"),
    )
    mk.add(
        telebot.types.InlineKeyboardButton("📋 Pending Res",      callback_data="ap_pending_reservations"),
        telebot.types.InlineKeyboardButton("⚙️ Edit Rates",       callback_data="ap_rates"),
    )
    mk.add(
        telebot.types.InlineKeyboardButton("🔧 Edit Service IDs", callback_data="ap_service_ids"),
    )
    mk.add(telebot.types.InlineKeyboardButton("💰 Edit Selling Prices", callback_data="ap_service_prices"))
    mk.add(
        telebot.types.InlineKeyboardButton("🔑 Edit API Key",     callback_data="ap_edit_apikey"),
        telebot.types.InlineKeyboardButton("📡 Set Logs Channel", callback_data="ap_set_logs"),
    )
    mk.add(
        telebot.types.InlineKeyboardButton("🌐 Edit SMM URL",     callback_data="ap_edit_smmurl"),
        telebot.types.InlineKeyboardButton("🖼 Edit QR URL",      callback_data="ap_edit_qr"),
    )
    mk.add(telebot.types.InlineKeyboardButton("🖼 Set Main Menu Photo", callback_data="ap_set_main_menu_photo"))
    return mk


def rates_markup():
    mk = telebot.types.InlineKeyboardMarkup(row_width=2)
    mk.add(
        telebot.types.InlineKeyboardButton("👍 Reactions Rate",   callback_data="rate_reaction"),
        telebot.types.InlineKeyboardButton("👀 Views Rate",       callback_data="rate_view"),
    )
    mk.add(
        telebot.types.InlineKeyboardButton("👥 Members Rate",     callback_data="rate_member"),
        telebot.types.InlineKeyboardButton("🤝 Referral ₹",       callback_data="rate_referral"),
    )
    mk.add(
        telebot.types.InlineKeyboardButton("🎁 Daily Bonus ₹",    callback_data="rate_bonus"),
    )
    mk.add(telebot.types.InlineKeyboardButton("📈 Global Markup %", callback_data="rate_markup"))
    mk.add(telebot.types.InlineKeyboardButton("🔙 Back",          callback_data="ap_back"))
    return mk


def service_ids_markup():
    mk = telebot.types.InlineKeyboardMarkup(row_width=1)
    mk.add(
        telebot.types.InlineKeyboardButton(
            f"👍 Reactions ID  (current: {cfg['service_id_reactions']})",
            callback_data="sid_reactions"
        ),
        telebot.types.InlineKeyboardButton(
            f"👀 Views ID  (current: {cfg['service_id_views']})",
            callback_data="sid_views"
        ),
        telebot.types.InlineKeyboardButton(
            f"👥 Members ID  (current: {cfg['service_id_members']})",
            callback_data="sid_members"
        ),
    )
    mk.add(telebot.types.InlineKeyboardButton("🔙 Back", callback_data="ap_back"))
    return mk


def pending_reservations_admin_markup():
    mk = telebot.types.InlineKeyboardMarkup(row_width=1)
    reservations = list(wallet_reservations_collection.find({"status": "pending"}).sort("created_at", 1))
    if not reservations:
        mk.add(telebot.types.InlineKeyboardButton("🔙 Back", callback_data="ap_back"))
        return mk
    for reservation in reservations[:10]:
        user_id = reservation.get("user_id")
        amount = reservation.get("amount")
        short_id = reservation.get("reservation_id", "")[:8]
        mk.add(telebot.types.InlineKeyboardButton(
            f"User {user_id} | ₹{float(amount):.2f} | {short_id}",
            callback_data=f"ap_pending_view:{reservation.get('reservation_id')}"
        ))
    mk.add(telebot.types.InlineKeyboardButton("🔙 Back", callback_data="ap_back"))
    return mk


def pending_reservation_detail_markup(reservation_id):
    mk = telebot.types.InlineKeyboardMarkup(row_width=2)
    mk.add(
        telebot.types.InlineKeyboardButton("✅ Settle", callback_data=f"ap_pending_settle:{reservation_id}"),
        telebot.types.InlineKeyboardButton("↩️ Release", callback_data=f"ap_pending_release:{reservation_id}"),
    )
    mk.add(telebot.types.InlineKeyboardButton("🔙 Back", callback_data="ap_pending_reservations"))
    return mk


# ─────────────────────────────────────────────────────────────
#  SERVICE MANAGEMENT
# ─────────────────────────────────────────────────────────────
def _safe_int(value, default=None):
    if value is None or value is False or value == "":
        return default
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_provider_service_payload(payload):
    if isinstance(payload, list):
        candidates = payload
    elif isinstance(payload, dict):
        if isinstance(payload.get("services"), list):
            candidates = payload["services"]
        elif isinstance(payload.get("data"), list):
            candidates = payload["data"]
        elif isinstance(payload.get("result"), list):
            candidates = payload["result"]
        elif isinstance(payload.get("items"), list):
            candidates = payload["items"]
        else:
            candidates = [payload]
    else:
        return []

    normalized = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        provider_id = (
            _safe_int(item.get("provider_service_id"))
            or _safe_int(item.get("service_id"))
            or _safe_int(item.get("id"))
            or _safe_int(item.get("service"))
        )
        if provider_id is None:
            continue

        name = (
            item.get("name")
            or item.get("service_name")
            or item.get("title")
            or item.get("service")
            or f"Service {provider_id}"
        )
        category = (
            item.get("category")
            or item.get("type")
            or item.get("service_type")
            or "General"
        )
        minimum = _safe_int(item.get("min"), 1) or 1
        maximum = _safe_int(item.get("max"), minimum) or minimum
        if maximum < minimum:
            maximum = minimum
        provider_rate = _safe_float(
            item.get("provider_rate"),
            _safe_float(
                item.get("rate"),
                _safe_float(item.get("price"), _safe_float(item.get("cost"), 0.0))
            )
        )
        if provider_rate <= 0:
            continue

        normalized.append({
            "provider_service_id": provider_id,
            "name": str(name),
            "category": str(category),
            "min": minimum,
            "max": maximum,
            "provider_rate": provider_rate,
        })
    return normalized


def sync_provider_services():
    base_url = (cfg.get("smm_panel_url") or "").strip()
    api_key = (cfg.get("smm_api_key") or "").strip()
    if not base_url or not api_key:
        return {"ok": False, "error": "SMM panel URL or API key is not configured."}

    try:
        response = requests.post(base_url, data={"key": api_key, "action": "services"}, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        return {"ok": False, "error": f"Provider request failed: {exc}"}

    try:
        payload = response.json()
    except ValueError:
        return {"ok": False, "error": "Provider returned a non-JSON response."}

    if isinstance(payload, dict) and payload.get("error"):
        return {"ok": False, "error": str(payload["error"]) }

    normalized = normalize_provider_service_payload(payload)
    if not normalized:
        return {"ok": False, "error": "Provider did not return any valid services."}

    inserted = 0
    updated = 0
    for service in normalized:
        existing = services_collection.find_one({"provider_service_id": service["provider_service_id"]})
        service_payload = {
            "name": service["name"],
            "provider_service_id": service["provider_service_id"],
            "category": service["category"],
            "min": service["min"],
            "max": service["max"],
            "provider_rate": service["provider_rate"],
            "selling_price": (
                existing.get("selling_price")
                if existing and _safe_float(existing.get("selling_price"), 0.0) > 0
                else (
                    existing.get("selling_rate")
                    if existing and _safe_float(existing.get("selling_rate"), 0.0) > 0
                    else calculate_default_selling_price(service["provider_rate"])
                )
            ),
            "enabled": existing.get("enabled", True) if existing else True,
        }
        if existing:
            services_collection.update_one(
                {"provider_service_id": service["provider_service_id"]},
                {"$set": service_payload}
            )
            updated += 1
        else:
            service_payload["_id"] = uuid4().hex
            services_collection.insert_one(service_payload)
            inserted += 1

    return {"ok": True, "inserted": inserted, "updated": updated, "total": len(normalized)}


def services_admin_markup():
    mk = telebot.types.InlineKeyboardMarkup(row_width=1)
    services = list(services_collection.find({}).sort([("category", 1), ("name", 1)]))
    for service in services:
        status = "✅" if service.get("enabled") else "⛔"
        mk.add(telebot.types.InlineKeyboardButton(
            f"{status} {service['name']}",
            callback_data=f"svc_admin_edit:{service['_id']}"
        ))
    mk.add(telebot.types.InlineKeyboardButton("🔄 Sync Services", callback_data="ap_sync_services"))
    mk.add(telebot.types.InlineKeyboardButton("➕ Add Service", callback_data="svc_admin_add"))
    mk.add(telebot.types.InlineKeyboardButton("🔙 Back", callback_data="ap_back"))
    return mk


def services_admin_text():
    return (
        "🧰 <b>Manage Services</b>\n\n"
        "Only enabled services appear in the user menu and search.\n"
        "Select a service to edit or enable/disable it."
    )


def service_editor_prompt(service=None):
    example = "Name | Provider ID | Category | Min | Max | Provider Rate | Selling Rate | Enabled"
    if service:
        values = " | ".join([
            str(service["name"]),
            str(service["provider_service_id"]),
            str(service["category"]),
            str(service["min"]),
            str(service["max"]),
            f"₹{get_provider_rate(service):.2f}",
            f"₹{get_selling_rate(service):.2f}",
            "yes" if service.get("enabled") else "no",
        ])
        return (
            "✏️ <b>Edit Service</b>\n\n"
            f"Current:\n<code>{escape(values)}</code>\n\n"
            f"Send all fields in this format:\n<code>{escape(example)}</code>"
        )
    return (
        "➕ <b>Add Service</b>\n\n"
        f"Send all fields in this format:\n<code>{escape(example)}</code>\n\n"
        "Provider rate is the provider's cost per 1000. Selling rate is the customer price per 1000."
    )


# ─────────────────────────────────────────────────────────────
#  /admin  – open admin panel
# ─────────────────────────────────────────────────────────────
@bot.message_handler(commands=['admin'])
@safe_handler
def admin_panel(message):
    reload_cfg()
    if not is_admin(message.chat.id):
        return
    bot.send_message(
        message.chat.id,
        "👑 <b>ADMIN CONTROL PANEL</b>\n\nSelect an action below:",
        reply_markup=admin_panel_markup()
    )


# ─────────────────────────────────────────────────────────────
#  ADMIN PANEL CALLBACKS
# ─────────────────────────────────────────────────────────────
@bot.callback_query_handler(func=lambda c: c.data.startswith("ap_") or c.data.startswith("rate_") or c.data.startswith("sid_") or c.data.startswith("svc_admin_") or c.data.startswith("svc_price_select:"))
@safe_callback
def admin_callback(call):
    reload_cfg()
    uid = call.message.chat.id
    if not is_admin(uid):
        bot.answer_callback_query(call.id, "❌ Not authorized.")
        return

    data = call.data

    if data == "ap_set_main_menu_photo":
        user_state[uid] = {"action": "admin_set_main_menu_photo"}
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("❌ Cancel", callback_data="ap_back"))
        bot.edit_message_text(
            "🖼 <b>Set Main Menu Photo</b>\n\nSend the photo to use above the main menu welcome message.",
            uid,
            call.message.message_id,
            reply_markup=mk,
        )
        bot.register_next_step_handler(call.message, process_admin_set_main_menu_photo)
        return

    # ── Service management ──
    if data == "ap_sync_services":
        result = sync_provider_services()
        if not result["ok"]:
            send_log(f"🔄 <b>Service sync failed</b>\nError: <code>{escape(str(result['error']))}</code>")
            bot.edit_message_text(
                f"⚠️ <b>Service Sync Failed</b>\n\n{escape(str(result['error']))}",
                uid,
                call.message.message_id,
                reply_markup=admin_panel_markup()
            )
            return

        send_log(
            f"🔄 <b>Service sync succeeded</b>\n"
            f"Inserted: {result['inserted']} | Updated: {result['updated']} | Total: {result['total']}"
        )
        bot.edit_message_text(
            f"✅ <b>Provider Services Synced</b>\n\n"
            f"Inserted: <b>{result['inserted']}</b>\n"
            f"Updated: <b>{result['updated']}</b>\n"
            f"Available from provider: <b>{result['total']}</b>",
            uid,
            call.message.message_id,
            reply_markup=admin_panel_markup()
        )
        return

    if data == "ap_services":
        bot.edit_message_text(
            services_admin_text(), uid, call.message.message_id,
            reply_markup=services_admin_markup()
        )
        return

    if data == "ap_service_prices":
        user_state[uid] = {"action": "admin_service_price_search"}
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("❌ Cancel", callback_data="ap_back"))
        bot.edit_message_text(
            "💰 <b>Edit Selling Price</b>\n\n"
            "Search by service name, category, platform, or provider service ID:",
            uid, call.message.message_id, reply_markup=mk
        )
        bot.register_next_step_handler(call.message, process_admin_service_price_search)
        return

    if data.startswith("svc_price_select:"):
        service_id = data.split(":", 1)[1]
        service = get_service_by_id(service_id)
        if not service or not service.get("enabled") or not is_user_catalog_service(service):
            bot.answer_callback_query(call.id, "Service not found or not in the user catalog.")
            return
        user_state[uid] = {"action": "admin_service_price_edit", "service_id": service_id}
        current_price = get_selling_rate(service)
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton(
            "❌ Cancel", callback_data="ap_service_prices"
        ))
        bot.edit_message_text(
            f"💰 <b>{escape(str(service['name']))}</b>\n\n"
            f"Provider service ID: <code>{service['provider_service_id']}</code>\n"
            f"Current selling price: <b>₹{format_selling_price(current_price)}/1K</b>\n\n"
            "Send the new customer selling price per 1000:",
            uid, call.message.message_id, reply_markup=mk
        )
        bot.register_next_step_handler(call.message, process_admin_service_price_input)
        return

    if data == "svc_admin_add":
        user_state[uid] = {"action": "admin_service_add"}
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("❌ Cancel", callback_data="ap_services"))
        bot.edit_message_text(
            service_editor_prompt(), uid, call.message.message_id, reply_markup=mk
        )
        bot.register_next_step_handler(call.message, process_admin_service_input)
        return

    if data.startswith("svc_admin_edit:"):
        service_id = data.split(":", 1)[1]
        service = get_service_by_id(service_id)
        if not service:
            bot.answer_callback_query(call.id, "Service not found.")
            return
        mk = telebot.types.InlineKeyboardMarkup(row_width=2)
        mk.add(
            telebot.types.InlineKeyboardButton(
                "⛔ Disable" if service.get("enabled") else "✅ Enable",
                callback_data=f"svc_admin_toggle:{service_id}"
            ),
            telebot.types.InlineKeyboardButton(
                "✏️ Edit Fields", callback_data=f"svc_admin_fields:{service_id}"
            ),
        )
        mk.add(telebot.types.InlineKeyboardButton("🔙 Back", callback_data="ap_services"))
        bot.edit_message_text(
            f"🧰 <b>{escape(str(service['name']))}</b>\n\n"
            f"Provider ID: <code>{service['provider_service_id']}</code>\n"
            f"Category: <b>{escape(str(service['category']))}</b>\n"
            f"Min / Max: <b>{service['min']} / {service['max']}</b>\n"
            f"Provider rate: <b>₹{get_provider_rate(service):.2f}</b> / 1000\n"
            f"Selling rate: <b>₹{get_selling_rate(service):.2f}</b> / 1000\n"
            f"Status: <b>{'Enabled' if service.get('enabled') else 'Disabled'}</b>",
            uid, call.message.message_id, reply_markup=mk
        )
        return

    if data.startswith("svc_admin_toggle:"):
        service_id = data.split(":", 1)[1]
        service = get_service_by_id(service_id)
        if not service:
            bot.answer_callback_query(call.id, "Service not found.")
            return
        services_collection.update_one(
            {"_id": service_id},
            {"$set": {"enabled": not service.get("enabled", False)}}
        )
        updated = get_service_by_id(service_id)
        bot.edit_message_text(
            f"✅ Service <b>{escape(str(updated['name']))}</b> is now "
            f"<b>{'enabled' if updated.get('enabled') else 'disabled'}</b>.",
            uid, call.message.message_id, reply_markup=services_admin_markup()
        )
        return

    if data.startswith("svc_admin_fields:"):
        service_id = data.split(":", 1)[1]
        service = get_service_by_id(service_id)
        if not service:
            bot.answer_callback_query(call.id, "Service not found.")
            return
        user_state[uid] = {"action": "admin_service_edit", "service_id": service_id}
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton(
            "❌ Cancel", callback_data=f"svc_admin_edit:{service_id}"
        ))
        bot.edit_message_text(
            service_editor_prompt(service), uid, call.message.message_id, reply_markup=mk
        )
        bot.register_next_step_handler(call.message, process_admin_service_input)
        return

    # ── Back to main panel ──
    if data == "ap_back":
        bot.edit_message_text(
            "👑 <b>ADMIN CONTROL PANEL</b>\n\nSelect an action below:",
            uid, call.message.message_id,
            reply_markup=admin_panel_markup()
        )
        return

    # ── Stats ──
    if data == "ap_stats":
        total_users   = len(users)
        banned_count  = len(banned_users)
        gift_count    = len(gift_codes)
        total_orders  = sum(len(v) for v in user_orders.values())
        total_balance = sum(user_balances.values())
        text = (
            f"📊 <b>BOT STATISTICS</b>\n\n"
            f"👥 Total Users: <b>{total_users}</b>\n"
            f"🚫 Banned Users: <b>{banned_count}</b>\n"
            f"🎁 Active Gift Codes: <b>{gift_count}</b>\n"
            f"🛒 Total Orders: <b>{total_orders}</b>\n"
            f"💰 Total INR Held: <b>₹{total_balance:.2f}</b>\n\n"
            f"⚙️ <b>Current Settings</b>\n"
            f"👍 Reactions provider rate: ₹{cfg['provider_rate_reactions']:.2f} / 1000\n"
            f"👀 Views provider rate: ₹{cfg['provider_rate_views']:.2f} / 1000\n"
            f"👥 Members provider rate: ₹{cfg['provider_rate_members']:.2f} / 1000\n"
            f"🤝 Referral reward: ₹{cfg['referral_reward_inr']:.2f}\n"
            f"🎁 Daily bonus: ₹{cfg['daily_bonus_inr']:.2f}\n"
            f"📈 Global markup: {cfg['markup_percentage']:.2f}%\n"
            f"📡 Logs Channel: {cfg.get('logs_channel') or 'Not Set'}"
        )
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("🔙 Back", callback_data="ap_back"))
        bot.edit_message_text(text, uid, call.message.message_id, reply_markup=mk)
        return

    # ── Broadcast ──
    if data == "ap_broadcast":
        user_state[uid] = {"action": "admin_broadcast"}
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("❌ Cancel", callback_data="ap_back"))
        bot.edit_message_text(
            "📢 <b>Broadcast</b>\n\nSend your message now.\nSupports text, photos, videos, stickers.\n\n<i>Reply or just send your next message.</i>",
            uid, call.message.message_id, reply_markup=mk
        )
        bot.register_next_step_handler(call.message, process_admin_broadcast)
        return

    # ── Gift code – create ──
    if data == "ap_giftcode_create":
        user_state[uid] = {"action": "admin_gc_create", "step": "code"}
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("❌ Cancel", callback_data="ap_back"))
        bot.edit_message_text(
            "🎁 <b>Create Gift Code</b>\n\nStep 1/2 – Enter the gift code text:",
            uid, call.message.message_id, reply_markup=mk
        )
        bot.register_next_step_handler(call.message, process_gc_create_step)
        return

    # ── Gift code – delete ──
    if data == "ap_giftcode_delete":
        if not gift_codes:
            bot.answer_callback_query(call.id, "No active gift codes.")
            return
        user_state[uid] = {"action": "admin_gc_delete"}
        codes_list = "\n".join([f"<code>{c}</code> → ₹{p:.2f}" for c, p in gift_codes.items()])
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("❌ Cancel", callback_data="ap_back"))
        bot.edit_message_text(
            f"🗑 <b>Delete Gift Code</b>\n\nActive codes:\n{codes_list}\n\nSend the code to delete:",
            uid, call.message.message_id, reply_markup=mk
        )
        bot.register_next_step_handler(call.message, process_gc_delete)
        return

    # ── Add balance ──
    if data == "ap_add_balance":
        user_state[uid] = {"action": "admin_add_bal"}
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("❌ Cancel", callback_data="ap_back"))
        bot.edit_message_text(
            "➕ <b>Add INR Balance</b>\n\nSend in format:\n<code>USER_ID AMOUNT</code>\n\nExample: <code>123456789 500</code>",
            uid, call.message.message_id, reply_markup=mk
        )
        bot.register_next_step_handler(call.message, process_admin_add_bal)
        return

    # ── Remove balance ──
    if data == "ap_remove_balance":
        user_state[uid] = {"action": "admin_rem_bal"}
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("❌ Cancel", callback_data="ap_back"))
        bot.edit_message_text(
            "➖ <b>Remove INR Balance</b>\n\nSend in format:\n<code>USER_ID AMOUNT</code>\n\nExample: <code>123456789 100</code>",
            uid, call.message.message_id, reply_markup=mk
        )
        bot.register_next_step_handler(call.message, process_admin_rem_bal)
        return

    # ── Check balance ──
    if data == "ap_check_balance":
        user_state[uid] = {"action": "admin_check_bal"}
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("❌ Cancel", callback_data="ap_back"))
        bot.edit_message_text(
            "💰 <b>Check User Balance</b>\n\nSend the User ID:",
            uid, call.message.message_id, reply_markup=mk
        )
        bot.register_next_step_handler(call.message, process_admin_check_bal)
        return

    # ── Ban ──
    if data == "ap_ban":
        user_state[uid] = {"action": "admin_ban"}
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("❌ Cancel", callback_data="ap_back"))
        bot.edit_message_text(
            "🚫 <b>Ban User</b>\n\nSend the User ID to ban:",
            uid, call.message.message_id, reply_markup=mk
        )
        bot.register_next_step_handler(call.message, process_admin_ban)
        return

    # ── Unban ──
    if data == "ap_unban":
        user_state[uid] = {"action": "admin_unban"}
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("❌ Cancel", callback_data="ap_back"))
        bot.edit_message_text(
            "✅ <b>Unban User</b>\n\nSend the User ID to unban:",
            uid, call.message.message_id, reply_markup=mk
        )
        bot.register_next_step_handler(call.message, process_admin_unban)
        return

    # ── List banned ──
    if data == "ap_list_banned":
        if not banned_users:
            bot.answer_callback_query(call.id, "No banned users.")
            return
        text = "📋 <b>Banned Users:</b>\n" + "\n".join(str(u) for u in banned_users)
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("🔙 Back", callback_data="ap_back"))
        bot.edit_message_text(text, uid, call.message.message_id, reply_markup=mk)
        return

    # ── Pending reservations ──
    if data == "ap_pending_reservations":
        reservations = list(wallet_reservations_collection.find({"status": "pending"}).sort("created_at", 1))
        if not reservations:
            bot.edit_message_text(
                "📋 <b>Pending Wallet Reservations</b>\n\nNo pending reservations found.",
                uid,
                call.message.message_id,
                reply_markup=pending_reservations_admin_markup(),
            )
            return
        lines = ["📋 <b>Pending Wallet Reservations</b>"]
        for reservation in reservations[:10]:
            created = reservation.get("created_at") or "unknown"
            lines.append(
                f"• User <code>{reservation.get('user_id')}</code> | "
                f"₹{float(reservation.get('amount', 0)):.2f} | "
                f"Res <code>{reservation.get('reservation_id')}</code> | "
                f"Req <code>{reservation.get('provider_request_id', 'n/a')}</code> | "
                f"Reason: {reservation.get('pending_reason', 'n/a')} | "
                f"Time: {created}"
            )
        text = "\n".join(lines)
        bot.edit_message_text(text, uid, call.message.message_id, reply_markup=pending_reservations_admin_markup())
        return

    if data.startswith("ap_pending_view:"):
        reservation_id = data.split(":", 1)[1]
        reservation = wallet_reservations_collection.find_one({"_id": reservation_id})
        if not reservation:
            bot.answer_callback_query(call.id, "Reservation not found.")
            return
        details = (
            "📋 <b>Reservation Details</b>\n\n"
            f"User ID: <code>{reservation.get('user_id')}</code>\n"
            f"Amount: <b>₹{float(reservation.get('amount', 0)):.2f}</b>\n"
            f"Reservation ID: <code>{reservation.get('reservation_id')}</code>\n"
            f"Provider Request ID: <code>{reservation.get('provider_request_id', 'n/a')}</code>\n"
            f"Order ID: <code>{reservation.get('order_id', 'n/a')}</code>\n"
            f"Reason: <code>{reservation.get('pending_reason', 'n/a')}</code>\n"
            f"Created: <code>{reservation.get('created_at', 'n/a')}</code>\n"
            f"Updated: <code>{reservation.get('updated_at', 'n/a')}</code>\n"
            f"Status: <b>{reservation.get('status', 'unknown')}</b>"
        )
        bot.edit_message_text(details, uid, call.message.message_id, reply_markup=pending_reservation_detail_markup(reservation_id))
        return

    if data.startswith("ap_pending_settle:"):
        reservation_id = data.split(":", 1)[1]
        reservation = wallet_reservations_collection.find_one({"_id": reservation_id})
        if not reservation:
            bot.answer_callback_query(call.id, "Reservation not found.")
            return
        if reservation.get("status") == "settled":
            bot.answer_callback_query(call.id, "✅ Already settled.")
            return
        if reservation.get("status") == "released":
            bot.answer_callback_query(call.id, "⚠️ Already released.")
            return
        settled = wallet_settle(reservation_id, reservation.get("order_id"))
        if settled:
            bot.answer_callback_query(call.id, "✅ Reservation settled.")
        else:
            bot.answer_callback_query(call.id, "⚠️ Reservation could not be settled.")
        bot.edit_message_text(
            "📋 <b>Pending Wallet Reservations</b>\n\nReservation action processed.",
            uid,
            call.message.message_id,
            reply_markup=pending_reservations_admin_markup(),
        )
        return

    if data.startswith("ap_pending_release:"):
        reservation_id = data.split(":", 1)[1]
        reservation = wallet_reservations_collection.find_one({"_id": reservation_id})
        if not reservation:
            bot.answer_callback_query(call.id, "Reservation not found.")
            return
        if reservation.get("status") == "released":
            bot.answer_callback_query(call.id, "✅ Already released.")
            return
        if reservation.get("status") == "settled":
            bot.answer_callback_query(call.id, "⚠️ Already settled; cannot release.")
            return
        released = wallet_release(reservation_id, reservation.get("order_id"))
        if released:
            bot.answer_callback_query(call.id, "✅ Reservation released.")
        else:
            bot.answer_callback_query(call.id, "⚠️ Reservation could not be released.")
        bot.edit_message_text(
            "📋 <b>Pending Wallet Reservations</b>\n\nReservation action processed.",
            uid,
            call.message.message_id,
            reply_markup=pending_reservations_admin_markup(),
        )
        return

    # ── Rates menu ──
    if data == "ap_rates":
        text = (
            f"⚙️ <b>Edit Rates</b>\n\n"
            f"👍 Reactions provider rate: ₹{cfg['provider_rate_reactions']:.2f} / 1000\n"
            f"👀 Views provider rate: ₹{cfg['provider_rate_views']:.2f} / 1000\n"
            f"👥 Members provider rate: ₹{cfg['provider_rate_members']:.2f} / 1000\n"
            f"🤝 Referral reward: ₹{cfg['referral_reward_inr']:.2f}\n"
            f"🎁 Daily bonus: ₹{cfg['daily_bonus_inr']:.2f}\n"
            f"📈 Global markup: {cfg['markup_percentage']:.2f}%\n\n"
            f"Select which rate to edit:"
        )
        bot.edit_message_text(text, uid, call.message.message_id, reply_markup=rates_markup())
        return

    # ── Individual rate edits ──
    rate_map = {
        "rate_reaction":  ("provider_rate_reactions", "👍 Reactions provider rate (₹ / 1000)"),
        "rate_view":      ("provider_rate_views",     "👀 Views provider rate (₹ / 1000)"),
        "rate_member":    ("provider_rate_members",   "👥 Members provider rate (₹ / 1000)"),
        "rate_referral":  ("referral_reward_inr",     "🤝 Referral reward (₹)"),
        "rate_bonus":     ("daily_bonus_inr",         "🎁 Daily bonus (₹)"),
        "rate_markup":    ("markup_percentage",       "📈 Global markup (%)"),
    }
    if data in rate_map:
        cfg_key, label = rate_map[data]
        user_state[uid] = {"action": "admin_edit_rate", "cfg_key": cfg_key, "label": label}
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("❌ Cancel", callback_data="ap_rates"))
        bot.edit_message_text(
            f"⚙️ <b>Edit {label}</b>\n\nCurrent value: <b>{cfg[cfg_key]}</b>\n\nSend the new value (numbers only):",
            uid, call.message.message_id, reply_markup=mk
        )
        bot.register_next_step_handler(call.message, process_admin_edit_rate)
        return

    # ── Service IDs menu ──
    if data == "ap_service_ids":
        bot.edit_message_text(
            "🔧 <b>Edit Service IDs</b>\n\nSelect which service to update:",
            uid, call.message.message_id,
            reply_markup=service_ids_markup()
        )
        return

    # ── Individual service ID edits ──
    sid_map = {
        "sid_reactions": ("service_id_reactions", "👍 Reactions"),
        "sid_views":     ("service_id_views",     "👀 Views"),
        "sid_members":   ("service_id_members",   "👥 Members"),
    }
    if data in sid_map:
        cfg_key, label = sid_map[data]
        user_state[uid] = {"action": "admin_edit_sid", "cfg_key": cfg_key, "label": label}
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("❌ Cancel", callback_data="ap_service_ids"))
        bot.edit_message_text(
            f"🔧 <b>Set {label} Service ID</b>\n\nCurrent ID: <b>{cfg[cfg_key]}</b>\n\nSend the new Service ID (integer only):",
            uid, call.message.message_id, reply_markup=mk
        )
        bot.register_next_step_handler(call.message, process_admin_edit_sid)
        return

    # ── Edit API Key ──
    if data == "ap_edit_apikey":
        user_state[uid] = {"action": "admin_edit_apikey"}
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("❌ Cancel", callback_data="ap_back"))
        bot.edit_message_text(
            f"🔑 <b>Edit SMM API Key</b>\n\nCurrent: <code>{cfg['smm_api_key']}</code>\n\nSend the new API key:",
            uid, call.message.message_id, reply_markup=mk
        )
        bot.register_next_step_handler(call.message, process_admin_edit_apikey)
        return

    # ── Set logs channel ──
    if data == "ap_set_logs":
        user_state[uid] = {"action": "admin_set_logs"}
        current = cfg.get("logs_channel") or "Not set"
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("❌ Cancel", callback_data="ap_back"))
        bot.edit_message_text(
            f"📡 <b>Set Logs Channel</b>\n\nCurrent: <b>{current}</b>\n\n"
            "Send the channel <b>username</b> (without @) or <b>chat ID</b>.\n\n"
            "⚠️ Make sure to add the bot as <b>Admin</b> in that channel first!",
            uid, call.message.message_id, reply_markup=mk
        )
        bot.register_next_step_handler(call.message, process_admin_set_logs)
        return

    # ── Edit SMM URL ── RydenX
    if data == "ap_edit_smmurl":
        user_state[uid] = {"action": "admin_edit_smmurl"}
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("❌ Cancel", callback_data="ap_back"))
        bot.edit_message_text(
            f"🌐 <b>Edit SMM Panel URL</b>\n\nCurrent: <code>{cfg['smm_panel_url']}</code>\n\nSend the new URL:",
            uid, call.message.message_id, reply_markup=mk
        )
        bot.register_next_step_handler(call.message, process_admin_edit_smmurl)
        return

    # ── Edit QR URL ──
    if data == "ap_edit_qr":
        user_state[uid] = {"action": "admin_edit_qr"}
        mk = telebot.types.InlineKeyboardMarkup()
        mk.add(telebot.types.InlineKeyboardButton("❌ Cancel", callback_data="ap_back"))
        bot.edit_message_text(
            f"🖼 <b>Edit QR Code Image URL</b>\n\nCurrent: <code>{cfg['qr_code_url']}</code>\n\nSend the new image URL:",
            uid, call.message.message_id, reply_markup=mk
        )
        bot.register_next_step_handler(call.message, process_admin_edit_qr)
        return

# ─────────────────────────────────────────────────────────────
#  ADMIN STEP PROCESSORS RydenX
# ─────────────────────────────────────────────────────────────
@safe_handler
def process_admin_broadcast(message):
    uid = message.chat.id
    state = user_state.pop(uid, {})
    if state.get("action") != "admin_broadcast":
        return
    if not is_admin(uid):
        return
    success = fail = 0
    for user in list(users):
        try:
            bot.copy_message(user, uid, message.message_id)
            success += 1
        except Exception:
            fail += 1
    bot.send_message(uid,
        f"✅ <b>Broadcast Done!</b>\n✅ Sent: {success}\n❌ Failed: {fail}",
        reply_markup=admin_panel_markup()
    )


@safe_handler
def process_gc_create_step(message):
    uid = message.chat.id
    state = user_state.get(uid, {})
    if state.get("action") != "admin_gc_create":
        return
    if not is_admin(uid):
        return
    if state["step"] == "code":
        code = message.text.strip()
        if not code:
            bot.send_message(uid, "❌ Invalid code. Try again:")
            bot.register_next_step_handler(message, process_gc_create_step)
            return
        user_state[uid]["gift_code"] = code
        user_state[uid]["step"] = "amount"
        bot.send_message(uid, f"Step 2/2 – Code: <code>{code}</code>\n\nNow enter the INR amount:")
        bot.register_next_step_handler(message, process_gc_create_step)
    elif state["step"] == "amount":
        try:
            amount = float(message.text.strip())
        except ValueError:
            bot.send_message(uid, "❌ Enter a valid number:")
            bot.register_next_step_handler(message, process_gc_create_step)
            return
        code = user_state.pop(uid)["gift_code"]
        gift_codes[code] = amount
        persist_gift_code(code, amount)
        bot.send_message(uid,
            f"✅ Gift code <code>{code}</code> created with <b>₹{amount:.2f}</b>!",
            reply_markup=admin_panel_markup()
        )


@safe_handler
def process_gc_delete(message):
    uid = message.chat.id
    state = user_state.pop(uid, {})
    if state.get("action") != "admin_gc_delete":
        return
    if not is_admin(uid):
        return
    code = message.text.strip()
    if code in gift_codes:
        del gift_codes[code]
        delete_gift_code(code)
        bot.send_message(uid, f"✅ Gift code <code>{code}</code> deleted.", reply_markup=admin_panel_markup())
    else:
        bot.send_message(uid, f"❌ Code <code>{code}</code> not found.", reply_markup=admin_panel_markup())


@safe_handler
def process_admin_add_bal(message):
    uid = message.chat.id
    state = user_state.pop(uid, {})
    if state.get("action") != "admin_add_bal" or not is_admin(uid):
        return
    try:
        parts = message.text.strip().split()
        target_id = int(parts[0])
        amount = float(parts[1])
        with wallet_balance_lock:
            user_balances[target_id] = user_balances.get(target_id, 0) + amount
            persist_user(target_id)
        send_log(f"✅ <b>Payment approved / wallet credited</b>\nUser ID: <code>{target_id}</code>\nAmount: ₹{amount:.2f}")
        bot.send_message(uid, f"✅ Added <b>₹{amount:.2f}</b> to user <code>{target_id}</code>.\nNew balance: ₹{user_balances[target_id]:.2f}", reply_markup=admin_panel_markup())
        try:
            bot.send_message(target_id, f"🎉 Admin added <b>₹{amount:.2f}</b> to your account!")
        except Exception:
            pass
    except (ValueError, IndexError):
        bot.send_message(uid, "❌ Invalid format. Use: <code>USER_ID AMOUNT</code>", reply_markup=admin_panel_markup())


@safe_handler
def process_admin_rem_bal(message):
    uid = message.chat.id
    state = user_state.pop(uid, {})
    if state.get("action") != "admin_rem_bal" or not is_admin(uid):
        return
    try:
        parts = message.text.strip().split()
        target_id = int(parts[0])
        amount = float(parts[1])
        if amount < 0:
            bot.send_message(uid, "❌ Removal amount must be positive.", reply_markup=admin_panel_markup())
            return
        with wallet_balance_lock:
            with mongo_client.start_session() as session:
                with session.start_transaction():
                    updated = wallet_atomic_debit(target_id, amount, session=session)
                    if not updated:
                        bot.send_message(uid, f"❌ Cannot remove <b>₹{amount:.2f}</b> from user <code>{target_id}</code> because the balance would go below zero.", reply_markup=admin_panel_markup())
                        return
                    user_balances[target_id] = float(updated["balance"])
                    persist_user(target_id)
                send_log(f"💰 <b>Wallet debited</b>\nUser ID: <code>{target_id}</code>\nAmount: ₹{amount:.2f}")
        bot.send_message(uid, f"✅ Removed <b>₹{amount:.2f}</b> from user <code>{target_id}</code>.\nNew balance: ₹{user_balances[target_id]:.2f}", reply_markup=admin_panel_markup())
        try:
            bot.send_message(target_id, f"⚠️ Admin deducted <b>₹{amount:.2f}</b> from your account.")
        except Exception:
            pass
    except (ValueError, IndexError):
        bot.send_message(uid, "❌ Invalid format. Use: <code>USER_ID AMOUNT</code>", reply_markup=admin_panel_markup())


@safe_handler
def process_admin_check_bal(message):
    uid = message.chat.id
    state = user_state.pop(uid, {})
    if state.get("action") != "admin_check_bal" or not is_admin(uid):
        return
    try:
        target_id = int(message.text.strip())
        bal = user_balances.get(target_id, 0)
        bot.send_message(uid, f"💰 User <code>{target_id}</code> balance: <b>₹{bal:.2f}</b>", reply_markup=admin_panel_markup())
    except ValueError:
        bot.send_message(uid, "❌ Invalid user ID.", reply_markup=admin_panel_markup())


@safe_handler
def process_admin_ban(message):
    uid = message.chat.id
    state = user_state.pop(uid, {})
    if state.get("action") != "admin_ban" or not is_admin(uid):
        return
    try:
        target_id = int(message.text.strip())
        banned_users.add(target_id)
        persist_user(target_id)
        bot.send_message(uid, f"🚫 User <code>{target_id}</code> has been banned.", reply_markup=admin_panel_markup())
        try:
            bot.send_message(target_id, "🚫 You have been banned from this bot.")
        except Exception:
            pass
    except ValueError:
        bot.send_message(uid, "❌ Invalid user ID.", reply_markup=admin_panel_markup())


@safe_handler
def process_admin_unban(message):
    uid = message.chat.id
    state = user_state.pop(uid, {})
    if state.get("action") != "admin_unban" or not is_admin(uid):
        return
    try:
        target_id = int(message.text.strip())
        banned_users.discard(target_id)
        persist_user(target_id)
        bot.send_message(uid, f"✅ User <code>{target_id}</code> has been unbanned.", reply_markup=admin_panel_markup())
        try:
            bot.send_message(target_id, "✅ You have been unbanned. Use /start to continue.")
        except Exception:
            pass
    except ValueError:
        bot.send_message(uid, "❌ Invalid user ID.", reply_markup=admin_panel_markup())


@safe_handler
def process_admin_edit_rate(message):
    uid = message.chat.id
    state = user_state.pop(uid, {})
    if state.get("action") != "admin_edit_rate" or not is_admin(uid):
        return
    try:
        val = float(message.text.strip())
        if val < 0:
            raise ValueError
        cfg[state["cfg_key"]] = val
        save_config(cfg)
        legacy_service_id = {
            "provider_rate_reactions": "reactions",
            "provider_rate_views": "views",
            "provider_rate_members": "members",
        }.get(state["cfg_key"])
        if legacy_service_id:
            services_collection.update_one(
                {"_id": legacy_service_id},
                {"$set": {"provider_rate": val}}
            )
        bot.send_message(uid,
            f"✅ <b>{state['label']}</b> updated to <b>{val}</b>",
            reply_markup=admin_panel_markup()
        )
    except ValueError:
        bot.send_message(uid, "❌ Invalid value. Must be a positive number.", reply_markup=admin_panel_markup())


@safe_handler
def process_admin_edit_sid(message):
    uid = message.chat.id
    state = user_state.pop(uid, {})
    if state.get("action") != "admin_edit_sid" or not is_admin(uid):
        return
    val_str = message.text.strip()
    if not val_str.isdigit():
        bot.send_message(uid, "❌ Service ID must be a whole number (integer).", reply_markup=admin_panel_markup())
        return
    val = int(val_str)
    cfg[state["cfg_key"]] = val
    save_config(cfg)
    legacy_service_id = {
        "service_id_reactions": "reactions",
        "service_id_views": "views",
        "service_id_members": "members",
    }.get(state["cfg_key"])
    if legacy_service_id:
        services_collection.update_one(
            {"_id": legacy_service_id},
            {"$set": {"provider_service_id": val}}
        )
    bot.send_message(uid,
        f"✅ <b>{state['label']} Service ID</b> updated to <b>{val}</b>",
        reply_markup=admin_panel_markup()
    )


@safe_handler
def process_admin_service_price_search(message):
    uid = message.chat.id
    state = user_state.pop(uid, {})
    if state.get("action") != "admin_service_price_search" or not is_admin(uid):
        return
    if message.content_type != "text":
        bot.send_message(uid, "❌ Send a text search term.", reply_markup=admin_panel_markup())
        return

    query = message.text.strip()
    if not query:
        bot.send_message(uid, "❌ Enter a service name, category, platform, or provider service ID.", reply_markup=admin_panel_markup())
        return

    query_lower = query.lower()
    services = []
    for service in services_collection.find({"enabled": True}).sort([("category", 1), ("name", 1)]):
        if not is_user_catalog_service(service):
            continue
        platform, category = get_user_catalog_service_parts(service)
        searchable = " ".join([
            str(service.get("name") or ""),
            str(service.get("category") or ""),
            str(service.get("provider_service_id") or ""),
            platform,
            category,
        ]).lower()
        if query_lower in searchable:
            services.append(service)
    services = services[:20]
    if not services:
        bot.send_message(uid, "❌ No enabled user-catalog services matched your search.", reply_markup=admin_panel_markup())
        return

    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    for service in services:
        platform, _ = get_user_catalog_service_parts(service)
        markup.add(telebot.types.InlineKeyboardButton(
            f"{format_service_platform(platform)} {service['name']} — "
            f"₹{format_selling_price(get_selling_rate(service))}/1K",
            callback_data=f"svc_price_select:{service['_id']}"
        ))
    markup.add(telebot.types.InlineKeyboardButton("🔙 Back", callback_data="ap_back"))
    bot.send_message(uid, "💰 <b>Select a service to price:</b>", reply_markup=markup)


@safe_handler
def process_admin_service_price_input(message):
    uid = message.chat.id
    state = user_state.pop(uid, {})
    if state.get("action") != "admin_service_price_edit" or not is_admin(uid):
        return
    try:
        price = float(message.text.strip())
        if price <= 0:
            raise ValueError
    except (AttributeError, ValueError):
        bot.send_message(uid, "❌ Selling price must be a positive number.", reply_markup=admin_panel_markup())
        return

    service = get_service_by_id(state.get("service_id"))
    if not service or not service.get("enabled") or not is_user_catalog_service(service):
        bot.send_message(uid, "❌ Service is no longer available in the user catalog.", reply_markup=admin_panel_markup())
        return
    services_collection.update_one(
        {"_id": service["_id"]},
        {"$set": {"selling_price": price}}
    )
    bot.send_message(
        uid,
        f"✅ <b>{escape(str(service['name']))}</b> selling price updated to "
        f"<b>₹{format_selling_price(price)}/1K</b>.",
        reply_markup=admin_panel_markup()
    )


@safe_handler
def process_admin_service_input(message):
    uid = message.chat.id
    state = user_state.pop(uid, {})
    if state.get("action") not in {"admin_service_add", "admin_service_edit"}:
        return
    if not is_admin(uid):
        return
    if message.content_type != "text":
        bot.send_message(uid, "❌ Send the service fields as text.", reply_markup=admin_panel_markup())
        return

    parts = [part.strip() for part in message.text.split("|")]
    if len(parts) != 8 or any(not part for part in parts[:3]):
        bot.send_message(
            uid,
            "❌ Invalid format. Use:\n"
            "<code>Name | Provider ID | Category | Min | Max | Provider Rate | Selling Rate | Enabled</code>",
            reply_markup=admin_panel_markup()
        )
        return

    enabled_values = {"1": True, "yes": True, "true": True, "on": True,
                      "0": False, "no": False, "false": False, "off": False}
    try:
        provider_service_id = int(parts[1])
        minimum = int(parts[3])
        maximum = int(parts[4])
        provider_rate = float(parts[5])
        selling_rate = float(parts[6])
        enabled_key = parts[7].lower()
        if (
            provider_service_id <= 0 or minimum < 1 or maximum < minimum or
            provider_rate <= 0 or selling_rate <= 0 or enabled_key not in enabled_values
        ):
            raise ValueError
    except ValueError:
        bot.send_message(
            uid,
            "❌ Invalid numeric range or enabled value. "
            "Use positive Provider ID/Min/rates, Max ≥ Min, and yes/no for Enabled.",
            reply_markup=admin_panel_markup()
        )
        return

    service_data = {
        "name": parts[0],
        "provider_service_id": provider_service_id,
        "category": parts[2],
        "min": minimum,
        "max": maximum,
        "provider_rate": provider_rate,
        "selling_price": selling_rate,
        "enabled": enabled_values[enabled_key],
    }
    if state["action"] == "admin_service_edit":
        services_collection.update_one(
            {"_id": state["service_id"]}, {"$set": service_data}
        )
        result = "updated"
    else:
        service_data["_id"] = uuid4().hex
        services_collection.insert_one(service_data)
        result = "added"

    bot.send_message(
        uid,
        f"✅ Service <b>{escape(parts[0])}</b> {result}.",
        reply_markup=admin_panel_markup()
    )


@safe_handler
def process_admin_edit_apikey(message):
    uid = message.chat.id
    state = user_state.pop(uid, {})
    if state.get("action") != "admin_edit_apikey" or not is_admin(uid):
        return
    new_key = message.text.strip()
    if len(new_key) < 5:
        bot.send_message(uid, "❌ API key seems too short.", reply_markup=admin_panel_markup())
        return
    cfg["smm_api_key"] = new_key
    save_config(cfg)
    bot.send_message(uid, f"✅ API key updated to <code>{new_key}</code>", reply_markup=admin_panel_markup())


@safe_handler
def process_admin_set_logs(message):
    uid = message.chat.id
    state = user_state.pop(uid, {})
    if state.get("action") != "admin_set_logs" or not is_admin(uid):
        return
    channel = message.text.strip().lstrip("@")
    cfg["logs_channel"] = channel
    save_config(cfg)
    # Test send
    try:
        target = channel if channel.startswith("-") else "@" + channel
        bot.send_message(target, "✅ Logs channel connected to SMM bot!")
        bot.send_message(uid, f"✅ Logs channel set to <b>{channel}</b> and test message sent!", reply_markup=admin_panel_markup())
    except Exception as e:
        bot.send_message(uid,
            f"⚠️ Channel saved as <b>{channel}</b> but test message failed.\nError: {e}\n\n"
            "Make sure bot is admin in the channel.",
            reply_markup=admin_panel_markup()
        )


@safe_handler
def process_admin_edit_smmurl(message):
    uid = message.chat.id
    state = user_state.pop(uid, {})
    if state.get("action") != "admin_edit_smmurl" or not is_admin(uid):
        return
    url = message.text.strip()
    if not url.startswith("http"):
        bot.send_message(uid, "❌ Invalid URL.", reply_markup=admin_panel_markup())
        return
    cfg["smm_panel_url"] = url
    save_config(cfg)
    bot.send_message(uid, f"✅ SMM Panel URL updated to <code>{url}</code>", reply_markup=admin_panel_markup())


@safe_handler
def process_admin_edit_qr(message):
    uid = message.chat.id
    state = user_state.pop(uid, {})
    if state.get("action") != "admin_edit_qr" or not is_admin(uid):
        return
    url = message.text.strip()
    if not url.startswith("http"):
        bot.send_message(uid, "❌ Invalid URL.", reply_markup=admin_panel_markup())
        return
    cfg["qr_code_url"] = url
    save_config(cfg)
    bot.send_message(uid, f"✅ QR code URL updated!", reply_markup=admin_panel_markup())


@safe_handler
def process_admin_set_main_menu_photo(message):
    uid = message.chat.id
    state = user_state.pop(uid, {})
    if state.get("action") != "admin_set_main_menu_photo" or not is_admin(uid):
        return
    if message.content_type != "photo" or not message.photo:
        bot.send_message(uid, "❌ Please send a photo.", reply_markup=admin_panel_markup())
        return
    cfg["main_menu_photo_file_id"] = message.photo[-1].file_id
    save_config(cfg)
    bot.send_message(uid, "✅ Main menu photo updated.", reply_markup=admin_panel_markup())


# ─────────────────────────────────────────────────────────────
#  /start RydenX
# ─────────────────────────────────────────────────────────────
@bot.message_handler(commands=['start'])
@safe_handler
@require_not_banned
def send_welcome(message):
    reload_cfg()
    user_id = message.chat.id
    text = message.text.split()

    # SAFE NAME HANDLING
    if message.chat.username:
        display_name = "@" + message.chat.username
    else:
        display_name = "Anonymous"

    if user_id not in users:
        users.add(user_id)
        persist_user(user_id)
        send_log(
            f"🆕 <b>New user</b>\n"
            f"User ID: <code>{user_id}</code>\n"
            f"Username: <code>{escape(display_name)}</code>"
        )

    if len(text) > 1:
        ref_str = text[1]
        if ref_str.isdigit():
            referrer_id = int(ref_str)
            if referrer_id == user_id:
                bot.send_message(user_id, "❌ 𝘿𝙊𝙎𝙏 𝙆𝙊 𝘽𝙃𝙀𝙅 𝘽𝙃𝘼𝙄. 𝙔𝙊𝙐 𝘾𝘼𝙉𝙉𝙊𝙏 𝙍𝙀𝙁𝙀𝙍 𝙔𝙊𝙐𝙍𝙎𝙀𝙇𝙁!")
                return
            user_referrals[user_id] = {"referrer": referrer_id, "rewarded": False}

    persist_user(user_id)
    user_link = f"<a href='tg://user?id={user_id}'>{display_name}</a>"

    if user_has_joined_all_channels(user_id):
        send_main_menu(user_id, getattr(message.from_user, "first_name", None))
        return

    bot.send_message(
        user_id,
        f"❤️ 𝘿𝙀𝘼𝙍 {user_link},\n\n"
        "𝙒𝙀𝘾𝙊𝙈𝙀 𝙏𝙊 𝙊𝙐𝙍 𝙏Ｇ 𝙎𝙀𝙍𝙑𝙄𝘾𝙀 𝘽𝙊𝗍!\n"
        "𝙁𝙤𝙧 𝙇𝙖𝙩𝙚𝙨𝙩 𝙐𝙥𝙙𝙖𝙩𝙚𝙨 & 𝙍𝙚𝙜𝙪𝙡𝙖𝙩𝙞𝙤𝙣𝙨 𝙔𝙤𝙪 𝙉𝙚𝙚𝙙 𝙏𝙤 𝙅𝙤𝙞𝙣 𝙊𝙪𝙧 𝘾𝙃𝗔𝗡𝗡𝗘𝗟𝗦:",
        reply_markup=join_menu(),
        disable_web_page_preview=True
    )


# ─────────────────────────────────────────────────────────────
#  Joined callback
# ─────────────────────────────────────────────────────────────
@bot.callback_query_handler(func=lambda call: call.data == "joined")
@safe_callback
def joined_button_handler(call):
    reload_cfg()
    user_id = call.message.chat.id

    if not user_has_joined_all_channels(user_id):
        send_log(f"🔐 <b>Force-join verification failed</b>\nUser ID: <code>{user_id}</code>")
        bot.answer_callback_query(call.id, "❌ Please join ALL channels first!")
        return

    try:
        bot.delete_message(user_id, call.message.message_id)
    except Exception:
        pass

    send_main_menu(user_id, getattr(call.message.chat, "first_name", None))

    first_name = call.message.chat.first_name or str(user_id)
    send_log(
        f"🔐 <b>Force-join verification succeeded</b>\n"
        f"User: <a href='tg://user?id={user_id}'>{escape(str(first_name))}</a>"
    )

    # Reward referrer
    if user_id in user_referrals:
        ref_info = user_referrals[user_id]
        if not ref_info.get("rewarded"):
            referrer_id = ref_info["referrer"]
            reward = float(cfg["referral_reward_inr"])
            user_balances[referrer_id] = user_balances.get(referrer_id, 0) + reward
            user_referrals[user_id]["rewarded"] = True
            persist_user(referrer_id)
            persist_user(user_id)
            send_log(
                f"👥 <b>Referral reward credited</b>\n"
                f"Referrer: <code>{referrer_id}</code>\n"
                f"Referred user: <code>{user_id}</code>\n"
                f"Amount: ₹{reward:.2f}"
            )
            try:
                bot.send_message(referrer_id, f"✅ You received <b>₹{reward:.2f}</b> referral reward!")
            except Exception:
                pass


@bot.callback_query_handler(func=lambda c: c.data.startswith("main_menu_"))
@safe_callback
def main_menu_action_callback(call):
    action_text = {
        "main_menu_my_orders": "📦 My Orders",
        "main_menu_check_balance": "💰 Check Balance",
        "main_menu_add_funds": "➕ Add Funds",
        "main_menu_refer": "📢 Refer & Earn",
        "main_menu_search": "🔎 Search Service",
        "main_menu_support": "📞 Support",
        "main_menu_help": "ℹ️ Help",
    }.get(call.data)
    if not action_text:
        return
    bot.answer_callback_query(call.id)
    trigger_main_menu_action(call, action_text)


# ─────────────────────────────────────────────────────────────
#  ORDER FLOW RydenX
# ─────────────────────────────────────────────────────────────
def start_order(message, service):
    reload_cfg()
    user_id = message.chat.id
    user_state.pop(user_id, None)
    user_state[user_id] = {
        "action": "order",
        "service_id": service["_id"],
        "service_name": service["name"],
        "service_min": service["min"],
        "service_max": service["max"],
        "selling_rate": get_selling_rate(service),
        "step": "awaiting_link",
        "url": None
    }
    bot.send_message(user_id,
        f"𝗦𝗘𝗡𝗗 𝗬𝗢𝗨𝗥 𝗧𝗘𝗟𝗘𝗚𝗥𝗔𝗠 𝗟𝗜𝗡𝗞 𝗙𝗢𝗥 {service['name']}:\n"
        f"(Selling rate: ₹{get_selling_rate(service):.2f} per 1000 {service['category']})"
    )


@bot.message_handler(func=lambda m: bool(m.text and get_enabled_service_by_name(m.text)))
@safe_handler
@require_not_banned
def order_service(message):
    service = get_enabled_service_by_name(message.text)
    if service:
        start_order(message, service)


@bot.message_handler(func=lambda m: m.text == "🔎 Search Service")
@safe_handler
@require_not_banned
def search_service(message):
    user_id = message.chat.id
    user_state[user_id] = {"action": "search_service"}
    bot.send_message(user_id, "🔎 Enter a service name or category to search:")
    bot.register_next_step_handler(message, process_service_search)


@safe_handler
def process_service_search(message):
    user_id = message.chat.id
    state = user_state.pop(user_id, {})
    if state.get("action") != "search_service":
        return
    if message.content_type != "text":
        bot.send_message(user_id, "❌ Please enter search text.")
        return
    query = message.text.strip()
    if not query:
        bot.send_message(user_id, "❌ Please enter a search term.")
        return

    matcher = {"$regex": re.escape(query), "$options": "i"}
    services = list(services_collection.find({
        "enabled": True,
        "$or": [{"name": matcher}, {"category": matcher}]
    }).sort([("category", 1), ("name", 1)]))
    services = [service for service in services if is_user_catalog_service(service)][:20]
    if not services:
        bot.send_message(user_id, "❌ No enabled services matched your search.")
        return

    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    for service in services:
        markup.add(telebot.types.InlineKeyboardButton(
            service["name"], callback_data=f"svc_order:{service['_id']}"
        ))
    bot.send_message(user_id, "🔎 <b>Enabled services found:</b>", reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data.startswith("svc_order:"))
@safe_callback
def order_service_callback(call):
    service_id = call.data.split(":", 1)[1]
    service = get_service_by_id(service_id, enabled_only=True)
    if not is_user_catalog_service(service):
        bot.answer_callback_query(call.id, "❌ This service is no longer enabled.")
        return
    bot.answer_callback_query(call.id)
    start_order(call.message, service)


@bot.callback_query_handler(func=lambda c: c.data.startswith("retry_res:"))
@safe_callback
def retry_reservation_handler(call):
    reservation_id = call.data.split(":", 1)[1]
    result = wallet_retry_status(reservation_id)
    if result["status"] == "not_found":
        bot.answer_callback_query(call.id, "Reservation not found.")
        return
    if result["status"] == "settled":
        bot.answer_callback_query(call.id, "✅ Already settled.")
        bot.send_message(
            call.message.chat.id,
            f"✅ This order was already placed.\nOrder ID: <code>{result['order_id']}</code>"
        )
        return
    if result["status"] == "released":
        bot.answer_callback_query(call.id, "✅ ₹ balance was released.")
        bot.send_message(
            call.message.chat.id,
            "✅ Your ₹ balance was already released for this reservation."
        )
        return
    bot.answer_callback_query(call.id, "⏳ Still pending.")
    if result.get("provider_request_id"):
        bot.send_message(
            call.message.chat.id,
            f"⏳ This reservation is still pending review.\n"
            f"Request ID: <code>{result['provider_request_id']}</code>\n"
            f"Reason: {result.get('reason', 'unknown')}\n\n"
            f"Your ₹{result.get('amount', 0):.2f} remains reserved. Please wait for admin review."
        )
    else:
        bot.send_message(
            call.message.chat.id,
            "⏳ This reservation is still pending. Please wait for admin review."
        )


@bot.message_handler(func=lambda m: (
    user_state.get(m.chat.id) is not None and
    user_state.get(m.chat.id, {}).get("action") == "order"
))
@safe_handler
def handle_pending_order(message):
    if is_main_command(message.text):
        user_state.pop(message.chat.id, None)
        return
    state = user_state.get(message.chat.id)
    if not state:
        return
    if state.get("step") == "awaiting_link":
        process_order_link(message)
    elif state.get("step") == "awaiting_quantity":
        process_order_quantity(message)
    else:
        user_state.pop(message.chat.id, None)


@safe_handler
def process_order_link(message):
    user_id = message.chat.id
    state   = user_state.get(user_id)
    if not state or state.get("step") != "awaiting_link":
        return
    if message.content_type != 'text':
        bot.send_message(user_id, "❌ Please send the link as text.")
        return
    state["url"]  = message.text.strip()
    state["step"] = "awaiting_quantity"
    selling_rate  = state["selling_rate"]
    bot.send_message(user_id,
        f"𝗘𝗡𝗧𝗘𝗥 𝗤𝗨𝗔𝗡𝗧𝗜𝗧𝗬 (𝗠𝗜𝗡 {state['service_min']}):\n"
        f"(Selling rate: ₹{selling_rate:.2f} per 1000 {state['service_name']})"
    )


@safe_handler
def process_order_quantity(message):
    reload_cfg()
    user_id = message.chat.id
    state   = user_state.get(user_id)
    if not state or state.get("step") != "awaiting_quantity":
        return
    if message.content_type != 'text' or not message.text.strip().isdigit():
        bot.send_message(user_id, "❌ Please enter numbers only.")
        return
    quantity = int(message.text.strip())
    if quantity < state["service_min"]:
        bot.send_message(user_id, f"❌ Minimum order quantity is {state['service_min']}.")
        return
    if quantity > state["service_max"]:
        bot.send_message(user_id, f"❌ Maximum order quantity is {state['service_max']}.")
        return

    service = get_service_by_id(state["service_id"], enabled_only=True)
    if not service:
        user_state.pop(user_id, None)
        bot.send_message(user_id, "❌ This service is no longer enabled.")
        return

    url            = state["url"]
    selling_rate   = state.get("selling_rate", get_selling_rate(service))
    charged_amount = quantity / 1000.0 * selling_rate
    try:
        reservation = wallet_hold(user_id, charged_amount)
    except Exception:
        bot.send_message(user_id, "❌ Unable to reserve ₹ balance right now. Please try again.")
        user_state.pop(user_id, None)
        return
    if not reservation:
        current_user = users_collection.find_one({"_id": user_id}) or {}
        available = float(current_user.get("balance", user_balances.get(user_id, 0)))
        user_balances[user_id] = available
        bot.send_message(
            user_id,
            f"❌ Insufficient ₹ balance. You need <b>₹{charged_amount:.2f}</b> "
            f"but have <b>₹{available:.2f}</b>."
        )
        user_state.pop(user_id, None)
        return

    reservation_id = reservation["reservation_id"]
    user_state.pop(user_id, None)

    provider_request_id = uuid4().hex
    if not wallet_mark_request_attempted(reservation_id, provider_request_id):
        bot.send_message(
            user_id,
            f"⚠️ This reservation already has a pending provider request.\n"
            f"Reservation ID: <code>{reservation_id}</code>\n"
            f"Use Retry to check its status.",
            reply_markup=pending_reservation_markup(reservation_id)
        )
        return

    order_data = {
        "key":      cfg["smm_api_key"],
        "action":   "add",
        "service":  service["provider_service_id"],
        "link":     url,
        "quantity": quantity
    }
    try:
        provider_response = requests.post(
            cfg["smm_panel_url"], data=order_data, timeout=15
        )
    except requests.RequestException:
        wallet_mark_pending(reservation_id, "timeout_or_connection")
        bot.send_message(
            user_id,
            f"⚠️ Provider response is pending. Your <b>₹{charged_amount:.2f}</b> "
            f"remains reserved.\nReservation ID: <code>{reservation_id}</code>",
            reply_markup=pending_reservation_markup(reservation_id)
        )
        return

    try:
        response = provider_response.json()
    except (AttributeError, TypeError, ValueError):
        wallet_mark_pending(reservation_id, "malformed_or_truncated_response")
        bot.send_message(
            user_id,
            f"⚠️ Provider response could not be verified. Your <b>₹{charged_amount:.2f}</b> "
            f"remains reserved.\nReservation ID: <code>{reservation_id}</code>",
            reply_markup=pending_reservation_markup(reservation_id)
        )
        return

    if not isinstance(response, dict):
        wallet_mark_pending(reservation_id, "malformed_or_truncated_response")
        bot.send_message(
            user_id,
            f"⚠️ Provider response could not be verified. Your <b>₹{charged_amount:.2f}</b> "
            f"remains reserved.\nReservation ID: <code>{reservation_id}</code>",
            reply_markup=pending_reservation_markup(reservation_id)
        )
        return

    raw_order_id = response.get("order")
    has_order_id = (
        isinstance(raw_order_id, (str, int)) and
        not isinstance(raw_order_id, bool) and
        bool(str(raw_order_id).strip())
    )
    raw_error = response.get("error")
    has_explicit_error = isinstance(raw_error, str) and bool(raw_error.strip())
    if has_order_id and not has_explicit_error:
        order_id = raw_order_id
        if not wallet_settle(reservation_id, order_id):
            wallet_mark_pending(reservation_id, "settlement_conflict")
            bot.send_message(
                user_id,
                f"⚠️ Order result could not be finalized. Your <b>₹{charged_amount:.2f}</b> "
                f"remains reserved.\nReservation ID: <code>{reservation_id}</code>",
                reply_markup=pending_reservation_markup(reservation_id)
            )
            return
    elif has_explicit_error and not has_order_id:
        wallet_release(reservation_id, order_id=None)
        send_log(
            f"❌ <b>Order failed</b>\n"
            f"User ID: <code>{user_id}</code>\n"
            f"Service: <b>{escape(str(service['name']))}</b>\n"
            f"Quantity: {quantity}\n"
            f"Charged: ₹{charged_amount:.2f}\n"
            f"Status: failed"
        )
        bot.send_message(
            user_id,
            f"❌ Order failed. ₹ balance released.\nError: {raw_error}"
        )
        return
    else:
        wallet_mark_pending(reservation_id, "ambiguous_provider_response")
        bot.send_message(
            user_id,
            f"⚠️ Provider response was ambiguous. Your <b>₹{charged_amount:.2f}</b> "
            f"remains reserved.\nReservation ID: <code>{reservation_id}</code>",
            reply_markup=pending_reservation_markup(reservation_id)
        )
        return

    if "order" in response:
        ts       = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        order_details = {
            "order_id":    order_id,
            "service_type": service["name"],
            "service_name": service["name"],
            "reservation_id": reservation_id,
            "link":        url,
            "quantity":    quantity,
            "charged_amount": charged_amount,
            "provider_rate": get_provider_rate(service),
            "selling_rate": selling_rate,
            "timestamp":   ts
        }
        user_orders.setdefault(user_id, []).append(order_details)
        persist_order(user_id, order_details)
        send_log(
            f"🛒 <b>Order placed</b>\n"
            f"User ID: <code>{user_id}</code>\n"
            f"Order ID: <code>{order_id}</code>\n"
            f"Service: <b>{escape(str(service['name']))}</b>\n"
            f"Quantity: {quantity}\n"
            f"Charged: ₹{charged_amount:.2f}\n"
            f"Status: placed"
        )

        bot.send_message(user_id,
            f"✅ 𝗢𝗥𝗗𝗘𝗥 𝗣𝗟𝗔𝗖𝗘𝗗 🦋\n"
            f"Service: {service['name']}\n"
            f"Quantity: {quantity}\n"
            f"Order ID: <code>{order_id}</code>\n"
            f"Estimated time: 2-3 hours"
        )

        # Admin notification
        admin_text = (
            f"🛒 <b>NEW ORDER</b>\n"
            f"👤 User: <a href='tg://user?id={user_id}'>{user_id}</a>\n"
            f"🔧 Service: {service['name']}\n"
            f"🔗 Link: {url}\n"
            f"📦 Qty: {quantity}\n"
            f"🆔 Order ID: {order_id}\n"
            f"🕐 Time: {ts}"
        )
        try:
            bot.send_message(primary_admin_id(), admin_text, disable_web_page_preview=True)
        except Exception:
            pass

        # Logs channel


# ─────────────────────────────────────────────────────────────
#  USER FEATURES RydenX
# ─────────────────────────────────────────────────────────────
@bot.message_handler(func=lambda m: m.text == "💰 Check Balance")
@safe_handler
@require_not_banned
def check_balance(message):
    user_state.pop(message.chat.id, None)
    reload_cfg()
    uid = message.chat.id
    bal = user_balances.get(uid, 0)
    bot.send_message(uid,
        f"💰 <b>Your Balance</b>\n\n"
        f"💰 Wallet Balance: <b>₹{bal:.2f}</b>"
    )


@bot.message_handler(func=lambda m: m.text == "🎁 Claim Bonus")
@safe_handler
@require_not_banned
def claim_bonus(message):
    user_state.pop(message.chat.id, None)
    reload_cfg()
    user_id = message.chat.id
    today   = datetime.now().date()
    if user_id in user_last_bonus and user_last_bonus[user_id] == today:
        bot.send_message(user_id, "❌ 𝘽𝙖𝙨 𝙠𝙧 𝙗𝙝𝙖𝙞 𝙚𝙠 𝙝𝙞 𝙙𝙞𝙣 𝙢𝙚 𝙠𝙞𝙩𝙣𝙖 𝙡𝙚𝙂𝙖🌚 YOU CAN CLAIM BONUS ONCE A DAY.")
        return
    bonus = float(cfg["daily_bonus_inr"])
    user_balances[user_id] = user_balances.get(user_id, 0) + bonus
    user_last_bonus[user_id] = today
    persist_user(user_id)
    bot.send_message(user_id, f"✅ <b>₹{bonus:.2f}</b> bonus added to your account! ☺")


@bot.message_handler(func=lambda m: m.text == "➕ Add Funds")
@safe_handler
@require_not_banned
def add_funds(message):
    user_state.pop(message.chat.id, None)
    reload_cfg()
    user_id = message.chat.id
    bot.send_photo(
        user_id,
        cfg["qr_code_url"],
        caption=f"📌 𝗦𝗖𝗔𝗡 𝗤𝗥 & 𝗣𝗔𝗬 𝗧𝗛𝗘𝗡 𝗦𝗘𝗡𝗗 𝗦𝗖𝗥𝗘𝗘𝗡𝗦𝗛𝗢𝗧.\n\nFor help DM {cfg['payment_contact']}"
    )
    user_state[user_id] = {"action": "waiting_payment_screenshot"}


@bot.message_handler(content_types=['photo'])
@safe_handler
@require_not_banned
def handle_payment_screenshot(message):
    user_id = message.chat.id
    state = user_state.pop(user_id, {})
    if state.get("action") != "waiting_payment_screenshot":
        return
    send_log(f"💳 <b>Payment submitted</b>\nUser ID: <code>{user_id}</code>")
    bot.forward_message(primary_admin_id(), user_id, message.message_id)
    bot.send_message(primary_admin_id(),
        f"💳 Payment screenshot from user <a href='tg://user?id={user_id}'>{user_id}</a>. Verify and add ₹ balance.",
        disable_web_page_preview=True
    )
    bot.send_message(user_id, "✅ 𝗣𝗔𝗬𝗠𝗘𝗡𝗧 𝗦𝗖𝗥𝗘𝗘𝗡𝗦𝗛𝗢𝗧 𝗦𝗘𝗡𝗧 𝗧𝗢 𝗔𝗗𝗠𝗜𝗡. Please wait for verification.")


@bot.message_handler(func=lambda m: m.text == "📢 Refer & Earn")
@safe_handler
@require_not_banned
def refer_earn(message):
    user_state.pop(message.chat.id, None)
    reload_cfg()
    user_id = message.chat.id
    bot_username = cfg.get("bot_username", "your_bot")
    link = f"https://t.me/{bot_username}?start={user_id}"
    referred = [r for r, info in user_referrals.items() if info["referrer"] == user_id]
    rewarded  = [r for r, info in user_referrals.items() if info["referrer"] == user_id and info["rewarded"]]
    bot.send_message(user_id,
        f"📢 <b>Refer & Earn</b>\n\n"
        f"Earn <b>₹{float(cfg['referral_reward_inr']):.2f}</b> per referral!\n\n"
        f"🔗 Your link:\n<code>{link}</code>\n\n"
        f"👥 Total referred: {len(referred)}\n"
        f"✅ Rewarded: {len(rewarded)}\n\n"
        f"Send /referrals to see your list."
    )


@bot.message_handler(commands=['referrals', 'refferals'])
@safe_handler
@require_not_banned
def show_referrals(message):
    user_id = message.chat.id
    ref_list = [str(r) for r, info in user_referrals.items() if info["referrer"] == user_id]
    if ref_list:
        bot.send_message(user_id, "📢 <b>Your Referrals:</b>\n" + "\n".join(ref_list))
    else:
        bot.send_message(user_id, "❌ You have 0 referrals yet.")


@bot.message_handler(func=lambda m: m.text == "🔳 GiftCode")
@safe_handler
@require_not_banned
def giftcode_handler(message):
    user_id = message.chat.id
    user_state.pop(user_id, None)
    user_state[user_id] = {"action": "giftcode"}
    bot.send_message(user_id, "𝗣𝗟𝗘𝗔𝗦𝗘 𝗘𝗡𝗧𝗘𝗥 𝗬𝗢𝗨𝗥 𝗚𝗜𝗙𝗧 𝗖𝗢𝗗𝗘:")
    bot.register_next_step_handler(message, process_giftcode)


@safe_handler
def process_giftcode(message):
    user_id = message.chat.id
    state   = user_state.pop(user_id, {})
    if state.get("action") != "giftcode":
        return
    if message.content_type != 'text':
        bot.send_message(user_id, "❌ Please send the gift code as text.")
        return
    code = message.text.strip()
    if code not in gift_codes:
        bot.send_message(user_id, "❌ Wrong code! Ask admin for a valid gift code.")
        return
    redeemed = user_redeemed_codes.setdefault(user_id, set())
    if code in redeemed:
        bot.send_message(user_id, "❌ You have already redeemed this gift code!")
        return
    redeemed.add(code)
    amount = gift_codes[code]
    user_balances[user_id] = user_balances.get(user_id, 0) + amount
    persist_user(user_id)
    bot.send_message(user_id, f"✅ Gift code <code>{code}</code> redeemed! You received <b>₹{amount:.2f}</b> 🎉")


@bot.message_handler(func=lambda m: m.text == "🖲 Track Order")
@safe_handler
@require_not_banned
def track_order(message):
    user_id = message.chat.id
    user_state.pop(user_id, None)
    user_state[user_id] = {"action": "track_order"}
    bot.send_message(user_id, "𝗘𝗡𝗧𝗘𝗥 𝗬𝗢𝗨𝗥 𝗢𝗥𝗗𝗘𝗥 𝗜𝗗:")
    bot.register_next_step_handler(message, process_track_order)


@safe_handler
def process_track_order(message):
    reload_cfg()
    user_id = message.chat.id
    state   = user_state.pop(user_id, {})
    if state.get("action") != "track_order":
        return
    if message.content_type != 'text' or not message.text.strip().isdigit():
        bot.send_message(user_id, "❌ Please send the Order ID as a number.")
        return
    order_id = message.text.strip()
    try:
        response = requests.post(cfg["smm_panel_url"], data={
            "key":    cfg["smm_api_key"],
            "action": "status",
            "order":  order_id
        }, timeout=15).json()
    except Exception as e:
        send_log(f"⚠️ <b>Provider error</b>\nOrder ID: <code>{order_id}</code>\nError type: <code>{type(e).__name__}</code>")
        bot.send_message(user_id, f"❌ Error connecting to SMM panel: {e}")
        return
    if "error" in response:
        send_log(f"⚠️ <b>Provider error</b>\nOrder ID: <code>{order_id}</code>\nError type: <code>order_status_error</code>")
        bot.send_message(user_id, f"❌ Error: {response['error']}")
    else:
        status = response.get("status", "Unknown")
        order = orders_collection.find_one({"user_id": int(user_id), "order_id": order_id})
        old_status = get_order_status_for_display(order) if order else "Unknown"
        if str(old_status).lower() != str(status).lower():
            send_log(
                f"🔄 <b>Order status changed</b>\n"
                f"Order ID: <code>{order_id}</code>\n"
                f"{escape(str(old_status))} → {escape(str(status))}"
            )
        if order:
            orders_collection.update_one(
                {"_id": order["_id"]},
                {"$set": {"status": str(status)}}
            )
        info   = "\n".join([f"{k.capitalize()}: {v}" for k, v in response.items() if k != "status"])
        msg    = f"✅ <b>Order {order_id}</b>\nStatus: <b>{status}</b>"
        if info:
            msg += f"\n{info}"
        bot.send_message(user_id, msg)


def get_order_status_for_display(order):
    for field in ("status", "order_status", "provider_status"):
        status = order.get(field)
        if status:
            return str(status)

    provider_response = order.get("provider_response")
    if isinstance(provider_response, dict) and provider_response.get("status"):
        return str(provider_response["status"])

    order_id = order.get("order_id")
    if order_id is not None:
        reservation = wallet_reservations_collection.find_one({"order_id": order_id})
        if reservation and reservation.get("status"):
            return str(reservation["status"])

    return "Not available"


def get_order_amount_for_display(order):
    charged_amount = _safe_float(order.get("charged_amount"), 0.0)
    if charged_amount > 0:
        return f"₹{charged_amount:.2f}"

    reservation_id = order.get("reservation_id")
    if reservation_id:
        reservation = wallet_reservations_collection.find_one({"_id": reservation_id})
        if reservation and reservation.get("amount") is not None:
            return f"₹{float(reservation['amount']):.2f}"

    quantity = order.get("quantity")
    if quantity is None:
        return "N/A"

    service_name = order.get("service_name") or order.get("service_type")
    service = services_collection.find_one({"name": service_name}) if service_name else None
    if not service:
        return "N/A"
    selling_rate = get_selling_rate(service)
    if selling_rate <= 0:
        return "N/A"
    amount = float(quantity) / 1000.0 * selling_rate
    return f"₹{amount:.2f}"


def render_my_orders_page(user_id, page=0, page_size=5):
    orders = list(orders_collection.find({"user_id": int(user_id)}).sort("_id", -1))
    total_pages = max(1, (len(orders) + page_size - 1) // page_size)
    page = max(0, min(page, total_pages - 1))
    start = page * page_size
    end = start + page_size
    page_orders = orders[start:end]

    if not page_orders:
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            telebot.types.InlineKeyboardButton("⬅️ Back", callback_data="my_orders_back"),
            telebot.types.InlineKeyboardButton("🏠 Home", callback_data="svc_catalog_home"),
        )
        return "📦 <b>My Orders</b>\n\n📦 You haven't placed any orders yet.", markup

    lines = ["📦 <b>My Orders</b>", f"Page {page + 1}/{total_pages}"]
    for order in page_orders:
        service_name = str(order.get("service_name") or order.get("service_type") or "Unknown")
        quantity = order.get("quantity", "N/A")
        order_id = order.get("order_id", "N/A")
        amount = get_order_amount_for_display(order)
        status = get_order_status_for_display(order)
        lines.append("")
        lines.append(f"🆔 <code>{escape(str(order_id))}</code>")
        lines.append(f"Service: <b>{escape(service_name)}</b>")
        lines.append(f"Quantity: <b>{quantity}</b>")
        lines.append(f"Amount: <b>{amount}</b>")
        lines.append(f"Status: <b>{escape(str(status))}</b>")

    markup = telebot.types.InlineKeyboardMarkup(row_width=4)
    if page > 0:
        markup.add(telebot.types.InlineKeyboardButton("⬅️ Previous", callback_data=f"my_orders_page:{page - 1}"))
    else:
        markup.add(telebot.types.InlineKeyboardButton("⬅️ Previous", callback_data="my_orders_disabled"))
    if page + 1 < total_pages:
        markup.add(telebot.types.InlineKeyboardButton("➡️ Next", callback_data=f"my_orders_page:{page + 1}"))
    else:
        markup.add(telebot.types.InlineKeyboardButton("➡️ Next", callback_data="my_orders_disabled"))
    markup.add(
        telebot.types.InlineKeyboardButton("⬅️ Back", callback_data="my_orders_back"),
        telebot.types.InlineKeyboardButton("🏠 Home", callback_data="svc_catalog_home"),
    )
    return "\n".join(lines), markup


@bot.message_handler(func=lambda m: m.text == "📦 My Orders")
@safe_handler
@require_not_banned
def my_orders(message):
    user_id = message.chat.id
    text, markup = render_my_orders_page(user_id, page=0)
    if markup is None:
        bot.send_message(user_id, text)
        return
    bot.send_message(user_id, text, reply_markup=markup, disable_web_page_preview=True)


@bot.callback_query_handler(func=lambda c: c.data.startswith("my_orders_page:"))
@safe_callback
def my_orders_page_callback(call):
    user_id = call.message.chat.id
    try:
        page = int(call.data.split(":", 1)[1])
    except (IndexError, TypeError, ValueError):
        bot.answer_callback_query(call.id, "This page is no longer available.")
        return
    if page < 0:
        bot.answer_callback_query(call.id, "This page is no longer available.")
        return
    bot.answer_callback_query(call.id)
    text, markup = render_my_orders_page(user_id, page=page)
    bot.edit_message_text(text, user_id, call.message.message_id, reply_markup=markup, disable_web_page_preview=True)


@bot.callback_query_handler(func=lambda c: c.data == "my_orders_disabled")
@safe_callback
def my_orders_disabled_callback(call):
    bot.answer_callback_query(call.id, "No more orders to show.")


@bot.callback_query_handler(func=lambda c: c.data == "my_orders_back")
@safe_callback
def my_orders_back_callback(call):
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass
    send_main_menu(call.message.chat.id, getattr(call.message.chat, "first_name", None))


@bot.message_handler(func=lambda m: m.text == "📜 Order History")
@safe_handler
@require_not_banned
def order_history(message):
    user_id = message.chat.id
    orders  = user_orders.get(user_id, [])
    if not orders:
        bot.send_message(user_id, "❌ You have no orders yet.")
        return
    text = "📜 <b>Your Last 5 Orders:</b>\n\n"
    for o in orders[-5:]:
        text += (
            f"🆔 <code>{o['order_id']}</code> | {o['service_type'].capitalize()} | "
            f"Qty: {o['quantity']} | {o['timestamp']}\n"
        )
    bot.send_message(user_id, text)


@bot.message_handler(func=lambda m: m.text == "💬 Feedback")
@safe_handler
@require_not_banned
def feedback(message):
    user_id = message.chat.id
    user_state.pop(user_id, None)
    user_state[user_id] = {"action": "feedback"}
    bot.send_message(user_id, "𝗘𝗡𝗧𝗘𝗥 𝗬𝗢𝗨𝗥 𝗙𝗘𝗘𝗗𝗕𝗔𝗖𝗞:")
    bot.register_next_step_handler(message, process_feedback)


@safe_handler
def process_feedback(message):
    user_id = message.chat.id
    state   = user_state.pop(user_id, {})
    if state.get("action") != "feedback":
        return
    if message.content_type != 'text':
        bot.send_message(user_id, "❌ Please send feedback as text.")
        return
    text = message.text.strip()
    bot.send_message(primary_admin_id(),
        f"💬 <b>Feedback</b> from <a href='tg://user?id={user_id}'>{user_id}</a>:\n\n{text}",
        disable_web_page_preview=True
    )
    bot.send_message(user_id, "✅ Feedback submitted! Thank you.")


# ─────────────────────────────────────────────────────────────
#  LEGACY TEXT COMMANDS (still work for admin convenience)
# ─────────────────────────────────────────────────────────────
@bot.message_handler(commands=['addbalance'])
@safe_handler
def cmd_add_balance(message):
    if not is_admin(message.chat.id):
        return
    try:
        _, uid_s, amount_s = message.text.split()
        uid  = int(uid_s)
        amount  = float(amount_s)
        user_balances[uid] = user_balances.get(uid, 0) + amount
        persist_user(uid)
        send_log(f"✅ <b>Payment approved / wallet credited</b>\nUser ID: <code>{uid}</code>\nAmount: ₹{amount:.2f}")
        bot.send_message(message.chat.id, f"✅ Added ₹{amount:.2f} to {uid}")
        try:
            bot.send_message(uid, f"✅ Admin added ₹{amount:.2f} to your account!")
        except Exception:
            pass
    except ValueError:
        bot.send_message(message.chat.id, "Usage: /addbalance <user_id> <amount>")


@bot.message_handler(commands=['removebalance'])
@safe_handler
def cmd_remove_balance(message):
    if not is_admin(message.chat.id):
        return
    try:
        _, uid_s, amount_s = message.text.split()
        uid  = int(uid_s)
        amount  = float(amount_s)
        if amount < 0:
            bot.send_message(message.chat.id, "Usage: /removebalance <user_id> <amount> (amount must be positive)")
            return
        with wallet_balance_lock:
            with mongo_client.start_session() as session:
                with session.start_transaction():
                    updated = wallet_atomic_debit(uid, amount, session=session)
                    if not updated:
                        bot.send_message(message.chat.id, f"❌ Cannot remove ₹{amount:.2f} from {uid}; balance would go below zero.")
                        return
                    user_balances[uid] = float(updated["balance"])
                    persist_user(uid)
                send_log(f"💰 <b>Wallet debited</b>\nUser ID: <code>{uid}</code>\nAmount: ₹{amount:.2f}")
        bot.send_message(message.chat.id, f"✅ Removed ₹{amount:.2f} from {uid}. New: ₹{user_balances[uid]:.2f}")
    except ValueError:
        bot.send_message(message.chat.id, "Usage: /removebalance <user_id> <amount>")


@bot.message_handler(commands=['checkbalance'])
@safe_handler
def cmd_check_balance(message):
    if not is_admin(message.chat.id):
        return
    try:
        parts = message.text.split()
        uid   = int(parts[1])
        bot.send_message(message.chat.id, f"Balance of {uid}: ₹{user_balances.get(uid, 0):.2f}")
    except (ValueError, IndexError):
        bot.send_message(message.chat.id, "Usage: /checkbalance <user_id>")


@bot.message_handler(commands=['giftcode'])
@safe_handler
def cmd_giftcode(message):
    if not is_admin(message.chat.id):
        return
    try:
        _, code, amount_s = message.text.split()
        amount = float(amount_s)
        gift_codes[code] = amount
        persist_gift_code(code, amount)
        bot.send_message(message.chat.id, f"✅ Gift code '{code}' = ₹{amount:.2f}")
    except ValueError:
        bot.send_message(message.chat.id, "Usage: /giftcode <code> <amount>")


@bot.message_handler(commands=['stats'])
@safe_handler
def cmd_stats(message):
    if not is_admin(message.chat.id):
        return
    bot.send_message(message.chat.id,
        f"📊 Total Users: {len(users)} | Banned: {len(banned_users)} | Gift codes: {len(gift_codes)}"
    )


@bot.message_handler(commands=['broadcast'])
@safe_handler
def cmd_broadcast(message):
    if not is_admin(message.chat.id):
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.send_message(message.chat.id, "Usage: /broadcast <message>")
        return
    success = fail = 0
    for user in list(users):
        try:
            bot.send_message(user, args[1])
            success += 1
        except Exception:
            fail += 1
    bot.send_message(message.chat.id, f"✅ Broadcast done. Sent: {success} | Failed: {fail}")


# ─────────────────────────────────────────────────────────────
#  POLLING
# ─────────────────────────────────────────────────────────────
from http.server import BaseHTTPRequestHandler, HTTPServer

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def log_message(self, format, *args):
        pass


def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    print(f"[HEALTH] Server listening on port {port}")
    server.serve_forever()


threading.Thread(target=run_health_server, daemon=True).start()

print("🤖 Bot started Powered by RydenX...")

while True:
    try:
        bot.polling(none_stop=True, timeout=60, long_polling_timeout=60)
    except (KeyboardInterrupt, SystemExit):
        print("[SHUTDOWN] Clean shutdown requested; exiting polling loop.")
        break
    except Exception as e:
        print(f"[POLLING ERROR] {e}")
        time.sleep(15)
