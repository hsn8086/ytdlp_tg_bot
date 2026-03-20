#!/bin/sh
set -eu

DOWNLOAD_PATH="${DOWNLOAD_DIR:-/tmp/ytdlp_bot_downloads}"
DATA_PATH="${DATA_DIR:-/app/data}"

mkdir -p "$DOWNLOAD_PATH"
chown -R appuser:appuser "$DOWNLOAD_PATH"

mkdir -p "$DATA_PATH"
chown -R appuser:appuser "$DATA_PATH"

exec runuser -u appuser -- "$@"
