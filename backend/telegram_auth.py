import hashlib
import hmac
import json
import time
from typing import Optional
from urllib.parse import parse_qsl

import httpx

from config import AUTH_MAX_AGE_SECONDS, MAX_UPLOAD_BYTES, TELEGRAM_BOT_TOKEN


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


async def download_avatar(url: str) -> Optional[bytes]:
    """Скачивает аватар с CDN Telegram.

    Ссылки t.me/i/userpic/... живут недолго, поэтому картинку сохраняем у себя.
    """
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            if len(resp.content) > MAX_UPLOAD_BYTES:
                return None
            return resp.content
    except (httpx.HTTPError, httpx.InvalidURL):
        return None
