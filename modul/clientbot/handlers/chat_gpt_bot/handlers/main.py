import html
import logging
import random
import os
import time
from asgiref.sync import sync_to_async
from aiogram import Bot, Dispatcher, types
from aiogram import F
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.types import FSInputFile, Message, CallbackQuery
from aiogram.utils.deep_linking import create_start_link
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
import asyncio

from modul.clientbot import shortcuts
from modul.clientbot.handlers.admin.keyboards import main_menu_bt
from modul.clientbot.handlers.chat_gpt_bot import buttons as bt
from modul.clientbot.handlers.chat_gpt_bot.all_openai import ChatGPT
from modul.clientbot.handlers.refs.handlers.bot import banned, check_channels
from modul.clientbot.handlers.refs.shortcuts import get_actual_price
# from modul.clientbot.handlers.main import save_user
from modul.loader import client_bot_router
from modul.clientbot.handlers.chat_gpt_bot.states import AiState, AiAdminState, ChatGptFilter
from modul.clientbot.handlers.chat_gpt_bot.shortcuts import (get_all_names, get_all_ids,
                                                             get_info_db, get_user_balance_db,
                                                             default_checker, update_bc,
                                                             update_bc_name, get_channels_with_type_for_check,
                                                             remove_sponsor_channel, process_chatgpt_referral_bonus)

robot = ChatGPT()

logger = logging.getLogger(__name__)

# ==========================================
# STAR NARXLARI KONSTANTASI
# ==========================================
STAR_PRICES = {
    'gpt3_no_context': 1,
    'gpt3_context': 2,
    'gpt4_no_context': 3,
    'gpt4_context': 4
}


def chat_gpt_bot_handlers():
    @client_bot_router.message(lambda message: message.text == "/adminpayamount")
    async def adminpayamount_cmd(message: types.Message, state: FSMContext):
        print("sad")
        await message.answer('Пришли токен')
        await state.set_state(AiAdminState.check_token_and_update)


from modul.clientbot.handlers.chat_gpt_bot.all_openai import ChatGPT

chatgpt = ChatGPT()


@client_bot_router.message(AiAdminState.check_token_and_update)
async def check_token_and_update(message: types.Message, state: FSMContext):
    if message.text == 'da98s74d5qw89a4dw6854a':
        await message.answer('Впишите id пользователя для пополнения или выбери его из кнопок',
                             reply_markup=bt.get_all_user_bt())
        await state.set_state(AiAdminState.check_user_to_update)
    else:
        await message.answer('Error')


