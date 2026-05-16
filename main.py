import os, asyncio, time, logging, re, random, string
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import List, Optional
from logging.handlers import RotatingFileHandler

os.environ["TZ"] = "Asia/Kolkata"
try:
    time.tzset()
except:
    pass

import motor.motor_asyncio
import pyrogram.utils
from aiohttp import web
from pyrogram import Client, filters, idle
from pyrogram.enums import ParseMode, ChatMemberStatus, ChatType
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto, ChatJoinRequest, ChatMemberUpdated, BotCommand
from pyrogram.errors import FloodWait, UserNotParticipant, UserIsBlocked, InputUserDeactivated, ChatAdminRequired, RPCError
from pyrogram.filters import Filter

from settings import Settings, CATEGORIES

class Config:
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
    API_ID = 14050586
    API_HASH = "42a60d9c657b106370c79bb0a8ac560c"
    OWNER_ID = 7074383232
    PORT = int(os.environ.get("PORT", "8080"))
    DB_URI = os.environ.get("DB_URI", "")
    DB_NAME = "link"
    TG_BOT_WORKERS = 40
    DATABASE_CHANNEL = int(os.environ.get("DATABASE_CHANNEL", "-1003104736593"))

    CHAT_ID = []
    APPROVED_WELCOME = "on"
    APPROVAL_WAIT_TIME = 5
    LINK_EXPIRY = 1

    START_PIC = "https://files.catbox.moe/hijl9a.jpg"
    PICS_URL = (os.environ.get('PICS', 'https://api.aniwallpaper.workers.dev/random?type=girl')).split()

    START_MSG = "<b>Manage, reshare & control your links — smarter than ever.\n\n<blockquote>‣ Created for: <a href='https://t.me/SyntaxRealm'>˹ SyntaxRealm ˼</a></blockquote></b>"
    OWNER = "https://t.me/DshDm_bot"
    CHANNELS_TXT = "Our Channels"

    OUR_CHANNELS = [
        {"name": "main", "url": "https://t.me/SyntaxRealm"},
        {"name": "sub-main", "url": "https://t.me/Syntax_Realm"},
        {"name": "ongoing-anime", "url": "https://t.me/crunchyroll_In_Hindi_SR"},
        {"name": "backup", "url": "https://t.me/TGUrlsHub"},
        {"name": "backup-2", "url": "https://t.me/TGEliteHub"},
    ]

    D = ["😘", "👾", "🤝", "👀", "❤️‍🔥", "💘", "😍", "😇", "🕊️", "🐳", "🎉", "🏆", "🗿", "⚡", "💯", "👌", "🍾"]

    FONTS = [
        "𝖠𝖡𝖢𝖣𝖤𝖥𝖦𝖧𝖨𝖩𝖪𝖫𝖬𝖭𝖮𝖯𝖰𝖱𝖲𝖳𝖴𝖵𝖶𝖷𝖸𝖹𝖺𝖻𝖼𝖽𝖾𝖿𝗀𝗁𝗂𝗃𝗄𝗅𝗆𝗇𝗈𝗉𝗊𝗋𝗌𝗍𝗎𝗏𝗐𝗑𝗒𝗓𝟢𝟣𝟤𝟥𝟦𝟧𝟨𝟩𝟪𝟫",
        "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ0123456789",
    ]

    ADMINS = os.environ.get("ADMINS", "1679112664 7163796885 6604184902 7737229061")

    UPSTREAM_REPO = os.environ.get("UPSTREAM_REPO", "https://github.com/IamElite/LINK-V2")
    UPSTREAM_BRANCH = os.environ.get("UPSTREAM_BRANCH", "kartik")

    LINK_HASH_PREFIX = "SyntaxRealm"

Config._ORIG = {k: getattr(Config, k) for k in list(Config.__dict__) if not k.startswith("_") and not callable(getattr(Config, k))}

pyrogram.utils.MIN_CHANNEL_ID = -1009147483647
id_pattern = re.compile(r'^.\d+$')

SELECTED_FONT = random.choice(Config.FONTS)

def get_random_mix_id():
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=6))

def stylize(text):
    normal = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    trans = str.maketrans(normal, SELECTED_FONT)
    def replace_outside_tags(match):
        return match.group(0).translate(trans)
    return re.sub(r'(?<=>)[^<]+(?=<)|^[^<]+|[^>]+$', replace_outside_tags, text)

def get_random_effect():
    EFFECT_IDS = [5104841245755180586, 5159385139981059251, 5046509860389126442]
    return random.choice(EFFECT_IDS)

try:
    ADMINS = [int(x) for x in Config.ADMINS.split() if x.isdigit()]
except:
    ADMINS = [1679112664]
ADMINS.append(Config.OWNER_ID)
ADMINS = list(set(ADMINS))

LOG_FILE = "bot.log"
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt='%d-%b-%y %H:%M:%S',
    handlers=[RotatingFileHandler(LOG_FILE, maxBytes=50000000, backupCount=5), logging.StreamHandler()]
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
LOGGER = lambda name: logging.getLogger(name)

