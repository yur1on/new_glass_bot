# bot/services/bot_runtime.py
import json
import os
import re
from pathlib import Path
from typing import Optional, Tuple, List
from datetime import timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import LabeledPrice

from asgiref.sync import sync_to_async
from django.conf import settings
from django.utils import timezone

# Django models
from bot.models import User, Message, BlockedUser, SizeSearch
from panel.models import GlassAlias, GlassLine, GlassSize

# Premium app models (you должны создать app premium и применить миграции)
from premium.models import PremiumPlan, PremiumSubscription, StarsPayment


# ----------------- Настройки -----------------

def _get_setting(name: str, default=None):
    return getattr(settings, name, os.getenv(name, default))


BOT_TOKEN = _get_setting("BOT_TOKEN", None) or _get_setting("tok", None)
ADMIN_ID = int(_get_setting("ADMIN_ID", 0) or 0)
WEBAPP_URL = _get_setting("WEBAPP_URL", "https://yur1on.github.io/tg-size-webapp/")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not found. Add BOT_TOKEN to settings.py or environment variables.")


# ----------------- Данные -----------------

belarusian_cities = [
    "minsk", "минск",
    "grodno", "гродно",
    "brest", "брест",
    "vitebsk", "витебск",
    "mogilev", "могилев",
    "gomel", "гомель",
    "baranovichi", "барановичи",
    "bobruisk", "бобруйск",
    "borisov", "борисов",
    "pinsk", "пинск",
    "orsha", "орша",
    "mozyr", "мозырь",
    "soligorsk", "солигорск",
    "lida", "лида",
    "novopolotsk", "новополоцк",
    "polotsk", "полоцк",
]

AD_TEXT = (
    '<b>Для жителей РБ 🇧🇾</b>\n'
    'Сервис для разборщиков мобильной техники.\n'
    'Канал: <a href="https://t.me/MobiraRazbor">@MobiraRazbor</a>\n'
    'Чат: <a href="https://t.me/mobirazbor_chat">@mobirazbor_chat</a>\n'
    'Сайт: <a href="https://mobirazbor.by">mobirazbor.by</a>'
)


def normalize_query(q: str) -> str:
    return (q or "").strip().lower()


def add_src(url: str, src: str) -> str:
    return f"{url}&src={src}" if "?" in url else f"{url}?src={src}"


# ----------------- Premium helpers -----------------

PREMIUM_FREE_LIMIT = 2  # без премиума показываем 2 результата


def _looks_like_meta_line(s: str) -> bool:
    """
    Строки-метаданные (типа Display: ...), которые не считаем "стеклами".
    """
    t = (s or "").strip().lower()
    if not t:
        return True
    if "display" in t:
        return True
    if "oled" in t or "pls" in t or "ips" in t:
        return True
    if t.startswith("<b>") and t.endswith("</b>"):
        return True
    return False


def split_lines_for_limit(lines: List[str]) -> Tuple[List[str], List[str]]:
    """
    Возвращает (model_lines, meta_lines).
    model_lines: то, что ограничиваем до 2 для free
    meta_lines: показываем всегда (например Display: ...)
    """
    model_lines: List[str] = []
    meta_lines: List[str] = []
    for ln in (lines or []):
        if _looks_like_meta_line(ln):
            meta_lines.append(ln)
        else:
            model_lines.append(ln)
    return model_lines, meta_lines


def apply_free_limit(lines: List[str], limit: int = PREMIUM_FREE_LIMIT) -> Tuple[List[str], int]:
    """
    Возвращает (visible_lines, hidden_count) — ограничивает только "модельные" строки.
    """
    model_lines, meta_lines = split_lines_for_limit(lines)
    if len(model_lines) <= limit:
        visible_models = model_lines
        hidden = 0
    else:
        visible_models = model_lines[:limit]
        hidden = len(model_lines) - limit

    visible = visible_models + meta_lines
    return visible, hidden


# ----------------- Django ORM helpers (async wrappers) -----------------

