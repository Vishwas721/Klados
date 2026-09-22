#!/usr/bin/env bash
set -euo pipefail

# Ensure required commands are available
command -v unshare >/dev/null || { echo "ERROR: unshare is required"; exit 1; }
command -v Xvfb >/dev/null || { echo "ERROR: Xvfb is required"; exit 1; }

# WSLg mounts /tmp/.X11-unix as a read-only tmpfs.
# We create a private writable directory and bind mount it over /tmp/.X11-unix
# inside a private namespace so Xvfb can create its sockets without touching WSLg's X0.
RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
CAMOUFOX_X11_DIR="$RUNTIME_DIR/camoufox-x11"

mkdir -p "$CAMOUFOX_X11_DIR"

# Execute arguments safely inside the isolated mount namespace
exec unshare --user --map-root-user --mount bash -c '
    set -euo pipefail
    mount --bind "$1" /tmp/.X11-unix
    shift
    exec "$@"
' -- "$CAMOUFOX_X11_DIR" "$@"