dbclient = motor.motor_asyncio.AsyncIOMotorClient(Config.DB_URI)
db = dbclient[Config.DB_NAME]
users_col = db['users']
channels_col = db['channels']
fsub_col = db['fsub_channels']
admins_col = db['admins']

settings = Settings(db['settings'])

async def add_user(user_id: int) -> bool:
    if await users_col.find_one({'_id': user_id}): return False
    await users_col.insert_one({'_id': user_id, 'created_at': datetime.now(timezone.utc)})
    return True

async def del_user(user_id: int) -> bool:
    result = await users_col.delete_one({'_id': user_id})
    return result.deleted_count > 0

async def full_userbase() -> List[int]:
    return [doc['_id'] async for doc in users_col.find()]

async def is_admin(user_id: int) -> bool:
    return bool(await admins_col.find_one({'_id': int(user_id)}))

async def add_admin(user_id: int) -> bool:
    await admins_col.update_one({'_id': user_id}, {'$set': {'_id': user_id}}, upsert=True)
    return True

async def remove_admin(user_id: int) -> bool:
    result = await admins_col.delete_one({'_id': user_id})
    return result.deleted_count > 0

async def list_admins() -> List[int]:
    return [a['_id'] async for a in admins_col.find()]

async def save_channel(channel_id: int) -> bool:
    await channels_col.update_one(
        {"channel_id": channel_id},
        {"$set": {"channel_id": channel_id, "status": "active", "created_at": datetime.now(timezone.utc)}},
        upsert=True
    )
    return True

async def get_channels() -> List[int]:
    channels = await channels_col.find({"status": "active"}).to_list(None)
    return [c["channel_id"] for c in channels if "channel_id" in c]

async def delete_channel(channel_id: int) -> bool:
    result = await channels_col.delete_one({"channel_id": channel_id})
    return result.deleted_count > 0

async def save_encoded_link(channel_id: int) -> Optional[str]:
    existing = await channels_col.find_one({"channel_id": channel_id, "encoded_link": {"$exists": True}})
    if existing:
        old = existing.get("encoded_link")
        if old and old.startswith(Config.LINK_HASH_PREFIX):
            return old
    while True:
        chars = ''.join(random.choices(string.ascii_lowercase + string.digits, k=7))
        suffix = chars
        for _ in range(4):
            if not await channels_col.find_one({"encoded_link": f"{Config.LINK_HASH_PREFIX}-{suffix}"}):
                encoded = f"{Config.LINK_HASH_PREFIX}-{suffix}"
                break
            suffix += random.choice(string.ascii_lowercase + string.digits)
        else:
            continue
        break
    await channels_col.update_one(
        {"channel_id": channel_id},
        {"$set": {"encoded_link": encoded, "status": "active", "updated_at": datetime.now(timezone.utc)}},
        upsert=True
    )
    return encoded

async def get_channel_by_encoded_link(encoded: str) -> Optional[int]:
    ch = await channels_col.find_one({"encoded_link": encoded, "status": "active"})
    return ch["channel_id"] if ch else None

async def save_invite_link(channel_id: int, link: str, is_request: bool) -> bool:
    await channels_col.update_one(
        {"channel_id": channel_id},
        {"$set": {"current_invite_link": link, "is_request_link": is_request, "invite_link_created_at": datetime.now(timezone.utc)}},
        upsert=True
    )
    return True

async def get_current_invite_link(channel_id: int) -> Optional[dict]:
    ch = await channels_col.find_one({"channel_id": channel_id, "status": "active"})
    if ch and "current_invite_link" in ch:
        return {"invite_link": ch["current_invite_link"], "is_request": ch.get("is_request_link", False)}
    return None

async def get_link_creation_time(channel_id: int):
    ch = await channels_col.find_one({"channel_id": channel_id, "status": "active"})
    return ch.get("invite_link_created_at") if ch else None

async def get_original_link(channel_id: int) -> Optional[str]:
    ch = await channels_col.find_one({"channel_id": channel_id})
    return ch.get("original_link") if ch else None

async def set_approval_off(channel_id: int, off: bool = True) -> bool:
    await channels_col.update_one({"channel_id": channel_id}, {"$set": {"approval_off": off}}, upsert=True)
    return True

async def is_approval_off(channel_id: int) -> bool:
    ch = await channels_col.find_one({"channel_id": channel_id})
    return bool(ch and ch.get("approval_off", False))

async def get_fsub_channels() -> List[int]:
    channels = await fsub_col.find({'status': 'active'}).to_list(None)
    return [c['channel_id'] for c in channels if 'channel_id' in c]

class IsOwnerOrAdmin(Filter):
    async def __call__(self, _, message):
        uid = message.from_user.id
        return uid == Config.OWNER_ID or uid in ADMINS or await is_admin(uid)

is_owner_or_admin = IsOwnerOrAdmin()

def get_readable_time(seconds: int) -> str:
    result = []
    for unit, div in [("d", 86400), ("h", 3600), ("m", 60), ("s", 1)]:
        if seconds >= div:
            result.append(f"{seconds // div}{unit}")
            seconds %= div
    return ":".join(result) or "0s"

