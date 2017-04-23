from gevent import monkey; monkey.patch_all()
import gevent
import gevent.pool
from flask import Flask, request, make_response
import requests

import cache
import ponymotes
import settings

app = Flask(__name__)

ponymotes.fetch_ponymotes()


def handle_request(id, query):
    sticker_ids = {}
    if len(query) < 2:
        emotes = []
    else:
        print(query)
        emotes, flags = ponymotes.perform_search(query)
        print(emotes, flags)
        emotes = emotes[:settings.STICKER_LIMIT]
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
                    "id": "bpmbot-" + emote,
                    "sticker_file_id": sticker_ids[emote],
                } for emote in emotes if sticker_ids.get(emote, None)
            ]
        }
    )


@app.route('/telegram/update', methods=['POST'])
def handle_update():
    if 'inline_query' not in request.json:
        return 'u wot mate?'
    query = request.json['inline_query']
    gevent.spawn(handle_request, query['id'], query['query'])
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
                  json={"url": settings.MY_URL + "/telegram/update", "allowed_updates": "inline_query"})
    from gevent.wsgi import WSGIServer
    http_server = WSGIServer(('', settings.PORT), app)
    http_server.serve_forever()