import os
import tempfile

import gevent
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
            return cached_result.decode("utf-8")
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
        _redis.set(_redis_key(emote), sticker_id.encode("utf-8"))
    else:
        _cached[emote] = sticker_id
    return sticker_id


if not os.path.exists(os.path.join(tempfile.gettempdir(), "bpm-spritesheets")):
    os.mkdir(os.path.join(tempfile.gettempdir(), "bpm-spritesheets"))


def _spritesheet_path(url):
    return os.path.join(tempfile.gettempdir(), "bpm-spritesheets", os.path.basename(url))

_pending_fetches = {}


def _fetch(url):
    print("fetching %s" % url)
    result = requests.get(url)
    with open(_spritesheet_path(url), 'bw') as f:
        f.write(result.content)


def get_spritesheet(url):
    if url in _pending_fetches:
        print("waiting for ongoing fetch")
        _pending_fetches[url].join()

    if os.path.exists(_spritesheet_path(url)):
        print("using cached spritesheet")
        return open(_spritesheet_path(url), 'rb')

    print("fetching spritesheet")
    _pending_fetches[url] = gevent.spawn(_fetch, url)
    _pending_fetches[url].join()
    del _pending_fetches[url]

    return open(_spritesheet_path(url), 'rb')
