#!/bin/sh
set -eu

DOWNLOAD_PATH="${DOWNLOAD_DIR:-/tmp/ytdlp_bot_downloads}"

mkdir -p "$DOWNLOAD_PATH"
chown -R appuser:appuser "$DOWNLOAD_PATH"

exec runuser -u appuser -- "$@"
