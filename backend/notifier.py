"""Отправка уведомлений в Telegram.

Сообщения шлёт сам бэкенд через Bot API — отдельный процесс бота нужен только
для входящих (/start и кнопки). Так уведомление не теряется, если бот перезапущен.
"""

import logging
from typing import List, Optional, Union

import httpx

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_PROXY_URL

log = logging.getLogger(__name__)

API = "https://api.telegram.org/bot{token}/{method}"


async def deliver(messages: List[dict]) -> None:
    """Отправляет пачку сообщений. Запускается в фоне (BackgroundTasks), уже
    после того как ответ ушёл клиенту — поэтому сетевые задержки Telegram не
    тормозят действия на сайте. Каждое сообщение — dict с chat_id/text/markup.
    """
    for msg in messages:
        await send_message(
            msg["chat_id"],
            msg["text"],
            msg.get("reply_markup"),
            msg.get("message_thread_id"),
        )


async def send_message(
    chat_id: Union[int, str],  # личка — id, общая лента — id или @ник группы
    text: str,
    reply_markup: Optional[dict] = None,
    message_thread_id: Optional[int] = None,
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
    # Тема супергруппы. Без него сообщение уходит в «General», а не туда,
    # где его ждут.
    if message_thread_id:
        payload["message_thread_id"] = message_thread_id

    try:
        async with httpx.AsyncClient(timeout=10, proxy=TELEGRAM_PROXY_URL) as client:
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


class DocumentError(Exception):
    """Файл не ушёл в Telegram — в отличие от уведомлений, об этом надо сказать.

    Человек нажал «выгрузить» и ждёт файл: молча проглотить ошибку нельзя,
    иначе он будет искать в чате то, чего там нет.
    """


async def send_document(
    chat_id: int, filename: str, content: bytes, caption: str = ""
) -> None:
    """Отправляет файл в личку. Бросает DocumentError, если не получилось."""
    if not TELEGRAM_BOT_TOKEN:
        raise DocumentError("Бот не настроен на сервере")
    if not chat_id:
        raise DocumentError("Неизвестно, в какой чат отправлять")

    try:
        async with httpx.AsyncClient(timeout=60, proxy=TELEGRAM_PROXY_URL) as client:
            resp = await client.post(
                API.format(token=TELEGRAM_BOT_TOKEN, method="sendDocument"),
                data={"chat_id": str(chat_id), "caption": caption[:1024]},
                files={"document": (filename, content)},
            )
    except httpx.HTTPError as exc:
        log.warning("Не смог отправить файл в Telegram: %s", exc)
        raise DocumentError("Telegram не отвечает, попробуй ещё раз")

    if resp.status_code != 200:
        # Причину не угадываем — в мини-апп заходят из чата с ботом, так что
        # обычное «нажми /start» тут ни при чём. Подробности пишем в лог.
        log.warning("Telegram не принял файл: %s", resp.text[:200])
        raise DocumentError("Telegram не принял файл, попробуй ещё раз")


def open_profile_keyboard(url: str) -> dict:
    """Кнопка «открыть анкету» под сообщением в общей ленте.

    Именно url, а не web_app: web_app-кнопки Telegram разрешает только в
    личке, в группе такая клавиатура не отправится вовсе.
    """
    return {"inline_keyboard": [[{"text": "👀 Открыть анкету", "url": url}]]}


def invite_keyboard(invite_id: int) -> dict:
    """Кнопки под приглашением «давай жить вместе»."""
    return {
        "inline_keyboard": [
            [
                {"text": "🤝 Согласен", "callback_data": f"invite:{invite_id}:yes"},
                {"text": "✖️ Отказаться", "callback_data": f"invite:{invite_id}:no"},
            ]
        ]
    }


def block_keyboard(request_id: int) -> dict:
    """Кнопки под предложением объединиться в блок."""
    return {
        "inline_keyboard": [
            [
                {"text": "🧩 Объединиться", "callback_data": f"block:{request_id}:yes"},
                {"text": "✖️ Отказаться", "callback_data": f"block:{request_id}:no"},
            ]
        ]
    }


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
