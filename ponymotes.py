from gevent import monkey; monkey.patch_all()
import bz2
import io
import json
import Levenshtein
import re
import requests

import cache
import settings

from PIL import Image, ImageFilter


def _init():
    global _emotes, _aliases, _tags, _subs, _reverse_aliases
    _emotes = {}
    _aliases = {}
    _reverse_aliases = {}
    _tags = {}
    _subs = {}

_init()


def fetch_ponymotes():
    _init()
    result = requests.get("https://ponymotes.net/bpm/_export.json.bz2")
    compressed = result.content
    uncompressed = bz2.decompress(compressed).decode('utf-8')
    data = json.loads(uncompressed)
    assert isinstance(data, dict)
    for name, emote in data.items():
        name = name[1:]
        if not emote.get('size'):
            continue
        if 'primary' in emote:
            _reverse_aliases.setdefault(emote['primary'][1:], []).append(name)
            _aliases[name] = {'primary': emote['primary'][1:], 'css': emote.get('css', None), 'name': name}
            continue
        emote['name'] = name
        _aliases[name] = {'primary': name, 'css': emote.get('css', None), 'name': name}
        _reverse_aliases.setdefault(name, []).append(name)
        _emotes[name] = emote
        for tag in emote['tags']:
            tag = tag[1:]
            _tags.setdefault(tag, []).append(name)

        _subs.setdefault(emote['source'][2:], []).append(name)


def search_names(text):
    results = set()
    for alias, emote in _aliases.items():
        if text in alias:
            results.add(emote['primary'])
    return results


def search_tags(text):
    results = set()
    if text in _tags:
        results.update(_tags[text])
    else:
        for tag, emotes in _tags.items():
            if text in tag:
                results.update(emotes)
    return results


def search_subs(text):
    results = set()
    for sub, emotes in _subs.items():
        if text in sub:
            results.update(emotes)
    return results


def perform_search(text):
    phrases = text.split()
    constraints = set()
    includes = set()
    excludes = set()
    names = set()
    flags = []

    has_includes = False
    has_constraints = False
    has_names = False

    if '+nsfw' not in phrases:
        excludes.update(search_tags('nsfw'))

    if '+nonpony' not in phrases:
        excludes.update(search_tags('nonpony'))

    name_queries = []
    for phrase in phrases:
        if phrase[0] == '+':
            has_includes = True
            if len(includes) == 0:
                includes.update(search_tags(phrase[1:]))
            else:
                includes.intersection_update(search_tags(phrase[1:]))
        elif phrase[0] == '-':
            excludes.update(search_tags(phrase[1:]))
        elif phrase[:2] == 'r/':
            has_constraints = True
            constraints.update(search_subs(phrase[2:]))
        elif phrase[:3] == 'sr:':
            has_constraints = True
            constraints.update(search_subs(phrase[3:]))
        else:
            has_names = True
            parts = phrase.split('-')
            name_queries.append(parts[0])
            names.update(search_names(parts[0]))
            flags.extend(parts[1:])

    # print(includes, excludes, constraints)
    if has_constraints and has_includes:
        result = constraints & (includes - excludes)
    elif has_includes:
        result = includes - excludes
    elif has_constraints:
        result = constraints - excludes
    else:
        result = set(_emotes.keys()) - excludes

    emotes = [emote_by_name(x) for x in (result & names if has_names else result)]
    if len(name_queries) == 1:
        emotes.sort(key=lambda x: (min(Levenshtein.distance(y, name_queries[0]) for y in _reverse_aliases[x['name']]), x['name']))

    return emotes, flags

def get_size(ponymote):
    return _emotes[ponymote].get('size', (0, 0))


def render_ponymote(name, flags, format='png', scale=1):
    if scale > 32 or format not in {'png', 'webp', 'gif', 'jpeg', 'bmp', 'tiff'}:
        scale = 1
        name = 'no'
        format = 'png'

    emote = _emotes[_aliases[name]['primary']]
    css = _aliases[name]['css'] or {}
    url = emote['image_url']
    is_cropped = False
    if url[:2] == '//':
        url = 'http:' + url

    total_scale = scale
    if scale > 1 and 'nowaifu' not in flags:
        cached = cache.get_cached_emote(name)
        cached_scale = int(cached.get(b'scale', b'1'))
        if cached_scale > 1 and emote['image_url'] == cached.get(b'url', b'').decode('utf-8'):
            use_scale = 1
            while use_scale < cached_scale and use_scale < scale:
                use_scale *= 2
            # We want to scale down, not up, but only from at most one size above what we wanted.
            if use_scale < cached_scale and use_scale < scale:
                use_scale *= 2
            if use_scale > 1:
                url = 'https://s3.amazonaws.com/{}/{}@{}x.png'.format(settings.SCALED_PONYMOTE_BUCKET, name, use_scale)
                scale /= use_scale
                is_cropped = True
    f = cache.get_spritesheet(url)
    try:
        img = Image.open(f)

        if 'size' in emote and not is_cropped:
            offset = [-x for x in emote.get('offset', (0, 0))]
            img = img.crop((offset[0], offset[1], offset[0] + emote['size'][0], offset[1] + emote['size'][1]))

        transform = css.get('transform', [])
        if 'scaleX(-1)' in transform or 'r' in flags:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)

        if 'scaleY(-1)' in transform or 'f' in flags:
            img = img.transpose(Image.FLIP_TOP_BOTTOM)

        numbers = [int(x) for x in flags if x.isdigit()][:1]
        if numbers:
            img = img.rotate(-numbers[0], resample=Image.BICUBIC, expand=True)

        blur = [x for x in flags if re.match(r'^blur(\d+)?$', x)]
        if blur:
            blur = blur[-1]
            blur = re.match(r'blur(\d+)?', blur).group(1)
            if not blur:
                blur = 2
            blur = int(blur)
            blur = int(blur * total_scale)
            new_img = Image.new(img.mode, (img.width + blur * 3, img.height + blur * 3))
            new_img.paste(img, (blur, blur))
            img = new_img.filter(ImageFilter.GaussianBlur(blur))

        if scale != 1:
            img = img.resize((int(img.size[0] * scale), int(img.size[1] * scale)), resample=Image.LANCZOS)

        output = io.BytesIO()
        img.save(output, format)
    finally:
        f.close()

    output.seek(0)
    return output.read()


def emote_by_name(name):
    return _emotes[name]


def get_base_emotes():
    return _emotes