async def revoke_invite_after_delay(client, channel_id: int, link: str, delay: int = 300):
    await asyncio.sleep(delay)
    try:
        await client.revoke_chat_invite_link(channel_id, link)
        LOGGER(__name__).info(f"Link revoked for {channel_id}")
    except RPCError as e:
        if "CHANNEL_PRIVATE" in str(e) or "CHAT_ADMIN_REQUIRED" in str(e):
            await delete_channel(channel_id)
            LOGGER(__name__).warning(f"Channel {channel_id} removed - no longer accessible")
        else:
            LOGGER(__name__).debug(f"Revoke skipped for {channel_id}: {e}")
    except:
        pass

async def auto_delete(msgs, delay: int):
    await asyncio.sleep(delay)
    if not isinstance(msgs, list): msgs = [msgs]
    for msg in msgs:
        try: await msg.delete()
        except: pass

channel_locks = defaultdict(asyncio.Lock)
chat_cache = {}

async def get_chat_cached(client, channel_id):
    if channel_id in chat_cache:
        info, ts = chat_cache[channel_id]
        if (datetime.now() - ts).total_seconds() < 300:
            return info
    info = await client.get_chat(channel_id)
    chat_cache[channel_id] = (info, datetime.now())
    return info

is_canceled = False
cancel_lock = asyncio.Lock()


class Bot(Client):
    def __init__(self):
        super().__init__(
            name="Bot",
            api_hash=Config.API_HASH,
            api_id=Config.API_ID,
            bot_token=Config.BOT_TOKEN,
            workers=Config.TG_BOT_WORKERS,
        )
        self.uptime = None

    async def start(self, *args, **kwargs):
        await super().start()
        self.uptime = datetime.now()
        self.me = await self.get_me()
        self.username = self.me.username
        self.set_parse_mode(ParseMode.HTML)
        
        try:
            await self.send_message(Config.OWNER_ID, "<b>🤖 Bot Started ✅</b>")
        except: pass

        try:
            m = await self.send_message(Config.DATABASE_CHANNEL, "<b>🤖 Bot Started ✅</b>")
            await self.delete_messages(Config.DATABASE_CHANNEL, m.id)
            LOGGER(__name__).info(f"DB channel {Config.DATABASE_CHANNEL} connected ✅")
        except Exception as e:
            LOGGER(__name__).warning(f"DB channel {Config.DATABASE_CHANNEL} connection failed: {e}")
        
        try:
            app = web.AppRunner(web.Application())
            await app.setup()
            await web.TCPSite(app, "0.0.0.0", Config.PORT).start()
        except: pass

        try:
            await self.set_bot_commands([
                BotCommand("start", "Start the bot & get links"),
                BotCommand("status", "[Admin] Bot status & ping"),
                BotCommand("stats", "[Owner] Bot uptime stats"),
                BotCommand("broadcast", "[Admin] Broadcast to all users"),
                BotCommand("cancel", "[Admin] Cancel ongoing broadcast"),
                BotCommand("channels", "[Admin] List connected channels"),
                BotCommand("links", "[Admin] Show all channel links"),
                BotCommand("addchat", "[Admin] Add a channel manually"),
                BotCommand("delchat", "[Admin] Remove a channel"),
                BotCommand("admins", "[Owner] List all admins"),
                BotCommand("addadmin", "[Owner] Add a new admin"),
                BotCommand("deladmin", "[Owner] Remove an admin"),
                BotCommand("approveoff", "[Admin] Disable auto-approve"),
                BotCommand("approveon", "[Admin] Enable auto-approve"),
                BotCommand("settings", "[Owner] Bot settings panel"),
            ])
        except: pass

        await self._load_settings()
        LOGGER(__name__).info(f"Bot @{self.username} started! ✊💦")

    async def _load_settings(self):
        await settings.load()
        for k in ["START_PIC", "START_MSG", "OWNER", "CHANNELS_TXT", "APPROVED_WELCOME", "APPROVAL_WAIT_TIME", "LINK_EXPIRY", "DATABASE_CHANNEL", "PICS_URL"]:
            v = await settings.get(k)
            if v is not None: _apply_setting(k, v)

    async def stop(self, *args):
        LOGGER(__name__).info("Bot stopped. ⛔️")
        await super().stop()

bot = Bot()

