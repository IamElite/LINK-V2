import os, asyncio, base64, time, logging, re, random
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Optional
from logging.handlers import RotatingFileHandler

import motor.motor_asyncio
import pyrogram.utils
from aiohttp import web
from pyrogram import Client, filters, idle
from pyrogram.enums import ParseMode, ChatMemberStatus
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto, ChatJoinRequest, ChatMemberUpdated
from pyrogram.errors import FloodWait, UserNotParticipant, UserIsBlocked, InputUserDeactivated, ChatAdminRequired, RPCError
from pyrogram.filters import Filter

pyrogram.utils.MIN_CHANNEL_ID = -1009147483647
id_pattern = re.compile(r'^.\d+$')

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
API_ID = 14050586
API_HASH = "42a60d9c657b106370c79bb0a8ac560c"
OWNER_ID = 7074383232
PORT = int(os.environ.get("PORT", "8080"))
DB_URI = os.environ.get("DB_URI", "")
DB_NAME = "link"
TG_BOT_WORKERS = 40
DATABASE_CHANNEL = -1003104736593

CHAT_ID = []
APPROVED_WELCOME = "on"
APPROVAL_WAIT_TIME = 5
LINK_EXPIRY = 1

START_PIC = "https://files.catbox.moe/yq2msx.jpg"
START_MSG = "<b>𝗐𝖾𝗅𝖼𝗈𝗆𝖾 𝗍𝗈 𝗍𝗁𝖾 𝖺𝖽𝗏𝖺𝗇𝖼𝖾𝖽 𝗅𝗂𝗇𝗄𝗌 𝗌𝗁𝖺𝗋𝗂𝗇𝗀 𝖻𝗈𝗍.</b>"
ABOUT_TXT = "<b>›› 𝖬𝖺𝗂𝗇𝗍𝖺𝗂𝗇𝖾𝖽 𝖻𝗒: @DshDm_bot</b>"
CHANNELS_TXT = "<b>›› 𝖮𝗎𝗋 𝖢𝗁𝖺𝗇𝗇𝖾𝗅𝗌</b>"

D = ["😘", "👾", "🤝", "👀", "❤️‍🔥", "💘", "😍", "😇", "🕊️", "🐳", "🎉", "🏆", "🗿", "⚡", "💯", "👌", "🍾"]

def stylize(text):
    normal = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    styled = "𝖠𝖡𝖢𝖣𝖤𝖥𝖦𝖧𝖨𝖩𝖪𝖫𝖬𝖭𝖮𝖯𝖰𝖱𝖲𝖳𝖴𝖵𝖶𝖷𝖸𝖹𝖺𝖻𝖼𝖽𝖾𝖿𝗀𝗁𝗂𝗃𝗄𝗅𝗆𝗇𝗈𝗉𝗊𝗋𝗌𝗍𝗎𝗏𝗐𝗑𝗒𝗓𝟢𝟣𝟤𝟥𝟦𝟧𝟨𝟩𝟪𝟫"
    return text.translate(str.maketrans(normal, styled))

def get_random_effect():
    EFFECT_IDS = [5104841245755180586, 5159385139981059251, 5046509860389126442]
    return random.choice(EFFECT_IDS)

try:
    ADMINS = [int(x) for x in os.environ.get("ADMINS", "1679112664 7163796885 6604184902 7737229061").split() if x.isdigit()]
except:
    ADMINS = [1679112664]
ADMINS.append(OWNER_ID)
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

dbclient = motor.motor_asyncio.AsyncIOMotorClient(DB_URI)
db = dbclient[DB_NAME]
users_col = db['users']
channels_col = db['channels']
fsub_col = db['fsub_channels']
admins_col = db['admins']

async def add_user(user_id: int) -> bool:
    if await users_col.find_one({'_id': user_id}): return False
    await users_col.insert_one({'_id': user_id, 'created_at': datetime.utcnow()})
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
        {"$set": {"channel_id": channel_id, "status": "active", "created_at": datetime.utcnow()}},
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
    encoded = base64.urlsafe_b64encode(str(channel_id).encode()).decode()
    await channels_col.update_one(
        {"channel_id": channel_id},
        {"$set": {"encoded_link": encoded, "status": "active", "updated_at": datetime.utcnow()}},
        upsert=True
    )
    return encoded

