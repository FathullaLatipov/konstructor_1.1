# modul/bot/main_bot/main.py (To'liq to'g'irlangan versiya)

import asyncio
from datetime import datetime, timedelta
from aiogram.filters import Command
from aiogram import Router, Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from asgiref.sync import sync_to_async
from django.db.models import F as DjangoF
from django.utils import timezone
from modul.config import settings_conf
from modul.loader import main_bot_router, client_bot_router
from modul.models import User
from modul.bot.main_bot.services.user_service import get_user_by_uid, create_user_directly
from modul.bot.main_bot.handlers.create_bot import create_bot_router
from modul.bot.main_bot.handlers.manage_bots import manage_bots_router
from aiogram.types import LabeledPrice
import requests
import logging

logger = logging.getLogger(__name__)

ADMIN_CHAT_ID = 575148251
MAIN_BOT_USERNAME = "konstruktor_test_my_bot"
STATS_COMMAND_ENABLED = True
webhook_url = 'https://ismoilov299.uz/'


async def main_menu():
    """Asosiy menyu klaviaturasi"""
    buttons = [
        [
            InlineKeyboardButton(text="Создать бота ⚙️", callback_data="create_bot"),
            InlineKeyboardButton(text="Мои боты 🖥️", callback_data="my_bots")
        ],
        [
            InlineKeyboardButton(text="Инфо 📖", callback_data="info"),
            InlineKeyboardButton(text="FAQ 💬", callback_data="faq")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def registration_keyboard(registration_url):
    """Ro'yxatdan o'tish klaviaturasi"""
    buttons = [[InlineKeyboardButton(text="📝 Регистрация", url=registration_url)]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==========================================
# UTILITY FUNCTIONS - BOT VALIDATSIYASI
# ==========================================

@sync_to_async
def validate_bot_exists(bot_db_id: int):
    """
    Bot bazada mavjudligini tekshirish
    bot_db_id - ChatGPT botning database ID si
    Returns: (exists: bool, bot_info: dict or None)
    """
    try:
        from modul.models import Bot

        bot = Bot.objects.filter(id=bot_db_id).select_related('owner').first()

        if bot:
            owner_info = None
            if bot.owner:
                owner_info = {
                    'uid': bot.owner.uid,
                    'username': bot.owner.username,
                    'first_name': bot.owner.first_name
                }

            bot_info = {
                'id': bot.id,
                'username': bot.username,
                'bot_type': getattr(bot, 'bot_type', None),
                'owner': owner_info
            }

            logger.info(f"✅ Bot validated: ID={bot_db_id}, username={bot.username}")
            return True, bot_info
        else:
            logger.error(f"❌ Bot not found: ID={bot_db_id}")
            return False, None

    except Exception as e:
        logger.error(f"Error validating bot {bot_db_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False, None


@sync_to_async
def get_detailed_payment_statistics(days=7):
    """To'lovlar statistikasini batafsil olish"""
    try:
        from modul.models import PaymentTransaction, User, Bot
        from django.db.models import Sum, Count, Q, F as DjangoF

        now = timezone.now()
        start_date = now - timedelta(days=days)

        # Faqat musbat to'lovlar
        all_payments = PaymentTransaction.objects.filter(
            status='completed',
            created_at__gte=start_date,
            amount_stars__gt=0,
            amount_rubles__gt=0
        ).order_by('-created_at')

        stats = {
            'total_payments': all_payments.count(),
            'total_stars': all_payments.aggregate(Sum('amount_stars'))['amount_stars__sum'] or 0,
            'total_rubles': all_payments.aggregate(Sum('amount_rubles'))['amount_rubles__sum'] or 0,
            'unique_users': all_payments.values('user_id').distinct().count(),
            'unique_bots': all_payments.values('bot_id').distinct().count(),
        }

        # Batafsil to'lovlar ro'yxati
        detailed_payments = []
        for payment in all_payments[:50]:
            try:
                user = User.objects.filter(uid=payment.user_id).first()
                user_name = "Unknown"
                user_username = "No username"

                if user:
                    user_name = user.first_name or "No name"
                    if user.last_name:
                        user_name += f" {user.last_name}"
                    user_username = f"@{user.username}" if user.username else "No username"

                bot = None
                try:
                    bot = Bot.objects.filter(id=payment.bot_id).select_related('owner').first()
                except Exception as bot_error:
                    logger.error(f"Error finding bot {payment.bot_id}: {bot_error}")

                bot_name = "Unknown Bot"
                bot_username = "unknown"
                bot_owner_id = None
                bot_owner_name = "Unknown"
                bot_owner_username = "unknown"

                if bot:
                    bot_name = f"Bot #{bot.id}"
                    bot_username = bot.username or "unknown"

                    if bot.owner:
                        owner = bot.owner
                        bot_owner_id = owner.uid
                        bot_owner_name = owner.first_name or "No name"
                        if owner.last_name:
                            bot_owner_name += f" {owner.last_name}"
                        bot_owner_username = f"@{owner.username}" if owner.username else "No username"

                detailed_payments.append({
                    'id': payment.id,
                    'date': payment.created_at.strftime('%d.%m.%Y %H:%M'),
                    'payment_id': payment.payment_id[:20] if payment.payment_id else 'N/A',
                    'user_id': payment.user_id,
                    'user_name': user_name,
                    'user_username': user_username,
                    'bot_id': payment.bot_id,
                    'bot_name': bot_name,
                    'bot_username': bot_username,
                    'bot_owner_id': bot_owner_id,
                    'bot_owner_name': bot_owner_name,
                    'bot_owner_username': bot_owner_username,
                    'stars': payment.amount_stars,
                    'rubles': payment.amount_rubles,
                })

            except Exception as e:
                logger.error(f"Error processing payment {payment.id}: {e}")
                continue

        stats['detailed_payments'] = detailed_payments

        # Bot statistikasi
        bot_stats = []
        for bot_payment in all_payments.values('bot_id').annotate(
                count=Count('id'),
                total_stars=Sum('amount_stars'),
                total_rubles=Sum('amount_rubles')
        ).order_by('-total_rubles'):
            try:
                bot = Bot.objects.filter(id=bot_payment['bot_id']).select_related('owner').first()
                if bot:
                    owner_name = "Unknown"
                    owner_username = "unknown"
                    if bot.owner:
                        owner_name = bot.owner.first_name or "No name"
                        if bot.owner.last_name:
                            owner_name += f" {bot.owner.last_name}"
                        owner_username = f"@{bot.owner.username}" if bot.owner.username else "No username"

                    bot_stats.append({
                        'bot_id': bot.id,
                        'bot_name': f"@{bot.username}" if bot.username else f"Bot #{bot.id}",
                        'bot_username': bot.username or "unknown",
                        'owner_id': bot.owner.uid if bot.owner else None,
                        'owner_name': owner_name,
                        'owner_username': owner_username,
                        'count': bot_payment['count'],
                        'total_stars': bot_payment['total_stars'],
                        'total_rubles': bot_payment['total_rubles']
                    })
            except Exception as e:
                logger.error(f"Error processing bot stats: {e}")
                continue

        stats['by_bot'] = bot_stats

        # Kunlik statistika
        daily_stats = []
        for i in range(days):
            day_start = now - timedelta(days=i + 1)
            day_end = now - timedelta(days=i)
            day_payments = all_payments.filter(
                created_at__gte=day_start,
                created_at__lt=day_end
            )
            daily_stats.append({
                'date': day_start.strftime('%d.%m.%Y'),
                'count': day_payments.count(),
                'rubles': day_payments.aggregate(Sum('amount_rubles'))['amount_rubles__sum'] or 0,
                'stars': day_payments.aggregate(Sum('amount_stars'))['amount_stars__sum'] or 0
            })
        stats['daily'] = daily_stats

        # Top users
        top_users_data = []
        for user_payment in all_payments.values('user_id').annotate(
                total_rubles=Sum('amount_rubles'),
                total_payments=Count('id'),
                total_stars=Sum('amount_stars')
        ).order_by('-total_rubles')[:10]:

            try:
                user = User.objects.filter(uid=user_payment['user_id']).first()

                if user:
                    user_name = user.first_name or "No name"
                    if user.last_name:
                        user_name += f" {user.last_name}"
                    user_username = f"@{user.username}" if user.username else "No username"
                else:
                    user_name = "Unknown"
                    user_username = "unknown"

                top_users_data.append({
                    'user_id': user_payment['user_id'],
                    'user_name': user_name,
                    'user_username': user_username,
                    'total_rubles': user_payment['total_rubles'],
                    'total_payments': user_payment['total_payments'],
                    'total_stars': user_payment['total_stars']
                })
            except Exception as e:
                logger.error(f"Error processing top user: {e}")
                continue

        stats['top_users'] = top_users_data

        return stats

    except Exception as e:
        logger.error(f"Error getting detailed payment statistics: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def format_detailed_statistics_message(stats, period_days=7):
    """Umumiy statistika xabari"""
    if not stats:
        return "❌ Ошибка при получении статистики"

    message = f"📊 <b>ДЕТАЛЬНАЯ СТАТИСТИКА ПЛАТЕЖЕЙ</b>\n"
    message += f"📅 <i>Период: {period_days} дней</i>\n"
    message += f"{'=' * 40}\n\n"

    message += f"💰 <b>ОБЩАЯ ИНФОРМАЦИЯ:</b>\n"
    message += f"├ Платежей: <b>{stats['total_payments']}</b> шт\n"
    message += f"├ Звезд: <b>{stats['total_stars']}</b> ⭐️\n"
    message += f"├ Сумма: <b>{stats['total_rubles']:.2f}₽</b>\n"
    message += f"├ Пользователей: <b>{stats['unique_users']}</b> чел\n"
    message += f"└ Ботов: <b>{stats['unique_bots']}</b> шт\n\n"

    if stats['total_payments'] > 0:
        avg_payment = stats['total_rubles'] / stats['total_payments']
        avg_per_user = stats['total_rubles'] / stats['unique_users'] if stats['unique_users'] > 0 else 0

        message += f"📈 <b>СРЕДНИЕ ПОКАЗАТЕЛИ:</b>\n"
        message += f"├ Платеж: <b>{avg_payment:.2f}₽</b>\n"
        message += f"└ На пользователя: <b>{avg_per_user:.2f}₽</b>\n\n"

    if stats['by_bot']:
        message += f"🤖 <b>ТОП БОТОВ:</b>\n"
        for idx, bot in enumerate(stats['by_bot'][:5], 1):
            message += f"\n<b>{idx}. {bot['bot_name']}</b>\n"
            message += f"├ Username: @{bot['bot_username']}\n"
            message += f"├ Bot ID: <code>{bot['bot_id']}</code>\n"
            message += f"├ 👤 Владелец: {bot['owner_name']}\n"
            message += f"├ Username: {bot['owner_username']}\n"
            message += f"├ Owner ID: <code>{bot['owner_id']}</code>\n"
            message += f"├ Платежей: <b>{bot['count']}</b> шт\n"
            message += f"├ Звезд: <b>{bot['total_stars']}</b> ⭐️\n"
            message += f"└ Сумма: <b>{bot['total_rubles']:.2f}₽</b>\n"
        message += "\n"

    return message


def format_recent_payments_message(stats, limit=10):
    """Oxirgi to'lovlar xabari"""
    if not stats or not stats.get('detailed_payments'):
        return "❌ Платежи не найдены"

    message = f"📋 <b>ПОСЛЕДНИЕ {limit} ПЛАТЕЖЕЙ:</b>\n"
    message += f"{'=' * 40}\n\n"

    for idx, payment in enumerate(stats['detailed_payments'][:limit], 1):
        bot_display_name = f"@{payment['bot_username']}" if payment['bot_username'] != 'unknown' else payment[
            'bot_name']

        message += f"<b>{idx}. Платеж #{payment['id']}</b>\n"
        message += f"├ 📅 Дата: {payment['date']}\n"
        message += f"├ 💳 ID: <code>{payment['payment_id']}</code>\n\n"

        message += f"├ 👤 <b>Пользователь:</b>\n"
        message += f"│  ├ Имя: {payment['user_name']}\n"
        message += f"│  ├ Username: {payment['user_username']}\n"
        message += f"│  └ ID: <code>{payment['user_id']}</code>\n\n"

        message += f"├ 🤖 <b>Бот:</b>\n"
        message += f"│  ├ Название: {bot_display_name}\n"
        message += f"│  └ ID: <code>{payment['bot_id']}</code>\n\n"

        if payment['bot_owner_id']:
            message += f"├ 👨‍💼 <b>Владелец бота:</b>\n"
            message += f"│  ├ Имя: {payment['bot_owner_name']}\n"
            message += f"│  ├ Username: {payment['bot_owner_username']}\n"
            message += f"│  └ ID: <code>{payment['bot_owner_id']}</code>\n\n"

        message += f"└ 💰 <b>Сумма:</b> {payment['stars']} ⭐️ = {payment['rubles']}₽\n"
        message += f"\n{'-' * 40}\n\n"

    return message


def format_top_users_message(stats):
    """Top users xabari"""
    if not stats or not stats.get('top_users'):
        return "❌ Данные не найдены"

    message = f"🏆 <b>ТОП ПОЛЬЗОВАТЕЛЕЙ:</b>\n"
    message += f"{'=' * 40}\n\n"

    for idx, user in enumerate(stats['top_users'], 1):
        message += f"<b>{idx}. {user['user_name']}</b>\n"
        message += f"├ Username: {user['user_username']}\n"
        message += f"├ ID: <code>{user['user_id']}</code>\n"
        message += f"├ Платежей: <b>{user['total_payments']}</b> шт\n"
        message += f"├ Звезд: <b>{user['total_stars']}</b> ⭐️\n"
        message += f"└ Всего: <b>{user['total_rubles']:.2f}₽</b>\n\n"

    return message


def format_daily_stats_message(stats, period_days=7):
    """Kunlik statistika xabari"""
    if not stats or not stats.get('daily'):
        return "❌ Данные не найдены"

    message = f"📅 <b>СТАТИСТИКА ПО ДНЯМ ({period_days} дней):</b>\n"
    message += f"{'=' * 40}\n\n"

    for day in stats['daily']:
        if day['count'] > 0:
            message += f"• <b>{day['date']}</b>\n"
            message += f"  ├ Платежей: {day['count']} шт\n"
            message += f"  ├ Звезд: {day['stars']} ⭐️\n"
            message += f"  └ Сумма: {day['rubles']:.2f}₽\n\n"

    return message


async def send_weekly_report(bot):
    """Haftalik hisobot yuborish"""
    try:
        logger.info("📊 Generating detailed weekly payment report...")

        stats = await get_detailed_payment_statistics(days=7)

        if stats and stats['total_payments'] > 0:
            msg1 = "🎉 <b>ЕЖЕНЕДЕЛЬНЫЙ ОТЧЕТ</b>\n\n"
            msg1 += format_detailed_statistics_message(stats, period_days=7)

            msg2 = format_recent_payments_message(stats, limit=10)
            msg3 = format_top_users_message(stats)
            msg4 = format_daily_stats_message(stats, period_days=7)

            await bot.send_message(chat_id=ADMIN_CHAT_ID, text=msg1, parse_mode="HTML")
            await asyncio.sleep(0.5)
            await bot.send_message(chat_id=ADMIN_CHAT_ID, text=msg2, parse_mode="HTML")
            await asyncio.sleep(0.5)
            await bot.send_message(chat_id=ADMIN_CHAT_ID, text=msg3, parse_mode="HTML")
            await asyncio.sleep(0.5)
            await bot.send_message(chat_id=ADMIN_CHAT_ID, text=msg4, parse_mode="HTML")

            logger.info("✅ Weekly detailed report sent successfully")
        else:
            logger.info("ℹ️ No payments this week, skipping report")

    except Exception as e:
        logger.error(f"❌ Error sending weekly report: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def schedule_weekly_reports(bot):
    """Haftalik hisobotlarni avtomatik yuborish"""
    while True:
        try:
            now = datetime.now()

            days_until_sunday = (6 - now.weekday()) % 7
            if days_until_sunday == 0 and now.hour >= 20:
                days_until_sunday = 7

            next_sunday = now + timedelta(days=days_until_sunday)
            next_sunday = next_sunday.replace(hour=20, minute=0, second=0, microsecond=0)

            if days_until_sunday == 0 and now.hour < 20:
                next_sunday = now.replace(hour=20, minute=0, second=0, microsecond=0)

            wait_seconds = (next_sunday - now).total_seconds()

            logger.info(f"⏰ Next weekly report: {next_sunday.strftime('%d.%m.%Y %H:%M:%S')}")
            logger.info(f"⏳ Waiting {wait_seconds / 3600:.1f} hours...")

            await asyncio.sleep(wait_seconds)
            await send_weekly_report(bot)
            await asyncio.sleep(60)

        except Exception as e:
            logger.error(f"❌ Error in weekly report scheduler: {e}")
            await asyncio.sleep(3600)


# ==========================================
# DATABASE FUNCTIONS
# ==========================================

@sync_to_async
def save_payment_to_db(user_id, source_bot_id, stars_amount, rubles_amount, payment_id, payment_date):
    """To'lovni bazaga saqlash - Django ORM"""
    try:
        from modul.models import PaymentTransaction

        payment = PaymentTransaction.objects.create(
            user_id=user_id,
            bot_id=source_bot_id,
            amount_stars=stars_amount,
            amount_rubles=rubles_amount,
            payment_id=payment_id,
            status='completed'
        )

        logger.info(f"✅ Payment saved to DB: ID={payment.id}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to save payment to DB: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


async def save_payment_transaction(
        user_id: int,
        source_bot_id: int,
        stars_amount: int,
        rubles_amount: float,
        payment_id: str,
        payment_date
) -> bool:
    """To'lovni saqlash - wrapper"""
    try:
        logger.info(f"💾 Saving payment...")
        logger.info(f"  User: {user_id}, Bot: {source_bot_id}")
        logger.info(f"  Amount: {rubles_amount}₽, Payment ID: {payment_id}")

        result = await save_payment_to_db(
            user_id, source_bot_id, stars_amount,
            rubles_amount, payment_id, payment_date
        )

        if result:
            logger.info("✅ Payment saved successfully")

        return result

    except Exception as e:
        logger.error(f"❌ Error saving payment: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


@sync_to_async
def get_user_info(user_id: int, bot_id: int):
    """Foydalanuvchi ma'lumotlarini olish"""
    try:
        user = User.objects.filter(uid=user_id).first()

        if user:
            return {
                'username': user.username if user.username else 'Не указан',
                'first_name': user.first_name if user.first_name else 'Не указан',
            }
        return None
    except Exception as e:
        logger.error(f"Error getting user info: {e}")
        return None


@sync_to_async
def get_user_balance(user_id: int, bot_id: int):
    """Foydalanuvchining balansini hisoblash"""
    try:
        from modul.models import PaymentTransaction
        from django.db.models import Sum

        total = PaymentTransaction.objects.filter(
            user_id=user_id,
            bot_id=bot_id,
            status='completed'
        ).aggregate(total=Sum('amount_rubles'))

        balance = total['total'] if total['total'] else 0
        return balance

    except Exception as e:
        logger.error(f"Error calculating balance: {e}")
        return 0


async def send_admin_notification(bot, user_id: int, bot_db_id: int, stars_amount: int, rubles_amount: float,
                                  payment_id: str):
    """Admin ga batafsil xabar yuborish - bot ma'lumotlari bilan"""
    try:
        # Foydalanuvchi ma'lumotlarini olish
        user_info = await get_user_info(user_id, bot_db_id)

        if user_info:
            username = user_info.get('username', 'Не указан')
            first_name = user_info.get('first_name', 'Не указан')
        else:
            username = 'Не найден'
            first_name = 'Не найден'

        balance = await get_user_balance(user_id, bot_db_id)

        # Bot ma'lumotlarini olish
        bot_exists, bot_info = await validate_bot_exists(bot_db_id)

        bot_display = f"<code>{bot_db_id}</code>"
        bot_owner_info = ""

        if bot_exists and bot_info:
            bot_display = f"@{bot_info['username']} (ID: <code>{bot_db_id}</code>)"

            if bot_info['owner']:
                owner = bot_info['owner']
                bot_owner_info = (
                    f"\n\n👨‍💼 <b>Владелец бота:</b>\n"
                    f"• ID: <code>{owner['uid']}</code>\n"
                    f"• Имя: {owner['first_name']}\n"
                    f"• Username: @{owner['username']}" if owner['username'] else f"• Имя: {owner['first_name']}"
                )

        message = (
            f"💰 <b>НОВОЕ ПОПОЛНЕНИЕ</b>\n\n"
            f"👤 <b>Пользователь:</b>\n"
            f"• ID: <code>{user_id}</code>\n"
            f"• Имя: {first_name}\n"
            f"• Username: @{username}\n\n"
            f"💎 <b>Детали платежа:</b>\n"
            f"• Звезды: {stars_amount} ⭐️\n"
            f"• Зачислено: {rubles_amount}₽\n"
            f"• Payment ID: <code>{payment_id}</code>\n\n"
            f"🤖 <b>Бот:</b> {bot_display}"
            f"{bot_owner_info}\n\n"
            f"💳 <b>Новый баланс пользователя:</b> {balance:.2f}₽\n\n"
            f"🕐 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
        )

        await bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=message,
            parse_mode="HTML"
        )

        logger.info(f"✅ Admin notification sent for payment {payment_id}")
        return True

    except Exception as e:
        logger.error(f"❌ Error sending admin notification: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


async def send_user_notification(user_id: int, bot_id: int, amount: float):
    """Foydalanuvchiga xabar yuborish"""
    try:
        logger.info(f"📨 Should send notification to user {user_id} about {amount}₽ top-up")
        # TODO: Implement client bot notification
        return True
    except Exception as e:
        logger.error(f"❌ Error sending user notification: {e}")
        return False


# ==========================================
# MAIN BOT HANDLERS
# ==========================================

def init_bot_handlers():
    @main_bot_router.message(CommandStart())
    async def cmd_start(message: Message, state: FSMContext):
        """Start komandasi handleri"""
        logger.info("=" * 50)
        logger.info(f"🚀 START command from user {message.from_user.id}")
        logger.info(f"📝 Message text: '{message.text}'")

        user = message.from_user
        args = message.text.split()
        logger.info(f"📊 Args: {args}")
        logger.info(f"📏 Args count: {len(args)}")

        # Agar to'lov parametrlari bo'lsa
        if len(args) > 1:
            logger.info(f"✅ Has args[1]: '{args[1]}'")

            if args[1].startswith("gptbot_"):
                logger.info("✅ Payment parameters detected!")
                logger.info("🔀 Redirecting to handle_payment_start...")
                await handle_payment_start(message, args[1])
                logger.info("✅ handle_payment_start completed")
                logger.info("=" * 50)
                return
            else:
                logger.info(f"ℹ️ Args[1] doesn't start with 'gptbot_': '{args[1]}'")
        else:
            logger.info("ℹ️ No additional args")

        # Normal start command
        logger.info("📋 Processing normal start command...")

        try:
            db_user = await get_user_by_uid(user.id)

            welcome_text = (
                f"👋 <b>Добро пожаловать, {user.first_name}!</b>\n\n"
                f"🤖 <b>Конструктор ботов</b> - создавайте и управляйте своими Telegram ботами!\n\n"
                f"🔧 <b>Возможности:</b>\n"
                f"• Создание ботов за 2-3 минуты\n"
                f"• 6 профессиональных ботов\n"
                f"• Полная панель управления\n"
                f"• Автоматическая настройка\n\n"
                f"Выберите действие:"
            )

            if db_user:
                await message.answer(
                    welcome_text,
                    reply_markup=await main_menu(),
                    parse_mode="HTML"
                )
                logger.info(f"✅ Main menu shown to existing user")
            else:
                new_user = await handle_auto_registration(message, user)
                if new_user:
                    await message.answer(
                        welcome_text,
                        reply_markup=await main_menu(),
                        parse_mode="HTML"
                    )
                    logger.info(f"✅ Main menu shown to new user")
                else:
                    await message.answer(
                        "❌ Произошла ошибка при регистрации. Попробуйте еще раз.\n/start",
                        parse_mode="HTML"
                    )

        except Exception as e:
            logger.error(f"❌ Error in cmd_start: {e}")
            import traceback
            logger.error(f"Traceback:\n{traceback.format_exc()}")

            await message.answer(
                "❌ Произошла ошибка. Попробуйте еще раз.\n/start",
                parse_mode="HTML"
            )

        logger.info("=" * 50)

    @main_bot_router.message(Command("stats", "payment_stats"))
    async def cmd_payment_stats(message: Message):
        """Batafsil to'lovlar statistikasi"""
        try:
            if message.from_user.id != ADMIN_CHAT_ID:
                await message.answer("❌ Эта команда только для администратора!")
                return

            args = message.text.split()
            days = 7

            if len(args) > 1:
                try:
                    days = int(args[1])
                    if days < 1 or days > 365:
                        days = 7
                except ValueError:
                    days = 7

            wait_msg = await message.answer("⏳ Подготовка детальной статистики...")

            stats = await get_detailed_payment_statistics(days=days)

            if stats:
                msg1 = format_detailed_statistics_message(stats, period_days=days)
                await wait_msg.edit_text(msg1, parse_mode="HTML")

                await asyncio.sleep(1)

                msg2 = format_recent_payments_message(stats, limit=10)
                await message.answer(msg2, parse_mode="HTML")

                await asyncio.sleep(0.5)

                msg3 = format_top_users_message(stats)
                await message.answer(msg3, parse_mode="HTML")

                await asyncio.sleep(0.5)

                msg4 = format_daily_stats_message(stats, period_days=days)
                await message.answer(msg4, parse_mode="HTML")

                logger.info(f"✅ Detailed statistics sent for {days} days")
            else:
                await wait_msg.edit_text("❌ Ошибка при получении статистики")

        except Exception as e:
            logger.error(f"❌ Error in payment_stats: {e}")
            import traceback
            logger.error(traceback.format_exc())
            await message.answer("❌ Произошла ошибка")

    @main_bot_router.message(Command("send_weekly_report"))
    async def cmd_send_weekly_report(message: Message):
        """Haftalik hisobotni darhol yuborish (test)"""
        try:
            if message.from_user.id != ADMIN_CHAT_ID:
                await message.answer("❌ Bu komanda faqat admin uchun!")
                return

            await message.answer("📊 Haftalik hisobot tayyorlanmoqda...")
            await send_weekly_report(message.bot)
            await message.answer("✅ Hisobot yuborildi!")

        except Exception as e:
            logger.error(f"Error in send_weekly_report command: {e}")
            await message.answer(f"❌ Xatolik: {e}")

    async def handle_payment_start(message: Message, payment_args: str):
        """Invoice yuborish - bot validatsiyasi bilan"""
        try:
            parts = payment_args.split("_")

            if len(parts) >= 4:
                client_user_id = int(parts[1])
                stars_amount = int(parts[2])
                bot_db_id = int(parts[3])  # Bu ChatGPT botning database ID si

                # Bot mavjudligini tekshirish
                bot_exists, bot_info = await validate_bot_exists(bot_db_id)

                if not bot_exists:
                    await message.answer(
                        f"❌ <b>Ошибка!</b>\n\n"
                        f"Бот с ID <code>{bot_db_id}</code> не найден в системе.\n"
                        f"Возможно, бот был удален или ID неверный.",
                        parse_mode="HTML"
                    )
                    logger.error(f"❌ Bot {bot_db_id} not found, payment cancelled")
                    return

                stars_to_rubles = {1: 5, 5: 25}

                if stars_amount not in stars_to_rubles:
                    await message.answer("❌ Неверная сумма")
                    return

                rubles_amount = stars_to_rubles[stars_amount]

                logger.info("=" * 50)
                logger.info("💳 CREATING INVOICE...")
                logger.info(f"🤖 Main bot ID: {message.bot.id}")
                logger.info(f"👤 Client user: {client_user_id}")
                logger.info(f"⭐ Stars: {stars_amount}")
                logger.info(f"💰 Rubles: {rubles_amount}")
                logger.info(f"🔗 Target bot DB ID: {bot_db_id}")
                if bot_info:
                    logger.info(f"🤖 Bot info: @{bot_info['username']}")
                    if bot_info['owner']:
                        logger.info(
                            f"👨‍💼 Bot owner: {bot_info['owner']['first_name']} (ID: {bot_info['owner']['uid']})")
                logger.info("=" * 50)

                try:
                    await message.answer_invoice(
                        title="Пополнение баланса ChatGPT бота",
                        description=f"Пополнение на {rubles_amount}₽",
                        payload=f"gptbot_topup_{client_user_id}_{stars_amount}_{rubles_amount}_{bot_db_id}",
                        currency="XTR",
                        prices=[LabeledPrice(label=f"{stars_amount} ⭐️", amount=stars_amount)],
                        provider_token="",
                    )

                    logger.info("✅ Invoice sent successfully!")

                except Exception as e:
                    logger.error(f"❌ Invoice error: {e}")
                    import traceback
                    logger.error(traceback.format_exc())

                    await message.answer(
                        f"❌ Ошибка создания счета:\n<code>{e}</code>",
                        parse_mode="HTML"
                    )
            else:
                await message.answer("❌ Неверные параметры")

        except Exception as e:
            logger.error(f"❌ Error in handle_payment_start: {e}")
            import traceback
            logger.error(traceback.format_exc())

    async def handle_auto_registration(message: Message, user):
        """Yangi foydalanuvchini avtomatik ro'yxatdan o'tkazish"""
        try:
            telegram_id = user.id
            first_name = user.first_name or "Пользователь"
            last_name = user.last_name or ""
            username = user.username or ""

            photo_url = None
            try:
                user_photos = await message.bot.get_user_profile_photos(telegram_id)
                if user_photos.total_count > 0:
                    photo_id = user_photos.photos[0][-1].file_id
                    photo_file = await message.bot.get_file(photo_id)
                    photo_url = f"https://api.telegram.org/file/bot{message.bot.token}/{photo_file.file_path}"
            except Exception as e:
                logger.warning(f"Could not get user photo for {telegram_id}: {e}")

            new_user = await create_user_directly(
                uid=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                profile_image_url=photo_url
            )

            if new_user:
                logger.info(f"User {telegram_id} auto-registered successfully")
                return new_user
            else:
                logger.error(f"Failed to auto-register user {telegram_id}")
                return None

        except Exception as e:
            logger.error(f"Error in auto registration for user {telegram_id}: {e}")
            return None

    # ===== PAYMENT HANDLERS =====

    @main_bot_router.pre_checkout_query()
    async def pre_checkout_query_handler(pre_checkout_query):
        """To'lovdan oldin tekshirish"""
        try:
            logger.info("=" * 50)
            logger.info(f"💳 PRE-CHECKOUT QUERY received")
            logger.info(f"From user: {pre_checkout_query.from_user.id}")
            logger.info(f"Payload: {pre_checkout_query.invoice_payload}")

            payload = pre_checkout_query.invoice_payload

            if payload.startswith("gptbot_topup_"):
                logger.info("✅ Payload format valid")

                try:
                    parts = payload.split("_")
                    client_user_id = int(parts[2])
                    stars_amount = int(parts[3])
                    rubles_amount = float(parts[4])
                    bot_db_id = int(parts[5])

                    logger.info(
                        f"📊 Parsed: user={client_user_id}, stars={stars_amount}, rubles={rubles_amount}, bot_db_id={bot_db_id}")

                    # DARHOL TASDIQLASH
                    await pre_checkout_query.answer(ok=True)

                    logger.info("✅ Pre-checkout approved!")
                    logger.info("=" * 50)

                except (ValueError, IndexError) as e:
                    logger.error(f"❌ Parse error: {e}")
                    await pre_checkout_query.answer(
                        ok=False,
                        error_message="Ошибка параметров платежа"
                    )

            else:
                logger.warning(f"⚠️ Invalid payload format: {payload}")
                await pre_checkout_query.answer(
                    ok=False,
                    error_message="Неверный платеж"
                )
                logger.info("=" * 50)

        except Exception as e:
            logger.error(f"❌ PRE-CHECKOUT ERROR: {e}")
            import traceback
            logger.error(traceback.format_exc())

            try:
                await pre_checkout_query.answer(
                    ok=False,
                    error_message="Ошибка обработки"
                )
            except Exception as answer_error:
                logger.error(f"❌ Failed to send answer: {answer_error}")

            logger.info("=" * 50)

    @main_bot_router.message(F.successful_payment)
    async def successful_payment_handler(message: Message):
        """Muvaffaqiyatli to'lov handleri - bot validatsiyasi bilan"""
        try:
            logger.info("=" * 50)
            logger.info(f"✅ SUCCESSFUL PAYMENT received")
            logger.info(f"From user: {message.from_user.id}")

            payment = message.successful_payment
            payload = payment.invoice_payload
            payment_id = payment.telegram_payment_charge_id

            logger.info(f"Payload: {payload}")
            logger.info(f"Payment ID: {payment_id}")
            logger.info(f"Total amount: {payment.total_amount}")

            if payload.startswith("gptbot_topup_"):
                parts = payload.split("_")
                client_user_id = int(parts[2])
                stars_amount = int(parts[3])
                rubles_amount = float(parts[4])
                bot_db_id = int(parts[5])

                logger.info(f"📊 Payment details:")
                logger.info(f"  - Client: {client_user_id}")
                logger.info(f"  - Stars: {stars_amount}")
                logger.info(f"  - Rubles: {rubles_amount}")
                logger.info(f"  - Bot DB ID: {bot_db_id}")

                # Bot mavjudligini tekshirish
                bot_exists, bot_info = await validate_bot_exists(bot_db_id)

                if not bot_exists:
                    logger.error(f"❌ Bot {bot_db_id} not found during payment processing!")
                    await message.answer(
                        f"⚠️ <b>Оплата получена, но бот не найден!</b>\n\n"
                        f"💎 Оплачено: {stars_amount} ⭐️\n"
                        f"💰 Сумма: {rubles_amount}₽\n"
                        f"🔗 ID платежа: <code>{payment_id}</code>\n\n"
                        f"📞 Обратитесь к администратору.",
                        parse_mode="HTML"
                    )

                    # Admin ga xabar
                    try:
                        await message.bot.send_message(
                            chat_id=ADMIN_CHAT_ID,
                            text=f"⚠️ <b>ВНИМАНИЕ: Платеж для несуществующего бота!</b>\n\n"
                                 f"👤 User ID: <code>{client_user_id}</code>\n"
                                 f"🤖 Bot DB ID: <code>{bot_db_id}</code>\n"
                                 f"💰 Сумма: {rubles_amount}₽\n"
                                 f"🔗 Payment ID: <code>{payment_id}</code>\n\n"
                                 f"❌ Bot не найден в базе!",
                            parse_mode="HTML"
                        )
                    except Exception as admin_error:
                        logger.error(f"Failed to notify admin: {admin_error}")

                    return

                logger.info(f"✅ Bot validated: @{bot_info['username']}")
                if bot_info['owner']:
                    logger.info(f"👨‍💼 Owner: {bot_info['owner']['first_name']} (ID: {bot_info['owner']['uid']})")

                try:
                    success = await save_payment_transaction(
                        user_id=client_user_id,
                        source_bot_id=bot_db_id,
                        stars_amount=stars_amount,
                        rubles_amount=rubles_amount,
                        payment_id=payment_id,
                        payment_date=datetime.now()
                    )

                    if success:
                        logger.info("✅ Payment saved to database")

                        try:
                            await send_admin_notification(
                                message.bot, client_user_id, bot_db_id,
                                stars_amount, rubles_amount, payment_id
                            )
                            logger.info("✅ Admin notification sent")
                        except Exception as e:
                            logger.error(f"⚠️ Failed to send admin notification: {e}")

                        try:
                            await send_user_notification(
                                client_user_id, bot_db_id, rubles_amount
                            )
                            logger.info("✅ User notification sent")
                        except Exception as e:
                            logger.error(f"⚠️ Failed to send user notification: {e}")

                        await message.answer(
                            f"✅ <b>Оплата прошла успешно!</b>\n\n"
                            f"💎 Оплачено: {stars_amount} ⭐️\n"
                            f"💰 Сумма: {rubles_amount}₽\n"
                            f"👤 Пользователь: <code>{client_user_id}</code>\n"
                            f"🤖 Бот: @{bot_info['username']}\n"
                            f"🔗 ID платежа: <code>{payment_id}</code>\n\n"
                            f"📊 Баланс успешно пополнен!",
                            parse_mode="HTML"
                        )

                        logger.info("✅ Payment fully processed")

                    else:
                        logger.error("❌ Failed to save payment")
                        await message.answer(
                            f"⚠️ <b>Оплата получена, но возникла ошибка при сохранении!</b>\n\n"
                            f"💎 Оплачено: {stars_amount} ⭐️\n"
                            f"💰 Сумма: {rubles_amount}₽\n"
                            f"🔗 ID: <code>{payment_id}</code>\n\n"
                            f"📞 Обратитесь к администратору.",
                            parse_mode="HTML"
                        )

                except Exception as db_error:
                    logger.error(f"❌ Database error: {db_error}")
                    import traceback
                    logger.error(traceback.format_exc())

                    await message.answer(
                        f"⚠️ <b>Оплата получена, но возникла ошибка!</b>\n\n"
                        f"🔗 ID платежа: <code>{payment_id}</code>\n"
                        f"💰 Сумма: {rubles_amount}₽\n\n"
                        f"📞 Администратор уведомлен.",
                        parse_mode="HTML"
                    )

            logger.info("=" * 50)

        except Exception as e:
            logger.error(f"❌ CRITICAL ERROR in successful_payment_handler: {e}")
            import traceback
            logger.error(traceback.format_exc())

            await message.answer(
                "❌ Критическая ошибка при обработке оплаты.\n"
                "Администратор уведомлен.",
                parse_mode="HTML"
            )
            logger.info("=" * 50)

    # ===== OTHER HANDLERS =====

    @main_bot_router.callback_query(F.data == "back_to_main")
    async def back_to_main(callback: CallbackQuery, state: FSMContext):
        """Asosiy menyuga qaytish"""
        await state.clear()
        await callback.message.edit_text(
            f"🏠 <b>Главное меню</b>\n\nВыберите нужное действие:",
            reply_markup=await main_menu(),
            parse_mode="HTML"
        )
        await callback.answer()

    @main_bot_router.callback_query(F.data == "info")
    async def show_info(callback: CallbackQuery):
        info_text = (
            f"📖 <b>Информация о Конструкторе ботов</b>\n\n"
            f"🤖 <b>Что это?</b>\n"
            f"Конструктор ботов - это платформа для создания и управления Telegram ботами без программирования.\n\n"
            f"⚡ <b>Быстро и просто:</b>\n"
            f"• Создание бота за 2-3 минуты\n"
            f"• Готовые бот функций\n"
            f"• Автоматическая настройка\n"
            f"• Подробная статистика\n\n"
            f"🎯 <b>6 профессиональных бот:</b>\n\n"
            f"💸 <b>Реферальная система</b> - зарабатывайте на рефералах\n"
            f"🎬 <b>Кино бот</b> - поиск и скачивание фильмов\n"
            f"🔥 <b>Загрузчик</b> - скачивание с YouTube, Instagram, TikTok\n"
            f"💬 <b>ChatGPT</b> - ИИ помощник\n"
            f"❤️ <b>Знакомства</b> - система знакомств Leo Match\n"
            f"👤 <b>Анонимный чат</b> - анонимное общение\n"
            f"💡 <b>Преимущества:</b>\n"
            f"• Без кодирования\n"
            f"• Мгновенный запуск\n"
            f"• Техническая поддержка\n"
            f"• Постоянные обновления"
        )

        await callback.message.edit_text(
            info_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🤖 Создать бота", callback_data="create_bot")],
                [InlineKeyboardButton(text="💬 Поддержка", url="https://t.me/Dark_Just")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()

    @main_bot_router.callback_query(F.data == "faq")
    async def show_faq(callback: CallbackQuery):
        """FAQ bo'limi"""
        faq_text = (
            f"💬 <b>Часто задаваемые вопросы (FAQ)</b>\n\n"
            f"❓ <b>Как создать бота?</b>\n"
            f"1. Нажмите 'Создать бота ⚙️'\n"
            f"2. Получите токен у @BotFather\n"
            f"3. Вставьте токен в наш бот\n"
            f"4. Выберите нужные модули\n"
            f"5. Готово! Бот работает\n\n"
            f"💰 <b>Сколько это стоит?</b>\n"
            f"Создание бота - БЕСПЛАТНО!\n"
            f"Комиссия берется только с заработанных средств в модулях.\n\n"
            f"🔧 <b>Нужно ли знать программирование?</b>\n"
            f"НЕТ! Всё уже готово. Просто выбираете модули и настраиваете.\n\n"
            f"⚙️ <b>Можно ли изменить модули позже?</b>\n"
            f"ДА! В любое время можете включить/выключить модули в настройках.\n\n"
            f"📊 <b>Как посмотреть статистику?</b>\n"
            f"В разделе 'Мои боты 🖥️' выберите бота и нажмите 'Статистика'.\n\n"
            f"🛠️ <b>Что если бот сломается?</b>\n"
            f"У нас есть техническая поддержка 24/7. Обращайтесь в любое время!\n\n"
            f"💸 <b>Как работает реферальная система?</b>\n"
            f"За каждого приглашенного друга вы получаете бонус. Размер бонуса настраивается.\n\n"
            f"🔐 <b>Безопасно ли давать токен бота?</b>\n"
            f"ДА! Токен используется только для управления ботом. Мы НЕ можем получить доступ к вашему аккаунту.\n\n"
            f"⏱️ <b>Как быстро бот начнет работать?</b>\n"
            f"Сразу после создания! Обычно 30-60 секунд на настройку."
        )

        await callback.message.edit_text(
            faq_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❓ Задать вопрос", url="https://t.me/Dark_Just")],
                [InlineKeyboardButton(text="📖 Инструкция", url="https://ismoilov299.uz")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")]
            ]),
            parse_mode="HTML"
        )
        await callback.answer()

    # Placeholder handlers
    @main_bot_router.callback_query(F.data == "statistics")
    async def statistics_redirect(callback: CallbackQuery):
        await callback.answer("📊 Статистику можно посмотреть в разделе 'Мои боты'")
        from modul.bot.main_bot.handlers.manage_bots import show_my_bots
        await show_my_bots(callback)

    @main_bot_router.callback_query(F.data == "balance")
    async def balance_redirect(callback: CallbackQuery):
        await callback.answer("💰 Баланс можно посмотреть в разделе 'Мои боты'")
        from modul.bot.main_bot.handlers.manage_bots import show_my_bots
        await show_my_bots(callback)

    @main_bot_router.callback_query(F.data == "settings")
    async def settings_redirect(callback: CallbackQuery):
        await callback.answer("🔧 Настройки ботов находятся в разделе 'Мои боты'")
        from modul.bot.main_bot.handlers.manage_bots import show_my_bots
        await show_my_bots(callback)

    @main_bot_router.callback_query(F.data == "help")
    async def help_redirect(callback: CallbackQuery):
        await show_faq(callback)

    # Include sub-routers
    main_bot_router.include_router(create_bot_router)
    main_bot_router.include_router(manage_bots_router)

    logger.info("Main bot handlers initialized successfully!")