@bot.on_chat_member_updated(filters.group | filters.channel)
async def auto_add_remove_channel(client: Bot, update: ChatMemberUpdated):
    try:
        new_member = update.new_chat_member
        old_member = update.old_chat_member
        chat = update.chat
        
        if not new_member: return
        
        me = client.me if hasattr(client, "me") else await client.get_me()
        if new_member.user.id != me.id: return
        
        LOGGER(__name__).info(f"ChatMemberUpdated triggered for {chat.title} ({chat.id}) | Status: {new_member.status}")
        
        is_removed = new_member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED, ChatMemberStatus.RESTRICTED]
        was_admin = old_member and old_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
        is_demoted = was_admin and new_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
        
        if is_removed or is_demoted:
            try:
                ch_data = await channels_col.find_one({"channel_id": chat.id})
                if ch_data:
                    if "db_message_id" in ch_data:
                        try: await client.delete_messages(Config.DATABASE_CHANNEL, ch_data["db_message_id"])
                        except Exception as e: LOGGER(__name__).error(f"Failed to delete DB msg: {e}")
                    
                    await delete_channel(chat.id)
                    LOGGER(__name__).info(f"Successfully cleaned up data for {chat.title} ({chat.id}) | Reason: {'Removed/Banned' if is_removed else 'Demoted'}")
            except Exception as e:
                LOGGER(__name__).error(f"Cleanup error for {chat.id}: {e}")
            return
    
        if new_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return
        
        if update.from_user:
            adder_id = update.from_user.id
            if adder_id != Config.OWNER_ID and adder_id not in ADMINS and not await is_admin(adder_id):
                return
        
        existing = await channels_col.find_one({"channel_id": chat.id, "status": "active"})
        if existing: return
        
        try:
            await save_channel(chat.id)
            enc1 = await save_encoded_link(chat.id)
            
            link1 = f"https://t.me/{client.username}?start={enc1}"
            link2 = f"https://t.me/{client.username}?start=req_{enc1}"
            
            msg_text = f"<b>📢 New Channel Added!</b>\n\n<b>📌 Name:</b> {chat.title}\n<b>🆔 ID:</b> <code>{chat.id}</code>\n\n<b>🔗 Normal Link:</b>\n<code>{link1}</code>\n\n<b>🔗 Request Link:</b>\n<code>{link2}</code>"
            
            sent_msg = await client.send_message(Config.DATABASE_CHANNEL, msg_text)
            
            await channels_col.update_one(
                {"channel_id": chat.id},
                {"$set": {"db_message_id": sent_msg.id}}
            )
            
            LOGGER(__name__).info(f"Auto-added channel: {chat.title} ({chat.id})")
            
        except Exception as e:
            LOGGER(__name__).error(f"Auto-add failed for {chat.id}: {e}")
    
    except Exception as e:
        LOGGER(__name__).error(f"ChatMemberUpdated handler error: {e}")

@bot.on_chat_member_updated(filters.channel)
async def auto_delete_on_join(client: Bot, update: ChatMemberUpdated):
    try:
        new_member = update.new_chat_member
        if not new_member:
            return
        
        if new_member.status not in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return
        
        user_id = new_member.user.id
        channel_id = update.chat.id
        
        user_data = await users_col.find_one({"user_id": user_id})
        if user_data and "pending_join" in user_data:
            pending = user_data["pending_join"]
            if pending.get("channel_id") == channel_id and not pending.get("is_request"):
                try:
                    msgs = [pending["msg_id"]]
                    if "notice_id" in pending: msgs.append(pending["notice_id"])
                    await client.delete_messages(user_id, msgs)
                except: pass
                await users_col.update_one({"user_id": user_id}, {"$unset": {"pending_join": ""}})
    except: pass

@bot.on_message(filters.command('start') & filters.private)
async def start_cmd(client: Bot, message: Message):
    user_id = message.from_user.id
    await add_user(user_id)
    
    try: await message.react(random.choice(Config.D))
    except: pass
    
    start_type = None
    text = message.text
    if len(text) > 7:
        try:
            arg = text.split(" ", 1)[1]
            is_request = arg.startswith("req_")
            if is_request:
                arg = arg[4:]
            channel_id = await get_channel_by_encoded_link(arg)
            
            if not channel_id:
                return await message.reply(f"<b>❌ {stylize('Invalid or expired link.')}</b>")
            
            orig = await get_original_link(channel_id)
            if orig:
                btn = InlineKeyboardMarkup([[InlineKeyboardButton(stylize("• Open Link •"), url=orig)]])
                return await message.reply(f"<b>✅ {stylize('Here is your link!')}</b>", reply_markup=btn)
            
            if is_request:
                inv = await client.create_chat_invite_link(channel_id, expire_date=datetime.now() + timedelta(minutes=Config.LINK_EXPIRY), creates_join_request=True)
            else:
                inv = await client.create_chat_invite_link(channel_id, expire_date=datetime.now() + timedelta(minutes=Config.LINK_EXPIRY), member_limit=1)

            invite_link = inv.invite_link
            asyncio.create_task(revoke_invite_after_delay(client, channel_id, invite_link, Config.LINK_EXPIRY * 60))
            btn_text = stylize("✿ Request to Join ✿") if is_request else stylize("✿ Join Channel ✿")
            btn = InlineKeyboardMarkup([[InlineKeyboardButton(btn_text, url=invite_link)]])
            
            try:
                chat = await get_chat_cached(client, channel_id)
                channel_name = stylize(chat.title)
            except:
                channel_name = stylize("✿ Click below to join! ✿")
            
            try: 
                sent = await client.send_message(user_id, f"<b>{channel_name}</b>", reply_markup=btn, effect_id=get_random_effect(), protect_content=True)
            except: 
                sent = await client.send_message(user_id, f"<b>{channel_name}</b>", reply_markup=btn, protect_content=True)
            
            notice_text = f"<b><i><u>{stylize(f'This link is dead in {Config.LINK_EXPIRY} min and also this message will be deleted.')}</u></i></b>"
            try:
                sent_notice = await client.send_message(user_id, notice_text, protect_content=True)
            except:
                sent_notice = await client.send_message(user_id, notice_text)
            
            await users_col.update_one(
                {"user_id": user_id},
                {"$set": {"pending_join": {"channel_id": channel_id, "msg_id": sent.id, "notice_id": sent_notice.id, "is_request": is_request}}},
                upsert=True
            )
            
            asyncio.create_task(auto_delete([sent, sent_notice], Config.LINK_EXPIRY * 60))
            start_type = stylize("🔗 Link Start")
            
        except Exception as e:
            await client.send_message(user_id, f"<b>❌ {stylize('Error')}: {e}</b>")
    else:
        await users_col.update_one({"user_id": user_id}, {"$unset": {"pending_join": ""}})
        btns = InlineKeyboardMarkup([
            [InlineKeyboardButton(stylize("˹ Owner ˼"), url=Config.OWNER), InlineKeyboardButton(stylize("˹ Channels ˼"), callback_data="channels")],
            [InlineKeyboardButton(stylize("✘"), callback_data="close")]
        ])
        pic_url = f"{random.choice(Config.PICS_URL)}?r={get_random_mix_id()}"
        try: await client.send_photo(user_id, pic_url, caption=f"<b>{stylize(Config.START_MSG)}</b>", reply_markup=btns, effect_id=get_random_effect())
        except:
            try: await client.send_photo(user_id, Config.START_PIC, caption=f"<b>{stylize(Config.START_MSG)}</b>", reply_markup=btns)
            except: await client.send_message(user_id, f"<b>{stylize(Config.START_MSG)}</b>", reply_markup=btns)
        start_type = stylize("📩 Simple Start")
    
    if start_type:
        try:
            user = message.from_user
            await client.send_message(Config.DATABASE_CHANNEL, f"<b>{start_type}</b>\n👤 {user.mention} | <code>{user_id}</code>")
        except: pass