@sync_to_async(thread_sensitive=True)
def db_is_user_blocked(user_id: int) -> bool:
    return BlockedUser.objects.filter(user_id=user_id).exists()


@sync_to_async(thread_sensitive=True)
def db_get_user(chat_id: int) -> Optional[User]:
    return User.objects.filter(chat_id=chat_id).first()


@sync_to_async(thread_sensitive=True)
def db_save_message(chat_id: int, text: str) -> None:
    # IMPORTANT: модели bot.models сейчас у тебя с managed=False и db_table="messages"
    # Это ок, если таблица реально называется "messages".
    Message.objects.create(chat_id=chat_id, message_text=text or "")


@sync_to_async(thread_sensitive=True)
def db_upsert_user(chat_id: int, name: str, city: str, phone_number: str) -> None:
    User.objects.update_or_create(
        chat_id=chat_id,
        defaults={"name": name or "", "city": city or "", "phone_number": phone_number or ""},
    )


@sync_to_async(thread_sensitive=True)
def db_delete_user(chat_id: int) -> int:
    return User.objects.filter(chat_id=chat_id).delete()[0]


@sync_to_async(thread_sensitive=True)
def db_block_user(user_id: int) -> None:
    BlockedUser.objects.get_or_create(user_id=user_id)


@sync_to_async(thread_sensitive=True)
def db_unblock_user(user_id: int) -> None:
    BlockedUser.objects.filter(user_id=user_id).delete()


@sync_to_async(thread_sensitive=True)
def db_get_belarus_chat_ids() -> List[int]:
    qs = User.objects.exclude(city__isnull=True).exclude(city__exact="")
    out: List[int] = []
    for u in qs:
        if (u.city or "").strip().lower() in belarusian_cities:
            out.append(u.chat_id)
    return out


@sync_to_async(thread_sensitive=True)
def db_save_size_search(chat_id: int, height: float, width: float, found_count: int, source: str) -> None:
    SizeSearch.objects.create(
        chat_id=int(chat_id),
        height=float(height),
        width=float(width),
        found_count=int(found_count),
        source=str(source or "unknown"),
        timestamp=timezone.now(),
    )


@sync_to_async(thread_sensitive=True)
def db_find_card_by_alias(user_query: str) -> Optional[Tuple[List[str], str]]:
    """
    Возвращает (lines, photo_filename) или None.
    Данные берутся из БД: GlassAlias -> card -> lines
    """
    q = normalize_query(user_query)
    if not q:
        return None

    alias = (
        GlassAlias.objects
        .select_related("card")
        .filter(query=q)
        .first()
    )
    if not alias:
        return None

    card = alias.card
    lines = list(
        GlassLine.objects
        .filter(card=card)
        .order_by("sort_order", "id")
        .values_list("text", flat=True)
    )
    photo = (getattr(card, "photo_filename", "") or "").strip()
    return lines, photo


@sync_to_async(thread_sensitive=True)
def db_find_sizes(height: float, width: float) -> List[dict]:
    """
    Возвращает список {model, photo_path}
    """
    qs = GlassSize.objects.filter(height=height, width=width)
    return [{"model": x.model_name, "photo_path": x.photo_path} for x in qs]


# -------- Premium DB wrappers --------

@sync_to_async(thread_sensitive=True)
def db_get_subscription(chat_id: int) -> Optional[PremiumSubscription]:
    return PremiumSubscription.objects.filter(chat_id=chat_id).first()


@sync_to_async(thread_sensitive=True)
def db_is_premium(chat_id: int) -> bool:
    sub = PremiumSubscription.objects.filter(chat_id=chat_id).first()
    return bool(sub and sub.active_until and sub.active_until >= timezone.now())


@sync_to_async(thread_sensitive=True)
def db_get_active_plans() -> List[PremiumPlan]:
    # Покажем все активные (у тебя 4 тарифа)
    return list(PremiumPlan.objects.filter(is_active=True).order_by("price_stars"))


