import asyncio
import hashlib
import hmac
import json
import time
from typing import Optional
from urllib.parse import parse_qsl

import httpx

from config import (
    AUTH_MAX_AGE_SECONDS,
    MAX_UPLOAD_BYTES,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_PROXY_URL,
)


class TelegramAuthError(Exception):
    pass


def _data_check_string(payload: dict) -> str:
    return "\n".join(f"{k}={payload[k]}" for k in sorted(payload))


def _matches(data_check_string: str, secret_key: bytes, provided_hash: str) -> bool:
    calculated = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(calculated, provided_hash)


def _check_age(auth_date) -> None:
    try:
        issued = int(auth_date)
    except (TypeError, ValueError):
        raise TelegramAuthError("Некорректный auth_date")
    if time.time() - issued > AUTH_MAX_AGE_SECONDS:
        raise TelegramAuthError("Подпись Telegram устарела, войди заново")


def verify_login_widget(data: dict) -> dict:
    """Проверка данных Telegram Login Widget.

    Ключ: secret = SHA256(bot_token).
    https://core.telegram.org/widgets/login#checking-authorization
    """
    if not TELEGRAM_BOT_TOKEN:
        raise TelegramAuthError("Вход через Telegram не настроен на сервере")

    payload = {k: v for k, v in data.items() if v is not None}
    provided = payload.pop("hash", None)
    if not provided:
        raise TelegramAuthError("Нет подписи (hash)")

    secret_key = hashlib.sha256(TELEGRAM_BOT_TOKEN.encode("utf-8")).digest()
    if not _matches(_data_check_string(payload), secret_key, provided):
        raise TelegramAuthError("Подпись Telegram не совпала")

    _check_age(payload.get("auth_date"))
    return payload


def verify_webapp_init_data(init_data: str) -> dict:
    """Проверка initData из Telegram Mini App (telegram-web-app.js).

    Ключ: secret = HMAC_SHA256(key="WebAppData", msg=bot_token) — отличается
    от схемы Login Widget.
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not TELEGRAM_BOT_TOKEN:
        raise TelegramAuthError("Вход через Telegram не настроен на сервере")

    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        raise TelegramAuthError("Некорректный initData")

    provided = pairs.pop("hash", None)
    if not provided:
        raise TelegramAuthError("Нет подписи (hash)")

    secret_key = hmac.new(
        b"WebAppData", TELEGRAM_BOT_TOKEN.encode("utf-8"), hashlib.sha256
    ).digest()
    if not _matches(_data_check_string(pairs), secret_key, provided):
        raise TelegramAuthError("Подпись Telegram не совпала")

    _check_age(pairs.get("auth_date"))

    try:
        user = json.loads(pairs.get("user", "{}"))
    except json.JSONDecodeError:
        raise TelegramAuthError("Некорректные данные пользователя")
    if not user:
        raise TelegramAuthError("Telegram не передал данные пользователя")
    return user


async def fetch_profile_photos(
    telegram_id: int, limit: int = 6, offset: int = 0
) -> tuple[list[bytes], int]:
    """Скачивает аватарки пользователя — у многих их несколько.

    Через Bot API: getUserProfilePhotos отдаёт список, каждая аватарка — набор
    размеров; берём самый крупный. Возвращаем сами картинки (вызывающий их
    сохранит) и общее число аватарок, чтобы знать, есть ли что догружать.

    Порциями: тянуть сразу все — долго, особенно через прокси.
    """
    if not TELEGRAM_BOT_TOKEN:
        return [], 0

    api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    files = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}"
    try:
        async with httpx.AsyncClient(
            timeout=15, follow_redirects=True, proxy=TELEGRAM_PROXY_URL
        ) as client:
            resp = await client.get(
                f"{api}/getUserProfilePhotos",
                params={"user_id": telegram_id, "limit": limit, "offset": offset},
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                return [], 0

            result = data["result"]
            total = int(result.get("total_count", 0))

            async def one(sizes: list) -> Optional[bytes]:
                """Одна аватарка: получаем путь к файлу и скачиваем."""
                if not sizes:
                    return None
                # Размеры отсортированы по возрастанию — берём последний.
                info = await client.get(
                    f"{api}/getFile", params={"file_id": sizes[-1]["file_id"]}
                )
                if info.status_code != 200 or not info.json().get("ok"):
                    return None
                path = info.json()["result"].get("file_path")
                if not path:
                    return None
                blob = await client.get(f"{files}/{path}")
                if blob.status_code != 200 or len(blob.content) > MAX_UPLOAD_BYTES:
                    return None
                return blob.content

            # Параллельно: последовательное скачивание заметно медленнее.
            loaded = await asyncio.gather(
                *(one(sizes) for sizes in result.get("photos", [])),
                return_exceptions=True,
            )
            photos = [b for b in loaded if isinstance(b, bytes)]
            return photos, total
    except (httpx.HTTPError, httpx.InvalidURL, KeyError, ValueError):
        # Аватарки — приятное дополнение: не смогли получить, не страшно.
        return [], 0


async def fetch_usernames(telegram_ids: list[int]) -> dict[int, str]:
    """Ники по Telegram ID через getChat.

    Нужно для выгрузки: у части анкет ник пустой или устарел (человек его
    сменил), а связаться с ним по одному числовому ID нельзя.

    Telegram отдаёт данные только про тех, кого бот «видел» — то есть кто
    хоть раз ему написал. На остальных просто не будет ответа: это лучше,
    чем ничего, и ошибкой выгрузку не роняет.
    """
    if not TELEGRAM_BOT_TOKEN or not telegram_ids:
        return {}

    api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
    found: dict[int, str] = {}
    try:
        async with httpx.AsyncClient(timeout=15, proxy=TELEGRAM_PROXY_URL) as client:

            async def one(chat_id: int) -> tuple[int, Optional[str]]:
                try:
                    resp = await client.get(
                        f"{api}/getChat", params={"chat_id": chat_id}
                    )
                    if resp.status_code != 200:
                        return chat_id, None
                    data = resp.json()
                    if not data.get("ok"):
                        return chat_id, None
                    return chat_id, data["result"].get("username")
                except (httpx.HTTPError, KeyError, ValueError):
                    return chat_id, None

            # Bot API ограничивает частоту запросов — идём небольшими пачками.
            for start in range(0, len(telegram_ids), 10):
                chunk = telegram_ids[start : start + 10]
                for chat_id, username in await asyncio.gather(
                    *(one(cid) for cid in chunk)
                ):
                    if username:
                        found[chat_id] = str(username).lstrip("@")
    except (httpx.HTTPError, httpx.InvalidURL):
        return found
    return found


async def download_avatar(url: str) -> Optional[bytes]:
    """Скачивает аватар с CDN Telegram.

    Ссылки t.me/i/userpic/... живут недолго, поэтому картинку сохраняем у себя.
    """
    try:
        async with httpx.AsyncClient(
            timeout=10, follow_redirects=True, proxy=TELEGRAM_PROXY_URL
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            if len(resp.content) > MAX_UPLOAD_BYTES:
                return None
            return resp.content
    except (httpx.HTTPError, httpx.InvalidURL):
        return None
