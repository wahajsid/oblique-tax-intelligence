#!/bin/sh
# Shim installed as /usr/local/bin/uvicorn in the Docker image.
# Some platforms (Railway, with a stored start command) exec the start command
# WITHOUT a shell, so "${PORT:-8000}" and '*' arrive as literal text. This shim
# re-evaluates the arguments through the shell so variables and quotes resolve,
# then starts the real uvicorn module. With plain arguments it is a no-op.
eval "set -- $*"
exec python -m uvicorn "$@"
