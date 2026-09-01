"""Dependency-free systemd sd_notify helper (Loop 6).

Sends readiness and watchdog pings to systemd over ``$NOTIFY_SOCKET`` without
requiring the optional ``systemd-python`` package (which does not build on
Python 3.14+). Falls back to a no-op when not running under systemd.
"""

from __future__ import annotations

import os
import socket


def _send(state: str) -> bool:
    """Send a single newline-terminated ``state`` string to ``$NOTIFY_SOCKET``.

    Returns ``True`` if the datagram was sent, ``False`` if not running under
    systemd or the socket is unavailable.
    """
    sock_path = os.environ.get("NOTIFY_SOCKET")
    if not sock_path:
        return False
    # Abstract sockets are denoted by an initial '@' which maps to a NUL byte.
    if sock_path[0] == "@":
        sock_path = "\0" + sock_path[1:]
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        with sock:
            sock.connect(sock_path)
            sock.sendall((state + "\n").encode("utf-8"))
        return True
    except OSError:
        return False


def notify_ready() -> bool:
    """Tell systemd the service has finished starting up."""
    return _send("READY=1")


def notify_watchdog() -> bool:
    """Tell systemd the service is still alive (for ``WatchdogSec``)."""
    return _send("WATCHDOG=1")


def notify_stopping() -> bool:
    """Tell systemd the service is stopping."""
    return _send("STOPPING=1")


__all__ = ["notify_ready", "notify_watchdog", "notify_stopping"]
