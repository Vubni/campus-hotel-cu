import os
from pathlib import Path
from typing import Optional

# Токен и имя бота из @BotFather. Без них вход через Telegram отключается,
# а загрузка фото файлом продолжает работать.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", 5 * 1024 * 1024))

# Насколько свежей должна быть подпись Telegram (защита от replay).
AUTH_MAX_AGE_SECONDS = int(os.getenv("TELEGRAM_AUTH_MAX_AGE", 24 * 60 * 60))


# Общий секрет между ботом и бэкендом: бот ходит в служебные ручки от имени
# Telegram-пользователя, и без секрета так смог бы кто угодно.
BOT_SECRET = os.getenv("BOT_SECRET", "").strip()

# Адрес сайта — подставляем в ссылки внутри сообщений бота.
SITE_URL = os.getenv("SITE_URL", "http://localhost:5173").rstrip("/")

# Короткое имя мини-аппа из @BotFather (t.me/<бот>/<это имя>). Пусто — считаем,
# что мини-апп подключён как главный, и ссылка идёт просто на бота.
TELEGRAM_MINIAPP_SHORT_NAME = os.getenv("TELEGRAM_MINIAPP_SHORT_NAME", "").strip()


def _supergroup_chat_id(raw: str) -> Optional[int]:
    """Chat id супергруппы из переменной окружения.

    Telegram показывает id супергруппы и без префикса «-100» (например, в
    ссылках и в сторонних клиентах), а Bot API принимает только полный вид.
    Чтобы не ловить «chat not found» из-за формата, дописываем префикс сами.
    """
    raw = raw.strip()
    if not raw.lstrip("-").isdigit():
        return None
    value = int(raw)
    if value > 0:
        return int(f"-100{value}")
    return value


# Общая лента: чат, куда бот пишет о каждой новой анкете. Это супергруппа с
# темами, поэтому кроме чата нужен и номер темы (message_thread_id) — без него
# сообщение упадёт в «General». Пусто — в ленту просто ничего не пишем.
FEED_CHAT_ID = _supergroup_chat_id(os.getenv("TELEGRAM_FEED_CHAT_ID", ""))
_feed_thread = os.getenv("TELEGRAM_FEED_THREAD_ID", "").strip()
FEED_THREAD_ID = int(_feed_thread) if _feed_thread.isdigit() else None


def profile_link(profile_id: int) -> str:
    """Ссылка, открывающая мини-апп сразу на нужной анкете.

    Внутри группы кнопка может быть только обычной url-кнопкой (web_app
    Telegram разрешает лишь в личке), поэтому ведём через t.me — он откроет
    мини-апп, а не браузер. start_param разбирает фронтенд.
    """
    param = f"p{profile_id}"
    if TELEGRAM_BOT_USERNAME:
        if TELEGRAM_MINIAPP_SHORT_NAME:
            return (
                f"https://t.me/{TELEGRAM_BOT_USERNAME}/"
                f"{TELEGRAM_MINIAPP_SHORT_NAME}?startapp={param}"
            )
        return f"https://t.me/{TELEGRAM_BOT_USERNAME}?startapp={param}"
    # Бота нет — остаётся обычный сайт: тот же параметр читается из адреса.
    return f"{SITE_URL}/?profile={profile_id}"


# Владельцы сервиса. Держим прямо здесь, чтобы админка работала сразу после
# развёртывания, без лишней переменной окружения. ADMIN_TELEGRAM_IDS (через
# запятую) заменяет этот список целиком — например, чтобы отозвать доступ.
DEFAULT_ADMIN_TELEGRAM_IDS = {716452039, 442325979}


def admin_telegram_ids() -> set[int]:
    """Кому доступна админка — Telegram ID через запятую.

    Личность подтверждается подписью Telegram, поэтому знание чужого ID
    ничего не даёт: подделать initData без токена бота нельзя.
    """
    raw = os.getenv("ADMIN_TELEGRAM_IDS", "").strip()
    if not raw:
        return set(DEFAULT_ADMIN_TELEGRAM_IDS)
    return {
        int(item.strip()) for item in raw.split(",") if item.strip().isdigit()
    }


ADMIN_TELEGRAM_IDS = admin_telegram_ids()


def allowed_origins() -> list[str]:
    """Origin'ы, которым браузер разрешит читать ответы API.

    ВАЖНО: это НЕ защита API. CORS проверяет только браузер — curl, скрипты и
    боты его игнорируют. Настоящая проверка личности — подпись Telegram
    (см. telegram_auth), CORS лишь мешает чужому сайту дёргать наш API из JS.

    По умолчанию — домен сайта из SITE_URL плюс локальная разработка.
    CORS_ORIGINS (через запятую) переопределяет список целиком.
    """
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if raw:
        return [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]
    origins = {SITE_URL}
    # Вите-дев и прод-контейнер на localhost — чтобы не ломать разработку.
    origins.update(
        ["http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173"]
    )
    return sorted(origins)

# Прокси до api.telegram.org и CDN Telegram — нужен там, где Telegram
# заблокирован. Формат: http://user:pass@host:port или socks5://user:pass@host:port.
# Пусто — ходим напрямую. Тот же прокси используется ботом.
TELEGRAM_PROXY_URL = os.getenv("TELEGRAM_PROXY_URL", "").strip() or None


def telegram_enabled() -> bool:
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_USERNAME)
