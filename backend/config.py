import os
from pathlib import Path

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