@bot.on_message(filters.command('status') & filters.private & is_owner_or_admin)
async def status_cmd(client: Bot, message: Message):
    t1 = time.time()
    msg = await message.reply(f"<b>{stylize('Processing...')}</b>")
    ping = (time.time() - t1) * 1000
    users = await full_userbase()
    uptime = get_readable_time(int((datetime.now() - client.uptime).total_seconds()))
    db_channels = await channels_col.count_documents({"status": "active"})
    try:
        dialogs = [d async for d in client.get_dialogs()]
        total_chats = len([d for d in dialogs if d.chat.type in (ChatType.CHANNEL, ChatType.SUPERGROUP, ChatType.GROUP)])
    except:
        total_chats = 0
    await msg.edit(f"<b>👥 {stylize('Users')}: {len(users)}\n📡 {stylize('Channels')}: {db_channels}\n💬 {stylize('Total Chats')}: {total_chats}\n⏱ {stylize('Uptime')}: {uptime}\n📶 {stylize('Ping')}: {ping:.2f}ms</b>")

@bot.on_message(filters.command('stats') & filters.user(Config.OWNER_ID))
async def stats_cmd(client: Bot, message: Message):
    uptime = get_readable_time(int((datetime.now() - client.uptime).total_seconds()))
    await message.reply(f"<b>{stylize('BOT UPTIME')}:</b> {uptime}")

@bot.on_message(filters.command('broadcast') & filters.private & is_owner_or_admin)
async def broadcast_cmd(client: Bot, message: Message):
    global is_canceled
    if not message.reply_to_message:
        return await message.reply(f"<b>{stylize('Reply to a message to broadcast.')}</b>")
    
    async with cancel_lock:
        is_canceled = False
    
    users = await full_userbase()
    total = len(users)
    msg = await message.reply(f"<b>📣 {stylize('Broadcasting to')} {total} {stylize('users...')}</b>")
    
    success = blocked = failed = 0
    for uid in users:
        async with cancel_lock:
            if is_canceled:
                return await msg.edit(f"<b>❌ {stylize('Broadcast cancelled!')}</b>")
        try:
            await message.reply_to_message.copy(uid)
            success += 1
        except UserIsBlocked:
            await del_user(uid)
            blocked += 1
        except InputUserDeactivated:
            await del_user(uid)
            blocked += 1
        except FloodWait as e:
            await asyncio.sleep(e.x)
            try:
                await message.reply_to_message.copy(uid)
                success += 1
            except:
                failed += 1
        except:
            failed += 1
    
    await msg.edit(f"<b>✅ {stylize('Broadcast Complete!')}\n\n• {stylize('Success')}: {success}\n• {stylize('Blocked')}: {blocked}\n• {stylize('Failed')}: {failed}</b>")

@bot.on_message(filters.command('cancel') & filters.private & is_owner_or_admin)
async def cancel_cmd(client: Bot, message: Message):
    global is_canceled
    async with cancel_lock:
        is_canceled = True
    await message.reply(f"<b>🛑 {stylize('Broadcast will be cancelled.')}</b>")


