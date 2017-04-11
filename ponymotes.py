from gevent import monkey; monkey.patch_all()
import bz2
import io
import json
import requests

from PIL import Image


def _init():
    global _emotes, _aliases, _tags, _subs
    _emotes = {}
    _aliases = {}
    _tags = {}
    _subs = {}

_init()


def fetch_ponymotes():
    result = requests.get("https://ponymotes.net/bpm/_export.json.bz2")
    compressed = result.content
    uncompressed = bz2.decompress(compressed)
    data = json.loads(uncompressed)
    assert isinstance(data, dict)
    for name, emote in data.items():
        name = name[1:]
        if 'primary' in emote:
            _aliases[name] = emote['primary'][1:]
            continue
        _aliases[name] = name
        _emotes[name] = emote
        for tag in emote['tags']:
            tag = tag[1:]
            _tags.setdefault(tag, []).append(name)

        _subs.setdefault(emote['source'][2:], []).append(name)


def search_names(text):
    results = set()
    for alias, emote in _aliases.items():
        if text in alias:
            results.add(emote)
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

    for phrase in phrases:
        if phrase[0] == '+':
            has_includes = True
            includes.update(search_tags(phrase[1:]))
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

    if has_names:
        return result & names, flags
    else:
        return result, flags


def get_size(ponymote):
    return _emotes[ponymote].get('size', (0, 0))


def render_ponymote(name, flags, format='png', scale=1):
    if scale > 5 or format not in {'png', 'webp', 'gif', 'jpeg', 'bmp', 'tiff'}:
        scale = 1
        name = 'no'
        format = 'png'

    emote = _emotes[_aliases[name]]
    url = emote['image_url']
    if url[:2] == '//':
        url = 'http:' + url
    result = requests.get(url)
    img = Image.open(io.BytesIO(result.content))
    if 'size' in emote:
        offset = [-x for x in emote.get('offset', (0, 0))]
        img = img.crop((offset[0], offset[1], offset[0] + emote['size'][0], offset[1] + emote['size'][1]))

    transform = emote.get('css', {}).get('transform', [])
    if 'scaleX(-1)' in transform or 'r' in flags:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)

    if 'scaleY(-1)' in transform or 'f' in flags:
        img = img.transpose(Image.FLIP_TOP_BOTTOM)

    if scale != 1:
        img = img.resize((int(img.size[0] * scale), int(img.size[1] * scale)), resample=Image.LANCZOS)

    output = io.BytesIO()
    img.save(output, format)
    output.seek(0)
    return output.read()
