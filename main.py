import os, asyncio, base64, time, logging, re
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

# ═══════════════════════════════════════════════════════════════════════════════
#                               CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

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

START_PIC = "https://telegra.ph/file/f3d3aff9ec422158feb05-d2180e3665e0ac4d32.jpg"
START_MSG = "<b>ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜᴇ ᴀᴅᴠᴀɴᴄᴇᴅ ʟɪɴᴋs sʜᴀʀɪɴɢ ʙᴏᴛ.</b>"
ABOUT_TXT = "<b>›› Maintained by: @DshDm_bot</b>"
CHANNELS_TXT = "<b>›› Our Channels</b>"

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

# ═══════════════════════════════════════════════════════════════════════════════
#                               DATABASE
# ═══════════════════════════════════════════════════════════════════════════════

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

# ═══════════════════════════════════════════════════════════════════════════════
#                               HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

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
        print(f"Link revoked for {channel_id}")
    except Exception as e:
        print(f"Revoke failed for {channel_id}: {e}")

async def auto_delete(msg, delay: int):
    await asyncio.sleep(delay)
    try: await msg.delete()
    except: pass

# Cache
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

# Broadcast state
is_canceled = False
cancel_lock = asyncio.Lock()

# ═══════════════════════════════════════════════════════════════════════════════
#                               BOT CLASS
# ═══════════════════════════════════════════════════════════════════════════════

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
        me = await self.get_me()
        self.username = me.username
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

# ═══════════════════════════════════════════════════════════════════════════════
#                           AUTO ADD CHANNEL
# ═══════════════════════════════════════════════════════════════════════════════

