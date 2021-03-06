from gevent import monkey; monkey.patch_all()
import gevent.queue
import gevent.pool

import cache
import ponymotes
ponymotes.fetch_ponymotes()

q = gevent.queue.Queue(items=ponymotes.get_base_emotes().values())
q.put(StopIteration)

total = len(q)


def consumer():
    for emote in q:
        try:
            print("{}/{} remain".format(len(q), total), emote['name'], cache.cache_sticker(emote, []))
        except Exception as e:
            print(e)
            print(emote.get('size'))

group = gevent.pool.Group()
for x in range(2):
    group.spawn(consumer)
group.join()
