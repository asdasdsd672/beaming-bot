import os

TOKEN = os.getenv("DISCORD_TOKEN", "MTUzMTQ0MDg1MDk1NjE5Mzk1Mg.G4eu_i.Ix202_OHRqBOGhCvzyMyV_zAr7tk9tRLeCfjCg")
PREFIX = os.getenv("PREFIX", "!")
OWNER_IDS = [int(x) for x in os.getenv("OWNER_IDS", "1527881220741009623").split(",") if x]

MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://CodeX:CodeX@codex-us1.qebkhlm.mongodb.net/?appName=CodeX-us1")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "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")

LAVALINK_HOST = os.getenv("LAVALINK_HOST", "lavalink.devamop.in")
LAVALINK_PORT = int(os.getenv("LAVALINK_PORT", "443"))
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD", "DevamOP")
LAVALINK_SECURE = os.getenv("LAVALINK_SECURE", "true").lower() == "true"
