"""A private Unix socket per seat; only the host launches database-backed servers."""

import os
import socketserver
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def seat_socket(directory, seat):
    # Temporary short paths also fit macOS sockaddr_un with long run directory names.
    with tempfile.TemporaryDirectory(prefix="cw-", dir="/tmp") as tmp:
        address = Path(tmp) / "arena.sock"
        link = directory / seat / "arena.sock"
        children = set()
        lock = threading.Lock()

        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                # Socket is a bidirectional byte stream. Seat and DB location are selected
                # here, never by a message originating from the participant.
                command = [
                    sys.executable,
                    "-m",
                    "cardwars.tools.mcp_server",
                    str(directory),
                    seat,
                ]
                with (directory / f"{seat}-mcp.log").open("ab") as log:
                    child = subprocess.Popen(
                        command,
                        stdin=self.request,
                        stdout=self.request,
                        stderr=log,
                        cwd=Path(__file__).resolve().parents[2],
                    )
                    with lock:
                        children.add(child)
                    try:
                        child.wait()
                    finally:
                        with lock:
                            children.discard(child)

        class Endpoint(socketserver.ThreadingUnixStreamServer):
            daemon_threads = True

        with Endpoint(str(address), Handler) as server:
            os.chmod(address, 0o600)
            if link.is_symlink() and not link.exists():
                link.unlink()
            link.symlink_to(address)
            thread = threading.Thread(
                target=server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True
            )
            thread.start()
            try:
                yield address
            finally:
                link.unlink(missing_ok=True)
                server.shutdown()
                thread.join()
                with lock:
                    active = list(children)
                for child in active:
                    child.terminate()
                    try:
                        child.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait()
