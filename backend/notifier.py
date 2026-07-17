"""Отправка уведомлений в Telegram.

Сообщения шлёт сам бэкенд через Bot API — отдельный процесс бота нужен только
для входящих (/start и кнопки). Так уведомление не теряется, если бот перезапущен.
"""

import logging
from typing import Optional

import httpx

from config import TELEGRAM_BOT_TOKEN

log = logging.getLogger(__name__)

API = "https://api.telegram.org/bot{token}/{method}"


async def send_message(
    chat_id: int, text: str, reply_markup: Optional[dict] = None
) -> bool:
    """Шлёт сообщение. Никогда не роняет вызывающий код.

    Уведомление — не критичная часть: если бот не настроен или человек не нажал
    /start, действие на сайте всё равно должно пройти.
    """
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        return False

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                API.format(token=TELEGRAM_BOT_TOKEN, method="sendMessage"),
                json=payload,
            )
        if resp.status_code != 200:
            # Частый случай: человек не начал диалог с ботом (403).
            log.warning("Telegram не принял сообщение: %s", resp.text[:200])
            return False
        return True
    except httpx.HTTPError as exc:
        log.warning("Не смог отправить в Telegram: %s", exc)
        return False


def vote_keyboard(request_id: int) -> dict:
    """Кнопки «Принять / Отклонить» под заявкой."""
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Принять", "callback_data": f"vote:{request_id}:yes"},
                {"text": "✖️ Отклонить", "callback_data": f"vote:{request_id}:no"},
            ]
        ]
    }
