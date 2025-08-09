import asyncio
import requests
from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from fragment_api_lib.client import FragmentAPIClient
import random, string
from lxml import html
import time

# --- НАСТРОЙКИ ---
STARS_SEED = "stamp member useful brick chest panic cram few regular wish device boy soldier bright abandon fantasy release east equip force crucial oblige borrow fragile"
STARS_WALLET = "UQBimhjgyaNdL7tNkvQF26T8llmevqau32tS2opyypF5U_z-"
STARS_WALLET_RAW = "0:629a18e0c9a35d2fbb4d92f405dba4fc96599ebea6aedf6b52da8a72ca917953"
TONAPI_KEY = "AEC4J4TEKH2MLBQAAAAKPYPJ7UBHN6WRMVTJGD73ES352YH7I4AA7P7O6AX6I6HVL5KZGUQ"

# --- Глобальный курс звёзд (обновляется через команду) ---
STARS_BASE_PRICE = 0.4567  # базовый курс, который задаёт админ

# --- FSM State для покупки звёзд ---
class BuyStarsStates(StatesGroup):
    waiting_for_stars_purchase_input = State()

# --- Команда для обновления курса звёзд ---
async def set_stars_price(message: types.Message):
    global STARS_BASE_PRICE
    try:
        parts = message.text.split()
        if len(parts) != 2:
            await message.answer("Использование: /setstarsprice 0.4789")
            return
        price = float(parts[1].replace(',', '.'))
        if price <= 0:
            raise ValueError
        STARS_BASE_PRICE = price
        await message.answer(f"Базовый курс звёзд обновлён: {STARS_BASE_PRICE} TON за 100 звёзд (оплата будет +2%)")
    except Exception:
        await message.answer("Ошибка! Использование: /setstarsprice 0.4789")

# --- 1. Обработчик кнопки "Купить звёзды" ---
async def handle_buy_stars_callback(callback_query: types.CallbackQuery, state: FSMContext):
    """Запрашивает username и количество звёзд у пользователя."""
    await callback_query.answer()
    await callback_query.message.answer(
        "Введите ваш Telegram username (например, @username) и количество звёзд, которые хотите купить.\n\nПример: @username 100\n\nПосле этого бот пришлёт вам счёт для оплаты TON, и после оплаты звёзды будут куплены и отправлены на ваш аккаунт.")
    await state.set_state(BuyStarsStates.waiting_for_stars_purchase_input)

# --- 2. Обработчик ввода username и количества звёзд ---
async def process_stars_purchase_input(message: types.Message, state: FSMContext, deals_db, payment_address):
    user_id = message.from_user.id
    text = message.text.strip()
    try:
        parts = text.split()
        if len(parts) != 2:
            raise ValueError
        username = parts[0]
        if username.startswith("@"): username = username[1:]
        amount = int(parts[1])
        if amount <= 0:
            raise ValueError
    except Exception:
        await message.answer("Неверный формат. Введите username и количество звёзд через пробел.\nПример: @username 100")
        return
    # Используем базовый курс +2%
    base_price = STARS_BASE_PRICE * (amount / 100)
    total_to_pay = round(base_price * 1.02, 6)
    payment_memo = ''.join(random.choices(string.ascii_lowercase + string.digits, k=15))
    await state.update_data(username=username, amount=amount, total_to_pay=total_to_pay, payment_memo=payment_memo)
    tonkeeper_url = (
        f"ton://transfer/{payment_address}"
        f"?amount={int(total_to_pay * 1e9)}"
        f"&text={payment_memo}"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Оплатить в Tonkeeper", url=tonkeeper_url)]
    ])
    await message.answer(
        f"Для покупки {amount} звёзд оплатите <b>{total_to_pay} TON</b> на адрес:\n"
        f"<code>{payment_address}</code>\n\n"
        f"Комментарий (MEMO): <code>{payment_memo}</code>",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    deal_id = payment_memo
    deals_db[deal_id] = {
        "type": "buy_stars",
        "user_id": user_id,
        "username": username,
        "amount": amount,
        "total_to_pay": total_to_pay,
        "payment_memo": payment_memo
    }
    await state.clear()

# --- 3. Watcher: отслеживает входящие платежи и инициирует покупку звёзд ---
async def stars_payment_watcher(bot, deals_db):
    processed_deals = set()
    headers = {"Authorization": f"Bearer {TONAPI_KEY}"}
    while True:
        try:
            url = f"https://tonapi.io/v2/blockchain/accounts/{STARS_WALLET_RAW}/transactions?limit=30"
            response = requests.get(url, headers=headers)
            data = response.json()
            txs = data.get("transactions", [])
            for tx in txs:
                in_msg = tx.get("in_msg", {})
                memo = None
                if "decoded_body" in in_msg and isinstance(in_msg["decoded_body"], dict):
                    memo = in_msg["decoded_body"].get("text")
                value = int(in_msg.get("value", 0))
                destination = in_msg.get("destination")
                tx_hash = tx.get("hash")
                if isinstance(destination, dict):
                    dest_addr = destination.get("address")
                else:
                    dest_addr = destination
                # Проверяем только raw-адрес
                if dest_addr != STARS_WALLET_RAW:
                    continue
                if not memo or not value or not tx_hash:
                    continue
                for deal_id, deal in deals_db.items():
                    if deal_id in processed_deals:
                        continue
                    if deal.get("type") != "buy_stars":
                        continue
                    expected_memo = deal.get("payment_memo")
                    total_amount = int(float(deal.get("total_to_pay", 0)) * 1e9)
                    buyer_id = deal.get("user_id")
                    if memo == expected_memo and value == total_amount:
                        try:
                            client = FragmentAPIClient()
                            res = client.buy_stars_without_kyc(
                                username=deal["username"],
                                amount=deal["amount"],
                                seed=STARS_SEED
                            )
                            await bot.send_message(buyer_id, f"Звёзды успешно куплены и отправлены на ваш аккаунт @{deal['username']}!")
                        except Exception as e:
                            await bot.send_message(buyer_id, f"Ошибка при покупке звёзд: {e}")
                        processed_deals.add(deal_id)
                        break
        except Exception as e:
            print(f"[STARS_WATCHER] Tonapi watcher error: {e}")
        await asyncio.sleep(1)

# Экспортируем только нужные функции и классы:
__all__ = [
    "BuyStarsStates",
    "handle_buy_stars_callback",
    "process_stars_purchase_input",
    "stars_payment_watcher",
    "set_stars_price"
] 