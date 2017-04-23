from gevent import monkey; monkey.patch_all()
import math
import os
import subprocess

import boto3

import cache
import ponymotes
import settings
import tempfile

print("Setting up S3...")
s3 = boto3.client('s3')

print("Fetching current ponymotes...")
ponymotes.fetch_ponymotes()

emotes = ponymotes.get_base_emotes()

print("Determining emotes to scale...")
todo = {}
for name, emote in emotes.items():
    if 'image_url' not in emote:
        continue
    cached = None
    # cached = cache.get_cached_emote(name)
    if cached is not None and cached.get('url', None) == emote['image_url']:
        continue
    # cache.clear_cached_stickers(name)
    if emote['size'][0] < settings.STICKER_MIN_SIZE and emote['size'][1] < settings.STICKER_MIN_SIZE:
        todo[name] = int(math.ceil(math.log(settings.STICKER_MIN_SIZE/max(*emote['size']), 2)))

print("Got {} emotes to scale, totalling {} operations.".format(len(todo), sum(todo.values())))

output_folder = '/tmp'

emote_paths = {}
iteration = 1
print("Fetching initial emotes...")
for i, emote in enumerate(todo.keys()):
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(ponymotes.render_ponymote(emote, []))
        emote_paths[emote] = f.name
    if i % 100 == 0:
        print("Done {} of {}.".format(i, len(todo)))

print("Finished fetching originals.")

while len(todo) > 0:
    print("----------")
    print("BEGIN ITERATION {}".format(iteration))
    print("{} emotes this round.".format(len(todo)))
    print("----------")
    with tempfile.NamedTemporaryFile('w', delete=False) as f:
        f.write("\n".join(emote_paths.values()))
        f.flush()
        print("waifu2x file list at {}".format(f.name))
    tmp_dir = tempfile.mkdtemp()
    print("Running waifu2x; output to {}...".format(tmp_dir))
    print("This will probably take about {} minutes...".format(round(0.25/60*len(todo))))
    subprocess.check_call(["th", "waifu2x.lua", "-m", "scale", "-l", f.name, "-o", tmp_dir+"/%s.png"])
    print("waifu2x completed.")
    print("Uploading scaled emotes and cleaning up...")
    this_round_len = len(todo)
    for i, emote in enumerate(list(todo.keys())):
        if todo[emote] <= 0:
            continue
        todo[emote] -= 1
        new_path = os.path.join(tmp_dir, os.path.basename(emote_paths[emote]))
        s3.upload_file(new_path, "bpm-scaled", "{}@{}x.png".format(emote, 2**iteration), ExtraArgs={
            'ACL': 'public-read', 'ContentType': 'image/png'
        })
        cache.cache_emote_scale(ponymotes.emote_by_name(emote), 2**iteration)
        os.unlink(emote_paths[emote])
        if todo[emote] > 0:
            emote_paths[emote] = new_path
        else:
            del emote_paths[emote]
            del todo[emote]
        if i % 100 == 0:
            print("Done {} of {}.".format(i, this_round_len))
    print("Finished iteration {}.".format(iteration))
    iteration += 1

print("Finished!")
