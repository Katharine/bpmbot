import os
import tempfile
import time

import gevent
import re
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
    return "m:{}".format(emote if isinstance(emote, str) else emote['name'])


def filter_flags(flags):
    new_flags = []
    for flag in flags:
        if flag in {'nowaifu', 'r', 'f'}:
            new_flags.append(flag)
            continue
        if flag.isdigit():
            new_flags.append(flag)
            continue
        if re.fullmatch(r'blur\d?', flag):
            new_flags.append(flag)
            continue
    return new_flags


def cache_sticker(emote, flags):
    flags = filter_flags(flags)
    flag_str = '-'.join(sorted(flags))
    if _redis:
        cached_result = _redis.hget(_redis_key(emote), "s-%s" % flag_str)
        if cached_result:
            return cached_result.decode("utf-8")
    else:
        if emote in _cached:
            return _cached[emote]
    scale = max(1, settings.STICKER_MIN_SIZE / max(emote['size']))
    result = requests.post(
        "https://api.telegram.org/bot{}/sendSticker".format(settings.TELEGRAM_TOKEN),
        headers={"Content-Type": "application/json"},
        json={
            "chat_id": settings.STICKER_DUMP,
            "sticker": (settings.MY_URL + "/emote/{}-{}@{}x.webp?now={}").format(emote['name'], flag_str, scale, time.time()),
            "disable_notification": True,
        }
    )
    if result.status_code != 200:
        return None
    sticker_id = result.json()["result"]["sticker"]["file_id"]
    if _redis:
        _redis.hmset(_redis_key(emote), {"s-%s" % flag_str: sticker_id.encode("utf-8"), 'url': emote['image_url']})
    else:
        _cached[emote] = sticker_id
    return sticker_id


if not os.path.exists(os.path.join(tempfile.gettempdir(), "bpm-spritesheets")):
    os.mkdir(os.path.join(tempfile.gettempdir(), "bpm-spritesheets"))


def _spritesheet_path(url):
    return os.path.join(tempfile.gettempdir(), "bpm-spritesheets", os.path.basename(url))

_pending_fetches = {}


def _fetch(url):
    print("Fetching %s..." % url)
    result = requests.get(url)
    with open(_spritesheet_path(url), 'bw') as f:
        f.write(result.content)


def get_spritesheet(url):
    if url in _pending_fetches:
        _pending_fetches[url].join()

    if os.path.exists(_spritesheet_path(url)):
        return open(_spritesheet_path(url), 'rb')

    _pending_fetches[url] = gevent.spawn(_fetch, url)
    _pending_fetches[url].join()
    del _pending_fetches[url]

    return open(_spritesheet_path(url), 'rb')


def get_cached_emote(name):
    return _redis.hgetall(_redis_key(name))


def clear_cached_stickers(emote):
    key = _redis_key(emote)
    keys = [x for x in _redis.hkeys(key) if x.startswith(b's-')]
    if len(keys) > 0:
        _redis.hdel(key, *keys)


def cache_emote_scale(emote, scale):
    key = _redis_key(emote)
    _redis.hmset(key, {'url': emote['image_url'].encode('utf-8'), 'scale': scale})


def note_emote_use(emote, user=None):
    key = _redis_key(emote)
    _redis.hincrby(key, 'uses', 1)
    if user:
        note_user_emote(user, emote)


def note_user_emote(user, emote):
    user_key = 'u:{}'.format(user['id'])
    _redis.hincrby(user_key, 'e:{}'.format(emote), 1)
