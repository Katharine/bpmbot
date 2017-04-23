from gevent import monkey; monkey.patch_all()
import gevent.queue
import gevent.pool

import cache
import ponymotes

q = gevent.queue.Queue(items=ponymotes.get_base_emotes().items())

total = len(q)


def consumer():
    for emote in q:
        print("{}/{} remain".format(len(q), total), emote['name'], cache.cache_sticker(emote, []))

group = gevent.pool.Group()
for x in range(2):
    group.spawn(consumer)
group.join()
