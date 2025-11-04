import logging

from modul.models import ChannelSponsor, SystemChannel, Bot
from asgiref.sync import sync_to_async
logger = logging.getLogger(__name__)

@sync_to_async
def create_channel_sponsor(channel_id: int, url: str = None, bot_token: str = None):
    try:
        bot_obj = Bot.objects.filter(token=bot_token).first()
        if not bot_obj:
            return None

        channel, created = ChannelSponsor.objects.get_or_create(
            chanel_id=channel_id,
            bot=bot_obj,  # ← Bot qo'shildi
            defaults={'url': url or ''}
        )

        if not created and url:
            channel.url = url
            channel.save()

        return channel
    except Exception as e:
        logger.error(f"Error creating sponsor channel: {e}")
        return None

@sync_to_async
def remove_channel_sponsor(channel_id):
    try:
        kanal = ChannelSponsor.objects.get(chanel_id=channel_id)
        kanal.delete()
        print(f"Kanal {channel_id} muvaffaqiyatli o‘chirildi.")
    except ChannelSponsor.DoesNotExist:
        print(f"Kanal {channel_id} topilmadi.")


@sync_to_async
def get_all_channels_sponsors() -> list:
    try:
        sponsor_channels = list(ChannelSponsor.objects.values_list('chanel_id', flat=True))
        system_channels = list(SystemChannel.objects.filter(is_active=True).values_list('channel_id', flat=True))
        all_channels = sponsor_channels + system_channels
        return all_channels
    except Exception as e:
        return []
