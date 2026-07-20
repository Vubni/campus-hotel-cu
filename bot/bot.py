"""Telegram-бот кампус-отелей «Диск» и «Облако».

Отвечает только за входящие: /start (привязка аккаунта к анкете) и кнопки
«Принять / Отклонить» под заявками. Сами уведомления шлёт бэкенд — так они
не потеряются, если бот перезапускается.

Вся логика заявок живёт в бэкенде: бот ходит в служебные ручки с общим
секретом и ничего не решает сам.
"""

import asyncio
import logging
import os

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bot")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
API_URL = os.getenv("API_URL", "http://backend:8000").rstrip("/")
BOT_SECRET = os.getenv("BOT_SECRET", "").strip()
SITE_URL = os.getenv("SITE_URL", "http://localhost:5173").rstrip("/")
# Прокси до api.telegram.org — нужен там, где Telegram заблокирован.
# Формат: http://user:pass@host:port или socks5://user:pass@host:port.
# Пусто — ходим напрямую.
TELEGRAM_PROXY_URL = os.getenv("TELEGRAM_PROXY_URL", "").strip()

dp = Dispatcher()


def api_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=API_URL, timeout=10, headers={"X-Bot-Secret": BOT_SECRET}
    )


@dp.message(Command("start"))
async def cmd_start(message: Message):
    user = message.from_user
    async with api_client() as client:
        try:
            resp = await client.post(
                "/api/bot/link",
                json={
                    "telegram_id": user.id,
                    "chat_id": message.chat.id,
                    "username": user.username,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            log.warning("link failed: %s", exc)
            await message.answer("Сайт сейчас недоступен, попробуй позже.")
            return

    if not data.get("linked"):
        # Раньше здесь просили вручную вписать ник в анкету: бот искал её
        # только по нику. Теперь мини-апп подтверждает человека подписью
        # Telegram и подставляет ник с фото сам — просить больше нечего.
        await message.answer(
            "👋 Привет! Я бот <b>кампус-отелей Диск и Облако</b>.\n\n"
            "Не нашёл твою анкету. Открой приложение кнопкой снизу — рядом с "
            "полем ввода — и заполни анкету: имя, фото и ник подтянутся из "
            "Telegram сами.\n\n"
            "После этого уведомления включатся автоматически."
        )
        return

    profile = data["profile"]
    campus = profile.get("campus")
    where = f" Ты в кампус-отеле <b>{campus}</b>." if campus else ""
    await message.answer(
        f"✅ Привет, {profile['name']}! Уведомления включены.{where}\n\n"
        "Буду писать, когда кто-то попросится к тебе в комнату, когда твою "
        "заявку рассмотрят, когда сосед выйдет из комнаты и когда в ней "
        "изменят число мест.\n\n"
        "/pending — заявки, ждущие твоего решения"
    )


@dp.message(Command("pending"))
async def cmd_pending(message: Message):
    async with api_client() as client:
        try:
            resp = await client.get(
                "/api/bot/pending", params={"telegram_id": message.from_user.id}
            )
            resp.raise_for_status()
            items = resp.json()["requests"]
        except httpx.HTTPError:
            await message.answer("Сайт сейчас недоступен, попробуй позже.")
            return

    if not items:
        await message.answer("Заявок, ждущих твоего решения, нет 👌")
        return

    for item in items:
        await message.answer(
            f"🔔 <b>{item['who']}</b> просится в комнату на {item['capacity']}.\n"
            f"@{item['telegram']}",
            reply_markup={
                "inline_keyboard": [
                    [
                        {
                            "text": "✅ Принять",
                            "callback_data": f"vote:{item['id']}:yes",
                        },
                        {
                            "text": "✖️ Отклонить",
                            "callback_data": f"vote:{item['id']}:no",
                        },
                    ]
                ]
            },
        )


@dp.callback_query(F.data.startswith("invite:"))
async def on_invite(call: CallbackQuery):
    """«Давай жить вместе»: комната создаётся только по согласию."""
    _, invite_id, decision = call.data.split(":")
    accept = decision == "yes"

    async with api_client() as client:
        try:
            resp = await client.post(
                "/api/bot/invite",
                json={
                    "telegram_id": call.from_user.id,
                    "invite_id": int(invite_id),
                    "accept": accept,
                },
            )
        except httpx.HTTPError:
            await call.answer("Сайт недоступен, попробуй позже", show_alert=True)
            return

    if resp.status_code != 200:
        detail = resp.json().get("detail", "Не получилось")
        await call.answer(detail, show_alert=True)
        if resp.status_code == 409:
            await call.message.edit_reply_markup(reply_markup=None)
        return

    data = resp.json()
    if data["status"] == "accepted":
        tail = f"🤝 Готово — комната на {data['capacity']} создана."
    else:
        tail = "✖️ Ты отказал(а)ся."

    await call.answer("Готово")
    await call.message.edit_text(f"{call.message.html_text}\n\n{tail}")


@dp.callback_query(F.data.startswith("vote:"))
async def on_vote(call: CallbackQuery):
    _, request_id, decision = call.data.split(":")
    approve = decision == "yes"

    async with api_client() as client:
        try:
            resp = await client.post(
                "/api/bot/vote",
                json={
                    "telegram_id": call.from_user.id,
                    "request_id": int(request_id),
                    "approve": approve,
                },
            )
        except httpx.HTTPError:
            await call.answer("Сайт недоступен, попробуй позже", show_alert=True)
            return

    if resp.status_code != 200:
        detail = resp.json().get("detail", "Не получилось")
        await call.answer(detail, show_alert=True)
        # Заявку уже закрыли — убираем кнопки, чтобы не жали впустую.
        if resp.status_code == 409:
            await call.message.edit_reply_markup(reply_markup=None)
        return

    data = resp.json()
    if data["status"] == "approved":
        tail = f"✅ {data['who']} принят(а) — все согласились."
    elif data["status"] == "rejected":
        tail = f"✖️ Заявка {data['who']} отклонена."
    else:
        tail = (
            f"Твой голос учтён: {data['votes_done']} из {data['votes_needed']}. "
            "Ждём остальных."
        )

    await call.answer("Готово")
    await call.message.edit_text(f"{call.message.html_text}\n\n{tail}")


async def main():
    if not TOKEN:
        raise SystemExit("Нет TELEGRAM_BOT_TOKEN — боту нечего делать")
    if not BOT_SECRET:
        raise SystemExit("Нет BOT_SECRET — бэкенд не пустит бота в служебные ручки")

    # Сообщения размечены HTML-тегами — задаём parse_mode по умолчанию.
    # Прокси (если задан) заворачивает все запросы к Telegram, включая polling.
    session = AiohttpSession(proxy=TELEGRAM_PROXY_URL) if TELEGRAM_PROXY_URL else None
    if TELEGRAM_PROXY_URL:
        log.info("Хожу в Telegram через прокси")
    bot = Bot(
        token=TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    # На всякий случай снимаем вебхук: мы работаем на long polling.
    await bot.delete_webhook(drop_pending_updates=False)
    log.info("Бот запущен, слушаю обновления")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
