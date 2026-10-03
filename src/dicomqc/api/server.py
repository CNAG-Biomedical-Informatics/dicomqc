"""Optional local server launcher and frozen desktop entry point."""

import argparse
import os
from pathlib import Path
import socket
import sys
import threading


def watch_parent(stream, shutdown) -> None:
    """The native parent owns the write end for its entire lifetime."""
    try:
        while stream.read(1):
            pass
    except (OSError, ValueError):
        pass
    finally:
        shutdown()


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--worker":
        from dicomqc.api.runner import run
        return run(argv[1]) if len(argv) == 2 else 2
    parser = argparse.ArgumentParser(prog="dicomqc serve")
    parser.add_argument("--state-dir", type=Path, required=True, help="Private run workspace, separate from inputs.")
    parser.add_argument("--port", type=int, default=8765, help="Loopback port; 0 chooses an available port.")
    parser.add_argument("--token-file", type=Path)
    parser.add_argument("--local-token-file", type=Path)
    parser.add_argument("--ready-file", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--parent-stdin", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    listener = None
    published = False
    try:
        import uvicorn
        from dicomqc.api.app import create_app
    except ImportError:
        print('Install the optional API with: pip install "dicomqc[api]"', file=sys.stderr)
        return 2
    try:
        if not 0 <= args.port <= 65535:
            raise ValueError("Invalid port")
        token = args.token_file.read_text().strip() if args.token_file else os.environ.get("DICOMQC_API_TOKEN", "")
        local = args.local_token_file.read_text().strip() if args.local_token_file else os.environ.get("DICOMQC_LOCAL_TOKEN", "")
        app = create_app(args.state_dir, token, local, shutdown=lambda: setattr(server, "should_exit", True))
        listener = socket.socket()
        listener.bind(("127.0.0.1", args.port))
        listener.listen(128)
        class ReadyServer(uvicorn.Server):
            async def startup(self, sockets=None):
                nonlocal published
                await super().startup(sockets=sockets)
                if self.started and not self.should_exit:
                    if args.ready_file:
                        from dicomqc.api.storage import write_json
                        write_json(args.ready_file, {"port": listener.getsockname()[1]})
                        published = True
                    else:
                        print(f"dicomqc local API: http://127.0.0.1:{listener.getsockname()[1]}", flush=True)

        # Uvicorn otherwise logs lifespan tracebacks containing local paths.
        server = ReadyServer(uvicorn.Config(app, log_level="critical", access_log=False))
        if args.parent_stdin:
            threading.Thread(target=watch_parent, args=(sys.stdin.buffer, lambda: setattr(server, "should_exit", True)), daemon=True).start()
        server.run(sockets=[listener])
        if not server.started:
            print("Cannot start the local API. Check the workspace and private configuration.", file=sys.stderr)
        return 0 if server.started else 2
    except (Exception, SystemExit):
        print("Cannot start the local API. Check workspace, port and both private tokens.", file=sys.stderr)
        return 2
    finally:
        if listener:
            listener.close()
        if published:
            try:
                args.ready_file.unlink(missing_ok=True)
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
