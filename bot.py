import os
import uuid
import asyncio
import logging
import aiohttp
from hashlib import md5

from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineQuery, InlineQueryResultCachedPhoto, InlineKeyboardMarkup, InlineKeyboardButton

from fastapi import FastAPI, Request, Header
from uvicorn import Config, Server

from dotenv import load_dotenv
from database import init_db, add_payment, get_payment_by_result_id, update_payment, get_payment

load_dotenv()

# logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('payments.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

API_TOKEN = os.getenv("API_TOKEN")
MARKET_API_TOKEN = os.getenv("MARKET_API_TOKEN")
MERCHANT_TOKEN = os.getenv("MERCHANT_TOKEN")
MERCHANT_ID = int(os.getenv("MERCHANT_ID"))
SUCCESS_URL = os.getenv("SUCCESS_URL")
COMMENT = os.getenv("COMMENT")
IMAGE = os.getenv("IMAGE")
ADMINS = [int(x) for x in os.getenv("ADMINS", "").split(",") if x]
CALLBACK_URL = os.getenv("CALLBACK_URL", "")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
app = FastAPI()

server = None


async def create_invoice(amount: int, payment_id: str) -> dict:
    """создает инвойс через апи маркета"""
    url = "https://api.lzt.market/invoice"
    headers = {
        "Authorization": f"Bearer {MARKET_API_TOKEN}",
        "Content-Type": "application/json"
    }
    data = {
        "currency": "rub",
        "amount": amount,
        "payment_id": payment_id,
        "comment": COMMENT,
        "url_success": SUCCESS_URL,
        "url_callback": CALLBACK_URL,
        "merchant_id": MERCHANT_ID
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data, headers=headers) as resp:
            return await resp.json()


@dp.inline_handler()
async def inline_handler(query: InlineQuery):
    # только админы могут создавать инвойсы
    if query.from_user.id not in ADMINS:
        return

    text = query.query.strip()

    if not text.isdigit():
        return

    amount = int(text)
    if amount < 1:
        return

    payment_id = f"tg_{query.from_user.id}_{uuid.uuid4().hex[:8]}"
    result_id = md5(f"{payment_id}".encode()).hexdigest()

    caption = f"💳 Status: pending\n\n💵 Amount: {amount} RUB"

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("⏳ Loading...", callback_data="loading"))

    item = InlineQueryResultCachedPhoto(
        id=result_id,
        photo_file_id=IMAGE,
        caption=caption,
        reply_markup=kb
    )

    await add_payment(payment_id, result_id, amount)
    await query.answer([item], cache_time=1, is_personal=True)


@dp.chosen_inline_handler()
async def chosen_handler(chosen: types.ChosenInlineResult):
    """создаем инвойс после отправки сообщения"""
    result_id = chosen.result_id
    inline_message_id = chosen.inline_message_id

    if not inline_message_id:
        log.warning(f"no inline_message_id for result: {result_id}")
        return

    payment = await get_payment_by_result_id(result_id)
    if not payment:
        log.warning(f"payment not found for result_id: {result_id}")
        return

    payment_id = payment["payment_id"]
    amount = payment["amount"]

    await update_payment(payment_id, inline_message_id=inline_message_id)

    try:
        result = await create_invoice(amount, payment_id)
        invoice_url = result["invoice"]["url"]
    except Exception as e:
        log.error(f"err creating invoice: {e}")
        await bot.edit_message_caption(
            inline_message_id=inline_message_id,
            caption=f"💳 Status: error\n\n💵 Amount: {amount} RUB"
        )
        return

    await update_payment(payment_id, invoice_url=invoice_url, status="created")

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("💳 Pay", url=invoice_url))

    await bot.edit_message_caption(
        inline_message_id=inline_message_id,
        caption=f"💳 Status: created\n\n💵 Amount: {amount} RUB",
        reply_markup=kb
    )
    log.info(f"invoice created: {payment_id}, amount: {amount}")


@app.post("/webhook/payment")
async def payment_webhook(request: Request, x_secret_key: str = Header(None)):
    """вебхук от платежки"""

    if x_secret_key != MERCHANT_TOKEN:
        return {"error": "invalid secret"}

    data = await request.json()

    if data.get("status") != "paid":
        return {"ok": True}

    payment_id = data.get("payment_id")
    amount = data.get("amount", 0)

    payment_data = await get_payment(payment_id)
    if not payment_data:
        log.warning(f"payment not found: {payment_id}")
        return {"ok": True}

    inline_message_id = payment_data.get("inline_message_id")
    if not inline_message_id:
        log.warning(f"no inline_message_id for: {payment_id}")
        return {"ok": True}

    try:
        await bot.edit_message_caption(
            inline_message_id=inline_message_id,
            caption=f"💳 Status: paid ✅\n\n💵 Amount: {amount} RUB",
            reply_markup=None
        )
        await update_payment(payment_id, status="paid")
        log.info(f"payment completed: {payment_id}, amount: {amount}")
    except Exception as e:
        log.error(f"err updating msg: {e}")

    return {"ok": True}


async def start_webhook_server():
    global server
    config = Config(app=app, host="0.0.0.0", port=80, log_level="info")
    server = Server(config)
    await server.serve()


async def on_startup(_):
    await init_db()
    asyncio.create_task(start_webhook_server())
    log.info("bot started")


async def on_shutdown(_):
    if server:
        server.should_exit = True
    await bot.session.close()
    log.info("bot stopped")


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        executor.start_polling(dp, on_startup=on_startup, on_shutdown=on_shutdown, skip_updates=True)
    except KeyboardInterrupt:
        pass