@bot.on_message(filters.command(['addchat', 'addch', "addchannle", "addchnnl"]) & is_owner_or_admin)
async def addchat_cmd(client: Bot, message: Message):
    try:
        channel_id = int(message.command[1])
    except:
        return await message.reply(f"<b>{stylize('Usage')}: /addchat {{channel_id}}</b>")
    
    try:
        chat = await client.get_chat(channel_id)
        await save_channel(channel_id)
        enc1 = await save_encoded_link(channel_id)
        
        link1 = f"https://t.me/{client.username}?start={enc1}"
        link2 = f"https://t.me/{client.username}?start=req_{enc1}"
        
        await message.reply(f"<b>✅ {stylize(chat.title)} {stylize('added!')}</b>\n\n<b>{stylize('Normal')}:</b> <code>{link1}</code>\n<b>{stylize('Request')}:</b> <code>{link2}</code>")
    except Exception as e:
        await message.reply(f"<b>❌ {stylize('Error')}: {e}</b>")

@bot.on_message(filters.command(['delchat', 'delch']) & is_owner_or_admin)
async def delchat_cmd(client: Bot, message: Message):
    try:
        channel_id = int(message.command[1])
        await delete_channel(channel_id)
        await message.reply(f"<b>✅ {stylize('Channel')} {channel_id} {stylize('removed.')}</b>")
    except:
        await message.reply(f"<b>{stylize('Usage')}: /delchat {{channel_id}}</b>")

@bot.on_message(filters.command('channels') & is_owner_or_admin)
async def channels_cmd(client: Bot, message: Message):
    channels = await get_channels()
    if not channels:
        return await message.reply(f"<b>{stylize('No channels available.')}</b>")
    
    text = f"<b>📺 {stylize('Connected Channels')}:</b>\n\n"
    for i, cid in enumerate(channels[:20], 1):
        try:
            chat = await get_chat_cached(client, cid)
            text += f"{i}. {stylize(chat.title)} (<code>{cid}</code>)\n"
        except:
            text += f"{i}. {stylize('Unknown')} (<code>{cid}</code>)\n"
    
    await message.reply(text)

@bot.on_message(filters.command('links') & is_owner_or_admin)
@bot.on_callback_query(filters.regex(r"^links_page_"))
async def links_handler(client: Bot, update):
    is_cb = isinstance(update, CallbackQuery)
    page = int(update.data.split("_")[-1]) if is_cb else 0
    
    channels = await get_channels()
    if not channels:
        msg = f"<b>{stylize('No channels.')}</b>"
        return await (update.answer(msg, show_alert=True) if is_cb else update.reply(msg))

    per_page = 5
    start, end = page * per_page, (page + 1) * per_page
    total_pages = (len(channels) + per_page - 1) // per_page
    
    text = f"<b>🔗 {stylize(f'All Links (Page {page+1}/{total_pages})')}</b>\n\n"
    for i, cid in enumerate(channels[start:end], start + 1):
        try:
            chat = await get_chat_cached(client, cid)
            e1 = await save_encoded_link(cid)
            l1 = f"https://t.me/{client.username}?start={e1}"
            l2 = f"https://t.me/{client.username}?start=req_{e1}"
            text += f"<b>{i}. {stylize(chat.title)}</b>\n• {stylize('Normal')}: <code>{l1}</code>\n• {stylize('Request')}: <code>{l2}</code>\n\n"
        except: continue
        
    btns = []
    if page > 0: btns.append(InlineKeyboardButton(stylize("« Back"), callback_data=f"links_page_{page-1}"))
    if end < len(channels): btns.append(InlineKeyboardButton(stylize("Next »"), callback_data=f"links_page_{page+1}"))
    
    rows = [btns] if btns else []
    rows.append([InlineKeyboardButton(stylize("✘"), callback_data="close")])
    kb = InlineKeyboardMarkup(rows)
    try:
        if is_cb: await update.edit_message_text(text, reply_markup=kb)
        else: await update.reply(text, reply_markup=kb)
    except: pass

@bot.on_message(filters.command('addadmin') & filters.user(Config.OWNER_ID))
async def addadmin_cmd(client, message: Message):
    try:
        uid = int(message.command[1])
        await add_admin(uid)
        await message.reply(f"<b>✅ {uid} {stylize('is now admin.')}</b>")
    except:
        await message.reply(f"<b>{stylize('Usage')}: /addadmin {{user_id}}</b>")

@bot.on_message(filters.command('deladmin') & filters.user(Config.OWNER_ID))
async def deladmin_cmd(client, message: Message):
    try:
        uid = int(message.command[1])
        await remove_admin(uid)
        await message.reply(f"<b>✅ {uid} {stylize('removed from admins.')}</b>")
    except:
        await message.reply(f"<b>{stylize('Usage')}: /deladmin {{user_id}}</b>")

@bot.on_message(filters.command('admins') & filters.user(Config.OWNER_ID))
async def admins_cmd(client, message: Message):
    admins = await list_admins()
    text = f"<b>👑 {stylize('Admins')}:</b>\n" + "\n".join([f"• <code>{a}</code>" for a in admins]) if admins else f"<b>{stylize('No admins.')}</b>"
    await message.reply(text)

