#!/bin/sh
# Starts as root only to fix ownership of the data directory, then drops to PUID:PGID.
# Unraid convention: 99:100 (nobody:users). If the container is started with --user, nothing is changed.
set -e

if [ "$(id -u)" = "0" ]; then
  PUID="${PUID:-99}"
  PGID="${PGID:-100}"
  for dir in "${DATA_DIR:-/data}" "${MUSIC_DIR:-}"; do
    [ -n "$dir" ] || continue
    mkdir -p "$dir"
    # A recursive chown on every start would be slow for a big library, so only do it when the top level is wrong.
    if [ "$(stat -c %u:%g "$dir")" != "$PUID:$PGID" ]; then
      chown -R "$PUID:$PGID" "$dir"
    fi
  done
  exec setpriv --reuid="$PUID" --regid="$PGID" --clear-groups "$@"
fi

exec "$@"
