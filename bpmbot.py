from gevent import monkey; monkey.patch_all()
import gevent
import gevent.pool
from flask import Flask, request, make_response
import re
import requests

import cache
import ponymotes
import settings

app = Flask(__name__)

ponymotes.fetch_ponymotes()

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


def handle_request(id, query):
    sticker_ids = {}
    if len(query) < 2:
        emotes = []
    else:
        print(query)
        emotes, flags = ponymotes.perform_search(query)
        flags = filter_flags(flags)
        print(emotes, flags)
        emotes = emotes[:settings.STICKER_LIMIT]
        # Don't use flags with more than
        if len(flags) > 0:
            emotes = emotes[:1]
        # emotes = ['{}-{}'.format(x, '-'.join(sorted(flags))) for x in emotes][:settings.STICKER_LIMIT]
        # send a sticker
        group = gevent.pool.Group()
        greenlets = {}
        for emote in emotes:
            greenlets[emote['name']] = group.spawn(cache.cache_sticker, emote, flags)
        group.join()
        sticker_ids = {k: x.get() for k, x in greenlets.items()}

    requests.post(
        "https://api.telegram.org/bot{}/answerInlineQuery".format(settings.TELEGRAM_TOKEN),
        headers={"Content-Type": "application/json"},
        json={
            "inline_query_id": id,
            "cache_time": settings.CACHE_TIME,
            "is_personal": False,
            "results": [
                {
                    "type": "sticker",
                    "id": emote['name'] + '-' + '-'.join(sorted(flags)),
                    "sticker_file_id": sticker_ids[emote['name']],
                } for emote in emotes if sticker_ids.get(emote['name'], None)
            ]
        }
    )


def handle_inline_result(emote, user):
    cache.note_emote_use(emote, user)


@app.route('/telegram/update', methods=['POST'])
def handle_update():
    if 'inline_query' in request.json:
        query = request.json['inline_query']
        gevent.spawn(handle_request, query['id'], query['query'])
    elif 'chosen_inline_result' in request.json:
        result = request.json['chosen_inline_result']
        handle_inline_result(result['result_id'], result['from'])
    return ''


@app.route('/emote/<emote>.<format>', defaults={'scale': 1}, methods=['GET'])
@app.route('/emote/<emote>@<scale>x.<format>', methods=['GET'])
def render_emote(emote, scale, format):
    parts = emote.split('-')

    response = make_response(ponymotes.render_ponymote(parts[0], parts[1:], format=format, scale=float(scale)))
    response.headers['Content-Type'] = 'image/' + format
    return response


if __name__ == '__main__':
    requests.post("https://api.telegram.org/bot{}/setWebhook".format(settings.TELEGRAM_TOKEN),
                  headers={"Content-Type": "application/json"},
                  json={
                      "url": settings.MY_URL + "/telegram/update",
                      "allowed_updates": ["inline_query", "chosen_inline_result"]
                  })
    from gevent.wsgi import WSGIServer
    http_server = WSGIServer(('', settings.PORT), app)
    http_server.serve_forever()