"""Telegram-бот «Кампус-отель Диск».

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
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bot")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
API_URL = os.getenv("API_URL", "http://backend:8000").rstrip("/")
BOT_SECRET = os.getenv("BOT_SECRET", "").strip()
SITE_URL = os.getenv("SITE_URL", "http://localhost:5173").rstrip("/")

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
        await message.answer(
            "👋 Привет! Я бот <b>Кампус-отель Диск</b>.\n\n"
            "Не нашёл твою анкету. Размести её на сайте — укажи там свой ник "
            f"@{user.username or '…'} — и снова нажми /start.\n\n{SITE_URL}"
        )
        return

    profile = data["profile"]
    await message.answer(
        f"✅ Привет, {profile['name']}! Уведомления включены.\n\n"
        "Буду писать, когда кто-то попросится к тебе в комнату, когда твою "
        "заявку рассмотрят и когда сосед выйдет из комнаты.\n\n"
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
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    # На всякий случай снимаем вебхук: мы работаем на long polling.
    await bot.delete_webhook(drop_pending_updates=False)
    log.info("Бот запущен, слушаю обновления")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
