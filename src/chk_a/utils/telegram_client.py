"""Async Telegram client with retry (Loop 4).

A thin wrapper around the Telegram Bot API ``sendMessage`` and ``sendPhoto``
endpoints. Network and HTTP errors are retried with ``tenacity`` (3 attempts,
exponential backoff). The client is intentionally dependency-light: ``aiohttp``
for the request, ``tenacity`` for resilience.

Security: Bot token is never logged. URL paths containing the token are masked
in all log output. User-supplied text/caption is HTML-escaped to prevent injection.
"""

from __future__ import annotations

import asyncio
import html
from pathlib import Path
from typing import Any

import aiohttp
from pydantic import SecretStr
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .logger import setup_logger

_API_BASE = "https://api.telegram.org"


def _html_escape(value: Any) -> str:
    """HTML escape a value for safe inclusion in Telegram HTML messages."""
    if value is None:
        return "N/A"
    return html.escape(str(value))


def _mask_token(text: str) -> str:
    """Mask bot token in log messages (keep first 4 and last 4 chars)."""
    if not text:
        return text
    # Pattern: bot<token>/method -> bot****...****/method
    import re
    return re.sub(
        r"bot([A-Za-z0-9_:]{8,})",
        lambda m: f"bot{m.group(1)[:4]}{'*' * max(0, len(m.group(1)) - 8)}{m.group(1)[-4:]}",
        text,
    )


def _mask_chat_id(text: str) -> str:
    """Mask chat_id in log messages."""
    if not text:
        return text
    import re
    # Mask numeric chat IDs (including negative for channels/groups)
    return re.sub(r"chat_id[=:]\s*-?\d+", "chat_id=***", text)


class TelegramClient:
    """Async sender for Telegram Bot API messages and photos."""

    def __init__(
        self,
        bot_token: SecretStr | str,
        logger_name: str = "chk_a.telegram",
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self.bot_token = bot_token.get_secret_value() if isinstance(bot_token, SecretStr) else bot_token
        self.logger = setup_logger(logger_name)
        self._session = session
        self._owns_session = session is None
        # Pre-compute masked token for logging
        self._masked_token = self._mask_token_for_log(self.bot_token)

    @staticmethod
    def _mask_token_for_log(token: str) -> str:
        """Return masked token for logging (first 4, last 4)."""
        if not token or len(token) < 8:
            return "***"
        return f"{token[:4]}{'*' * (len(token) - 8)}{token[-4:]}"

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    def _build_url(self, method: str) -> str:
        """Build API URL (token in path - masked in logs)."""
        return f"{_API_BASE}/bot{self.bot_token}/{method}"

    def _log_url(self, method: str) -> str:
        """Return URL with masked token for logging."""
        return f"{_API_BASE}/bot{self._masked_token}/{method}"

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
    )
    async def _post(self, payload: dict[str, Any]) -> None:
        session = await self._get_session()
        url = self._build_url("sendMessage")
        # Log with masked token
        self.logger.debug("POST %s payload=%s", self._log_url("sendMessage"), _mask_chat_id(str(payload)))
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
        url = self._build_url("sendPhoto")
        self.logger.debug("POST %s (multipart)", self._log_url("sendPhoto"))
        async with session.post(url, data=data, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            resp.raise_for_status()

    async def send_message(self, chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
        """Send ``text`` to ``chat_id``. Returns ``True`` on success, ``False`` otherwise."""
        if not self.bot_token or not chat_id:
            self.logger.warning("Telegram send skipped: missing bot_token or chat_id")
            return False
        try:
            # HTML escape user-supplied text to prevent injection
            safe_text = _html_escape(text)
            await self._post({"chat_id": chat_id, "text": safe_text, "parse_mode": parse_mode})
            self.logger.info("Telegram message sent to chat_id=%s", _mask_chat_id(f"chat_id={chat_id}"))
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
            # Stream file instead of reading all into memory
            data = aiohttp.FormData()
            data.add_field("chat_id", chat_id)
            if caption:
                # HTML escape user-supplied caption to prevent injection
                safe_caption = _html_escape(caption)
                data.add_field("caption", safe_caption)
                data.add_field("parse_mode", parse_mode)
            # Add photo file - stream from file
            data.add_field(
                "photo", photo_path.open("rb"), filename=photo_path.name, content_type="image/jpeg"
            )
            await self._post_multipart(data)
            self.logger.info("Telegram photo sent to chat_id=%s file=%s", _mask_chat_id(f"chat_id={chat_id}"), photo_path.name)
            return True
        except Exception as exc:
            self.logger.warning("Telegram photo send failed: %s", exc)
            return False

    async def close(self) -> None:
        """Close the underlying session if we own it."""
        if self._session is not None and self._owns_session and not self._session.closed:
            await self._session.close()


__all__ = ["TelegramClient"]