@client_bot_router.message(AiAdminState.check_user_to_update)
async def check_user_to_update(message: types.Message, state: FSMContext):
    people = [str(i).strip("(),'") for i in await get_all_names()]
    ids = [str(i).strip("(),'") for i in await get_all_ids()]

    if message.text in people:
        await message.answer("Введите сумму для пополнения", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(AiAdminState.update_balance_state)
        await state.set_data(message.from_user.id, {"username": message.text})
    elif message.text in ids:
        await message.answer("Введите сумму для пополнения", reply_markup=types.ReplyKeyboardRemove())
        await state.set_state(AiAdminState.update_balance_state)
        await state.set_data(message.from_user.id, {"username": message.text})
    else:
        await message.answer("Error Find Buttons", reply_markup=types.ReplyKeyboardRemove())


@client_bot_router.message(AiAdminState.update_balance_state)
async def update_balance(message: types.Message, state: FSMContext):
    data = await state.get_data(message.from_user.id)
    if message.text:
        amount = message.text
        if "userid" in data:
            await update_bc(tg_id=data["userid"], sign='+', amount=amount)
        elif "username" in data:
            await update_bc_name(tg_id=data["username"], sign='+', amount=amount)
        await message.answer('Successfully updated')
    else:
        await message.answer('Error updating')


@client_bot_router.message(
    StateFilter(None),
    ChatGptFilter()
)
async def start_message(message: types.Message, state: FSMContext, bot: Bot):
    from modul.clientbot.handlers.main import save_user
    user_id = message.from_user.id

    if message.text == "/adminpayamount":
        await message.answer('Пришли токен')
        await state.set_state(AiAdminState.check_token_and_update)
        print(await state.get_state())
        return

    print(await state.get_state())

    referral = None
    if message.text and message.text.startswith('/start '):
        args = message.text[7:]
        if args and args.isdigit():
            referral = args
            await state.update_data(referral=referral)
            print(f"Extracted referral: {referral}")

    channels = await get_channels_with_type_for_check()
    print(f"📡 Found channels: {channels}")

    if channels:
        print(f"🔒 Channels exist, checking user subscription for {user_id}")
        not_subscribed_channels = []
        invalid_channels_to_remove = []

        for channel_id, channel_url, channel_type in channels:
            try:
                if channel_type == 'system':
                    from modul.loader import main_bot
                    member = await main_bot.get_chat_member(chat_id=int(channel_id), user_id=user_id)
                    print(f"System channel {channel_id} checked via main_bot: {member.status}")
                else:
                    member = await message.bot.get_chat_member(chat_id=int(channel_id), user_id=user_id)
                    print(f"Sponsor channel {channel_id} checked via current_bot: {member.status}")

                if member.status == "left":
                    try:
                        if channel_type == 'system':
                            chat_info = await main_bot.get_chat(chat_id=int(channel_id))
                        else:
                            chat_info = await message.bot.get_chat(chat_id=int(channel_id))

                        not_subscribed_channels.append({
                            'id': channel_id,
                            'title': chat_info.title,
                            'invite_link': channel_url or chat_info.invite_link or f"https://t.me/{channel_id.strip('-')}"
                        })
                    except Exception as e:
                        print(f"⚠️ Error getting chat info for channel {channel_id}: {e}")
                        not_subscribed_channels.append({
                            'id': channel_id,
                            'title': f"Канал {channel_id}",
                            'invite_link': channel_url or f"https://t.me/{channel_id.strip('-')}"
                        })
            except Exception as e:
                logger.error(f"Error checking channel {channel_id} (type: {channel_type}): {e}")

                if channel_type == 'sponsor':
                    invalid_channels_to_remove.append(channel_id)
                    logger.info(f"Added invalid sponsor channel {channel_id} to removal list")
                else:
                    logger.warning(f"System channel {channel_id} error (ignoring): {e}")
                continue

        if invalid_channels_to_remove:
            for channel_id in invalid_channels_to_remove:
                await remove_sponsor_channel(channel_id)

        if not_subscribed_channels:
            print(f"🚫 User {user_id} not subscribed to all channels")

            channels_text = "📢 <b>Для использования бота необходимо подписаться на каналы:</b>\n\n"
            kb = InlineKeyboardBuilder()

            for index, channel in enumerate(not_subscribed_channels):
                title = channel['title']
                invite_link = channel['invite_link']

                channels_text += f"{index + 1}. {title}\n"
                kb.button(text=f"📢 {title}", url=invite_link)

            kb.button(text="✅ Проверить подписку", callback_data="check_chan_chatgpt")
            kb.adjust(1)

            await message.answer(
                channels_text + "\n\nПосле подписки на все каналы нажмите кнопку «Проверить подписку».",
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )

            print(f"📝 State saved for user {user_id}: referral data will be processed after channel check")
            return

    print(f"✅ User {user_id} subscribed to all channels or no channels found")
    try:
        bot_db_id = await get_chatgpt_bot_db_id(message.bot.token)
        result = await get_user_balance_db(user_id, bot_db_id)
        print(f"User {user_id} found in database: {result}")
        await message.answer(
            f'Привет {message.from_user.username}\nВаш баланс - {result:.0f} ⭐️',
            reply_markup=bt.first_buttons()
        )
    except:
        print(f"User {user_id} not found, creating new user")
        new_link = await create_start_link(message.bot, str(message.from_user.id), encode=True)
        link_for_db = new_link[new_link.index("=") + 1:]
        try:
            await save_user(u=message.from_user, bot=bot, link=link_for_db, referrer_id=referral)
        except TypeError:
            await save_user(u=message.from_user, bot=bot, link=link_for_db)

        if referral and referral.isdigit():
            ref_id = int(referral)
            if ref_id != user_id:
                print(f"🔄 Processing referral for NEW user {user_id} from {ref_id}")
                success, reward = await process_chatgpt_referral_bonus(user_id, ref_id, bot.token)

                if success:
                    try:
                        user_name = html.escape(message.from_user.first_name)
                        user_profile_link = f'tg://user?id={user_id}'

                        await asyncio.sleep(1)

                        await bot.send_message(
                            chat_id=ref_id,
                            text=f"У вас новый реферал! <a href='{user_profile_link}'>{user_name}</a>\n"
                                 f"💰 Получено: {reward} ⭐️",
                            parse_mode="HTML"
                        )
                        print(f"📨 Sent referral notification to {ref_id} about user {user_id}")
                    except Exception as e:
                        print(f"⚠️ Error sending notification to referrer {ref_id}: {e}")

        result = await get_user_balance_db(user_id, bot.token)
        print(f"New user {user_id} created: {result}")

        await message.answer(
            f'Привет {message.from_user.username}\nВаш баланс - {result:.0f} ⭐️',
            reply_markup=bt.first_buttons()
        )

    await state.clear()


@client_bot_router.callback_query(F.data == "check_chan_chatgpt", ChatGptFilter())
async def check_channels_chatgpt_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """ChatGPT bot uchun kanal obunasini tekshirish"""
    from modul.clientbot.handlers.main import save_user
    user_id = callback.from_user.id
    print(f"🔍 ChatGPT check_chan callback triggered for user {user_id}")

    # State dan referral ma'lumotni olish
    state_data = await state.get_data()
    referral = state_data.get('referral')
    print(f"👤 Referral from state for user {user_id}: {referral}")

    # Kanallarni qayta tekshirish
    channels = await get_channels_with_type_for_check()

    subscribed_all = True
    invalid_channels_to_remove = []

    for channel_id, channel_url, channel_type in channels:
        try:
            if channel_type == 'system':
                from modul.loader import main_bot
                member = await main_bot.get_chat_member(chat_id=int(channel_id), user_id=user_id)
            else:
                member = await bot.get_chat_member(chat_id=int(channel_id), user_id=user_id)

            if member.status in ['left', 'kicked']:
                subscribed_all = False
                break
        except Exception as e:
            logger.error(f"Error checking channel {channel_id} (type: {channel_type}): {e}")
            if channel_type == 'sponsor':
                invalid_channels_to_remove.append(channel_id)
            subscribed_all = False
            break

    if invalid_channels_to_remove:
        for channel_id in invalid_channels_to_remove:
            await remove_sponsor_channel(channel_id)

    if not subscribed_all:
        await callback.answer("❌ Вы еще не подписались на все каналы!", show_alert=True)
        return

    print(f"✅ User {user_id} subscribed to all channels")

    try:
        result = await get_info_db(user_id)
        print(f"User {user_id} already exists")
    except:
        print(f"Creating new user {user_id}")
        new_link = await create_start_link(bot, str(user_id), encode=True)
        link_for_db = new_link[new_link.index("=") + 1:]
        await save_user(u=callback.from_user, bot=bot, link=link_for_db, referrer_id=referral)
        if referral and referral.isdigit():
            ref_id = int(referral)
            if ref_id != user_id:
                success, reward = await process_chatgpt_referral_bonus(user_id, ref_id, bot.token)

                if success:
                    try:
                        user_name = html.escape(callback.from_user.first_name)
                        user_profile_link = f'tg://user?id={user_id}'

                        await bot.send_message(
                            chat_id=ref_id,
                            text=f"У вас новый реферал! <a href='{user_profile_link}'>{user_name}</a>\n"
                                 f"💰 Получено: {reward}₽",
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        print(f"Error sending referral notification: {e}")

    try:
        await callback.message.delete()
    except:
        pass

    result = await get_user_balance_db(user_id, bot.token)
    await callback.message.answer(
        f'Привет {callback.from_user.username}\nВаш баланс - {result:.0f}',
        reply_markup=bt.first_buttons()
    )

    await state.clear()
    await callback.answer()


@client_bot_router.message(StateFilter('waiting_for_gpt4'), ChatGptFilter())
async def test_gpt4_handler(message: Message, state: FSMContext):
    """Vaqtincha test handler"""
    print(f"🟢 GPT-4 handler triggered!")
    print(f"   Message: {message.text}")

    await message.answer("✅ Test: GPT-4 handler ishlayapti!")
    await state.clear()
    print(f"   State cleared!")


@client_bot_router.callback_query(F.data == "chat_4")
async def chat_4_callback(callback_query: types.CallbackQuery):
    await callback_query.message.edit_text(
        '🤖 GPT-4:\n\n'
        '📋 Используется самая последняя языковая модель GPT-4 Turbo.\n'
        '🔘 Принимает текст.\n'
        '🗯 Чат без контекста — не учитывает контекст, каждый ваш запрос как новый диалог.\n'
        '⚡️ 1 запрос = 3 ⭐️\n'
        '💬 Чат с контекстом — каждый ответ с учетом контекста вашего диалога.\n'
        '⚡️ 1 запрос = 4 ⭐️\n'
        '└ Выберите чат:',
        reply_markup=bt.choice_1_4()
    )


@client_bot_router.callback_query(F.data == "chat_3")
async def chat_3_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(
        '🤖 GPT-3.5:\n\n'
        '📋 Используется самая экономически эффективная модель GPT-3.5 Turbo.\n'
        '🔘 Принимает текстовое сообщение.\n'
        '🗯 Чат без контекста — не учитывает контекст, каждый ваш запрос как новый диалог.\n'
        '⚡️ 1 запрос = 1 ⭐️\n'
        '💬 Чат с контекстом — каждый ответ с учетом контекста вашего диалога.\n'
        '⚡️ 1 запрос = 2 ⭐️',
        reply_markup=bt.choice_1_3_5()
    )


# ==========================================
# UTILITY FUNCTIONS
# ==========================================

@sync_to_async
def get_chatgpt_bot_db_id(bot_identifier):
    """
    Bot identifikatoridan database ID ni olish (flexible)
    bot_identifier - Bot database ID yoki Bot token
    Returns: Database ID (int) yoki None
    """
    try:
        from modul.models import Bot

        # Agar int bo'lsa, avval database ID deb tekshiramiz
        if isinstance(bot_identifier, int):
            bot = Bot.objects.filter(id=bot_identifier).first()
            if bot:
                logger.info(f"✅ Bot found by ID: {bot.id}, username={bot.username}")
                return bot.id

        # Token deb tekshiramiz
        bot = Bot.objects.filter(token=str(bot_identifier)).first()

        if bot:
            logger.info(f"✅ Bot found by token: ID={bot.id}, username={bot.username}")
            return bot.id
        else:
            logger.error(f"❌ Bot not found with identifier: {str(bot_identifier)[:15]}...")
            return None

    except Exception as e:
        logger.error(f"❌ Error getting bot DB ID: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


@sync_to_async
def get_user_balance_db(user_id: int, bot_identifier):
    """
    Foydalanuvchining balansini hisoblash (Flexible - ID yoki Token)
    user_id - foydalanuvchi Telegram ID si
    bot_identifier - Bot database ID yoki Bot token
    Returns: Balance in Stars (float)
    """
    try:
        from modul.models import PaymentTransaction, Bot
        from django.db.models import Sum

        actual_bot_id = None

        # 1. Avval database ID deb tekshiramiz
        if isinstance(bot_identifier, int):
            logger.info(f"🔍 Trying as database ID: {bot_identifier}")

            bot_exists = Bot.objects.filter(id=bot_identifier).exists()

            if bot_exists:
                logger.info(f"✅ Bot exists with ID: {bot_identifier}")
                total = PaymentTransaction.objects.filter(
                    user_id=user_id,
                    bot_id=bot_identifier,
                    status='completed'
                ).aggregate(total_stars=Sum('amount_stars'))

                balance = float(total['total_stars']) if total['total_stars'] else 0.0
                logger.info(
                    f"✅ Balance by database ID: user={user_id}, bot_id={bot_identifier}, balance={balance:.0f} ⭐️")
                return balance
            else:
                logger.info(f"⚠️ Bot not found by ID {bot_identifier}, trying as token...")

        # 2. Token deb tekshiramiz
        logger.info(f"🔍 Looking up bot by token: {str(bot_identifier)[:15]}...")

        bot = Bot.objects.filter(token=str(bot_identifier)).first()

        if bot:
            logger.info(f"✅ Bot found by token: database ID={bot.id}")
            actual_bot_id = bot.id

            total = PaymentTransaction.objects.filter(
                user_id=user_id,
                bot_id=actual_bot_id,
                status='completed'
            ).aggregate(total_stars=Sum('amount_stars'))

            balance = float(total['total_stars']) if total['total_stars'] else 0.0
            logger.info(f"✅ Balance for user {user_id} in bot {actual_bot_id} (via token): {balance:.0f} ⭐️")
            return balance
        else:
            logger.warning(f"⚠️ Bot not found by token: {str(bot_identifier)[:15]}...")
            logger.error(f"❌ Bot not found with identifier: {bot_identifier}")
            return 0.0

    except Exception as e:
        logger.error(f"❌ Error getting balance for user {user_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 0.0


# ==========================================
# GPT CHAT HANDLERS - YANGILANGAN
# ==========================================

@client_bot_router.callback_query(F.data.in_(['not', 'with', 'not4', 'with4', 'again_gpt3', 'again_gpt4']))
async def chat_options_callback(callback: types.CallbackQuery, state: FSMContext):
    """GPT tanlov - balance checking bilan"""
    user_id = callback.from_user.id

    bot_db_id = await get_chatgpt_bot_db_id(callback.bot.token)

    if not bot_db_id:
        await callback.answer("❌ Ошибка: бот не найден", show_alert=True)
        return

    user_balance = await get_user_balance_db(user_id, bot_db_id)

    # Narxlar - Stars da
    prices = {
        'not': STAR_PRICES['gpt3_no_context'],
        'again_gpt3': STAR_PRICES['gpt3_no_context'],
        'with': STAR_PRICES['gpt3_context'],
        'not4': STAR_PRICES['gpt4_no_context'],
        'again_gpt4': STAR_PRICES['gpt4_no_context'],
        'with4': STAR_PRICES['gpt4_context']
    }

    price = prices.get(callback.data, 1)

    # BALANS TEKSHIRISH - ESKI KODDA BU YO'Q EDI!
    if user_balance < price:
        await callback.message.answer(
            f'⚠️ <b>Недостаточно средств!</b>\n\n'
            f'💰 Ваш баланс: {user_balance:.0f} ⭐️\n'
            f'💳 Требуется: {price} ⭐️\n'
            f'📊 Не хватает: {price - user_balance:.0f} ⭐️\n\n'
            f'💡 Пополните баланс для продолжения работы',
            parse_mode="HTML",
            reply_markup=bt.balance_menu()
        )
        await callback.answer("❌ Недостаточно средств", show_alert=True)
        return

    # Balans yetarli - state o'rnatish (pul hali yechilmaydi!)
    if callback.data in ['not', 'again_gpt3']:
        await callback.message.answer(
            f'🤖 <b>GPT-3.5 без контекста активирован</b>\n\n'
            f'💬 Отправьте ваш вопрос\n'
            f'💰 Стоимость: {price} ⭐️\n'
            f'📊 Ваш баланс: {user_balance:.0f} ⭐️',
            parse_mode="HTML"
        )
        await state.set_state(AiState.gpt3)
        await state.update_data(context=False)

    elif callback.data == 'with':
        await callback.message.answer(
            f'🤖 <b>GPT-3.5 с контекстом активирован</b>\n\n'
            f'💬 Начните диалог\n'
            f'💰 Стоимость за сообщение: {price} ⭐️\n'
            f'📊 Ваш баланс: {user_balance:.0f} ⭐️\n\n'
            f'ℹ️ Для выхода: /start или /reset',
            parse_mode="HTML"
        )
        await state.set_state(AiState.gpt3)
        await state.update_data(context=True)

    elif callback.data in ['not4', 'again_gpt4']:
        await callback.message.answer(
            f'🤖 <b>GPT-4 без контекста активирован</b>\n\n'
            f'💬 Отправьте ваш вопрос\n'
            f'💰 Стоимость: {price} ⭐️\n'
            f'📊 Ваш баланс: {user_balance:.0f} ⭐️',
            parse_mode="HTML"
        )
        await state.set_state(AiState.gpt4)
        await state.update_data(context=False)

    elif callback.data == 'with4':
        await callback.message.answer(
            f'🤖 <b>GPT-4 с контекстом активирован</b>\n\n'
            f'💬 Начните диалог\n'
            f'💰 Стоимость за сообщение: {price} ⭐️\n'
            f'📊 Ваш баланс: {user_balance:.0f} ⭐️\n\n'
            f'ℹ️ Для выхода: /start или /reset',
            parse_mode="HTML"
        )
        await state.set_state(AiState.gpt4)
        await state.update_data(context=True)

    await callback.answer()


@client_bot_router.callback_query(F.data.in_({"back", "back_on_menu"}))
async def back_callback(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    user_id = callback.from_user.id
    if callback.data == 'back':
        try:
            result = await get_user_balance_db(user_id, bot.token)
            print(result)
            await callback.message.edit_text(f'Привет {callback.from_user.username}\nВаш баланс - {result:.0f}',
                                             reply_markup=bt.first_buttons())
            await state.clear()
        except Exception as e:
            print(e)
            await start_message(callback.message, bot)
    elif callback.data == 'back_on_menu':
        try:
            await callback.message.edit_text(
                f'Привет {callback.from_user.first_name}',
                reply_markup=bt.first_buttons()
            )
            await state.clear()
        except Exception as e:
            await callback.message.edit_text(
                f'Привет {callback.from_user.first_name}',
                reply_markup=bt.first_buttons()
            )
            print(e)


@client_bot_router.callback_query(F.data.in_({"alloy", "echo", "nova", "fable", "shimmer"}))
async def voice_selection_callback(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user_balance = await get_user_balance_db(user_id)
    if user_balance >= 3:
        await update_balance(tg_id=user_id, sign='-', amount=3)
        await callback.message.edit_text("Введите текст для озвучки:")
        await state.set_data({"voice": callback.data})
        await state.set_state('waiting_for_text_to_voice')
    else:
        await callback.message.answer('Не хватает на балансе тыкай --> /start')


@client_bot_router.callback_query(F.data == "settings")
async def settings_callback(callback: types.CallbackQuery):
    await callback.message.edit_text('Настройки', reply_markup=bt.settings())


@client_bot_router.callback_query(F.data == "helper")
async def helper_callback(callback: types.CallbackQuery):
    await callback.message.edit_text('ℹ️ Помощь:', reply_markup=bt.help_bt())


@client_bot_router.callback_query(F.data == "FAQ")
async def faq_callback(callback: types.CallbackQuery):
    await callback.message.edit_text('❔ Часто задаваемые вопросы', reply_markup=bt.faqs())


@client_bot_router.callback_query(F.data == "what")
async def what_bot_can_do_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(
        '🤖 Что умеет бот?\n\n'
        'Бот умеет отвечать на любые вопросы (GPT-4 Turbo), генерировать '
        'изображения (DALL·E 3), озвучивать текст (TTS), '
        'превращать аудио в текст (Whisper) и многое другое.',
        reply_markup=bt.back_in_faq()
    )


@client_bot_router.callback_query(F.data == "use")
async def how_to_use_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(
        '📖 Как использовать бота?\n\n'
        'Просто выберите нужную функцию из меню и следуйте инструкциям. '
        'Для генерации изображений опишите, что хотите увидеть. '
        'Для озвучки текста отправьте текст, который хотите озвучить. '
        'Для расшифровки аудио отправьте аудиофайл.',
        reply_markup=bt.back_in_faq()
    )


@client_bot_router.callback_query(F.data == "balance")
async def what_is_balance_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(
        '💰 Что такое баланс?\n\n'
        'Баланс — это ваши средства, которые используются для оплаты запросов к боту. '
        'Каждый запрос к GPT, генерация изображения или озвучка текста стоит определенное количество рублей. '
        'Баланс можно пополнить через платежную систему.',
        reply_markup=bt.back_in_faq()
    )


@client_bot_router.callback_query(F.data == "functions")
async def what_functions_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(
        '🔧 Какие функции доступны?\n\n'
        'Доступны следующие функции:\n'
        '• GPT-3.5 и GPT-4 для ответов на вопросы\n'
        '• Генерация изображений (DALL·E 3)\n'
        '• Озвучка текста (TTS)\n'
        '• Расшифровка аудио (Whisper)\n'
        '• И другие функции, которые необходимы для его работы.',
        reply_markup=bt.back_in_faq()
    )


@client_bot_router.callback_query(F.data == "how")
async def how_to_pay_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(
        '💳 Как пополнить баланс?\n\n'
        'Информация обновляется',
        reply_markup=bt.back_in_faq()
    )


# ==========================================
# GPT-3.5 HANDLER - YANGILANGAN
# ==========================================
@client_bot_router.message(AiState.gpt3, ChatGptFilter())
async def gpt3(message: Message, state: FSMContext):
    """GPT-3.5 handler with balance checking"""

    context_data = await state.get_data()
    context = context_data.get("context", False)

    user_id = message.from_user.id
    bot_db_id = await get_chatgpt_bot_db_id(message.bot.token)

    if not bot_db_id:
        await message.answer("❌ Ошибка: бот не найден в базе данных")
        await state.clear()
        return

    # Context mode da reset komandalarini tekshirish
    if context and message.text in ['/start', '/restart', '/reset']:
        await state.clear()
        await start_message(message, state, message.bot)
        return

    if not message.text:
        await message.answer('Я могу обрабатывать только текст ! /start')
        return

    # Stars narxini aniqlash
    star_cost = STAR_PRICES['gpt3_context'] if context else STAR_PRICES['gpt3_no_context']

    try:
        # 1. BALANSNI TEKSHIRISH
        current_balance = await get_user_balance_db(user_id, bot_db_id)

        if current_balance < star_cost:
            await message.answer(
                f"⚠️ <b>Недостаточно средств!</b>\n\n"
                f"💰 Ваш баланс: {current_balance:.0f} ⭐️\n"
                f"💳 Требуется: {star_cost} ⭐️\n"
                f"📊 Не хватает: {star_cost - current_balance:.0f} ⭐️\n\n"
                f"💡 Пополните баланс для продолжения работы",
                parse_mode="HTML",
                reply_markup=bt.balance_menu()
            )

            if not context:
                await state.clear()
            return

        # 2. BALANSDAN YECHIB OLISH
        success = await update_bc(tg_id=user_id, sign='-', amount=star_cost, bot_id=bot_db_id)

        if not success:
            await message.answer('❌ Ошибка списания средств. Попробуйте /start')
            if not context:
                await state.clear()
            return

        new_balance = current_balance - star_cost

        # 3. GPT SO'ROVINI BAJARISH
        await message.bot.send_chat_action(message.chat.id, 'typing')

        logger.info(f'GPT3 {"CONTEXT" if context else "NO_CONTEXT"} user_id={user_id}, stars_deducted={star_cost}')

        gpt_answer = robot.chat_gpt(
            user_id=user_id,
            message=message.text,
            gpt='gpt-3.5-turbo',
            context=context
        )

        if gpt_answer:
            # Javobni yuborish + balans ma'lumoti
            balance_info = f"\n\n💰 Списано: {star_cost} ⭐️ | Остаток: {new_balance:.0f} ⭐️"

            if not context:
                await message.answer(
                    gpt_answer + balance_info,
                    parse_mode='Markdown',
                    reply_markup=bt.again_gpt3()
                )
                await state.clear()
            else:
                await message.answer(
                    gpt_answer + balance_info,
                    parse_mode='Markdown'
                )
        else:
            # Xatolik - pul qaytariladi
            await update_bc(tg_id=user_id, sign='+', amount=star_cost, bot_id=bot_db_id)
            await message.answer('❌ Произошла ошибка при обработке запроса. Средства возвращены.')

            if not context:
                await state.clear()

    except Exception as e:
        logger.error(f'GPT3 Error: {e}', exc_info=True)

        # Xatolik bo'lsa, pul qaytariladi
        try:
            await update_bc(tg_id=user_id, sign='+', amount=star_cost, bot_id=bot_db_id)
            await message.answer('❌ Произошла ошибка при обработке запроса. Средства возвращены.')
        except:
            await message.answer('❌ Произошла ошибка при обработке запроса')

        if not context:
            await state.clear()


# ==========================================
# GPT-4 HANDLER - YANGILANGAN
# ==========================================
@client_bot_router.message(AiState.gpt4, ChatGptFilter())
async def gpt4(message: Message, state: FSMContext):
    """GPT-4 handler with balance checking"""

    context_data = await state.get_data()
    context = context_data.get("context", False)

    user_id = message.from_user.id
    bot_db_id = await get_chatgpt_bot_db_id(message.bot.token)

    if not bot_db_id:
        await message.answer("❌ Ошибка: бот не найден в базе данных")
        await state.clear()
        return

    # Context mode da reset komandalarini tekshirish
    if context and message.text in ['/start', '/restart', '/reset']:
        await state.clear()
        await start_message(message, state, message.bot)
        return

    if not message.text:
        await message.answer('Я могу обрабатывать только текст ! /start')
        return

    # Stars narxini aniqlash
    star_cost = STAR_PRICES['gpt4_context'] if context else STAR_PRICES['gpt4_no_context']

    try:
        # 1. BALANSNI TEKSHIRISH
        current_balance = await get_user_balance_db(user_id, bot_db_id)

        if current_balance < star_cost:
            await message.answer(
                f"⚠️ <b>Недостаточно средств!</b>\n\n"
                f"💰 Ваш баланс: {current_balance:.0f} ⭐️\n"
                f"💳 Требуется: {star_cost} ⭐️\n"
                f"📊 Не хватает: {star_cost - current_balance:.0f} ⭐️\n\n"
                f"💡 Пополните баланс для продолжения работы",
                parse_mode="HTML",
                reply_markup=bt.balance_menu()
            )

            if not context:
                await state.clear()
            return

        # 2. BALANSDAN YECHIB OLISH
        success = await update_bc(tg_id=user_id, sign='-', amount=star_cost, bot_id=bot_db_id)

        if not success:
            await message.answer('❌ Ошибка списания средств. Попробуйте /start')
            if not context:
                await state.clear()
            return

        new_balance = current_balance - star_cost

        # 3. GPT SO'ROVINI BAJARISH
        await message.bot.send_chat_action(message.chat.id, 'typing')

        logger.info(f'GPT4 {"CONTEXT" if context else "NO_CONTEXT"} user_id={user_id}, stars_deducted={star_cost}')

        gpt_answer = robot.chat_gpt(
            user_id=user_id,
            message=message.text,
            gpt="gpt-4o",
            context=context
        )

        if gpt_answer:
            # Javobni yuborish + balans ma'lumoti
            balance_info = f"\n\n💰 Списано: {star_cost} ⭐️ | Остаток: {new_balance:.0f} ⭐️"

            if not context:
                await message.answer(
                    gpt_answer + balance_info,
                    parse_mode='Markdown',
                    reply_markup=bt.again_gpt4()
                )
                await state.clear()
            else:
                await message.answer(
                    gpt_answer + balance_info,
                    parse_mode='Markdown'
                )
        else:
            # Xatolik - pul qaytariladi
            await update_bc(tg_id=user_id, sign='+', amount=star_cost, bot_id=bot_db_id)
            await message.answer('❌ GPT4 Недоступен. Средства возвращены.')

            if not context:
                await state.clear()

    except Exception as e:
        logger.error(f'GPT4 Error: {e}', exc_info=True)

        # Xatolik bo'lsa, pul qaytariladi
        try:
            await update_bc(tg_id=user_id, sign='+', amount=star_cost, bot_id=bot_db_id)
            await message.answer('❌ Произошла ошибка при обработке запроса. Средства возвращены.')
        except:
            await message.answer('❌ Произошла ошибка при обработке запроса')

        if not context:
            await state.clear()


# ==========================================
# BALANCE & PAYMENT HANDLERS
# ==========================================

@client_bot_router.callback_query(F.data == "ref",ChatGptFilter())
async def gain(message: Message, bot: Bot, state: FSMContext):
    bot_db = await shortcuts.get_bot(bot)
    await state.clear()
    if shortcuts.have_one_module(bot_db, 'chatgpt'):
        channels_checker = await check_channels(message)
        checker_banned = await banned(message)
        if channels_checker and checker_banned:
            me = await bot.get_me()
            link = f"https://t.me/{me.username}?start={message.from_user.id}"

            price = await get_actual_price(bot.token)

            await message.bot.send_message(message.from_user.id,
                                           f"👥 Приглашай друзей и зарабатывай, за \nкаждого друга ты получишь {price}₽\n\n"
                                           f"🔗 Ваша ссылка для приглашений:\n {link}",
                                           reply_markup=await main_menu_bt())
    else:
        channels_checker = await check_channels(message)
        checker_banned = await banned(message)
        if channels_checker and checker_banned:
            me = await bot.get_me()
            link = f"https://t.me/{me.username}?start={message.from_user.id}"

            price = await get_actual_price(bot.token)

            await message.bot.send_message(message.from_user.id,
                                           f"👥 Приглашай друзей и зарабатывай, за \nкаждого друга ты получишь {price}₽\n\n"
                                           f"🔗 Ваша ссылка для приглашений:\n {link}"
                                           "\n Что бы вернуть функционал основного бота напишите /start",
                                           reply_markup=await main_menu_bt())

@client_bot_router.callback_query(F.data == "show_balance")
async def show_balance_callback(callback: types.CallbackQuery):
    """Balansni ko'rsatish - faqat Stars"""
    user_id = callback.from_user.id

    bot_db_id = await get_chatgpt_bot_db_id(callback.bot.token)

    if not bot_db_id:
        await callback.answer("❌ Ошибка: бот не найден в базе данных", show_alert=True)
        return

    try:
        user_balance = await get_user_balance_db(user_id, bot_db_id)

        await callback.message.edit_text(
            f"💰 <b>Ваш баланс:</b> {user_balance:.0f} ⭐️\n\n"
            f"📊 <b>Тарифы:</b>\n"
            f"• GPT-3.5 без контекста: 1 ⭐️\n"
            f"• GPT-3.5 с контекстом: 2 ⭐️\n"
            f"• GPT-4 без контекста: 3 ⭐️\n"
            f"• GPT-4 с контекстом: 4 ⭐️\n\n"
            f"💡 Пополнить баланс можно через главный бот",
            reply_markup=bt.balance_menu(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error showing balance: {e}")
        await callback.message.edit_text(
            "Ошибка при получении баланса",
            reply_markup=bt.back()
        )

    await callback.answer()


@client_bot_router.callback_query(F.data == "top_up_balance")
async def top_up_balance_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "💳 <b>Выберите количество Stars для пополнения:</b>\n\n"
        "⭐️ <i>Оплата через Telegram Stars</i>\n"
        "🔒 <i>Безопасно и мгновенно</i>",
        reply_markup=bt.top_up_options(),
        parse_mode="HTML"
    )
    await callback.answer()


@client_bot_router.callback_query(F.data.startswith("topup_"))
async def topup_redirect_callback(callback: types.CallbackQuery):
    """Stars orqali to'lov - faqat Stars ko'rsatish"""
    stars_amount = callback.data.replace("topup_", "").replace("_star", "").replace("_stars", "")
    main_bot_username = "konstruktor_test_my_bot"

    bot_db_id = await get_chatgpt_bot_db_id(callback.bot.token)

    if not bot_db_id:
        await callback.answer("❌ Ошибка: бот не найден в базе данных", show_alert=True)
        logger.error(f"Bot DB ID not found for token: {callback.bot.token[:10]}...")
        return

    logger.info(f"User {callback.from_user.id} redirecting to payment: {stars_amount} stars, bot_db_id={bot_db_id}")

    await callback.message.edit_text(
        f"💎 <b>Пополнение на {stars_amount} Stars</b>\n\n"
        f"🔄 Переходите в основной бот для оплаты:\n"
        f"👇 Нажмите кнопку ниже",
        reply_markup=InlineKeyboardBuilder().button(
            text=f"💳 Перейти к оплате ({stars_amount} ⭐️)",
            url=f"https://t.me/{main_bot_username}?start=gptbot_{callback.from_user.id}_{stars_amount}_{bot_db_id}"
        ).as_markup(),
        parse_mode="HTML"
    )

    await callback.answer("🔄 Переходите в основной бот для завершения оплаты")