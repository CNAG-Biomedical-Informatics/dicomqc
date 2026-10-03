"""Worker watchdog, including unexpected parent death on Windows and Unix."""

import os
from pathlib import Path
import socket
import sys
import threading

from dicomqc.api.storage import read_json


def run(directory: str) -> int:
    connection = None
    try:
        guard = read_json(Path(directory) / "guard.json")
        connection = socket.create_connection(("127.0.0.1", guard["port"]), timeout=10)
        connection.sendall(guard["secret"].encode())
        connection.settimeout(None)
    except (OSError, ValueError, KeyError, TypeError):
        if connection:
            connection.close()
        return 1

    def watch():
        try:
            connection.recv(1)
        except OSError:
            pass
        finally:
            os._exit(1)

    threading.Thread(target=watch, daemon=True).start()
    from dicomqc.api.worker import main
    return main(directory)


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1]))
