CATEGORIES = {
    "bot_config": {
        "name": "🤖 Bot Config",
        "keys": {
            "BOT_TOKEN": {"label": "BOT_TOKEN", "type": "str", "secret": True},
            "API_ID": {"label": "API_ID", "type": "int"},
            "API_HASH": {"label": "API_HASH", "type": "str", "secret": True},
            "OWNER_ID": {"label": "OWNER_ID", "type": "int"},
            "DB_URI": {"label": "DB_URI", "type": "str", "secret": True},
            "DB_NAME": {"label": "DB_NAME", "type": "str"},
        }
    },
    "messages": {
        "name": "💬 Messages",
        "keys": {
            "START_PIC": {"label": "START_PIC", "type": "str"},
            "START_MSG": {"label": "START_MSG", "type": "text"},
            "OWNER": {"label": "OWNER", "type": "str"},
            "CHANNELS_TXT": {"label": "CHANNELS_TXT", "type": "str"},
        }
    },
    "channels": {
        "name": "📺 Channels",
        "keys": {
            "DATABASE_CHANNEL": {"label": "DATABASE_CHANNEL", "type": "int"},
        }
    },
    "features": {
        "name": "⚙️ Features",
        "keys": {
            "APPROVED_WELCOME": {"label": "APPROVED_WELCOME", "type": "toggle"},
            "APPROVAL_WAIT_TIME": {"label": "APPROVAL_WAIT_TIME", "type": "int"},
            "LINK_EXPIRY": {"label": "LINK_EXPIRY", "type": "int"},
        }
    },
    "upstream": {
        "name": "🔄 Upstream",
        "keys": {
            "UPSTREAM_REPO": {"label": "UPSTREAM_REPO", "type": "str"},
            "UPSTREAM_BRANCH": {"label": "UPSTREAM_BRANCH", "type": "str"},
        }
    },
    "pics": {
        "name": "🖼️ PICS",
        "keys": {
            "PICS_URL": {"label": "PICS_URL", "type": "list"},
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