async def save_encoded_link2(channel_id: int, encoded: str) -> Optional[str]:
    await channels_col.update_one(
        {"channel_id": channel_id},
        {"$set": {"req_encoded_link": encoded, "status": "active"}},
        upsert=True
    )
    return encoded

async def get_channel_by_encoded_link(encoded: str) -> Optional[int]:
    ch = await channels_col.find_one({"encoded_link": encoded, "status": "active"})
    return ch["channel_id"] if ch else None

async def get_channel_by_encoded_link2(encoded: str) -> Optional[int]:
    ch = await channels_col.find_one({"req_encoded_link": encoded, "status": "active"})
    return ch["channel_id"] if ch else None

async def save_invite_link(channel_id: int, link: str, is_request: bool) -> bool:
    await channels_col.update_one(
        {"channel_id": channel_id},
        {"$set": {"current_invite_link": link, "is_request_link": is_request, "invite_link_created_at": datetime.utcnow()}},
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
        return uid == OWNER_ID or uid in ADMINS or await is_admin(uid)

is_owner_or_admin = IsOwnerOrAdmin()

async def encode(string: str) -> str:
    return base64.urlsafe_b64encode(string.encode()).decode().strip("=")

async def decode(b64: str) -> str:
    b64 = b64.strip("=")
    return base64.urlsafe_b64decode((b64 + "=" * (-len(b64) % 4)).encode()).decode()

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
            api_hash=API_HASH,
            api_id=API_ID,
            bot_token=BOT_TOKEN,
            workers=TG_BOT_WORKERS,
        )
        self.uptime = None

    async def start(self, *args, **kwargs):
        await super().start()
        self.uptime = datetime.now()
        self.me = await self.get_me()
        self.username = self.me.username
        self.set_parse_mode(ParseMode.HTML)
        
        try:
            await self.send_message(OWNER_ID, "<b>🤖 Bot Started ✅</b>")
        except: pass
        
        try:
            app = web.AppRunner(web.Application())
            await app.setup()
            await web.TCPSite(app, "0.0.0.0", PORT).start()
        except: pass
        
        LOGGER(__name__).info(f"Bot @{self.username} started!")

    async def stop(self, *args):
        await super().stop()
        LOGGER(__name__).info("Bot stopped.")

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
                        try: await client.delete_messages(DATABASE_CHANNEL, ch_data["db_message_id"])
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
            if adder_id != OWNER_ID and adder_id not in ADMINS and not await is_admin(adder_id):
                return
        
        existing = await channels_col.find_one({"channel_id": chat.id, "status": "active"})
        if existing: return
        
        try:
            await save_channel(chat.id)
            enc1 = await save_encoded_link(chat.id)
            enc2 = await encode(str(chat.id))
            await save_encoded_link2(chat.id, enc2)
            
            link1 = f"https://t.me/{client.username}?start={enc1}"
            link2 = f"https://t.me/{client.username}?start=req_{enc2}"
            
            msg_text = f"<b>📢 New Channel Added!</b>\n\n<b>📌 Name:</b> {chat.title}\n<b>🆔 ID:</b> <code>{chat.id}</code>\n\n<b>🔗 Normal Link:</b>\n<code>{link1}</code>\n\n<b>🔗 Request Link:</b>\n<code>{link2}</code>"
            
            sent_msg = await client.send_message(DATABASE_CHANNEL, msg_text)
            
            await channels_col.update_one(
                {"channel_id": chat.id},
                {"$set": {"db_message_id": sent_msg.id}}
            )
            
            LOGGER(__name__).info(f"Auto-added channel: {chat.title} ({chat.id})")
            
        except Exception as e:
            LOGGER(__name__).error(f"Auto-add failed for {channel_id}: {e}")
    
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
    
    try: await message.react(random.choice(D))
    except: pass
    
    start_type = None
    text = message.text
    if len(text) > 7:
        try:
            arg = text.split(" ", 1)[1]
            is_request = arg.startswith("req_")
            if is_request:
                arg = arg[4:]
                channel_id = await get_channel_by_encoded_link2(arg)
            else:
                channel_id = await get_channel_by_encoded_link(arg)
            
            if not channel_id:
                return await message.reply(f"<b>❌ {stylize('Invalid or expired link.')}</b>")
            
            orig = await get_original_link(channel_id)
            if orig:
                btn = InlineKeyboardMarkup([[InlineKeyboardButton(stylize("• Open Link •"), url=orig)]])
                return await message.reply(f"<b>✅ {stylize('Here is your link!')}</b>", reply_markup=btn)
            
            if is_request:
                inv = await client.create_chat_invite_link(channel_id, expire_date=datetime.now() + timedelta(minutes=LINK_EXPIRY), creates_join_request=True)
            else:
                inv = await client.create_chat_invite_link(channel_id, expire_date=datetime.now() + timedelta(minutes=LINK_EXPIRY), member_limit=1)
            
            invite_link = inv.invite_link
            btn_text = stylize("✿ Request to Join ✿") if is_request else stylize("✿ Join Channel ✿")
            btn = InlineKeyboardMarkup([[InlineKeyboardButton(btn_text, url=invite_link)]])
            
            try:
                chat = await get_chat_cached(client, channel_id)
                channel_name = stylize(chat.title)
            except:
                channel_name = stylize("Click below to join!")
            
            try: 
                sent = await client.send_message(user_id, f"<b>{channel_name}</b>", reply_markup=btn, effect_id=get_random_effect(), protect_content=True)
            except: 
                sent = await client.send_message(user_id, f"<b>{channel_name}</b>", reply_markup=btn, protect_content=True)
            
            notice_text = f"<b><i>{stylize(f'This link will be dead in {LINK_EXPIRY} min and this message will be deleted.')}</i></b>"
            try:
                sent_notice = await client.send_message(user_id, notice_text, protect_content=True)
            except:
                sent_notice = await client.send_message(user_id, notice_text)
            
            await users_col.update_one(
                {"user_id": user_id},
                {"$set": {"pending_join": {"channel_id": channel_id, "msg_id": sent.id, "notice_id": sent_notice.id, "is_request": is_request}}},
                upsert=True
            )
            
            asyncio.create_task(auto_delete([sent, sent_notice], LINK_EXPIRY * 60))
            start_type = stylize("🔗 Link Start")
            
        except Exception as e:
            await client.send_message(user_id, f"<b>❌ {stylize('Error')}: {e}</b>")
    else:
        await users_col.update_one({"user_id": user_id}, {"$unset": {"pending_join": ""}})
        btns = InlineKeyboardMarkup([
            [InlineKeyboardButton(stylize("• About"), callback_data="about"), InlineKeyboardButton(stylize("• Channels"), callback_data="channels")],
            [InlineKeyboardButton(stylize("• Close •"), callback_data="close")]
        ])
        try: await client.send_photo(user_id, START_PIC, caption=START_MSG, reply_markup=btns, effect_id=get_random_effect())
        except: await client.send_photo(user_id, START_PIC, caption=START_MSG, reply_markup=btns)
        start_type = stylize("📩 Simple Start")
    
    if start_type:
        try:
            user = message.from_user
            await client.send_message(DATABASE_CHANNEL, f"<b>{start_type}</b>\n👤 {user.mention} | <code>{user_id}</code>")
        except: pass

