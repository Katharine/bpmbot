from os import environ as _environ

PORT = int(_environ.get('PORT', 8081))
TELEGRAM_TOKEN = _environ.get('TELEGRAM_TOKEN', None)
CACHE_TIME = int(_environ.get('CACHE_TIME', 10))
MY_URL = _environ.get("MY_URL", "https://5e64928c.ngrok.io/")
REDIS_URL = _environ.get("REDIS_URL", None)
STICKER_DUMP = int(_environ.get("STICKER_DUMP", 0))
STICKER_LIMIT = int(_environ.get("STICKER_LIMIT", 5))
STICKER_MIN_SIZE = 256