@bot.on_message(filters.command('approveoff') & is_owner_or_admin)
async def approveoff_cmd(client, message: Message):
    try:
        cid = int(message.command[1])
        await set_approval_off(cid, True)
        await message.reply(f"<b>✅ {stylize('Auto-approve OFF for')} {cid}</b>")
    except:
        await message.reply(f"<b>{stylize('Usage')}: /approveoff {{channel_id}}</b>")

@bot.on_message(filters.command('approveon') & is_owner_or_admin)
async def approveon_cmd(client, message: Message):
    try:
        cid = int(message.command[1])
        await set_approval_off(cid, False)
        await message.reply(f"<b>✅ {stylize('Auto-approve ON for')} {cid}</b>")
    except:
        await message.reply(f"<b>{stylize('Usage')}: /approveon {{channel_id}}</b>")

@bot.on_chat_join_request((filters.group | filters.channel) & filters.chat(Config.CHAT_ID) if Config.CHAT_ID else (filters.group | filters.channel))
async def auto_approve(client, req: ChatJoinRequest):
    chat = req.chat
    user = req.from_user
    
    if await is_approval_off(chat.id):
        return
    
    await asyncio.sleep(Config.APPROVAL_WAIT_TIME)
    
    try:
        await client.approve_chat_join_request(chat.id, user.id)
        
        user_data = await users_col.find_one({"user_id": user.id})
        if user_data and "pending_join" in user_data:
            pending = user_data["pending_join"]
            if pending.get("channel_id") == chat.id:
                try:
                    msgs = [pending["msg_id"]]
                    if "notice_id" in pending: msgs.append(pending["notice_id"])
                    await client.delete_messages(user.id, msgs)
                except: pass
                await users_col.update_one({"user_id": user.id}, {"$unset": {"pending_join": ""}})
        
        if Config.APPROVED_WELCOME == "on":
            try:
                msg_text = f"{stylize('» Hello')} {user.mention}.\n\n{stylize('Your request to join')} <b>{stylize(chat.title)}</b> {stylize('has been approved!')}"
                btn = InlineKeyboardMarkup([[InlineKeyboardButton(stylize("Visit For More"), url="https://t.me/SyntaxRealm")]])
                await client.send_message(user.id, msg_text, reply_markup=btn)
            except: pass
    except: pass

@bot.on_callback_query()
async def callback_handler(client: Bot, query: CallbackQuery):
    data = query.data
    
    if data == "close":
        await query.message.delete()
    
    elif data == "channels":
        btns = []
        for chnl in Config.OUR_CHANNELS:
            name, url = chnl.get("name"), chnl.get("url")
            if name and url and url != "https://t.me/":
                btns.append([InlineKeyboardButton(stylize("• " + name + " •"), url=url)])
        
        btns.append([InlineKeyboardButton(stylize("« Back •"), callback_data="start")])
        
        await query.edit_message_media(
            InputMediaPhoto(Config.START_PIC, f"<b>›› {stylize(Config.CHANNELS_TXT)}</b>"),
            reply_markup=InlineKeyboardMarkup(btns)
        )

    elif data == "start":
        btns = InlineKeyboardMarkup([
            [InlineKeyboardButton(stylize("˹ Owner ˼"), url=Config.OWNER), InlineKeyboardButton(stylize("˹ Channels ˼"), callback_data="channels")],
            [InlineKeyboardButton(stylize("✘"), callback_data="close")]
        ])
        try:
            await query.edit_message_media(InputMediaPhoto(Config.START_PIC, f"<b>{stylize(Config.START_MSG)}</b>"), reply_markup=btns)
        except:
            await query.edit_message_text(f"<b>{stylize(Config.START_MSG)}</b>", reply_markup=btns)

    elif data.startswith("settings"):
        await settings_callback(client, query)

settings_awaiting = {}

async def _show_category(client, chat_id, msg_id, cat):
    if cat not in CATEGORIES: return
    cat_data = CATEGORIES[cat]
    text = f"<b>{cat_data['name']}</b>\n\n"
    btns = []
    for key, meta in cat_data["keys"].items():
        cur = await settings.get(key)
        if cur is None:
            cur = _current_val(key)
        if meta.get("secret") and cur != "-":
            cur = cur[:6] + "..."
        label = meta["label"]
        text += f"<b>{label}</b>: <code>{cur}</code>\n"
        if meta["type"] == "toggle":
            btns.append([InlineKeyboardButton(f"🔄 {label}", callback_data=f"settings_toggle_{cat}_{key}")])
        else:
            btns.append([InlineKeyboardButton(f"✏️ {label}", callback_data=f"settings_edit_{cat}_{key}")])
        btns.append([InlineKeyboardButton(f"↩️ Reset", callback_data=f"settings_reset_{cat}_{key}")])
    btns.append([InlineKeyboardButton("« Back", callback_data="settings")])
    btns.append([InlineKeyboardButton("✘", callback_data="close")])
    try:
        await client.edit_message_text(chat_id, msg_id, text, reply_markup=InlineKeyboardMarkup(btns))
    except:
        pass