@bot.on_chat_member_updated(filters.channel)
async def auto_add_channel(client: Bot, update: ChatMemberUpdated):
    # Check if bot was added as admin
    if not update.new_chat_member:
        return
    
    new_member = update.new_chat_member
    
    # Check if the update is about the bot itself
    me = await client.get_me()
    if new_member.user.id != me.id:
        return
    
    # Check if bot is now an admin
    if new_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
        return
    
    # Check if the person who added is an admin/owner
    if update.from_user:
        adder_id = update.from_user.id
        if adder_id != OWNER_ID and adder_id not in ADMINS and not await is_admin(adder_id):
            return
    
    channel_id = update.chat.id
    channel_title = update.chat.title
    
    # Check if already added
    existing = await channels_col.find_one({"channel_id": channel_id, "status": "active"})
    if existing:
        return
    
    try:
        # Save channel
        await save_channel(channel_id)
        enc1 = await save_encoded_link(channel_id)
        enc2 = await encode(str(channel_id))
        await save_encoded_link2(channel_id, enc2)
        
        link1 = f"https://t.me/{client.username}?start={enc1}"
        link2 = f"https://t.me/{client.username}?start=req_{enc2}"
        
        # Send to DATABASE_CHANNEL
        msg = f"""<b>📢 New Channel Added!</b>

<b>📌 Name:</b> {channel_title}
<b>🆔 ID:</b> <code>{channel_id}</code>

<b>🔗 Normal Link:</b>
<code>{link1}</code>

<b>🔗 Request Link:</b>
<code>{link2}</code>"""
        
        await client.send_message(DATABASE_CHANNEL, msg)
        LOGGER(__name__).info(f"Auto-added channel: {channel_title} ({channel_id})")
        
    except Exception as e:
        LOGGER(__name__).error(f"Auto-add failed for {channel_id}: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
#                               COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.on_message(filters.command('start') & filters.private)
async def start_cmd(client: Bot, message: Message):
    user_id = message.from_user.id
    await add_user(user_id)
    
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
                return await message.reply("<b>❌ Invalid or expired link.</b>")
            
            orig = await get_original_link(channel_id)
            if orig:
                btn = InlineKeyboardMarkup([[InlineKeyboardButton("• Open Link •", url=orig)]])
                return await message.reply("<b>✅ Here is your link!</b>", reply_markup=btn)
            
            async with channel_locks[channel_id]:
                old = await get_current_invite_link(channel_id)
                now = datetime.now()
                
                if old:
                    created = await get_link_creation_time(channel_id)
                    if created and (now - created).total_seconds() < 240:
                        invite_link = old["invite_link"]
                        is_req = old["is_request"]
                    else:
                        try: await client.revoke_chat_invite_link(channel_id, old["invite_link"])
                        except: pass
                        inv = await client.create_chat_invite_link(channel_id, expire_date=now + timedelta(minutes=10), creates_join_request=is_request)
                        invite_link = inv.invite_link
                        is_req = is_request
                        await save_invite_link(channel_id, invite_link, is_req)
                else:
                    inv = await client.create_chat_invite_link(channel_id, expire_date=now + timedelta(minutes=10), creates_join_request=is_request)
                    invite_link = inv.invite_link
                    is_req = is_request
                    await save_invite_link(channel_id, invite_link, is_req)
            
            btn_text = "• Request to Join •" if is_req else "• Join Channel •"
            btn = InlineKeyboardMarkup([[InlineKeyboardButton(btn_text, url=invite_link)]])
            await message.reply("<b>✅ Here is your link!</b>", reply_markup=btn)
            
            asyncio.create_task(revoke_invite_after_delay(client, channel_id, invite_link, 300))
            
        except Exception as e:
            await message.reply(f"<b>❌ Error: {e}</b>")
    else:
        btns = InlineKeyboardMarkup([
            [InlineKeyboardButton("• About", callback_data="about"), InlineKeyboardButton("• Channels", callback_data="channels")],
            [InlineKeyboardButton("• Close •", callback_data="close")]
        ])
        try:
            await message.reply_photo(START_PIC, caption=START_MSG, reply_markup=btns)
        except:
            await message.reply(START_MSG, reply_markup=btns)

@bot.on_message(filters.command('status') & filters.private & is_owner_or_admin)
async def status_cmd(client: Bot, message: Message):
    t1 = time.time()
    msg = await message.reply("<b>Processing...</b>")
    ping = (time.time() - t1) * 1000
    users = await full_userbase()
    uptime = get_readable_time(int((datetime.now() - client.uptime).total_seconds()))
    await msg.edit(f"<b>👥 Users: {len(users)}\n⏱ Uptime: {uptime}\n📶 Ping: {ping:.2f}ms</b>")

@bot.on_message(filters.command('stats') & filters.user(OWNER_ID))
async def stats_cmd(client: Bot, message: Message):
    uptime = get_readable_time(int((datetime.now() - client.uptime).total_seconds()))
    await message.reply(f"<b>BOT UPTIME:</b> {uptime}")

@bot.on_message(filters.command('broadcast') & filters.private & is_owner_or_admin)
async def broadcast_cmd(client: Bot, message: Message):
    global is_canceled
    if not message.reply_to_message:
        return await message.reply("<b>Reply to a message to broadcast.</b>")
    
    async with cancel_lock:
        is_canceled = False
    
    users = await full_userbase()
    total = len(users)
    msg = await message.reply(f"<b>📣 Broadcasting to {total} users...</b>")
    
    success = blocked = failed = 0
    for uid in users:
        async with cancel_lock:
            if is_canceled:
                return await msg.edit("<b>❌ Broadcast cancelled!</b>")
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
    
    await msg.edit(f"<b>✅ Broadcast Complete!\n\n• Success: {success}\n• Blocked: {blocked}\n• Failed: {failed}</b>")

@bot.on_message(filters.command('cancel') & filters.private & is_owner_or_admin)
async def cancel_cmd(client: Bot, message: Message):
    global is_canceled
    async with cancel_lock:
        is_canceled = True
    await message.reply("<b>🛑 Broadcast will be cancelled.</b>")

PAGE_SIZE = 6

@bot.on_message((filters.command('addchat') | filters.command('addch')) & is_owner_or_admin)
async def addchat_cmd(client: Bot, message: Message):
    try:
        channel_id = int(message.command[1])
    except:
        return await message.reply("<b>Usage: /addchat {channel_id}</b>")
    
    try:
        chat = await client.get_chat(channel_id)
        await save_channel(channel_id)
        enc1 = await save_encoded_link(channel_id)
        enc2 = await encode(str(channel_id))
        await save_encoded_link2(channel_id, enc2)
        
        link1 = f"https://t.me/{client.username}?start={enc1}"
        link2 = f"https://t.me/{client.username}?start=req_{enc2}"
        
        await message.reply(f"<b>✅ {chat.title} added!</b>\n\n<b>Normal:</b> <code>{link1}</code>\n<b>Request:</b> <code>{link2}</code>")
    except Exception as e:
        await message.reply(f"<b>❌ Error: {e}</b>")

@bot.on_message((filters.command('delchat') | filters.command('delch')) & is_owner_or_admin)
async def delchat_cmd(client: Bot, message: Message):
    try:
        channel_id = int(message.command[1])
        await delete_channel(channel_id)
        await message.reply(f"<b>✅ Channel {channel_id} removed.</b>")
    except:
        await message.reply("<b>Usage: /delchat {channel_id}</b>")

@bot.on_message(filters.command('channels') & is_owner_or_admin)
async def channels_cmd(client: Bot, message: Message):
    channels = await get_channels()
    if not channels:
        return await message.reply("<b>No channels available.</b>")
    
    text = "<b>📺 Connected Channels:</b>\n\n"
    for i, cid in enumerate(channels[:20], 1):
        try:
            chat = await get_chat_cached(client, cid)
            text += f"{i}. {chat.title} (<code>{cid}</code>)\n"
        except:
            text += f"{i}. Unknown (<code>{cid}</code>)\n"
    
    await message.reply(text)

@bot.on_message(filters.command('links') & is_owner_or_admin)
async def links_cmd(client: Bot, message: Message):
    channels = await get_channels()
    if not channels:
        return await message.reply("<b>No channels.</b>")
    
    text = "<b>🔗 All Links:</b>\n\n"
    for i, cid in enumerate(channels[:10], 1):
        try:
            chat = await get_chat_cached(client, cid)
            enc1 = await save_encoded_link(cid)
            enc2 = await encode(str(cid))
            await save_encoded_link2(cid, enc2)
            l1 = f"https://t.me/{client.username}?start={enc1}"
            l2 = f"https://t.me/{client.username}?start=req_{enc2}"
            text += f"<b>{i}. {chat.title}</b>\n• Normal: <code>{l1}</code>\n• Request: <code>{l2}</code>\n\n"
        except:
            continue
    
    await message.reply(text)

@bot.on_message(filters.command('addadmin') & filters.user(OWNER_ID))
async def addadmin_cmd(client, message: Message):
    try:
        uid = int(message.command[1])
        await add_admin(uid)
        await message.reply(f"<b>✅ {uid} is now admin.</b>")
    except:
        await message.reply("<b>Usage: /addadmin {user_id}</b>")

@bot.on_message(filters.command('deladmin') & filters.user(OWNER_ID))
async def deladmin_cmd(client, message: Message):
    try:
        uid = int(message.command[1])
        await remove_admin(uid)
        await message.reply(f"<b>✅ {uid} removed from admins.</b>")
    except:
        await message.reply("<b>Usage: /deladmin {user_id}</b>")

@bot.on_message(filters.command('admins') & filters.user(OWNER_ID))
async def admins_cmd(client, message: Message):
    admins = await list_admins()
    text = "<b>👑 Admins:</b>\n" + "\n".join([f"• <code>{a}</code>" for a in admins]) if admins else "<b>No admins.</b>"
    await message.reply(text)

@bot.on_message(filters.command('approveoff') & is_owner_or_admin)
async def approveoff_cmd(client, message: Message):
    try:
        cid = int(message.command[1])
        await set_approval_off(cid, True)
        await message.reply(f"<b>✅ Auto-approve OFF for {cid}</b>")
    except:
        await message.reply("<b>Usage: /approveoff {channel_id}</b>")

@bot.on_message(filters.command('approveon') & is_owner_or_admin)
async def approveon_cmd(client, message: Message):
    try:
        cid = int(message.command[1])
        await set_approval_off(cid, False)
        await message.reply(f"<b>✅ Auto-approve ON for {cid}</b>")
    except:
        await message.reply("<b>Usage: /approveon {channel_id}</b>")

# ═══════════════════════════════════════════════════════════════════════════════
#                           AUTO APPROVE
# ═══════════════════════════════════════════════════════════════════════════════

@bot.on_chat_join_request((filters.group | filters.channel) & filters.chat(CHAT_ID) if CHAT_ID else (filters.group | filters.channel))
async def auto_approve(client, req: ChatJoinRequest):
    chat = req.chat
    user = req.from_user
    
    if await is_approval_off(chat.id):
        return
    
    await asyncio.sleep(APPROVAL_WAIT_TIME)
    
    try:
        await client.approve_chat_join_request(chat.id, user.id)
        if APPROVED_WELCOME == "on":
            try:
                await client.send_message(user.id, f"<b>✅ Your request to join {chat.title} has been approved!</b>")
            except: pass
    except: pass

# ═══════════════════════════════════════════════════════════════════════════════
#                           CALLBACKS
# ═══════════════════════════════════════════════════════════════════════════════

@bot.on_callback_query()
async def callback_handler(client: Bot, query: CallbackQuery):
    data = query.data
    
    if data == "close":
        await query.message.delete()
    
    elif data == "about":
        await query.edit_message_media(
            InputMediaPhoto("https://envs.sh/Wdj.jpg", ABOUT_TXT),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("• Back", callback_data="start")]])
        )
    
    elif data == "channels":
        await query.edit_message_media(
            InputMediaPhoto("https://envs.sh/Wdj.jpg", CHANNELS_TXT),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("• Back", callback_data="start")]])
        )
    
    elif data == "start":
        btns = InlineKeyboardMarkup([
            [InlineKeyboardButton("• About", callback_data="about"), InlineKeyboardButton("• Channels", callback_data="channels")],
            [InlineKeyboardButton("• Close •", callback_data="close")]
        ])
        try:
            await query.edit_message_media(InputMediaPhoto(START_PIC, START_MSG), reply_markup=btns)
        except:
            await query.edit_message_text(START_MSG, reply_markup=btns)

# ═══════════════════════════════════════════════════════════════════════════════
#                               RUN
# ═══════════════════════════════════════════════════════════════════════════════

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
