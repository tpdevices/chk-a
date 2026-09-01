"""Per-cycle correlation id context (Loop 7).

A :class:`contextvars.ContextVar` carries a correlation id through an entire
monitoring cycle so every log line emitted during that cycle can be traced
back to it. The :class:`~chk_a.utils.logger.JSONFormatter` reads this var and
attaches ``correlation_id`` to each JSON record automatically.
"""

from __future__ import annotations

import contextvars
from typing import Optional
from uuid import uuid4

correlation_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "chk_a_correlation_id", default=None
)


def new_correlation_id() -> str:
    """Generate a fresh correlation id (uuid4 hex)."""
    return uuid4().hex


def set_correlation_id(cid: Optional[str]) -> None:
    """Set the correlation id for the current context."""
    correlation_id_var.set(cid)


def get_correlation_id() -> Optional[str]:
    """Return the correlation id for the current context (or ``None``)."""
    return correlation_id_var.get()