@bot.on_message(filters.command('status') & filters.private & is_owner_or_admin)
async def status_cmd(client: Bot, message: Message):
    t1 = time.time()
    msg = await message.reply(f"<b>{stylize('Processing...')}</b>")
    ping = (time.time() - t1) * 1000
    users = await full_userbase()
    uptime = get_readable_time(int((datetime.now() - client.uptime).total_seconds()))
    await msg.edit(f"<b>👥 {stylize('Users')}: {len(users)}\n⏱ {stylize('Uptime')}: {uptime}\n📶 {stylize('Ping')}: {ping:.2f}ms</b>")

@bot.on_message(filters.command('stats') & filters.user(OWNER_ID))
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

PAGE_SIZE = 6

@bot.on_message(filters.command(['addchat', 'addch']) & is_owner_or_admin)
async def addchat_cmd(client: Bot, message: Message):
    try:
        channel_id = int(message.command[1])
    except:
        return await message.reply(f"<b>{stylize('Usage')}: /addchat {{channel_id}}</b>")
    
    try:
        chat = await client.get_chat(channel_id)
        await save_channel(channel_id)
        enc1 = await save_encoded_link(channel_id)
        enc2 = await encode(str(channel_id))
        await save_encoded_link2(channel_id, enc2)
        
        link1 = f"https://t.me/{client.username}?start={enc1}"
        link2 = f"https://t.me/{client.username}?start=req_{enc2}"
        
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
            e1, e2 = await save_encoded_link(cid), await encode(str(cid))
            await save_encoded_link2(cid, e2)
            l1, l2 = f"https://t.me/{client.username}?start={e1}", f"https://t.me/{client.username}?start=req_{e2}"
            text += f"<b>{i}. {stylize(chat.title)}</b>\n• {stylize('Normal')}: <code>{l1}</code>\n• {stylize('Request')}: <code>{l2}</code>\n\n"
        except: continue
        
    btns = []
    if page > 0: btns.append(InlineKeyboardButton(stylize("« Back"), callback_data=f"links_page_{page-1}"))
    if end < len(channels): btns.append(InlineKeyboardButton(stylize("Next »"), callback_data=f"links_page_{page+1}"))
    
    rows = [btns] if btns else []
    rows.append([InlineKeyboardButton(stylize("• Close •"), callback_data="close")])
    kb = InlineKeyboardMarkup(rows)
    try:
        if is_cb: await update.edit_message_text(text, reply_markup=kb)
        else: await update.reply(text, reply_markup=kb)
    except: pass

