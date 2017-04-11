from os import environ as _environ

PORT = int(_environ.get('PORT', 8081))
TELEGRAM_TOKEN = _environ['TELEGRAM_TOKEN']
CACHE_TIME = int(_environ.get('CACHE_TIME', 10))
MY_URL = _environ.get("MY_URL", "https://5e64928c.ngrok.io/")
