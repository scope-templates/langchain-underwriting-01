import os
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_server_exits_with_a_message_when_its_port_is_taken():
    with socket.socket() as held:
        held.bind(("127.0.0.1", 0))
        held.listen()
        port = held.getsockname()[1]
        result = subprocess.run([sys.executable, "-m", "app"], cwd=ROOT, env={**os.environ, "PORT": str(port)},
                                capture_output=True, text=True, timeout=60)
    assert result.returncode != 0
    assert f"Port {port} on 127.0.0.1 is already in use" in result.stderr
