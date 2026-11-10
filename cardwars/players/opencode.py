"""Run OpenCode V2 against one private server after its seat MCP connection is ready."""

import os
import re
import secrets
import select
import shutil
import subprocess
import sys
import threading
import time


def main(argv):
    cli = shutil.which("opencode")
    if cli is None:
        raise ValueError("Install OpenCode V2 to use this harness")
    env = os.environ.copy()
    env["OPENCODE_PASSWORD"] = secrets.token_urlsafe(32)
    with subprocess.Popen(
        [cli, "serve", "--hostname", "127.0.0.1", "--port", "0"],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        text=True,
    ) as server:
        try:
            if not select.select([server.stdout], [], [], 30)[0]:
                raise RuntimeError("OpenCode server startup timed out")
            url = re.fullmatch(
                r"server listening on (http://127\.0\.0\.1:\d+)",
                server.stdout.readline().strip(),
            )
            if url is None:
                raise RuntimeError("OpenCode failed to start a private local server")
            # Keep server diagnostics flowing throughout long matches; only the client's
            # structured stdout belongs in the player's event stream.
            drain = threading.Thread(
                target=shutil.copyfileobj, args=(server.stdout, sys.stderr), daemon=True
            )
            drain.start()
            endpoint = ["--server", url[1]]
            deadline = time.monotonic() + 30
            while True:
                reply = subprocess.run(
                    [cli, "mcp", "list", *endpoint],
                    env=env,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=True,
                )
                status = reply.stdout.strip()
                if re.fullmatch(r"✓\s+arena\s+connected", status):
                    break
                if time.monotonic() >= deadline or server.poll() is not None:
                    raise RuntimeError(f"OpenCode MCP inventory is not ready: {status}")
                time.sleep(0.2)
            if argv == ["--check"]:
                print(status)
                return 0
            return subprocess.run(
                [cli, "run", *endpoint, *argv], env=env, check=False
            ).returncode
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
