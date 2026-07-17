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


def telegram_enabled() -> bool:
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_USERNAME)
