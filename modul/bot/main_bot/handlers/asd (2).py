from asgiref.sync import sync_to_async
from your_app.models import Bot  # импортируй свою модель
import re
import logging

logger = logging.getLogger(__name__)

@sync_to_async
def validate_bot_token(token: str):
    """
    Проверка токена бота.
    Проверяет:
    1. Формат токена.
    2. Не используется ли он уже в БД.
    """

    # Проверка формата токена
    if not re.match(r'^\d{8,10}:[A-Za-z0-9_-]{35}$', token):
        return False, "Неправильный формат токена"

    try:
        # Проверяем, не используется ли токен уже
        if Bot.objects.filter(token=token).exists():
            return False, "Этот токен уже используется другим ботом"

        return True, "Токен корректный"
    except Exception as e:
        logger.error(f"Ошибка при проверке токена {token}: {e}")
        return False, "Ошибка проверки токена (БД недоступна)"



import aiohttp
import asyncio
import logging

logger = logging.getLogger(__name__)

async def get_bot_info_from_telegram(token: str):
    """
    Получение информации о боте через Telegram API с таймаутом.
    """
    url = f"https://api.telegram.org/bot{token}/getMe"

    try:
        timeout = aiohttp.ClientTimeout(total=5)  # максимум 5 секунд
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.warning(f"Telegram API вернул {response.status} для токена {token}")
                    return None

                data = await response.json()
                if not data.get("ok"):
                    logger.warning(f"Telegram ответил ошибкой: {data}")
                    return None

                bot_info = data["result"]
                return {
                    "id": bot_info["id"],
                    "username": bot_info["username"],
                    "first_name": bot_info.get("first_name", ""),
                    "is_bot": bot_info["is_bot"],
                }

    except asyncio.TimeoutError:
        logger.error(f"Таймаут при получении информации о боте (token={token})")
        return None
    except aiohttp.ClientError as e:
        logger.error(f"Ошибка сети при обращении к Telegram API: {e}")
        return None
    except Exception as e:
        logger.exception(f"Неизвестная ошибка при запросе к Telegram API для токена {token}: {e}")
        return None
