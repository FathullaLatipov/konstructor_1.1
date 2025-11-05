import re
import asyncio
import logging
from aiogram import types
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async

from your_app.models import Bot
from your_project.settings import settings_conf
from your_project.utils import create_bot, get_user_by_uid, set_bot_webhook

logger = logging.getLogger(__name__)

# --- Основная функция ---

@create_bot_router.message(StateFilter(CreateBotStates.waiting_for_token))
async def process_token(message: types.Message, state: FSMContext):
    logger.info(f"[START] process_token от {message.from_user.id} | текст: {message.text}")

    token = message.text.strip()

    # Проверка формата
    if not re.match(r'^\d{8,10}:[A-Za-z0-9_-]{35}$', token):
        await message.answer(
            "❌ <b>Неправильный формат токена!</b>\n\n"
            "Токен должен быть в формате:\n"
            "<code>1234567890:AAHfn3yN8ZSN9JXOp4RgQOtHqEbWr-abc</code>\n\n"
            "🔄 Попробуйте снова или нажмите /start.",
            parse_mode="HTML"
        )
        return

    # Проверка в БД
    is_valid, error_message = await validate_bot_token(token)
    if not is_valid:
        await message.answer(f"❌ <b>Ошибка токена:</b> {error_message}", parse_mode="HTML")
        return

    # Анимация проверки
    loading_msg = await message.answer("⏳ <b>Проверка токена...</b>", parse_mode="HTML")

    # Получаем данные о боте из Telegram с таймаутом
    try:
        bot_info = await asyncio.wait_for(get_bot_info_from_telegram(token), timeout=6)
    except asyncio.TimeoutError:
        await loading_msg.edit_text("⏳ <b>Telegram API долго не отвечает. Попробуйте позже.</b>", parse_mode="HTML")
        return

    if not bot_info:
        await loading_msg.edit_text(
            "❌ <b>Не удалось получить данные о боте.</b>\n"
            "Проверьте токен и попробуйте снова.",
            parse_mode="HTML"
        )
        return

    if not bot_info.get('is_bot', False):
        await loading_msg.edit_text(
            "❌ <b>Это не токен бота!</b>\n"
            "Создайте бота в @BotFather и введите корректный токен.",
            parse_mode="HTML"
        )
        return

    # Проверка выбора модуля
    data = await state.get_data()
    selected_module = data.get("selected_module")

    if not selected_module:
        await loading_msg.edit_text("❌ <b>Модуль не выбран!</b> Начните заново /start", parse_mode="HTML")
        return

    # Проверка пользователя
    user = await get_user_by_uid(message.from_user.id)
    if not user:
        await loading_msg.edit_text("❌ <b>Пользователь не найден!</b> Введите /start", parse_mode="HTML")
        return

    # Сохраняем данные в state
    await state.update_data(
        token=token,
        bot_username=bot_info["username"],
        bot_name=bot_info["first_name"],
        bot_id=bot_info["id"]
    )

    # Создаем запись бота
    await loading_msg.edit_text("⚙️ <b>Создание бота...</b>", parse_mode="HTML")
    modules = {selected_module: True}

    try:
        new_bot = await create_bot(
            owner_uid=message.from_user.id,
            token=token,
            username=bot_info["username"],
            modules=modules
        )
    except Exception as e:
        logger.exception(f"Ошибка при создании бота: {e}")
        await loading_msg.edit_text("❌ Ошибка при создании бота. Попробуйте позже.", parse_mode="HTML")
        return

    if not new_bot:
        await loading_msg.edit_text("❌ Не удалось создать бота. Повторите попытку позже.", parse_mode="HTML")
        return

    # Установка вебхука
    webhook_url = settings_conf.WEBHOOK_URL.format(token=token)
    webhook_success = await set_bot_webhook(token, webhook_url)

    if not webhook_success:
        logger.warning(f"Webhook не установлен для @{bot_info['username']}")
        await loading_msg.edit_text(
            "⚠️ <b>Бот создан, но вебхук не установлен.</b>\n"
            "Возможно, потребуется ручная настройка.",
            parse_mode="HTML"
        )

    # Информация о модуле
    module_names = {
        'refs': '👥 Реферальный',
        'leo': '💞 Дайвинчик',
        'music': '💬 Asker Бот',
        'kino': '🎥 Кинотеатр',
        'download': '💾 DownLoader',
        'chatgpt': '💡 ChatGPT'
    }

    selected_module_name = module_names.get(selected_module, f"⚙️ {selected_module}")

    # Финальное сообщение
    success_text = (
        f"🎉 <b>Бот успешно создан!</b>\n\n"
        f"🤖 <b>Информация:</b>\n"
        f"• <b>Username:</b> @{bot_info['username']}\n"
        f"• <b>Имя:</b> {bot_info['first_name']}\n"
        f"• <b>ID:</b> <code>{bot_info['id']}</code>\n\n"
        f"🔧 <b>Модуль:</b> {selected_module_name}\n\n"
        f"🚀 <b>Ссылка:</b> https://t.me/{bot_info['username']}\n\n"
        f"✨ Бот готов к работе!"
    )

    await loading_msg.edit_text(
        success_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Открыть бот", url=f"https://t.me/{bot_info['username']}")],
            [InlineKeyboardButton(text="🤖 Мои боты", callback_data="my_bots")],
            [InlineKeyboardButton(text="➕ Создать еще", callback_data="create_bot")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")]
        ]),
        parse_mode="HTML"
    )

    logger.info(f"[SUCCESS] @{bot_info['username']} создан пользователем {message.from_user.id}")

    # Очистка состояния
    await state.clear()
