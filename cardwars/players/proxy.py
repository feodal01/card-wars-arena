"""Relay MCP stdio to one already seat-bound Unix socket, without access to match storage."""
import os
import socket
import sys
import threading


def main() -> None:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.connect(sys.argv[1])

        def upload():
            try:
                while chunk := os.read(0, 65536):
                    connection.sendall(chunk)
                connection.shutdown(socket.SHUT_WR)
            except (BrokenPipeError, ConnectionResetError):
                return

        threading.Thread(target=upload, daemon=True).start()
        while chunk := connection.recv(65536):
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
