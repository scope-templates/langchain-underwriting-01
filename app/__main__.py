import os
import socket
import sys

import uvicorn

HOST = "127.0.0.1"

try:
    port = int(os.environ.get("PORT", "8000"))
except ValueError:
    sys.exit(f"PORT must be a port number, not {os.environ['PORT']!r}.")

with socket.socket() as probe:
    if os.name != "nt":
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        probe.bind((HOST, port))
    except OSError:
        sys.exit(f"Port {port} on {HOST} is already in use. Set PORT to a free port and start again.")

uvicorn.run("app.main:create_app", factory=True, host=HOST, port=port)