@bot.on_message(filters.command('addadmin') & filters.user(OWNER_ID))
async def addadmin_cmd(client, message: Message):
    try:
        uid = int(message.command[1])
        await add_admin(uid)
        await message.reply(f"<b>✅ {uid} {stylize('is now admin.')}</b>")
    except:
        await message.reply(f"<b>{stylize('Usage')}: /addadmin {{user_id}}</b>")

@bot.on_message(filters.command('deladmin') & filters.user(OWNER_ID))
async def deladmin_cmd(client, message: Message):
    try:
        uid = int(message.command[1])
        await remove_admin(uid)
        await message.reply(f"<b>✅ {uid} {stylize('removed from admins.')}</b>")
    except:
        await message.reply(f"<b>{stylize('Usage')}: /deladmin {{user_id}}</b>")

@bot.on_message(filters.command('admins') & filters.user(OWNER_ID))
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

@bot.on_chat_join_request((filters.group | filters.channel) & filters.chat(CHAT_ID) if CHAT_ID else (filters.group | filters.channel))
async def auto_approve(client, req: ChatJoinRequest):
    chat = req.chat
    user = req.from_user
    
    if await is_approval_off(chat.id):
        return
    
    await asyncio.sleep(APPROVAL_WAIT_TIME)
    
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
        
        if APPROVED_WELCOME == "on":
            try:
                msg_text = f"{stylize('Hello')} ᚐ⎯‌ {user.mention}\n\n{stylize('Your request to join')} <b>{stylize(chat.title)}</b> {stylize('has been approved!')}"
                btn = InlineKeyboardMarkup([[InlineKeyboardButton(stylize("Visit For More"), url="https://t.me/SyntaxRealm")]])
                await client.send_message(user.id, msg_text, reply_markup=btn)
            except: pass
    except: pass

@bot.on_callback_query()
async def callback_handler(client: Bot, query: CallbackQuery):
    data = query.data
    
    if data == "close":
        await query.message.delete()
    
    elif data == "about":
        await query.edit_message_media(
            InputMediaPhoto(START_PIC, ABOUT_TXT),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(stylize("• Back"), callback_data="start")]])
        )
    
    elif data == "channels":
        await query.edit_message_media(
            InputMediaPhoto(START_PIC, CHANNELS_TXT),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(stylize("• Back"), callback_data="start")]])
        )
    
    elif data == "start":
        btns = InlineKeyboardMarkup([
            [InlineKeyboardButton(stylize("• About"), callback_data="about"), InlineKeyboardButton(stylize("• Channels"), callback_data="channels")],
            [InlineKeyboardButton(stylize("• Close •"), callback_data="close")]
        ])
        try:
            await query.edit_message_media(InputMediaPhoto(START_PIC, START_MSG), reply_markup=btns)
        except:
            await query.edit_message_text(START_MSG, reply_markup=btns)

async def start_bot():
    try:
        await bot.start()
        await idle()
    except Exception as e:
        LOGGER(__name__).error(f"Startup Error: {e}")
    finally:
        await bot.stop()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(start_bot())