@sync_to_async(thread_sensitive=True)
def db_get_plan_by_code(code: str) -> Optional[PremiumPlan]:
    return PremiumPlan.objects.filter(code=code, is_active=True).first()


@sync_to_async(thread_sensitive=True)
def db_activate_premium(chat_id: int, days: int) -> PremiumSubscription:
    """
    ВАЖНО: если Premium уже активен — продлеваем от active_until.
    Если не активен — считаем от сейчас.
    """
    now = timezone.now()
    sub = PremiumSubscription.objects.filter(chat_id=chat_id).first()

    if sub and sub.active_until and sub.active_until > now:
        base = sub.active_until
    else:
        base = now

    until = base + timedelta(days=int(days))

    sub, _ = PremiumSubscription.objects.update_or_create(
        chat_id=chat_id,
        defaults={"active_until": until},
    )
    return sub


@sync_to_async(thread_sensitive=True)
def db_log_stars_payment(
    chat_id: int,
    plan: Optional[PremiumPlan],
    payload: str,
    currency: str,
    total_amount: int,
    telegram_charge_id: str,
    provider_charge_id: str,
) -> None:
    StarsPayment.objects.create(
        chat_id=chat_id,
        plan=plan,
        invoice_payload=payload,
        currency=currency,
        total_amount=total_amount,
        telegram_payment_charge_id=telegram_charge_id or "",
        provider_payment_charge_id=provider_charge_id or "",
    )


# ----------------- UI: клавиатуры -----------------

async def create_menu_button():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    start_button = types.KeyboardButton('🚀 start')
    registration_button = types.KeyboardButton('🗂registration')
    help_button = types.KeyboardButton('ℹ️ Info')

    size_button = types.KeyboardButton(
        '🔎подбор стекла по размеру',
        web_app=types.WebAppInfo(url=add_src(WEBAPP_URL, "menu"))
    )
    premium_button = types.KeyboardButton('⭐ Premium')

    markup.add(start_button, registration_button, help_button)
    markup.add(size_button)
    markup.add(premium_button)
    return markup


def premium_inline_keyboard(plans: List[PremiumPlan], active: bool) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    action = "Продлить" if active else "Купить"
    for p in plans[:4]:
        kb.add(
            types.InlineKeyboardButton(
                text=f"⭐ {action}: {p.title} — {p.duration_days} дн. — {p.price_stars} Stars",
                callback_data=f"premium:buy:{p.code}",
            )
        )
    kb.add(types.InlineKeyboardButton(text="❌ Закрыть", callback_data="premium:close"))
    return kb


def upgrade_inline_button() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("⭐ Открыть всё (Premium)", callback_data="premium:show"))
    return kb


# ----------------- FSM: Регистрация -----------------

class UserRegistration(StatesGroup):
    name = State()
    city = State()
    phone_number = State()


# ----------------- Runtime builder -----------------

