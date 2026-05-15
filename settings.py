CATEGORIES = {
    "bot_config": {
        "name": "🤖 Bot Config",
        "keys": {
            "BOT_TOKEN": {"label": "Bot Token", "type": "str", "secret": True},
            "API_ID": {"label": "API ID", "type": "int"},
            "API_HASH": {"label": "API Hash", "type": "str", "secret": True},
            "OWNER_ID": {"label": "Owner ID", "type": "int"},
            "DB_URI": {"label": "DB URI", "type": "str", "secret": True},
            "DB_NAME": {"label": "DB Name", "type": "str"},
        }
    },
    "messages": {
        "name": "💬 Messages",
        "keys": {
            "START_PIC": {"label": "Start Pic URL", "type": "str"},
            "START_MSG": {"label": "Start Message", "type": "text"},
            "OWNER": {"label": "Owner Link", "type": "str"},
            "CHANNELS_TXT": {"label": "Channels Text", "type": "str"},
        }
    },
    "channels": {
        "name": "📺 Channels",
        "keys": {
            "DATABASE_CHANNEL": {"label": "DB Channel ID", "type": "int"},
        }
    },
    "features": {
        "name": "⚙️ Features",
        "keys": {
            "APPROVED_WELCOME": {"label": "Welcome on Approve", "type": "toggle"},
            "APPROVAL_WAIT_TIME": {"label": "Approval Wait (sec)", "type": "int"},
            "LINK_EXPIRY": {"label": "Link Expiry (min)", "type": "int"},
        }
    },
    "upstream": {
        "name": "🔄 Upstream",
        "keys": {
            "UPSTREAM_REPO": {"label": "Upstream Repo", "type": "str"},
            "UPSTREAM_BRANCH": {"label": "Upstream Branch", "type": "str"},
        }
    },
    "pics": {
        "name": "🖼️ PICS",
        "keys": {
            "PICS_URL": {"label": "PICS URLs", "type": "list"},
        }
    },
}

class Settings:
    def __init__(self, collection):
        self.col = collection
        self._cache = {}

    async def load(self):
        self._cache = {}
        async for doc in self.col.find():
            self._cache[doc["key"]] = doc["value"]

    async def get(self, key, default=None):
        if key in self._cache:
            return self._cache[key]
        doc = await self.col.find_one({"key": key})
        if doc:
            self._cache[key] = doc["value"]
            return doc["value"]
        return default

    async def set(self, key, value):
        await self.col.update_one({"key": key}, {"$set": {"key": key, "value": value}}, upsert=True)
        self._cache[key] = value

    async def delete(self, key):
        await self.col.delete_one({"key": key})
        self._cache.pop(key, None)

    async def getall(self):
        return dict(self._cache)
