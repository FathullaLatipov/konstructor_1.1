import logging
from datetime import datetime

from django.db.models import F
from asgiref.sync import sync_to_async
from django.db import transaction

from modul.models import UserTG


def get_all_names():
    result = UserTG.objects.values_list("username", flat=True)
    return list(result)


@sync_to_async
def get_all_ids():
    result = UserTG.objects.values_list("uid", flat=True)
    return list(result)


@sync_to_async
def get_user_balance_db(user_id: int, bot_id: int = None):
    """
    Foydalanuvchining balansini olish
    PaymentTransaction dan to'lovlarni hisoblaydi + eski referal balance
    """
    try:
        # 1. PaymentTransaction dan balance (to'lovlar va GPT yechimlar)
        from modul.models import PaymentTransaction
        from django.db.models import Sum

        if bot_id is None:
            logger.error("bot_id required")
            payment_balance = 0.0
        else:
            total = PaymentTransaction.objects.filter(
                user_id=user_id,
                bot_id=bot_id,
                status='completed'
            ).aggregate(total=Sum('amount_rubles'))

            payment_balance = float(total['total']) if total['total'] else 0.0

        # 2. Eski referal balance (o'zgarmaydi)
        try:
            # Sizning eski referal sistemangiz
            # Masalan: ChatGPTBotUser modeli yoki boshqa
            from modul.models import ChatGPTBotUser
            user = ChatGPTBotUser.objects.filter(user_id=user_id).first()
            referral_balance = float(user.balance) if user and hasattr(user, 'balance') else 0.0
        except:
            referral_balance = 0.0

        # Jami balance
        total_balance = payment_balance + referral_balance

        logger.info(
            f"Balance: user={user_id}, bot={bot_id}, "
            f"payment={payment_balance}₽, referral={referral_balance}₽, "
            f"total={total_balance}₽"
        )

        return total_balance

    except Exception as e:
        logger.error(f"Error getting balance: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 0.0


@sync_to_async
def get_info_db(tg_id):
    result = UserTG.objects.filter(uid=tg_id).values_list("username", "uid", "balance")
    return list(result)


# shortcuts.py ga qo'shing:

@sync_to_async
def get_channels_with_type_for_check():
    try:
        from modul.models import ChannelSponsor, SystemChannel

        # ChannelSponsor modelidan kanallar
        sponsor_channels = ChannelSponsor.objects.all()
        sponsor_list = [(str(c.chanel_id), '', 'sponsor') for c in sponsor_channels]

        # SystemChannel modelidan aktiv kanallar
        system_channels = SystemChannel.objects.filter(is_active=True)
        system_list = [(str(c.channel_id), c.channel_url, 'system') for c in system_channels]

        # Ikkalasini birlashtirish
        all_channels = sponsor_list + system_list

        print(f"Found sponsor channels: {len(sponsor_list)}, system channels: {len(system_list)}")
        return all_channels
    except Exception as e:
        print(f"Error getting channels with type: {e}")
        return []


@sync_to_async
def remove_sponsor_channel(channel_id):
    """Faqat sponsor kanallarni o'chirish"""
    try:
        from modul.models import ChannelSponsor
        deleted_count = ChannelSponsor.objects.filter(chanel_id=channel_id).delete()
        print(f"Removed invalid sponsor channel {channel_id}, deleted: {deleted_count[0]}")
    except Exception as e:
        print(f"Error removing sponsor channel {channel_id}: {e}")


async def get_chatgpt_bonus_amount(bot_token):
    """Bot sozlamalaridan bonus miqdorini olish"""
    try:
        from modul.models import AdminInfo
        admin_info = await sync_to_async(AdminInfo.objects.filter(bot_token=bot_token).first)()
        return float(admin_info.price) if admin_info and admin_info.price else 3.0
    except:
        return 3.0


async def process_chatgpt_referral_bonus(user_id: int, referrer_id: int, bot_token: str):
    """ChatGPT bot uchun referral bonusini hisoblash"""
    try:
        # Bonus miqdorini olish
        bonus_amount = await get_chatgpt_bonus_amount(bot_token)

        # Referrer mavjudligini tekshirish
        referrer_exists = await default_checker(referrer_id)
        if not referrer_exists:
            print(f"Referrer {referrer_id} not found")
            return False, 0

        # Balansni oshirish - sizning mavjud funksiyangiz bilan
        success = await update_bc(referrer_id, "+", bonus_amount)
        if success:
            print(f"Added {bonus_amount} to referrer {referrer_id} for user {user_id}")
            return True, bonus_amount

        return False, 0
    except Exception as e:
        print(f"Error in process_chatgpt_referral_bonus: {e}")
        return False, 0


@sync_to_async
def update_bc(tg_id: int, sign: str, amount: float, bot_id: int = None):
    """
    Balansni yangilash
    FAQAT minus (GPT so'rov) uchun PaymentTransaction ishlatadi
    Plus (referal) eski sistemada qoladi
    """
    try:
        amount_value = float(amount)

        # MINUS - GPT so'rov, PaymentTransaction ga yozish
        if sign == '-':
            if bot_id is None:
                logger.error("bot_id required for deduction")
                return False

            from modul.models import PaymentTransaction

            PaymentTransaction.objects.create(
                user_id=tg_id,
                bot_id=bot_id,
                amount_rubles=-amount_value,  # Minus
                amount_stars=0,
                payment_id=f"gpt_deduct_{tg_id}_{bot_id}_{int(datetime.now().timestamp())}",
                status='completed'
            )

            logger.info(f"✅ Deducted {amount_value}₽ from user {tg_id} (GPT request)")
            return True

        # PLUS - referal bonus, ESKI SISTEMA
        else:
            # Eski referal sistemangiz (o'zgarmaydi)
            try:
                from modul.models import ChatGPTBotUser
                user = ChatGPTBotUser.objects.filter(user_id=tg_id).first()

                if user:
                    user.balance += amount_value
                    user.save()
                    logger.info(f"✅ Added {amount_value}₽ to user {tg_id} (referral - old system)")
                    return True
                else:
                    logger.error(f"User not found: {tg_id}")
                    return False
            except Exception as ref_error:
                logger.error(f"Error updating referral balance: {ref_error}")
                return False

    except Exception as e:
        logger.error(f"Error in update_bc: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

logger = logging.getLogger(__name__)


@sync_to_async
def update_bc_name(tg_id: str, sign: str, amount: float, bot_id: int = None):
    """Username yoki ID orqali balance yangilash"""
    try:
        from modul.models import User, PaymentTransaction, ChatGPTBotUser

        # ID ni aniqlash
        if tg_id.isdigit():
            user_id = int(tg_id)
        else:
            user = User.objects.filter(username=tg_id).first()
            if not user:
                logger.error(f"User not found: {tg_id}")
                return False
            user_id = user.uid

        amount_value = float(amount)

        # MINUS - PaymentTransaction
        if sign == '-':
            if bot_id is None:
                return False

            PaymentTransaction.objects.create(
                user_id=user_id,
                bot_id=bot_id,
                amount_rubles=-amount_value,
                amount_stars=0,
                payment_id=f"admin_deduct_{user_id}_{int(datetime.now().timestamp())}",
                status='completed'
            )
            return True

        # PLUS - eski referal sistema
        else:
            user = ChatGPTBotUser.objects.filter(user_id=user_id).first()
            if user:
                user.balance += amount_value
                user.save()
                return True
            return False

    except Exception as e:
        logger.error(f"Error: {e}")
        return False

@sync_to_async
def default_checker(tg_id):
    result = UserTG.objects.filter(uid=tg_id).exists()
    return result


