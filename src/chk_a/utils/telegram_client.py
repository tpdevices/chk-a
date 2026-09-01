"""Async Telegram client with retry (Loop 4).

A thin wrapper around the Telegram Bot API ``sendMessage`` and ``sendPhoto``
endpoints. Network and HTTP errors are retried with ``tenacity`` (3 attempts,
exponential backoff). The client is intentionally dependency-light: ``aiohttp``
for the request, ``tenacity`` for resilience.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import aiohttp
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .logger import setup_logger

_API_BASE = "https://api.telegram.org"


class TelegramClient:
    """Async sender for Telegram Bot API messages and photos."""

    def __init__(
        self,
        bot_token: str,
        logger_name: str = "chk_a.telegram",
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self.bot_token = bot_token
        self.logger = setup_logger(logger_name)
        self._session = session
        self._owns_session = session is None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
    )
    async def _post(self, payload: dict[str, Any]) -> None:
        session = await self._get_session()
        url = f"{_API_BASE}/bot{self.bot_token}/sendMessage"
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            resp.raise_for_status()

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
    )
    async def _post_multipart(self, data: aiohttp.FormData) -> None:
        session = await self._get_session()
        url = f"{_API_BASE}/bot{self.bot_token}/sendPhoto"
        async with session.post(url, data=data, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            resp.raise_for_status()

    async def send_message(self, chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
        """Send ``text`` to ``chat_id``. Returns ``True`` on success, ``False`` otherwise."""
        if not self.bot_token or not chat_id:
            self.logger.warning("Telegram send skipped: missing bot_token or chat_id")
            return False
        try:
            await self._post({"chat_id": chat_id, "text": text, "parse_mode": parse_mode})
            return True
        except Exception as exc:  # network / HTTP / retry exhaustion
            self.logger.warning("Telegram send failed: %s", exc)
            return False

    async def send_photo(
        self,
        chat_id: str,
        photo_path: str | Path,
        caption: str | None = None,
        parse_mode: str = "HTML",
    ) -> bool:
        """Send a photo to ``chat_id``. Returns ``True`` on success, ``False`` otherwise."""
        if not self.bot_token or not chat_id:
            self.logger.warning("Telegram photo send skipped: missing bot_token or chat_id")
            return False
        photo_path = Path(photo_path)
        if not photo_path.is_file():
            self.logger.warning("Telegram photo send skipped: file not found: %s", photo_path)
            return False
        try:
            # Read file into memory so we can close it before the request
            photo_bytes = photo_path.read_bytes()
            data = aiohttp.FormData()
            data.add_field("chat_id", chat_id)
            if caption:
                data.add_field("caption", caption)
                data.add_field("parse_mode", parse_mode)
            # Add photo file
            data.add_field("photo", photo_bytes, filename=photo_path.name, content_type="image/jpeg")
            await self._post_multipart(data)
            return True
        except Exception as exc:
            self.logger.warning("Telegram photo send failed: %s", exc)
            return False

    async def close(self) -> None:
        """Close the underlying session if we own it."""
        if self._session is not None and self._owns_session and not self._session.closed:
            await self._session.close()


__all__ = ["TelegramClient"]
