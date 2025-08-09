import asyncio
import logging
import uuid
import requests
import os
import json
import base64
import subprocess
import time
import sqlite3
import random

from buy_stars import handle_buy_stars_callback, BuyStarsStates, process_stars_purchase_input, stars_payment_watcher, STARS_WALLET, set_stars_price, STARS_SEED
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile, BotCommand, InputMediaPhoto
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from fragment_api_lib.client import FragmentAPIClient
from aiogram.fsm.storage.memory import MemoryStorage
# Удаляю все импорты tontools и связанные функции

# Импортирую TonTools
# from tontools import Wallet, TonCenterClient

# Временное хранилище для сделок (в реальном приложении используйте базу данных)
deals_db_otc = {}    # Для обычных сделок
deals_db_stars = {}  # Для покупки звёзд
# Временное хранилище для кошельков пользователей
user_wallets = {}
# Временное хранилище для языковых настроек пользователей
user_languages = {}
# Словарь для хранения количества завершённых сделок
# user_completed_deals = {}

# --- Работа с SQLite для завершённых сделок ---
DB_PATH = 'deals.db'

pending_star_buy = set()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS completed_deals (
        user_id INTEGER PRIMARY KEY,
        count INTEGER DEFAULT 0
    )''')
    conn.commit()
    conn.close()

def get_completed_deals(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT count FROM completed_deals WHERE user_id=?', (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def increment_completed_deals(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO completed_deals (user_id, count) VALUES (?, 1) ON CONFLICT(user_id) DO UPDATE SET count = count + 1', (user_id,))
    conn.commit()
    conn.close()
# Seed-фраза кошелька бота для выплат
# BOT_SEED = "decade axis doctor rifle game soldier object armed dirt slot give cute spy cave next mixture duty grid shove appear more rather tortoise ribbon"
# Удаляю все импорты tonsdk

# Словарь для хранения локализованных строк
LANG_STRINGS = {
    "en": {
        "welcome_text": (
            "@nimbleotcbot - your reliable OTC assistant! 👋\n\n"
            "Buy and sell any goods and services with confidence!\n"
            "From Telegram gifts and stickers to tokens and fiat – deals are simple and secure.\n\n"
            "🏆 Safe transactions with TON\n"
            "💎 Commission only 3%\n"
            "🔒 Full protection\n\n"
            "Select an option:"
        ),
        "create_deal_btn": "🆕 New Deal",
        "wallet_btn": "💳 My Wallet",
        "referrals_btn": "🤝 Referrals",
        "deals_btn": "🛍️ My Deals",
        "language_btn": "🌐 Язык/Language",
        "support_btn": "🆘 Help",
        "back_btn": "⬅️ Back",
        "enter_amount": "💰 Please enter the TON amount for your deal (e.g., 10.5):",
        "amount_positive_error": "The amount must be greater than zero. Try again:",
        "amount_format_error": "Invalid format. Enter a number (e.g., 10.5):",
        "enter_description": "✏️ Describe your deal (e.g., 3x Not Cap Stickers):",
        "wallet_not_linked": (
            "🚫 To create a deal, you need to add your TON wallet.\n"
            "Tap 'My Wallet' in the menu to link it."
        ),
        "deal_created_success": "✅ Deal created!",
        "amount_label": "💰 Amount",
        "description_label": "📝 Details",
        "buyer_link_label": "🔗 Link for buyer",
        "commission_paid_by_buyer": "💔 Buyer covers the full commission.",
        "copy_link_btn": "🛍️ Copy Link",
        "cancel_deal_btn": "❌ Cancel Deal",
        "link_copied": "Link to deal #{deal_id} copied!",
        "deal_cancelled": "Deal #{deal_id} has been cancelled.",
        "wallet_current": "💳 Your wallet:",
        "wallet_not_linked_yet": "not set",
        "wallet_change_prompt": "🔄 To update, enter a new address:\n🔑 Format: EQ... or UQ...",
        "wallet_linked_success": "✅ TON wallet `{wallet_address}` saved!",
        "wallet_invalid_format": "❌ Invalid TON address. It must start with EQ or UQ. Try again:",
        "language_choose": "🌐 Choose your language:",
        "english_btn": "🇬🇧 English",
        "russian_btn": "🇷🇺 Russian",
        "language_switched_en": "Language switched to English.",
        "language_switched_ru": "Вы переключились на русский язык.",
        "back_to_main_menu_msg": "Returned to main menu.",
        "you_are_buyer": "🤝 You are the buyer in this deal",
        "seller_label": "🙋‍♀️ Seller",
        "successful_deals_label": "completed deals",
        "you_buy_label": "🛍️ You are buying",
        "payment_address_label": "🏦 Pay to address:",
        "payment_memo_label": "📝 Payment comment (MEMO):",
        "amount_to_pay_label": "💰 Total to pay:",
        "check_data_warning": "⚠️ Double-check before paying.\n**MEMO is required!**\n⏳ After payment, wait for confirmation.",
        "start_command_description": "Start the bot and open the main menu",
        "wallet_command_description": "Add or update your TON wallet",
        "scan_command_description": "Check user stickers",
        "partners_message": "Referral program info.",
        "partners_program_title": "🏆 Referral Program",
        "reward_label": "🏅 Reward",
        "you_receive": "└ You get: 40%",
        "statistics_label": "📊 Stats",
        "invited_label": "├ Invited: 0",
        "earned_label": "└ Earned: 0 TON",
        "your_referral_link_label": "🔗 Your referral link",
        "referral_condition": "If your referral completes deals for 100 TON — you get\n1.2 TON to your wallet 😉",
        "share_link_btn": "🔗 Share link",
        "deals_message": "You tapped 'My Deals'.",
        "support_message": "You tapped 'Help'.",
        "support_contact": "For support, contact @Ivanlebedef",
        "choose_action": "Select an action:"
    },
    "ru": {
        "welcome_text": (
            "@nimbleotcbot — ваш надежный OTC-бот! 👋\n\n"
            "Покупайте и продавайте любые товары и услуги с уверенностью!\n"
            "От Telegram-подарков и стикеров до токенов и фиата — сделки проходят просто и безопасно.\n\n"
            "🏆 Сделки с TON под защитой\n"
            "💎 Комиссия всего 3%\n"
            "🔒 Полная безопасность\n\n"
            "Выберите нужный пункт:"
        ),
        "create_deal_btn": "🆕 Новая сделка",
        "wallet_btn": "💳 Мой кошелек",
        "referrals_btn": "🤝 Рефералы",
        "deals_btn": "🛍️ Мои сделки",
        "language_btn": "🌍 Язык/Language",
        "support_btn": "🆘 Помощь",
        "back_btn": "⬅️ Назад",
        "enter_amount": "💰 Введите сумму сделки в TON (например, 10.5):",
        "amount_positive_error": "Сумма должна быть больше нуля. Попробуйте снова:",
        "amount_format_error": "Неверный формат. Введите число (например, 10.5):",
        "enter_description": "✏️ Опишите сделку (например, 3x Not Cap Stickers):",
        "wallet_not_linked": (
            "🚫 Для создания сделки добавьте TON-кошелек.\n"
            "Нажмите 'Мой кошелек' в меню для привязки."
        ),
        "deal_created_success": "✅ Сделка создана!",
        "amount_label": "💰 Сумма",
        "description_label": "📝 Детали",
        "buyer_link_label": "🔗 Ссылка для покупателя",
        "commission_paid_by_buyer": "💔 Комиссию полностью оплачивает покупатель.",
        "copy_link_btn": "🛍️ Скопировать ссылку",
        "cancel_deal_btn": "❌ Отменить сделку",
        "link_copied": "Ссылка на сделку #{deal_id} скопирована!",
        "deal_cancelled": "Сделка #{deal_id} отменена.",
        "wallet_current": "💳 Ваш кошелек:",
        "wallet_not_linked_yet": "не указан",
        "wallet_change_prompt": "🔄 Чтобы изменить, введите новый адрес:\n🔑 Формат: EQ... или UQ...",
        "wallet_linked_success": "✅ TON-кошелек `{wallet_address}` сохранён!",
        "wallet_invalid_format": "❌ Неверный адрес TON. Должен начинаться с EQ или UQ. Попробуйте снова:",
        "language_choose": "🌐 Выберите язык:",
        "english_btn": "🇬🇧 English",
        "russian_btn": "🇷🇺 Русский",
        "language_switched_en": "Вы переключились на английский язык.",
        "language_switched_ru": "Язык переключён на русский.",
        "back_to_main_menu_msg": "Вы вернулись в главное меню.",
        "you_are_buyer": "🤝 Вы — покупатель в этой сделке",
        "seller_label": "🙋‍♀️ Продавец",
        "successful_deals_label": "завершённых сделок",
        "you_buy_label": "🛍️ Вы покупаете",
        "payment_address_label": "🏦 Адрес для оплаты:",
        "payment_memo_label": "📝 Комментарий к платежу (MEMO):",
        "amount_to_pay_label": "💰 К оплате:",
        "check_data_warning": "⚠️ Проверьте данные перед оплатой.\n**MEMO обязателен!**\n⏳ После оплаты ожидайте подтверждения.",
        "start_command_description": "Запустить бота и открыть главное меню",
        "wallet_command_description": "Добавить или изменить TON-кошелек",
        "scan_command_description": "Проверить стикеры пользователя",
        "partners_message": "Информация о реферальной программе.",
        "partners_program_title": "🏆 Реферальная программа",
        "reward_label": "🏅 Вознаграждение",
        "you_receive": "└ Вы получаете: 40%",
        "statistics_label": "📊 Статистика",
        "invited_label": "├ Приглашено: 0",
        "earned_label": "└ Заработано: 0 TON",
        "your_referral_link_label": "🔗 Ваша реферальная ссылка",
        "referral_condition": "Если ваш реферал совершит сделок на 100 TON — вы получите\n1.2 TON на свой кошелек 😉",
        "share_link_btn": "🔗 Поделиться ссылкой",
        "deals_message": "Вы нажали 'Мои сделки'.",
        "support_message": "Вы нажали 'Помощь'.",
        "support_contact": "Для поддержки обращайтесь к @Ivanlebedef",
        "choose_action": "Выберите действие:"
    }
}

def get_text(user_id: int, key: str) -> str:
    """Возвращает локализованный текст по ключу и ID пользователя."""
    lang = user_languages.get(user_id, "ru") # По умолчанию русский
    return LANG_STRINGS[lang].get(key, LANG_STRINGS["ru"][key]) # Fallback to Russian


# Configure logging
logging.basicConfig(level=logging.INFO)

# Bot token from BotFather
TOKEN = "7732186774:AAGX0A2XPeY0G-8B61HfmVb2wAEQK2-2Js4"

# Адрес кошелька, который нужно отслеживать
TON_TRACK_ADDRESS = "UQDQoHshokE-7jJP2XRbr2LJLv4McWB2qETbGNTK7NEF8ktB"

# TONCENTER API KEY и адрес для отслеживания
TONAPI_KEY = "AEC4J4TE3DPZHAYAAAAOTKRT3QCHI33DTZYZOJQKIDL7SPPICM5JDKRU266ZFL2PN2XFTQA"
TRACK_ADDRESS = "0:d0a07b21a2413eee324fd9745baf62c92efe0c716076a844db18d4caecd105f2"

# --- НАСТРОЙКИ 1plat.cash ---
ONEPLAT_SHOP_ID = '604'
ONEPLAT_SECRET = 'ROS396U0Y71HMU95PIUUHCY2AQ1611Z6'
ONEPLAT_BASE_URL = 'https://1plat.cash'

import hashlib
import aiohttp
import requests

CRYSTALPAY_LOGIN = 'nimble'
CRYSTALPAY_SECRET = '55613b7dfbfad848f2dd79c5e3cc41d32a94fb08'
CRYSTALPAY_API = 'https://api.crystalpay.io/v3/'

# --- FSM для покупки звёзд за рубли через CrystalPAY API ---
class BuyStarsRubStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_username = State()
    waiting_for_method = State()

# --- Методы оплаты (можно получить через API, пока статично) ---
CRYSTALPAY_METHODS = [
    ("CRYSTALPAY", "💳 CrystalPAY P2P"),
    ("TEST", "🧪 Тестовый платёж")
]

# --- Создание инвойса через CrystalPAY API ---
def create_crystalpay_invoice(amount, description, lifetime=15, required_method=None, extra=None):
    data = {
        "auth_login": CRYSTALPAY_LOGIN,
        "auth_secret": CRYSTALPAY_SECRET,
        "amount": amount,
        "type": "purchase",
        "lifetime": lifetime,
        "description": description,
    }
    if required_method:
        data["required_method"] = required_method
    if extra:
        data["extra"] = extra
    resp = requests.post(CRYSTALPAY_API + 'invoice/create/', json=data)
    return resp.json()

# --- Проверка инвойса через CrystalPAY API ---
def check_crystalpay_invoice(invoice_id):
    data = {
        "auth_login": CRYSTALPAY_LOGIN,
        "auth_secret": CRYSTALPAY_SECRET,
        "id": invoice_id
    }
    resp = requests.post(CRYSTALPAY_API + 'invoice/info/', json=data)
    return resp.json()

# --- Старт FSM ---
async def start_buy_stars_rub(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    await callback_query.message.answer("Введите количество звёзд, которое хотите купить:")
    await state.set_state(BuyStarsRubStates.waiting_for_amount)

async def process_stars_amount(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Введите корректное количество звёзд (целое число больше 0):")
        return
    await state.update_data(amount=amount)
    await message.answer("Введите username Fragment (без @), на который отправить звёзды:")
    await state.set_state(BuyStarsRubStates.waiting_for_username)

async def process_stars_username(message: types.Message, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount")
    username = message.text.strip().lstrip("@")
    await state.update_data(username=username, amount=amount)
    # Показываем выбор метода оплаты
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=f"rub_method_{method}")] for method, label in CRYSTALPAY_METHODS
        ] + [[InlineKeyboardButton(text="Назад", callback_data="back_to_main_menu")]]
    )
    await message.answer("Выберите способ оплаты:", reply_markup=kb)
    await state.set_state(BuyStarsRubStates.waiting_for_method)

async def process_rub_method(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    data = await state.get_data()
    amount = data.get("amount")
    username = data.get("username")
    if amount is None or username is None:
        await callback_query.message.answer("Ошибка: не удалось получить данные заказа. Попробуйте начать покупку заново.")
        await state.clear()
        return
    rub_amount = int(round(amount * 1.4))
    method = callback_query.data.replace("rub_method_", "")
    # Минимальный лимит (пример: 10 руб)
    min_limit = 10
    if rub_amount < min_limit:
        await callback_query.message.answer(
            f"Минимальная сумма для CrystalPAY — {min_limit}₽. Сейчас выбрано: {rub_amount}₽. Пожалуйста, выберите большее количество звёзд."
        )
        return
    # --- Создание инвойса через CrystalPAY API ---
    try:
        invoice = create_crystalpay_invoice(
            rub_amount,
            f"Покупка {amount} звёзд для @{username}",
            lifetime=15,
            required_method=method
        )
        if invoice.get("error"):
            await callback_query.message.answer(f"Ошибка при создании счёта: {invoice.get('errors')}")
            return
        url = invoice["url"]
        invoice_id = invoice["id"]
    except Exception as e:
        await callback_query.message.answer(f"Ошибка при создании счёта: {e}")
        return
    await state.update_data(rub_invoice_id=invoice_id, rub_username=username, rub_amount=amount)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Перейти к оплате", url=url)],
        [InlineKeyboardButton(text="Проверить оплату", callback_data="check_rub_payment")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_main_menu")]
    ])
    await callback_query.message.answer(f"Оплатите {rub_amount}₽ за {amount} звёзд по ссылке:", reply_markup=kb)
    # await state.clear()  # Не очищаем состояние сразу после создания инвойса

# --- Проверка оплаты ---
async def handle_check_rub_payment(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    data = await state.get_data()
    invoice_id = data.get("rub_invoice_id")
    username = data.get("rub_username")
    amount = data.get("rub_amount")
    if not invoice_id:
        await callback_query.message.answer("Не найден заказ для проверки. Попробуйте заново.")
        return
    try:
        info = check_crystalpay_invoice(invoice_id)
        state_ = info.get("state")
        if state_ == "payed":
            try:
                client = FragmentAPIClient()
                res = client.buy_stars_without_kyc(
                    username=username,
                    amount=amount,
                    seed=STARS_SEED
                )
                await callback_query.message.answer(f"Звёзды успешно куплены и отправлены на аккаунт @{username} через Fragment!")
            except Exception as e:
                await callback_query.message.answer(f"Ошибка при покупке звёзд через Fragment: {e}")
            await state.clear()  # Очищаем только после успешной оплаты
        elif state_ == "expired":
            await callback_query.message.answer("Счёт просрочен. Попробуйте создать новый.")
        else:
            await callback_query.message.answer("Оплата ещё не поступила. Проверьте позже.")
    except Exception as e:
        await callback_query.message.answer(f"Ошибка при проверке оплаты: {e}")

# --- Регистрация новых хендлеров ---
# dp.callback_query.register(start_buy_stars_rub, lambda c: c.data == "buy_stars_rub")
# dp.message.register(process_stars_amount, BuyStarsRubStates.waiting_for_amount)
# dp.message.register(process_stars_username, BuyStarsRubStates.waiting_for_username)
# dp.callback_query.register(process_rub_method, lambda c: c.data.startswith("rub_method_"))
# dp.callback_query.register(handle_check_rub_payment, lambda c: c.data == "check_rub_payment")

# Функция для перевода user-friendly TON адреса (UQ.../EQ...) в raw (0:...)
def normalize_address(addr):
    if not addr:
        return None
    if addr.startswith("0:"):
        return addr.lower()
    if addr.startswith("UQ") or addr.startswith("EQ"):
        try:
            raw = base64.urlsafe_b64decode(addr + '==')
            return f"0:{raw[1:].hex()}"
        except Exception:
            return addr
    return addr


# --- Новый watcher на Tonapi ---
async def tonapi_payment_watcher(bot, deals_db):
    # print("Tonapi watcher запущен!")
    processed_deals = set()
    headers = {"Authorization": f"Bearer {TONAPI_KEY}"}
    while True:
        try:
            url = f"https://tonapi.io/v2/blockchain/accounts/{TRACK_ADDRESS}/transactions?limit=30"
            response = requests.get(url, headers=headers)
            data = response.json()
            txs = data.get("transactions", [])
            # print(f"[WATCHER] Получено {len(txs)} транзакций")
            
            for tx in txs:
                in_msg = tx.get("in_msg", {})
                memo = None
                if "decoded_body" in in_msg and isinstance(in_msg["decoded_body"], dict):
                    memo = in_msg["decoded_body"].get("text")
                value = int(in_msg.get("value", 0))
                destination = in_msg.get("destination")
                tx_hash = tx.get("hash")
                
                # destination может быть dict или строкой
                if isinstance(destination, dict):
                    dest_addr = destination.get("address")
                else:
                    dest_addr = destination
                
                # print(f"[WATCHER] Транзакция: memo={memo}, value={value}, dest={dest_addr}, hash={tx_hash}")
                
                # Проверяем, что транзакция пришла на наш кошелек
                if dest_addr != TRACK_ADDRESS:
                    # print(f"[WATCHER] Адрес не совпадает: {dest_addr} != {TRACK_ADDRESS}")
                    continue
                if not memo or not value or not tx_hash:
                    # print(f"[WATCHER] Пропускаем: нет memo или value")
                    continue
                
                # print(f"[WATCHER] Проверяем deals_db: {len(deals_db)} сделок")
                for deal_id, deal in deals_db.items():
                    # print(f"[WATCHER] Проверяем сделку {deal_id}: {deal}")
                    if deal_id in processed_deals:
                        # print(f"[WATCHER] Сделка {deal_id} уже обработана")
                        continue
                    
                    expected_memo = deal.get("payment_memo")
                    amount = float(deal.get("amount", 0))
                    fee = amount * 0.03 if deal.get("type") != "buy_stars" else 0.03 * float(deal.get("total_to_pay", 0))
                    total_amount = int((amount + fee) * 1e9) if deal.get("type") != "buy_stars" else int(float(deal.get("total_to_pay", 0)) * 1e9)
                    buyer_id = deal.get("buyer_id") if deal.get("type") != "buy_stars" else deal.get("user_id")
                    seller_id = deal.get("seller_id") if deal.get("type") != "buy_stars" else None
                    
                    # print(f"[WATCHER] Сравнение: memo='{memo}' == '{expected_memo}' = {memo == expected_memo}")
                    # print(f"[WATCHER] Сравнение: value={value} == {total_amount} = {value == total_amount}")
                    
                    if memo == expected_memo and value == total_amount:
                        # print(f"[WATCHER] НАЙДЕНО СОВПАДЕНИЕ! Отправляю сообщения. buyer_id={buyer_id}, seller_id={seller_id}")
                        if deal.get("type") == "buy_stars":
                            try:
                                seed = "addict runway paper tongue ozone relax brisk immune notice file raw drift dream book loan assault know shaft length moment spy correct unique plug"
                                res = stars_payment_watcher(
                                    username=deal["username"],
                                    amount=deal["amount"],
                                    seed=seed
                                )
                                await bot.send_message(buyer_id, f"Звёзды успешно куплены и отправлены на ваш аккаунт @{deal['username']}!\n\nОтвет Fragment: {res}")
                            except Exception as e:
                                await bot.send_message(buyer_id, f"Ошибка при покупке звёзд: {e}")
                        else:
                            try:
                                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                                    [InlineKeyboardButton(text="Я отправил товар", callback_data=f"seller_sent_{deal_id}")]
                                ])
                                await bot.send_message(seller_id, f"✅ Покупатель оплатил сделку #{deal_id}! Теперь вы можете передать товар покупателю.", reply_markup=keyboard)
                                # print(f"[WATCHER] Сообщение отправлено продавцу: {seller_id}")
                            except Exception as e:
                                print(f"[WATCHER] Ошибка при отправке продавцу: {e}")
                        if buyer_id:
                            try:
                                await bot.send_message(buyer_id, f"Оплата получена! Ожидайте передачи товара от продавца.")
                                # print(f"[WATCHER] Сообщение отправлено покупателю: {buyer_id}")
                            except Exception as e:
                                print(f"[WATCHER] Ошибка при отправке покупателю: {e}")
                        else:
                            try:
                                await bot.send_message(seller_id, f"Покупатель оплатил сделку #{deal_id}, но не авторизовался через ссылку. Свяжитесь с ним вручную.")
                                # print(f"[WATCHER] Покупатель не авторизовался, уведомление продавцу: {seller_id}")
                            except Exception as e:
                                print(f"[WATCHER] Ошибка при отправке продавцу (no buyer): {e}")
                        processed_deals.add(deal_id)
                        break
        except Exception as e:
            print(f"[WATCHER] Tonapi watcher error: {e}")
        await asyncio.sleep(1)


# Список рабочих liteserver'ов (сгенерирован скриптом)
liteservers = [
    {"ip": "5.9.10.47", "port": 19949, "id": "n4VDnSCUuSpjnCyUk9e3QOOd6o0ItSWYbTnW3Wnn8wk="},
    {"ip": "5.9.10.15", "port": 48014, "id": "3XO67K/qi+gu3T9v8G2hx1yNmWZhccL3O7SoosFo8G0="},
    {"ip": "135.181.177.59", "port": 53312, "id": "aF91CuUHuuOv9rm2W5+O/4h38M3sRm40DtSdRxQhmtQ="},
    {"ip": "135.181.140.212", "port": 13206, "id": "K0t3+IWLOXHYMvMcrGZDPs+pn58a17LFbnXoQkKc2xw="},
    {"ip": "135.181.140.221", "port": 46995, "id": "wQE0MVhXNWUXpWiW5Bk8cAirIh5NNG3cZM1/fSVKIts="},
    {"ip": "65.21.141.233", "port": 30131, "id": "wrQaeIFispPfHndEBc0s0fx7GSp8UFFvebnytQQfc6A="},
    {"ip": "65.21.141.198", "port": 47160, "id": "vOe1Xqt/1AQ2Z56Pr+1Rnw+f0NmAA7rNCZFIHeChB7o="},
    {"ip": "65.21.141.231", "port": 17728, "id": "BYSVpL7aPk0kU5CtlsIae/8mf2B/NrBi7DKmepcjX6Q="},
    {"ip": "65.21.141.197", "port": 13570, "id": "iVQH71cymoNgnrhOT35tl/Y7k86X5iVuu5Vf68KmifQ="},
    {"ip": "135.181.132.198", "port": 53560, "id": "NlYhh/xf4uQpE+7EzgorPHqIaqildznrpajJTRRH2HU="},
    {"ip": "135.181.132.253", "port": 46529, "id": "jLO6yoooqUQqg4/1QXflpv2qGCoXmzZCR+bOsYJ2hxw="},
]

# Функция отправки TON через внешний процесс (скрипт send_ton_external.py)
def send_ton_external(seed_phrase, to_address, amount_ton):
    try:
        result = subprocess.run([
            'python', 'send_ton_external.py',
            '--seed', seed_phrase,
            '--to', to_address,
            '--amount', str(amount_ton)
        ], capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            return {"ok": True, "result": result.stdout.strip()}
        else:
            return {"ok": False, "error": result.stderr.strip()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def send_ton_via_js_api(to_address, amount, comment=""):
    url = "http://localhost:3000/send"
    data = {"to": to_address, "amount": amount, "comment": comment}
    try:
        response = requests.post(url, json=data, timeout=30)
        return response.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}

# Пример вызова (замени на реальный вызов в нужном месте):
# result = send_ton_via_js_api("UQ...", 0.1, "Test from Python bot")
# print(result)


class CreateDealStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_description = State()


class WalletStates(StatesGroup):
    waiting_for_wallet_address = State()


class LanguageStates(StatesGroup):
    waiting_for_language_selection = State()


async def start_command(message: types.Message) -> None:
    """Handles the /start command."""
    # Проверяем, содержит ли команда /start параметр deal_ID
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("deal_"):
        deal_id = args[1].replace("deal_", "")
        logging.info(f"Start command received with deal_id: {deal_id}")
        deal_info = deals_db_otc.get(deal_id)

        if deal_info:
            # Для watcher: сохраняем payment_memo в deal_info, если его нет (для старых сделок)
            if "payment_memo" not in deal_info:
                import random, string
                deal_info["payment_memo"] = ''.join(random.choices(string.ascii_lowercase + string.digits, k=15))
                deals_db_otc[deal_id] = deal_info
            # Запрещаем продавцу начинать сделку с самим собой
            if message.from_user.id == deal_info.get("seller_id"):
                await message.answer("Вы не можете быть покупателем в своей же сделке.")
                return
            # Всегда сохраняем buyer_id, если он не установлен или отличается
            if deal_info.get("buyer_id") != message.from_user.id:
                deal_info["buyer_id"] = message.from_user.id
                deals_db_otc[deal_id] = deal_info
            amount = deal_info["amount"]
            description = deal_info["description"]
            seller_username = deal_info["seller_username"]
            seller_id = deal_info["seller_id"]
            seller_wallet = deal_info["seller_wallet"]
            # Фиксированный кошелек для покупателя
            payment_address = "UQDQoHshokE-7jJP2XRbr2LJLv4McWB2qETbGNTK7NEF8ktB"
            # payment_memo для оплаты
            payment_memo = deal_info["payment_memo"]
            # Расчет комиссии (заглушка)
            fee = amount * 0.03 # 3% комиссия
            total_amount_to_pay = amount + fee
            # Количество завершённых сделок продавца
            seller_completed = get_completed_deals(seller_id)

            deal_message = (
                f"{get_text(message.from_user.id, 'you_are_buyer')} #{deal_id}!\n"
                f"{get_text(message.from_user.id, 'seller_label')}: @{seller_username} ({get_text(message.from_user.id, 'successful_deals_label')}: {seller_completed})\n"
                f"{get_text(message.from_user.id, 'you_buy_label')}: {description}\n\n"
                f"{get_text(message.from_user.id, 'payment_address_label')}\n`{payment_address}`\n\n"
                f"{get_text(message.from_user.id, 'payment_memo_label')}\n`{payment_memo}`\n\n"
                f"{get_text(message.from_user.id, 'amount_to_pay_label')}\n**{total_amount_to_pay:.2f} TON** (Fee: {fee:.2f})\n\n"
                f"{get_text(message.from_user.id, 'check_data_warning')}\n\n"
                f"{get_text(message.from_user.id, 'commission_paid_by_buyer')}"
            )

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💎 Оплатить в Tonkeeper", url=f"ton://transfer/{payment_address}?amount={int(total_amount_to_pay * 1e9)}&text={payment_memo}")],
                [InlineKeyboardButton(text="🚪 Выйти из сделки", callback_data=f"cancel_deal_{deal_id}")]
            ])

            await message.answer(deal_message, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
            return # Завершаем выполнение, чтобы не отправлять welcome_text
        else:
            await message.answer(f"Сделка #{deal_id} не найдена.")
            return

    welcome_text = get_text(message.from_user.id, "welcome_text")
    keyboard = get_main_keyboard(message.from_user.id)
    
    photo_path = "photo_2025-07-17_09-52-22.jpg"
    try:
        photo = FSInputFile(photo_path)
        await message.answer_photo(photo, caption=welcome_text, reply_markup=keyboard)
    except Exception:
        await message.answer(welcome_text, reply_markup=keyboard)


async def help_command(message: types.Message) -> None:
    """Handles the /help command."""
    await message.reply(get_text(message.from_user.id, "echo_message"))


async def echo_message(message: types.Message) -> None:
    print(f"[DEBUG] echo_message: {message.text}")
    await message.answer(message.text)


async def any_message(message: types.Message):
    print(f"[DEBUG] any_message: {message.text}")


async def handle_create_deal_callback(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    await callback_query.answer()
    user_id = callback_query.from_user.id
    await callback_query.message.answer(get_text(user_id, "enter_amount"), reply_markup=get_back_keyboard(user_id))
    await state.set_state(CreateDealStates.waiting_for_amount)

async def handle_wallet_callback(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    await callback_query.answer()
    user_id = callback_query.from_user.id
    current_wallet = user_wallets.get(user_id, get_text(user_id, "wallet_not_linked_yet"))
    await callback_query.message.answer(
        f"{get_text(user_id, 'wallet_current')}\n`{current_wallet}`\n\n"
        f"{get_text(user_id, 'wallet_change_prompt')}"
    , parse_mode=ParseMode.MARKDOWN)
    await state.set_state(WalletStates.waiting_for_wallet_address)

async def handle_scan_callback(callback_query: types.CallbackQuery) -> None:
    await callback_query.answer()
    user_id = callback_query.from_user.id
    await callback_query.message.answer(get_text(user_id, "scan_message"))

async def handle_partners_callback(callback_query: types.CallbackQuery) -> None:
    await callback_query.answer()
    user_id = callback_query.from_user.id
    referral_link = f"t.me/nimbleotcbot?start=ref={user_id}"
    
    partners_message = (
        f"{get_text(user_id, 'partners_program_title')}\n\n"
        f"{get_text(user_id, 'reward_label')}\n"
        f"{get_text(user_id, 'you_receive')}\n\n"
        f"{get_text(user_id, 'statistics_label')}\n"
        f"{get_text(user_id, 'invited_label')}\n"
        f"{get_text(user_id, 'earned_label')}\n\n"
        f"{get_text(user_id, 'your_referral_link_label')}\n`{referral_link}`\n\n"
        f"{get_text(user_id, 'referral_condition')}"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(user_id, "share_link_btn"), switch_inline_query=referral_link)],
        [InlineKeyboardButton(text=get_text(user_id, "back_btn"), callback_data="back_to_main_menu")]
    ])
    
    try:
        logging.info(f"Attempting to edit message {callback_query.message.message_id} in chat {callback_query.message.chat.id}")
        await callback_query.message.edit_caption(caption=partners_message, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        logging.info("Successfully edited caption for partners message.")
    except Exception as e:
        logging.error(f"Failed to edit caption for partners message: {e}")
        # As a fallback, send a new message if editing fails
        await callback_query.message.answer(partners_message, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        logging.info("Sent new message as a fallback.")

async def handle_deals_callback(callback_query: types.CallbackQuery) -> None:
    await callback_query.answer()
    user_id = callback_query.from_user.id
    await callback_query.message.answer(get_text(user_id, "deals_message"))

async def handle_language_callback(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    await callback_query.answer()
    user_id = callback_query.from_user.id
    await callback_query.message.answer(get_text(user_id, "language_choose"), reply_markup=get_language_keyboard(user_id))
    await state.set_state(LanguageStates.waiting_for_language_selection)

async def handle_support_callback(callback_query: types.CallbackQuery) -> None:
    await callback_query.answer()
    user_id = callback_query.from_user.id
    await callback_query.message.answer(get_text(user_id, "support_contact"))

# Обработчик нажатия продавцом кнопки "Я отправил товар"
async def handle_seller_sent_callback(callback_query: types.CallbackQuery) -> None:
    await callback_query.answer()
    user_id = callback_query.from_user.id
    deal_id = callback_query.data.replace("seller_sent_", "")
    deal = deals_db_otc.get(deal_id)
    if not deal:
        await callback_query.message.answer(f"Сделка #{deal_id} не найдена.")
        return
    buyer_id = deal.get("buyer_id")
    if not buyer_id:
        await callback_query.message.answer("Покупатель не найден. Возможно, он не переходил по ссылке сделки. Свяжитесь с ним вручную.")
        return
    # Кнопки для покупателя: "Я получил товар" и "Поддержка"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Я получил товар", callback_data=f"buyer_received_{deal_id}")],
        [InlineKeyboardButton(text="Поддержка", callback_data="support")]
    ])
    try:
        await callback_query.bot.send_message(buyer_id, f"Продавец сообщил, что отправил вам товар по сделке #{deal_id}.\n\nПожалуйста, подтвердите получение товара или обратитесь в поддержку, если есть вопросы.", reply_markup=keyboard)
        await callback_query.message.answer("Покупателю отправлено уведомление о доставке товара.")
    except Exception as e:
        await callback_query.message.answer(f"Ошибка при отправке сообщения покупателю: {e}")

# Обработчик нажатия покупателем кнопки "Я получил товар"
async def handle_buyer_received_callback(callback_query: types.CallbackQuery) -> None:
    await callback_query.answer()
    user_id = callback_query.from_user.id
    deal_id = callback_query.data.replace("buyer_received_", "")
    deal = deals_db_otc.get(deal_id)
    if not deal:
        await callback_query.message.answer(f"Сделка #{deal_id} не найдена.")
        return
    seller_id = deal.get("seller_id")
    buyer_id = deal.get("buyer_id")
    seller_wallet = deal.get("seller_wallet")
    amount = float(deal.get("amount", 0))
    # Увеличиваем количество завершённых сделок
    increment_completed_deals(seller_id)
    increment_completed_deals(buyer_id)
    # Выплата продавцу — теперь вся сумма сделки (комиссия только с покупателя)
    payout = amount
    try:
        result = send_ton_via_js_api(
            to_address=seller_wallet,
            amount=payout,
            comment=f"Commission for deal #{deal_id}"
        )
        if result.get("ok"):
            await callback_query.bot.send_message(seller_id, f"Сделка #{deal_id} завершена! Поздравляем!\n\nВам отправлено {payout} TON на кошелёк {seller_wallet}.")
        else:
            await callback_query.bot.send_message(seller_id, f"Ошибка при выплате: {result}")
    except Exception as e:
        await callback_query.bot.send_message(seller_id, f"Ошибка при выплате: {e}")
    try:
        await callback_query.bot.send_message(buyer_id, f"Сделка #{deal_id} завершена! Поздравляем!")
    except Exception:
        pass
    await callback_query.message.answer("Сделка завершена!")
    deals_db_otc.pop(deal_id, None)

async def handle_share_commission_callback(callback_query: types.CallbackQuery) -> None:
    await callback_query.answer()
    user_id = callback_query.from_user.id
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Закрыть", callback_data="back_to_main_menu")]
    ])
    await callback_query.message.answer(get_text(user_id, "share_commission_message"), reply_markup=keyboard)

async def handle_back_to_main_menu_callback(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    await callback_query.answer()
    user_id = callback_query.from_user.id
    await state.clear()
    welcome_text = get_text(user_id, "welcome_text")
    keyboard = get_main_keyboard(user_id)
    photo_path = "photo_2025-07-17_09-52-22.jpg"
    try:
        photo = FSInputFile(photo_path)
        media = InputMediaPhoto(media=photo, caption=welcome_text)
        try:
            await callback_query.message.edit_media(media=media, reply_markup=keyboard)
        except Exception:
            await callback_query.message.answer_photo(photo, caption=welcome_text, reply_markup=keyboard)
    except Exception:
        try:
            await callback_query.message.edit_text(welcome_text, reply_markup=keyboard)
        except Exception:
            await callback_query.message.answer(welcome_text, reply_markup=keyboard)

async def handle_copy_link_callback(callback_query: types.CallbackQuery) -> None:
    await callback_query.answer()
    user_id = callback_query.from_user.id
    deal_id = callback_query.data.replace("copy_link_", "")
    # Формируем ссылку для копирования
    deal_link = f"t.me/nimbleotcbot?start=deal_{deal_id}"
    await callback_query.message.answer(f"{get_text(user_id, 'link_copied').format(deal_id=deal_id)}\n{deal_link}")

async def handle_cancel_deal_callback(callback_query: types.CallbackQuery) -> None:
    await callback_query.answer()
    user_id = callback_query.from_user.id
    deal_id = callback_query.data.replace("cancel_deal_", "")
    # Если это покупатель выходит из сделки
    deal_info = deals_db_otc.get(deal_id)
    if deal_info and deal_info.get("buyer_id") == user_id:
        # Удаляем сообщение у покупателя
        try:
            await callback_query.message.delete()
        except Exception:
            pass
        # Уведомляем продавца
        seller_id = deal_info.get("seller_id")
        try:
            await callback_query.bot.send_message(seller_id, f"Покупатель вышел из сделки #{deal_id}.")
        except Exception:
            pass
        # Очищаем buyer_id, чтобы сделка могла быть использована другим покупателем
        deal_info["buyer_id"] = None
        deals_db_otc[deal_id] = deal_info
        return
    # Если продавец отменяет сделку
    deals_db_otc.pop(deal_id, None)
    await callback_query.message.answer(get_text(user_id, "deal_cancelled").format(deal_id=deal_id))


async def process_amount_input(message: types.Message, state: FSMContext) -> None:
    """Handles the amount input for deal creation."""
    user_id = message.from_user.id
    try:
        amount = float(message.text.replace(',', '.'))
        if amount <= 0:
            await message.answer(get_text(user_id, "amount_positive_error"))
            return
        await state.update_data(amount=amount)
        await message.answer(get_text(user_id, "enter_description"), reply_markup=get_back_keyboard(user_id))
        await state.set_state(CreateDealStates.waiting_for_description)
    except ValueError:
        await message.answer(get_text(user_id, "amount_format_error"))


async def process_description_input(message: types.Message, state: FSMContext) -> None:
    """Handles the description input for deal creation."""
    description = message.text
    user_data = await state.get_data()
    amount = user_data.get("amount")
    seller_id = message.from_user.id
    seller_username = message.from_user.username or f"id{seller_id}"

    # Проверка, привязан ли кошелек продавца
    if seller_id not in user_wallets:
        logging.info(f"Seller {seller_id} wallet not linked.")
        await message.answer(get_text(seller_id, "wallet_not_linked"))
        await state.clear() # Очищаем состояние, так как сделка не будет создана
        return
    
    seller_wallet = user_wallets[seller_id]

    deal_id = uuid.uuid4().hex[:7] # Generate a unique, short ID
    # Генерируем уникальный MEMO для сделки
    import random, string
    payment_memo = ''.join(random.choices(string.ascii_lowercase + string.digits, k=15))

    # Сохраняем информацию о сделке
    deals_db_otc[deal_id] = {
        "amount": amount,
        "description": description,
        "seller_id": seller_id,
        "seller_username": seller_username,
        "seller_wallet": seller_wallet,
        "buyer_id": None,  # Будет установлен, когда покупатель перейдет по ссылке
        "payment_memo": payment_memo
    }
    logging.info(f"Deal {deal_id} created and added to deals_db_otc: {deals_db_otc[deal_id]}")

    buyer_link = f"t.me/nimbleotcbot?start=deal_{deal_id}"
    # Количество завершённых сделок продавца
    seller_completed = get_completed_deals(seller_id)

    deal_message = (
        f"{get_text(seller_id, 'deal_created_success')} #{deal_id}\n\n"
        f"{get_text(seller_id, 'amount_label')}: {amount:.2f} TON\n"
        f"{get_text(seller_id, 'description_label')}: {description}\n\n"
        f"{get_text(seller_id, 'buyer_link_label')}: {buyer_link}\n"
        f"{get_text(seller_id, 'successful_deals_label')}: {seller_completed}"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text(seller_id, "copy_link_btn"), callback_data=f"copy_link_{deal_id}")],
        [InlineKeyboardButton(text=get_text(seller_id, "cancel_deal_btn"), callback_data=f"cancel_deal_{deal_id}")]
    ])

    await message.reply(deal_message, reply_markup=keyboard)
    await state.clear() # Clear state after deal creation


def get_back_keyboard(user_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=get_text(user_id, "back_btn"), callback_data="back_to_main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def process_wallet_input(message: types.Message, state: FSMContext) -> None:
    """Handles the wallet address input."""
    user_id = message.from_user.id
    wallet_address = message.text.strip()
    # Простая валидация адреса TON (можно улучшить)
    if wallet_address.startswith("EQ") or wallet_address.startswith("UQ"):
        user_wallets[user_id] = wallet_address
        await message.answer(get_text(user_id, "wallet_linked_success").format(wallet_address=wallet_address), parse_mode=ParseMode.MARKDOWN)
        await state.clear()
        # Возвращаем пользователя в главное меню
        await message.answer(get_text(user_id, "choose_action"), reply_markup=get_main_keyboard(user_id))
    else:
        await message.answer(get_text(user_id, "wallet_invalid_format"))


async def process_language_selection_callback(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """Handles language selection callbacks when in language selection state."""
    await callback_query.answer() # Acknowledge the callback query
    user_id = callback_query.from_user.id
    updated = False
    if callback_query.data == "set_lang_en":
        user_languages[user_id] = "en"
        updated = True
    elif callback_query.data == "set_lang_ru":
        user_languages[user_id] = "ru"
        updated = True
    elif callback_query.data == "back_to_main_menu":
        await state.clear()
        welcome_text = get_text(user_id, "welcome_text")
        keyboard = get_main_keyboard(user_id)
        photo_path = "photo_2025-07-17_09-52-22.jpg"
        try:
            photo = FSInputFile(photo_path)
            media = InputMediaPhoto(media=photo, caption=welcome_text)
            try:
                await callback_query.message.edit_media(media=media, reply_markup=keyboard)
            except Exception:
                await callback_query.message.answer_photo(photo, caption=welcome_text, reply_markup=keyboard)
        except Exception:
            try:
                await callback_query.message.edit_text(welcome_text, reply_markup=keyboard)
            except Exception:
                await callback_query.message.answer(welcome_text, reply_markup=keyboard)
        return
    await state.clear()
    if updated:
        welcome_text = get_text(user_id, "welcome_text")
        keyboard = get_main_keyboard(user_id)
        photo_path = "photo_2025-07-17_09-52-22.jpg"
        try:
            photo = FSInputFile(photo_path)
            media = InputMediaPhoto(media=photo, caption=welcome_text)
            try:
                await callback_query.message.edit_media(media=media, reply_markup=keyboard)
            except Exception:
                await callback_query.message.answer_photo(photo, caption=welcome_text, reply_markup=keyboard)
        except Exception:
            try:
                await callback_query.message.edit_text(welcome_text, reply_markup=keyboard)
            except Exception:
                await callback_query.message.answer(welcome_text, reply_markup=keyboard)


def get_language_keyboard(user_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=get_text(user_id, "english_btn"), callback_data="set_lang_en")],
        [InlineKeyboardButton(text=get_text(user_id, "russian_btn"), callback_data="set_lang_ru")],
        [InlineKeyboardButton(text=get_text(user_id, "back_btn"), callback_data="back_to_main_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def confirm_payment_command(message: types.Message) -> None:
    """Handles the /confirm_payment command for buyer."""
    # Проверяем, есть ли deal_id в сообщении
    args = message.text.split()
    if len(args) < 2:
        logging.info("confirm_payment_command: No deal_ID provided.")
        await message.answer("Использование: /confirm_payment deal_ID")
        return

    deal_id = args[1].lstrip('#')
    logging.info(f"confirm_payment_command received for deal_id: {deal_id}")
    deal_info = deals_db_otc.get(deal_id)
    
    if not deal_info:
        logging.warning(f"confirm_payment_command: Deal {deal_id} not found in deals_db_otc.")
        await message.answer(f"Сделка #{deal_id} не найдена.")
        return

    # Проверяем, является ли пользователь отправивший команду покупателем сделки
    if message.from_user.id != deal_info.get("buyer_id"):
        logging.warning(f"confirm_payment_command: User {message.from_user.id} is not buyer of deal {deal_id}. Buyer ID: {deal_info.get('buyer_id')}")
        await message.answer("Вы не являетесь покупателем этой сделки.")
        return
    
    # Отправляем сообщение продавцу
    seller_message = (
        f"✅ Покупатель оплатил сделку #{deal_id}!\n\n"
        "Теперь вы можете передать товар покупателю."
    )
    
    try:
        await message.bot.send_message(
            chat_id=deal_info["seller_id"],
            text=seller_message
        )
        logging.info(f"Confirmation message sent to seller {deal_info['seller_id']} for deal {deal_id}")
        await message.answer(f"Сообщение о подтверждении оплаты отправлено продавцу сделки #{deal_id}")
    except Exception as e:
        logging.error(f"Error sending confirmation message for deal {deal_id}: {e}")
        await message.answer(f"Ошибка при отправке сообщения продавцу: {str(e)}")


# Удаляю все строки с subprocess.run и связанные с ними блоки


# Обёртка для FSM-обработчика покупки звёзд (вынесена на верхний уровень)
async def stars_purchase_input_wrapper(message: types.Message, state: FSMContext):
    print(f"[DEBUG] stars_purchase_input_wrapper: state={await state.get_state()}, text={message.text}")
    await process_stars_purchase_input(message, state, deals_db_stars, STARS_WALLET)


async def admin_only_set_stars_price(message: types.Message):
    if message.from_user.id == 2029065770:
        await set_stars_price(message)
    else:
        await message.answer("Нет доступа.")


# --- Меню выбора способа оплаты звёзд ---
async def handle_buy_stars_menu(callback_query: types.CallbackQuery, state: FSMContext):
    print("DEBUG: handle_buy_stars_menu вызван")
    await callback_query.answer()
    user_id = callback_query.from_user.id
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оплатить TON", callback_data="buy_stars_ton")],
        [InlineKeyboardButton(text="Оплатить RUB (карта/СБП/QR/крипта)", callback_data="buy_stars_rub")],
        [InlineKeyboardButton(text=get_text(user_id, "back_btn"), callback_data="back_to_main_menu")]
    ])
    await callback_query.message.answer("Выберите способ оплаты:", reply_markup=kb)

# --- Обработчик для оплаты звёзд через TON (Tonkeeper) ---
async def handle_buy_stars_ton(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    # Вызываем старую логику покупки звёзд через TON
    await handle_buy_stars_callback(callback_query, state)

# --- Универсальный debug-обработчик для всех callback_query ---
async def debug_callback(callback_query: types.CallbackQuery, state: FSMContext):
    print(f"DEBUG: callback_data={callback_query.data}")
    await callback_query.answer("DEBUG!", show_alert=True)

async def main() -> None:
    """Starts the bot."""
    init_db()
    bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Set up bot commands
    commands = [
        BotCommand(command="start", description=get_text(0, "start_command_description")), 
        BotCommand(command="wallet", description=get_text(0, "wallet_command_description")), 
        BotCommand(command="scan", description=get_text(0, "scan_command_description")), 
    ]
    await bot.set_my_commands(commands)

    # Register command handlers
    dp.message.register(start_command, Command("start"))
    dp.message.register(help_command, Command("help"))
    dp.message.register(confirm_payment_command, Command("confirm_payment"))
    dp.message.register(admin_only_set_stars_price, Command("setstarsprice"))

    # Register handlers for deal creation states
    dp.message.register(process_amount_input, CreateDealStates.waiting_for_amount)
    dp.message.register(process_description_input, CreateDealStates.waiting_for_description)

    # Register handler for wallet input
    dp.message.register(process_wallet_input, WalletStates.waiting_for_wallet_address)

    # Register handler for language selection callbacks in the specific state
    dp.callback_query.register(process_language_selection_callback, LanguageStates.waiting_for_language_selection)

    # Add handlers for main menu inline keyboard buttons
    dp.callback_query.register(handle_create_deal_callback, lambda c: c.data == "create_deal")
    dp.callback_query.register(handle_wallet_callback, lambda c: c.data == "wallet")
    dp.callback_query.register(handle_scan_callback, lambda c: c.data == "scan")
    dp.callback_query.register(handle_partners_callback, lambda c: c.data == "partners")
    dp.callback_query.register(handle_deals_callback, lambda c: c.data == "deals")
    dp.callback_query.register(handle_language_callback, lambda c: c.data == "language")
    dp.callback_query.register(handle_support_callback, lambda c: c.data == "support")
    dp.callback_query.register(handle_share_commission_callback, lambda c: c.data == "share_commission")
    dp.callback_query.register(handle_back_to_main_menu_callback, lambda c: c.data == "back_to_main_menu")
    dp.callback_query.register(handle_copy_link_callback, lambda c: c.data.startswith("copy_link_"))
    dp.callback_query.register(handle_cancel_deal_callback, lambda c: c.data.startswith("cancel_deal_"))
    dp.callback_query.register(handle_seller_sent_callback, lambda c: c.data.startswith("seller_sent_"))
    dp.callback_query.register(handle_buyer_received_callback, lambda c: c.data.startswith("buyer_received_"))
    # dp.callback_query.register(handle_buy_stars_callback, lambda c: c.data == "buy_stars")  # Удаляю старый обработчик
    dp.callback_query.register(handle_buy_stars_menu, lambda c: c.data == "buy_stars")  # Новый обработчик с выбором способа оплаты
    dp.callback_query.register(handle_buy_stars_ton, lambda c: c.data == "buy_stars_ton") # Новый обработчик для оплаты TON
    # dp.callback_query.register(handle_buy_stars_rub, lambda c: c.data == "buy_stars_rub") # Удалён старый обработчик для карты
    dp.callback_query.register(start_buy_stars_rub, lambda c: c.data == "buy_stars_rub") # Оставлен только новый FSM-обработчик
    dp.callback_query.register(process_rub_method, lambda c: c.data.startswith("rub_method_"))
    dp.callback_query.register(handle_check_rub_payment, lambda c: c.data == "check_rub_payment") # Удален обработчик проверки оплаты
    dp.message.register(process_stars_amount, BuyStarsRubStates.waiting_for_amount)
    dp.message.register(process_stars_username, BuyStarsRubStates.waiting_for_username)
    dp.message.register(stars_purchase_input_wrapper, BuyStarsStates.waiting_for_stars_purchase_input)
    dp.message.register(echo_message)
    dp.message.register(any_message)
    # watcher для OTC-сделок
    asyncio.create_task(tonapi_payment_watcher(bot, deals_db_otc))
    # watcher для покупки звёзд
    asyncio.create_task(stars_payment_watcher(bot, deals_db_stars))

    await dp.start_polling(bot)


def get_main_keyboard(user_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=get_text(user_id, "create_deal_btn"), callback_data="create_deal")],
        [InlineKeyboardButton(text=get_text(user_id, "wallet_btn"), callback_data="wallet")],
        [InlineKeyboardButton(text="⭐️ Купить звёзды", callback_data="buy_stars")],
        [InlineKeyboardButton(text=get_text(user_id, "referrals_btn"), callback_data="partners")],
        [InlineKeyboardButton(text=get_text(user_id, "language_btn"), callback_data="language"), InlineKeyboardButton(text=get_text(user_id, "support_btn"), callback_data="support")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


if __name__ == "__main__":
    asyncio.run(main()) 