async def settings_callback(client, query):
    data = query.data
    if data == "settings":
        text = "<b>⚙️ Settings Panel</b>\n\nSelect a category to manage:"
        btns = []
        for cat_key, cat in CATEGORIES.items():
            btns.append([InlineKeyboardButton(cat["name"], callback_data=f"settings_cat_{cat_key}")])
        btns.append([InlineKeyboardButton("✘", callback_data="close")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(btns))

    elif data.startswith("settings_cat_"):
        cat = data.replace("settings_cat_", "")
        await _show_category(client, query.message.chat.id, query.message.id, cat)

    elif data.startswith("settings_toggle_"):
        suffix = data[data.find("_toggle_") + 8:]
        cat = next((c for c in CATEGORIES if suffix.startswith(c + "_")), None)
        if not cat: return
        key = suffix[len(cat)+1:]
        cur = await settings.get(key, "off")
        new = "off" if cur == "on" else "on"
        await settings.set(key, new)
        _apply_setting(key, new)
        await query.answer(f"✅ {key} -> {new}", show_alert=False)
        await _show_category(client, query.message.chat.id, query.message.id, cat)

    elif data.startswith("settings_reset_"):
        suffix = data[data.find("_reset_") + 7:]
        cat = next((c for c in CATEGORIES if suffix.startswith(c + "_")), None)
        if not cat: return
        key = suffix[len(cat)+1:]
        await settings.delete(key)
        _reload_default(key)
        await query.answer(f"↩️ {key} reset to default!", show_alert=False)
        await _show_category(client, query.message.chat.id, query.message.id, cat)

    elif data.startswith("settings_edit_"):
        suffix = data[data.find("_edit_") + 6:]
        cat = next((c for c in CATEGORIES if suffix.startswith(c + "_")), None)
        if not cat: return
        key = suffix[len(cat)+1:]
        settings_awaiting[query.from_user.id] = {"key": key, "cat": cat, "msg_id": query.message.id}
        await query.message.reply(f"<b>✏️ Send new value for</b> <code>{key}</code>\n/skip to keep current /cancel to abort")
        await query.answer()

@bot.on_message(filters.private & filters.text & filters.create(lambda _, __, m: m.from_user.id in settings_awaiting))
async def settings_input(client, message):
    uid = message.from_user.id
    if uid not in settings_awaiting: return
    sd = settings_awaiting[uid]
    key = sd["key"]
    cat = sd.get("cat")
    msg_id = sd.get("msg_id")
    val = message.text.strip()
    await settings.set(key, val)
    _apply_setting(key, val)
    del settings_awaiting[uid]
    try:
        await message.reply(f"<b>✅</b> <code>{key}</code> updated!")
    except:
        await message.reply(f"<b>✅</b> <code>{key}</code> updated!")
    if cat and msg_id:
        try:
            await _show_category(client, message.chat.id, msg_id, cat)
        except:
            pass

@bot.on_message(filters.command("skip") & filters.private)
async def settings_skip(client, message):
    uid = message.from_user.id
    settings_awaiting.pop(uid, None)
    await message.reply("<b>⏭️ Skipped.</b>")

@bot.on_message(filters.command("cancel") & filters.private & filters.create(lambda _, __, m: m.from_user.id in settings_awaiting), group=-1)
async def settings_abort(client, message):
    uid = message.from_user.id
    settings_awaiting.pop(uid, None)
    await message.reply("<b>🚫 Aborted.</b>")

@bot.on_message(filters.command("settings") & filters.private & filters.user(Config.OWNER_ID))
async def settings_cmd(client, message):
    await settings.load()
    text = "<b>⚙️ Settings Panel</b>\n\nSelect a category to manage:"
    btns = []
    for cat_key, cat in CATEGORIES.items():
        btns.append([InlineKeyboardButton(cat["name"], callback_data=f"settings_cat_{cat_key}")])
    btns.append([InlineKeyboardButton("✘", callback_data="close")])
    await message.reply(text, reply_markup=InlineKeyboardMarkup(btns))

def _current_val(key):
    v = getattr(Config, key, None)
    if v is None or v == "" or v == []:
        return "-"
    if isinstance(v, list):
        return " ".join(str(x) if not isinstance(x, dict) else x.get("url", str(x)) for x in v)
    if isinstance(v, int):
        return str(v)
    return str(v)

def _apply_setting(key, val):
    if key == "PICS_URL":
        if isinstance(val, list):
            setattr(Config, key, val)
        else:
            setattr(Config, key, str(val).split() if " " in str(val) else [str(val)])
    elif key in ("APPROVAL_WAIT_TIME", "LINK_EXPIRY", "DATABASE_CHANNEL", "API_ID", "OWNER_ID", "PORT"):
        setattr(Config, key, int(val) if not isinstance(val, int) else val)
    elif key in ("TG_BOT_WORKERS",):
        setattr(Config, key, int(val) if not isinstance(val, int) else val)
    else:
        setattr(Config, key, val)

def _reload_default(key):
    if key in Config._ORIG:
        _apply_setting(key, Config._ORIG[key])

async def start_bot():
    started = False
    try:
        await bot.start()
        started = True
        await idle()
    except Exception as e:
        LOGGER(__name__).error(f"Startup Error: {e}")
    finally:
        if started:
            await bot.stop()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_bot())
