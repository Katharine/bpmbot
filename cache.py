import redis
import requests

import settings

if settings.REDIS_URL:
    _pool = redis.BlockingConnectionPool.from_url(settings.REDIS_URL, max_connections=10)
    _redis = redis.Redis(connection_pool=_pool)
else:
    _redis = None

_cached = {}


def _redis_key(emote):
    return "sid:{}".format(emote)


def cache_sticker(emote):
    if _redis:
        cached_result = _redis.get(_redis_key(emote))
        if cached_result:
            return str(cached_result)
    else:
        if emote in _cached:
            return _cached[emote]
    result = requests.post(
        "https://api.telegram.org/bot{}/sendSticker".format(settings.TELEGRAM_TOKEN),
        headers={"Content-Type": "application/json"},
        json={
            "chat_id": 93363441,
            "sticker": (settings.MY_URL + "/emote/{}@2x.webp").format(emote),
        }
    )
    if result.status_code != 200:
        return None
    sticker_id = result.json()["result"]["sticker"]["file_id"]
    if _redis:
        _redis.set(_redis_key(emote), sticker_id)
    else:
        _cached[emote] = sticker_id
    return sticker_id
