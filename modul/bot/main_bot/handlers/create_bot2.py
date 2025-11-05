# import re
# import asyncio
# import logging
# from aiogram import Router, types
# from aiogram.filters import StateFilter
# from aiogram.fsm.context import FSMContext
# from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
# from asgiref.sync import sync_to_async
# from your_app.models import Bot
# from your_project.settings import settings_conf
# from your_project.utils import create_bot, get_user_by_uid, set_bot_webhook
# from states import CreateBotStates  # твой класс состояний FSM
#
# create_bot_router = Router()
# logger = logging.getLogger(__name__)
#
#
# # --- Проверка токена ---
# @sync_to_async
# def validate_bot_token(token: str):
#     """Проверка токена на формат и дубликат"""
#     if not re.match(r'^\d{8,10}:[A-Za-z0-9_-]{35}$', token):
#         return False, "Неправильный формат токена"
#
#     try:
#         if Bot.objects.filter(token=token).exists():
#             return False, "Этот токен уже используется другим ботом"
#         return True, "Токен корректный"
#     except Exception as e:
#         logger.error(f"Ошибка при проверке токена {token}: {e}")
#         return False, "Ошибка при проверке токена в БД"
#
#
# # --- Получение данных о боте ---
# async def get_bot_info_from_telegram(token: str):
#     """Запрос getMe к Telegram API с таймаутом"""
#     import aiohttp
#     url = f"https://api.telegram.org/bot{token}/getMe"
#
#     try:
#         timeout = aiohttp.ClientTimeout(total=5)
#         async with aiohttp.ClientSession(timeout=timeout) as session:
#             async with session.get(url) as response:
#                 if response.status != 200:
#                     logger.warning(f"Telegram API вернул статус {response.status}")
#                     return None
#
#                 data = await response.json()
#                 if not data.get("ok"):
#                     logger.warning(f"Telegram ошибка: {data}")
#                     return None
#
#                 result = data["result"]
#                 return {
#                     "id": result["id"],
#                     "username": result["username"],
#                     "first_name": result.get("first_name", ""),
#                     "is_bot": result["is_bot"],
#                 }
#
#     except asyncio.TimeoutError:
#         logger.error(f"Таймаут при обращении к Telegram API (token={token})")
#         return None
#     except Exception as e:
#         logger.exception(f"Ошибка при запросе getMe: {e}")
#         return None
#
#
# # --- Обработка выбора модуля ---
# @create_bot_router.callback_query(lambda c: c.data and c.data.startswith("select_module:"))
# async def module_select_handler(callback: types.CallbackQuery, state: FSMContext):
#     module_key = callback.data.split(":", 1)[1]
#
#     await state.update_data(selected_module=module_key)
#     await state.set_state(CreateBotStates.waiting_for_token)
#
#     await callback.message.edit_text(
#         f"✅ Выбран модуль: <b>{module_key}</b>\n\n"
#         f"Теперь отправьте токен вашего бота (из @BotFather):",
#         parse_mode="HTML"
#     )
#     await callback.answer()
#
#
# # --- Основная функция обработки токена ---
# @create_bot_router.message(StateFilter(CreateBotStates.waiting_for_token))
# async def process_token(message: types.Message, state: FSMContext):
#     logger.info(f"[START] process_token от {message.from_user.id} | текст: {message.text}")
#
#     # Проверяем состояние
#     data = await state.get_data()
#     logger.info(f"FSM DATA: {data}")
#
#     if not data or "selected_module" not in data:
#         kb = InlineKeyboardMarkup(inline_keyboard=[
#             [InlineKeyboardButton("👥 Рефы", callback_data="select_module:refs"),
#              InlineKeyboardButton("💬 Asker", callback_data="select_module:anon")],
#             [InlineKeyboardButton("💡 ChatGPT", callback_data="select_module:chatgpt")]
#         ])
#         await message.answer(
#             "❌ <b>Модуль не выбран!</b>\n\n"
#             "Пожалуйста, выберите модуль снова:",
#             reply_markup=kb,
#             parse_mode="HTML"
#         )
#         return
#
#     selected_module = data["selected_module"]
#
#     token = message.text.strip()
#     if not re.match(r'^\d{8,10}:[A-Za-z0-9_-]{35}$', token):
#         await message.answer(
#             "❌ <b>Неправильный формат токена!</b>\n\n"
#             "Введите токен снова или нажмите /start",
#             parse_mode="HTML"
#         )
#         return
#
#     # Проверка токена в БД
#     is_valid, error_message = await validate_bot_token(token)
#     if not is_valid:
#         await message.answer(f"❌ <b>Ошибка токена:</b> {error_message}", parse_mode="HTML")
#         return
#
#     # Проверяем бота через Telegram API
#     loading_msg = await message.answer("⏳ Проверка токена...", parse_mode="HTML")
#     try:
#         bot_info = await asyncio.wait_for(get_bot_info_from_telegram(token), timeout=6)
#     except asyncio.TimeoutError:
#         await loading_msg.edit_text("⏳ Telegram API долго не отвечает. Попробуйте позже.")
#         return
#
#     if not bot_info or not bot_info.get("is_bot", False):
#         await loading_msg.edit_text("❌ Токен некорректный. Проверьте и попробуйте снова.")
#         return
#
#     user = await get_user_by_uid(message.from_user.id)
#     if not user:
#         await loading_msg.edit_text("❌ Пользователь не найден. Введите /start.")
#         return
#
#     # Сохраняем данные в FSM
#     await state.update_data(
#         token=token,
#         bot_username=bot_info["username"],
#         bot_name=bot_info["first_name"],
#         bot_id=bot_info["id"]
#     )
#
#     # Создаем нового бота
#     await loading_msg.edit_text("⚙️ Создание бота...", parse_mode="HTML")
#     modules = {selected_module: True}
#
#     new_bot = await create_bot(
#         owner_uid=message.from_user.id,
#         token=token,
#         username=bot_info["username"],
#         modules=modules
#     )
#
#     if not new_bot:
#         await loading_msg.edit_text("❌ Ошибка при создании бота. Попробуйте позже.")
#         return
#
#     webhook_url = settings_conf.WEBHOOK_URL.format(token=token)
#     webhook_success = await set_bot_webhook(token, webhook_url)
#
#     # Имена модулей
#     module_names = {
#         'refs': '👥 Реферальный',
#         'leo': '💞 Дайвинчик',
#         'anon': '💬 Asker Бот',
#         'kino': '🎥 Кинотеатр',
#         'download': '💾 DownLoader',
#         'chatgpt': '💡 ChatGPT'
#     }
#
#     selected_module_name = module_names.get(selected_module, f"⚙️ {selected_module}")
#
#     success_text = (
#         f"🎉 <b>Бот успешно создан!</b>\n\n"
#         f"🤖 <b>Информация:</b>\n"
#         f"• Username: @{bot_info['username']}\n"
#         f"• Имя: {bot_info['first_name']}\n"
#         f"• ID: <code>{bot_info['id']}</code>\n\n"
#         f"🔧 Модуль: {selected_module_name}\n"
#         f"🚀 Ссылка: https://t.me/{bot_info['username']}\n\n"
#         f"✨ Бот готов к работе!"
#     )
#
#     await loading_msg.edit_text(
#         success_text,
#         reply_markup=InlineKeyboardMarkup(inline_keyboard=[
#             [InlineKeyboardButton(text="🔗 Открыть бот", url=f"https://t.me/{bot_info['username']}")],
#             [InlineKeyboardButton(text="🤖 Мои боты", callback_data="my_bots")],
#             [InlineKeyboardButton(text="➕ Создать еще", callback_data="create_bot")],
#             [InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_to_main")]
#         ]),
#         parse_mode="HTML"
#     )
#
#     logger.info(f"[SUCCESS] @{bot_info['username']} создан пользователем {message.from_user.id}")
#     await state.clear()