def build_runtime():
    bot = Bot(BOT_TOKEN, parse_mode="HTML")
    dp = Dispatcher(bot, storage=MemoryStorage())

    # ----------------- Админ команды -----------------

    @dp.message_handler(commands=['block'])
    async def block_user_cmd(message: types.Message):
        if ADMIN_ID and message.from_user.id != ADMIN_ID:
            await message.answer("У вас нет прав.")
            return
        try:
            user_id_to_block = int(message.text.split()[1])
            await db_block_user(user_id_to_block)
            await message.reply(f"Пользователь с ID {user_id_to_block} заблокирован.")
        except (IndexError, ValueError):
            await message.reply("Используйте команду: /block <user_id>")

    @dp.message_handler(commands=['unblock'])
    async def unblock_user_cmd(message: types.Message):
        if ADMIN_ID and message.from_user.id != ADMIN_ID:
            await message.answer("У вас нет прав.")
            return
        try:
            user_id_to_unblock = int(message.text.split()[1])
            await db_unblock_user(user_id_to_unblock)
            await message.reply(f"Пользователь с ID {user_id_to_unblock} разблокирован.")
        except (IndexError, ValueError):
            await message.reply("Используйте команду: /unblock <user_id>")

    @dp.message_handler(commands=['send'])
    async def send_updates_command(message: types.Message):
        if ADMIN_ID and message.from_user.id != ADMIN_ID:
            await message.answer("У вас нет прав для отправки сообщений.")
            return

        message_text = (
            "Друзья! Представляем новый проект — mobirazbor.by :\n"
            "платформа для разборщиков мобильной техники,\n"
            "удобный сервис для учёта и поиска запчастей мобильной техники.\n"
            "🔹Личный склад\n🔹Умный поиск по всей базе\n🔹Поддержка фото, описаний, отзывов и связи между пользователями\n"
        )

        chat_ids = await db_get_belarus_chat_ids()
        sent = 0
        for chat_id in chat_ids:
            try:
                await bot.send_message(chat_id, message_text)
                sent += 1
            except Exception:
                pass
        await message.answer(f"Сообщение отправлено. Доставлено: {sent}/{len(chat_ids)}")

    @dp.message_handler(commands=['send_to_user'])
    async def send_to_user_command(message: types.Message):
        if ADMIN_ID and message.from_user.id != ADMIN_ID:
            await message.answer("У вас нет прав.")
            return
        try:
            user_id = int(message.text.split()[1])
            message_text = ' '.join(message.text.split()[2:])
            await bot.send_message(user_id, message_text)
            await message.answer(f"Сообщение отправлено пользователю {user_id}.")
        except (IndexError, ValueError):
            await message.answer("Формат: /send_to_user <ID> <текст>")

    # ----------------- /delete_registration -----------------

    @dp.message_handler(commands=['delete_registration'])
    async def delete_registration(message: types.Message):
        chat_id = message.chat.id
        deleted = await db_delete_user(chat_id)
        if deleted:
            await bot.send_message(chat_id, "Ваши регистрационные данные успешно удалены. Для регистрации: /registration")
        else:
            await bot.send_message(chat_id, "Запись не найдена. Для регистрации: /registration")

    # ----------------- Premium: меню/покупка Stars -----------------

    async def show_premium_menu(chat_id: int):
        sub = await db_get_subscription(chat_id)
        now = timezone.now()
        active = bool(sub and sub.active_until and sub.active_until >= now)

        if active:
            status = f"✅ <b>Premium активен</b>\nДо: <b>{sub.active_until:%d.%m.%Y %H:%M}</b>\n\n"
        else:
            status = "🔒 <b>Premium не активен</b>\n\n"

        plans = await db_get_active_plans()
        if not plans:
            await bot.send_message(
                chat_id,
                status +
                "⚠️ Тарифы Premium не настроены в админке.\n"
                "Админу: создайте PremiumPlan и включите is_active.",
            )
            return

        await bot.send_message(
            chat_id,
            status +
            "⭐ <b>Premium подписка</b>\n"
            "Без Premium показываем только 2 результата.\n"
            "С Premium — полный список без ограничений.\n\n"
            "Выберите тариф 👇",
            reply_markup=premium_inline_keyboard(plans, active=active),
        )

    @dp.message_handler(commands=["premium"])
    async def premium_cmd(message: types.Message):
        await db_save_message(message.chat.id, message.text)
        await show_premium_menu(message.chat.id)

    @dp.message_handler(lambda m: (m.text or "").strip() == "⭐ Premium")
    async def premium_button_handler(message: types.Message):
        await db_save_message(message.chat.id, message.text)
        await show_premium_menu(message.chat.id)

    @dp.callback_query_handler(lambda c: c.data == "premium:show")
    async def premium_show_cb(call: types.CallbackQuery):
        await call.answer()
        await show_premium_menu(call.from_user.id)

    @dp.callback_query_handler(lambda c: c.data == "premium:close")
    async def premium_close_cb(call: types.CallbackQuery):
        await call.answer("Ок")
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

    @dp.callback_query_handler(lambda c: c.data and c.data.startswith("premium:buy:"))
    async def premium_buy_cb(call: types.CallbackQuery):
        await call.answer()
        chat_id = call.from_user.id

        plan_code = call.data.split("premium:buy:", 1)[1].strip()
        plan = await db_get_plan_by_code(plan_code)
        if not plan:
            await bot.send_message(chat_id, "Тариф не найден или отключён. Напишите админу.")
            return

        # payload должен быть уникальным
        payload = f"premium:{chat_id}:{int(timezone.now().timestamp())}:{plan.code}"

        # В Stars: currency="XTR" и provider_token="" (пустой)
        prices = [LabeledPrice(label=f"{plan.title} ({plan.duration_days} дней)", amount=int(plan.price_stars))]

        await bot.send_invoice(
            chat_id=chat_id,
            title=f"{plan.title}",
            description="Открывает полный список результатов без ограничений.",
            payload=payload,
            provider_token="",
            currency="XTR",
            prices=prices,
            start_parameter="premium",
        )

    @dp.pre_checkout_query_handler(lambda q: True)
    async def process_pre_checkout(pre_checkout_query: types.PreCheckoutQuery):
        await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

    @dp.message_handler(content_types=types.ContentType.SUCCESSFUL_PAYMENT)
    async def successful_payment_handler(message: types.Message):
        chat_id = message.chat.id
        sp = message.successful_payment

        payload = sp.invoice_payload or ""
        plan_code = ""
        try:
            parts = payload.split(":")
            if len(parts) >= 4:
                plan_code = parts[3]
        except Exception:
            plan_code = ""

        plan = await db_get_plan_by_code(plan_code) if plan_code else None
        days = int(plan.duration_days) if plan else 30

        await db_log_stars_payment(
            chat_id=chat_id,
            plan=plan,
            payload=payload,
            currency=sp.currency,
            total_amount=int(sp.total_amount),
            telegram_charge_id=getattr(sp, "telegram_payment_charge_id", "") or "",
            provider_charge_id=getattr(sp, "provider_payment_charge_id", "") or "",
        )

        sub = await db_activate_premium(chat_id, days)

        await bot.send_message(
            chat_id,
            f"✅ <b>Premium активирован!</b>\n"
            f"Добавлено: {days} дней\n"
            f"Действует до: <b>{sub.active_until:%d.%m.%Y %H:%M}</b>\n\n"
            "Теперь будут показываться все результаты без ограничений. ⭐"
        )

    # ----------------- /size -----------------

    @dp.message_handler(commands=['size'])
    async def size_cmd(message: types.Message):
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        kb.add(
            types.KeyboardButton(
                "🔎подбор стекла по размеру",
                web_app=types.WebAppInfo(url=add_src(WEBAPP_URL, "cmd"))
            )
        )
        kb.add(types.KeyboardButton("↩️ В меню"))

        await message.answer(
            "🔎 <b>Подбор стекла по размерам</b>\n\n"
            "Нажмите кнопку 👇 «🔎подбор стекла по размеру».\n\n"
            "Если передумали — нажмите «↩️ В меню».",
            reply_markup=kb
        )

    @dp.message_handler(lambda m: m.text == "↩️ В меню")
    async def back_to_menu(message: types.Message):
        await message.answer("Меню:", reply_markup=await create_menu_button())

    # ----------------- /info -----------------

    @dp.message_handler(commands=['info'])
    async def handle_info(message: types.Message):
        chat_id = message.chat.id
        await bot.send_message(
            chat_id,
            "🤖 Я бот для поиска взаимозаменяемых моделей стекол телефонов и планшетов.\n\n"
            "✔️Для поиска взаимозаменяемых стекол отправьте сообщение нужной модели\n\n"
            "✔️Для подбора стекла по размерам: кнопка «🔎подбор стекла по размеру» или команда /size\n\n"
            "✔️/registration - команда для регистрации\n\n"
            "✔️/delete_registration - команда для удаления своих регистрационных данных из базы\n\n"
            "⭐ Premium: /premium — открыть полный список результатов\n\n"
            "✔️Если нашли ошибку или знаете взаимозаменяемую модель стекла, напишите пожалуйста @expert_glass_lcd\n",
            reply_markup=await create_menu_button()
        )

    @dp.message_handler(lambda message: message.text == 'ℹ️ Info')
    async def info_button_handler(message: types.Message):
        await db_save_message(message.chat.id, message.text)
        await handle_info(message)

    # ----------------- /start и кнопка start -----------------

    async def send_message_with_ad(chat_id: int, text: str, reply_markup=None):
        await bot.send_message(chat_id, text + "\n\nmobirazbor.by", reply_markup=reply_markup)

    @dp.message_handler(commands=['start'])
    async def start_cmd(message: types.Message):
        chat_id = message.chat.id
        await db_save_message(chat_id, message.text)

        user = await db_get_user(chat_id)
        if user:
            await send_message_with_ad(
                chat_id,
                f"Привет👋, @{message.from_user.username}!\n"
                "Введите модель стекла телефона или планшета, которое вы ищете.\n"
                "Изучите информацию и откройте доп. кнопки 👉 /info\n\n"
                "⭐ Premium: /premium",
                reply_markup=await create_menu_button(),
            )
        else:
            await send_message_with_ad(
                chat_id,
                "Это бот для поиска взаимозаменяемых стекол для переклейки.\n"
                "Для пользования ботом, пожалуйста, зарегистрируйтесь! Используйте команду /registration",
                reply_markup=await create_menu_button(),
            )

    @dp.message_handler(lambda message: message.text == '🚀 start')
    async def start_button_handler(message: types.Message):
        chat_id = message.chat.id
        await db_save_message(chat_id, message.text)

        user = await db_get_user(chat_id)
        if user:
            await bot.send_message(
                chat_id,
                f"Привет👋, @{message.from_user.username}\n"
                "Введите модель стекла телефона или планшета, которое вы ищете.\n"
                "Изучите информацию и откройте доп. кнопки 👉 /info\n\n"
                "⭐ Premium: /premium",
                reply_markup=await create_menu_button()
            )
        else:
            await bot.send_message(
                chat_id,
                "Это бот для поиска взаимозаменяемых стекол для переклейки.\n"
                "Для пользования ботом, пожалуйста, зарегистрируйтесь! Используйте команду /registration",
                reply_markup=await create_menu_button()
            )

    # ----------------- Регистрация -----------------

    @dp.message_handler(commands=['registration'])
    async def start_registration(message: types.Message, state: FSMContext):
        chat_id = message.chat.id
        user = await db_get_user(chat_id)
        if user:
            await bot.send_message(
                chat_id,
                f"Вы зарегистрированы!\n"
                f"Ваше имя: {user.name}\nВаш город: {user.city}\nВаш № тел.: {user.phone_number}\n\n"
                "Для удаления данных: /delete_registration"
            )
        else:
            await bot.send_message(chat_id, "Здравствуйте!\nВведите свое имя для регистрации:")
            await UserRegistration.name.set()

    @dp.message_handler(lambda message: message.text == '🗂registration')
    async def registration_button_handler(message: types.Message, state: FSMContext):
        chat_id = message.chat.id
        await db_save_message(chat_id, message.text)
        await start_registration(message, state)

    @dp.message_handler(state=UserRegistration.name)
    async def register_name(message: types.Message, state: FSMContext):
        chat_id = message.chat.id
        name = (message.text or "").strip()
        await state.update_data(name=name)
        await UserRegistration.city.set()
        await bot.send_message(chat_id, "Введите Ваш город:", reply_markup=await create_menu_button())

    @dp.message_handler(lambda message: (message.text or "").isdigit(), state=UserRegistration.city)
    async def register_invalid_city(message: types.Message):
        await bot.send_message(message.chat.id, "Некорректно введен город!")

    @dp.message_handler(state=UserRegistration.city)
    async def register_city(message: types.Message, state: FSMContext):
        chat_id = message.chat.id
        city = (message.text or "").strip()
        await state.update_data(city=city)
        await UserRegistration.phone_number.set()
        await bot.send_message(chat_id, "Введите Ваш номер телефона:")

    @dp.message_handler(lambda message: not (message.text or "").isdigit(), state=UserRegistration.phone_number)
    async def register_invalid_phone(message: types.Message):
        await bot.send_message(
            message.chat.id,
            "Номер телефона должен содержать только цифры. Пожалуйста, введите корректный номер телефона."
        )

    @dp.message_handler(lambda message: (message.text or "").isdigit(), state=UserRegistration.phone_number)
    async def register_phone(message: types.Message, state: FSMContext):
        chat_id = message.chat.id
        phone_number = (message.text or "").strip()

        data = await state.get_data()
        name = data.get("name", "")
        city = data.get("city", "")

        await db_upsert_user(chat_id, name, city, phone_number)
        await state.finish()

        await bot.send_message(
            chat_id,
            "Регистрация успешно завершена!\n\n"
            "Введите модель стекла телефона или планшета, которое вы ищите.\n\n"
            "Изучите информацию и откройте доп. кнопки 👉 /info"
        )

    # ----------------- WebApp: поиск по размерам -----------------

    @dp.message_handler(content_types=types.ContentType.WEB_APP_DATA)
    async def handle_size_webapp(message: types.Message, state: FSMContext):
        chat_id = message.chat.id

        user = await db_get_user(chat_id)
        if not user:
            await bot.send_message(
                chat_id,
                "Для пользования ботом пожалуйста зарегистрируйтесь!\nИспользуйте команду 👉 /registration",
                reply_markup=await create_menu_button()
            )
            return

        try:
            data = json.loads(message.web_app_data.data)
            height = float(str(data.get("height", "")).replace(",", "."))
            width = float(str(data.get("width", "")).replace(",", "."))
            source = str(data.get("src", "unknown"))
        except Exception:
            await bot.send_message(
                chat_id,
                "Некорректный формат. Введите длину и ширину числами (можно с запятой).",
                reply_markup=await create_menu_button()
            )
            return

        found = await db_find_sizes(height, width)
        await db_save_size_search(chat_id, height, width, len(found), source)

        if found:
            await bot.send_message(
                chat_id,
                f"<em><u>Стекла по размерам {height}x{width} найдено:</u></em>",
            )
            for row in found:
                model = row.get("model")
                photo_path = row.get("photo_path") or ""
                if photo_path and os.path.exists(photo_path):
                    with open(photo_path, "rb") as photo:
                        await bot.send_photo(chat_id, photo, caption=f"<b>Модель:</b> {model}")
                else:
                    await bot.send_message(chat_id, f"<b>Модель:</b> {model}")
        else:
            await bot.send_message(
                chat_id,
                "🔘По указанным размерам ничего не найдено!\n"
                "🔘Попробуйте увеличить или уменьшить размер в запросе на 0,5мм"
            )

        await bot.send_message(chat_id, "Меню:", reply_markup=await create_menu_button())

    # ----------------- Фото callback -----------------

    @dp.callback_query_handler(lambda query: query.data and query.data.startswith('photo:'))
    async def process_photo_callback(callback_query: types.CallbackQuery):
        photo_name = callback_query.data.split(':', 1)[1].strip()

        base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))
        possible_paths = [
            base_dir / "photos1" / photo_name,
            base_dir / "photos" / photo_name,
            base_dir / photo_name,
            Path(photo_name),
        ]

        photo_path = None
        for p in possible_paths:
            try:
                if p.exists():
                    photo_path = p
                    break
            except Exception:
                continue

        query_text = callback_query.message.text or ""

        if photo_path:
            lines = [ln.strip() for ln in query_text.splitlines()]
            found_lines = [ln for ln in lines[1:] if ln]
            photo_caption = "<b>Фото стекла:</b>\n" + "\n".join(found_lines) if found_lines else "<b>Фото стекла</b>"

            await bot.send_photo(
                callback_query.from_user.id,
                open(photo_path, 'rb'),
                caption=photo_caption,
                parse_mode='html'
            )
        else:
            await bot.send_message(callback_query.from_user.id, "Фото не найдено.")

    # ----------------- Основной текстовый обработчик (ПОИСК ИЗ БД!) -----------------

    @dp.message_handler()
    async def handle_text(message: types.Message, state: FSMContext):
        user_message = message.text
        if not user_message:
            return

        user_message_lower = normalize_query(user_message)
        chat_id = message.chat.id

        await db_save_message(chat_id, user_message_lower)

        # блокировка
        if await db_is_user_blocked(message.from_user.id):
            await message.reply("Вы заблокированы и не можете использовать этого бота.")
            return

        # подсказки/валидация
        if 'galaxy' in user_message_lower:
            await bot.send_message(chat_id, "Повторите пожалуйста запрос не используя слово <b>galaxy</b>.")
            return
        if 'realmi' in user_message_lower:
            await bot.send_message(chat_id, "❗️Исправте <u>realmi</u> на <b>realme</b>.")
            return
        if 'techno' in user_message_lower:
            await bot.send_message(chat_id, "❗️Исправте <u>techno</u> на <b>tecno</b>.")
            return
        if 'tehno' in user_message_lower:
            await bot.send_message(chat_id, "❗️Исправте <u>tehno</u> на <b>tecno</b>.")
            return
        if '+' in user_message_lower:
            await bot.send_message(chat_id, "❗️Исправте знак <u>+</u> на слово <b>plus</b>.")
            return

        # русский текст — просим английский
        if re.search(r"[а-яё]", user_message_lower):
            await bot.send_message(chat_id, "Пожалуйста, пишите модель на <b>английском</b> языке.")
            return

        # регистрация обязательна
        user = await db_get_user(chat_id)
        if not user:
            await bot.send_message(chat_id, "Для пользования ботом зарегистрируйтесь: 👉 /registration")
            return

        found = await db_find_card_by_alias(user_message_lower)

        if found:
            lines, photo = found

            premium = await db_is_premium(chat_id)
            hidden_count = 0
            if not premium:
                lines, hidden_count = apply_free_limit(lines, PREMIUM_FREE_LIMIT)

            keyboard = types.InlineKeyboardMarkup(row_width=1)

            response = (
                f"<em><u>Взаимозаменяемые стекла по поиску 🔍<b>'{user_message}'</b> найдено:</u></em>\n"
            )
            for line in lines:
                response += f"{line}\n"

            if hidden_count > 0:
                response += (
                    f"\n🔒 <b>Ещё скрыто:</b> {hidden_count}\n"
                    f"⭐ Откройте всё: /premium"
                )
                keyboard.add(types.InlineKeyboardButton("⭐ Открыть всё (Premium)", callback_data="premium:show"))

            if photo:
                keyboard.add(
                    types.InlineKeyboardButton("Посмотреть фото стекла", callback_data=f"photo:{photo}")
                )

            await bot.send_message(chat_id, response, reply_markup=keyboard)
            await bot.send_message(chat_id, "\n" + AD_TEXT, disable_web_page_preview=True)
            return

        await bot.send_message(
            chat_id,
            "<em><b>По Вашему запросу ничего не найдено!</b>\n\n"
            "1️⃣ Проверьте ошибки при написании модели.\n"
            "2️⃣ Попробуйте ввести полное название модели.\n\n"
            "🔎 <b>Вы можете подобрать стекло по размерам</b>\n"
            "👇 <b>нажмите кнопку внизу меню</b>\n"
            "«🔎подбор стекла по размеру»\n"
            "или команда /size</em>",
            reply_markup=await create_menu_button()
        )

    # ----------------- runner -----------------

    def runner():
        executor.start_polling(dp, skip_updates=False)

    return runner
