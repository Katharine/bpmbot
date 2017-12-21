#!/bin/bash

set -e

# Check that our environment variables are set (because otherwise this will fail)
: "${AWS_ACCESS_KEY_ID?Must set AWS_ACCESS_KEY_ID}"
: "${AWS_SECRET_ACCESS_KEY?Must set AWS_SECRET_ACCESS_KEY}"
: "${REDIS_URL?Must set REDIS_URL}"
: "${TELEGRAM_TOKEN?Must set TELEGRAM_TOKEN}"
: "${STICKER_DUMP?Must set STICKER_DUMP}"
: "${MY_URL?Must set MY_URL}"

cd /root/waifu2x
python3 ../bpmbot/batch_resize.py
python3 ../bpmbot/bulk_cache.py
