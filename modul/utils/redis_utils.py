# modul/utils/redis_utils.py
"""
Redis Cache va Utility funksiyalar
"""

from django.core.cache import cache, caches
from typing import Optional, Any, List, Dict
import json
import logging
import time
from functools import wraps
import hashlib

logger = logging.getLogger(__name__)


class RedisCache:
    """Redis cache uchun asosiy utility class"""

    @staticmethod
    def set(key: str, value: Any, timeout: Optional[int] = 3600) -> bool:
        """
        Ma'lumotni cache ga saqlash

        Args:
            key: Cache key
            value: Saqlanadigan qiymat
            timeout: Amal qilish muddati (soniyalarda)

        Returns:
            bool: Muvaffaqiyatli yoki yo'q
        """
        try:
            cache.set(key, value, timeout)
            logger.debug(f"Cache set: {key}")
            return True
        except Exception as e:
            logger.error(f"Redis set error for key {key}: {e}")
            return False

    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        """Cache dan ma'lumot olish"""
        try:
            value = cache.get(key, default)
            if value is not None:
                logger.debug(f"Cache hit: {key}")
            else:
                logger.debug(f"Cache miss: {key}")
            return value
        except Exception as e:
            logger.error(f"Redis get error for key {key}: {e}")
            return default

    @staticmethod
    def delete(key: str) -> bool:
        """Cache dan o'chirish"""
        try:
            cache.delete(key)
            logger.debug(f"Cache deleted: {key}")
            return True
        except Exception as e:
            logger.error(f"Redis delete error for key {key}: {e}")
            return False

    @staticmethod
    def get_many(keys: List[str]) -> Dict[str, Any]:
        """Ko'p qiymatlarni bir vaqtda olish"""
        try:
            return cache.get_many(keys)
        except Exception as e:
            logger.error(f"Redis get_many error: {e}")
            return {}

    @staticmethod
    def set_many(data: Dict[str, Any], timeout: Optional[int] = 3600) -> bool:
        """Ko'p qiymatlarni bir vaqtda saqlash"""
        try:
            cache.set_many(data, timeout)
            logger.debug(f"Cache set_many: {len(data)} items")
            return True
        except Exception as e:
            logger.error(f"Redis set_many error: {e}")
            return False

    @staticmethod
    def incr(key: str, delta: int = 1) -> Optional[int]:
        """
        Qiymatni oshirish (counter uchun)
        Agar key mavjud bo'lmasa, delta qiymatini yaratadi
        """
        try:
            return cache.incr(key, delta)
        except ValueError:
            # Key mavjud emas, yangi yaratish
            cache.set(key, delta)
            return delta
        except Exception as e:
            logger.error(f"Redis incr error for key {key}: {e}")
            return None

    @staticmethod
    def decr(key: str, delta: int = 1) -> Optional[int]:
        """Qiymatni kamaytirish"""
        try:
            return cache.decr(key, delta)
        except ValueError:
            cache.set(key, 0)
            return 0
        except Exception as e:
            logger.error(f"Redis decr error for key {key}: {e}")
            return None

    @staticmethod
    def exists(key: str) -> bool:
        """Key mavjudligini tekshirish"""
        try:
            return cache.get(key) is not None
        except Exception as e:
            logger.error(f"Redis exists error for key {key}: {e}")
            return False

    @staticmethod
    def ttl(key: str) -> Optional[int]:
        """Key ning qolgan amal qilish muddatini olish"""
        try:
            return cache.ttl(key)
        except Exception as e:
            logger.error(f"Redis ttl error for key {key}: {e}")
            return None

    @staticmethod
    def expire(key: str, timeout: int) -> bool:
        """Key ning amal qilish muddatini o'zgartirish"""
        try:
            cache.expire(key, timeout)
            return True
        except Exception as e:
            logger.error(f"Redis expire error for key {key}: {e}")
            return False


class BotCache:
    """Bot ma'lumotlari uchun maxsus cache"""

    CACHE_TIMEOUT = 3600  # 1 soat

    @staticmethod
    def _get_bot_key(bot_token: str) -> str:
        """Bot cache key ni generatsiya qilish"""
        return f"bot:{bot_token}"

    @staticmethod
    def cache_bot(bot_token: str, bot_data: dict, timeout: int = CACHE_TIMEOUT):
        """Bot ma'lumotlarini cache qilish"""
        key = BotCache._get_bot_key(bot_token)
        RedisCache.set(key, bot_data, timeout)
        logger.info(f"Bot cached: {bot_token}")

    @staticmethod
    def get_cached_bot(bot_token: str) -> Optional[dict]:
        """Cache dan bot ma'lumotlarini olish"""
        key = BotCache._get_bot_key(bot_token)
        return RedisCache.get(key)

    @staticmethod
    def invalidate_bot_cache(bot_token: str):
        """Bot cache ni tozalash"""
        key = BotCache._get_bot_key(bot_token)
        RedisCache.delete(key)
        logger.info(f"Bot cache invalidated: {bot_token}")

    @staticmethod
    def _get_bot_stats_key(bot_token: str) -> str:
        """Bot statistika key"""
        return f"bot_stats:{bot_token}"

    @staticmethod
    def cache_bot_stats(bot_token: str, stats: dict, timeout: int = 300):
        """Bot statistikasini cache qilish (5 daqiqa)"""
        key = BotCache._get_bot_stats_key(bot_token)
        RedisCache.set(key, stats, timeout)

    @staticmethod
    def get_cached_bot_stats(bot_token: str) -> Optional[dict]:
        """Cache dan statistika olish"""
        key = BotCache._get_bot_stats_key(bot_token)
        return RedisCache.get(key)


class UserCache:
    """Foydalanuvchi ma'lumotlari uchun cache"""

    CACHE_TIMEOUT = 900  # 15 daqiqa

    @staticmethod
    def _get_user_key(user_id: int) -> str:
        return f"user:{user_id}"

    @staticmethod
    def cache_user(user_id: int, user_data: dict, timeout: int = CACHE_TIMEOUT):
        """Foydalanuvchi ma'lumotlarini cache qilish"""
        key = UserCache._get_user_key(user_id)
        RedisCache.set(key, user_data, timeout)

    @staticmethod
    def get_cached_user(user_id: int) -> Optional[dict]:
        """Cache dan foydalanuvchi ma'lumotlarini olish"""
        key = UserCache._get_user_key(user_id)
        return RedisCache.get(key)

    @staticmethod
    def invalidate_user_cache(user_id: int):
        """Foydalanuvchi cache ni tozalash"""
        key = UserCache._get_user_key(user_id)
        RedisCache.delete(key)


class RateLimiter:
    """Rate limiting uchun utility"""

    @staticmethod
    def check_rate_limit(
            user_id: int,
            action: str,
            max_requests: int = 10,
            window: int = 60
    ) -> tuple[bool, Optional[int]]:
        """
        Rate limit tekshirish

        Args:
            user_id: Foydalanuvchi ID
            action: Amal nomi (masalan, 'message', 'api_call')
            max_requests: Maksimal so'rovlar soni
            window: Vaqt oynasi (soniyalarda)

        Returns:
            (allowed, remaining): Ruxsat berilganmi va qolgan so'rovlar
        """
        key = f"rate_limit:{user_id}:{action}"

        try:
            current = RedisCache.get(key, 0)

            if current >= max_requests:
                ttl = RedisCache.ttl(key)
                logger.warning(f"Rate limit exceeded for user {user_id}, action {action}")
                return False, 0

            # Counter ni oshirish
            if current == 0:
                RedisCache.set(key, 1, window)
                return True, max_requests - 1
            else:
                new_count = RedisCache.incr(key)
                remaining = max_requests - new_count
                return True, max(0, remaining)

        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            # Xatolik bo'lsa, ruxsat berish (fail-open)
            return True, None

    @staticmethod
    def reset_rate_limit(user_id: int, action: str):
        """Rate limit ni reset qilish"""
        key = f"rate_limit:{user_id}:{action}"
        RedisCache.delete(key)


def cache_result(timeout: int = 3600, key_prefix: str = ""):
    """
    Function natijasini cache qilish uchun decorator

    Usage:
        @cache_result(timeout=600, key_prefix="bot_users")
        def get_bot_users(bot_id):
            # DB query
            return users
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Cache key yaratish
            key_parts = [key_prefix or func.__name__]
            key_parts.extend([str(arg) for arg in args])
            key_parts.extend([f"{k}:{v}" for k, v in sorted(kwargs.items())])

            cache_key = ":".join(key_parts)
            cache_key = hashlib.md5(cache_key.encode()).hexdigest()

            # Cache dan olishga harakat qilish
            cached_result = RedisCache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_result

            # Function ni bajarish
            result = func(*args, **kwargs)

            # Natijani cache qilish
            RedisCache.set(cache_key, result, timeout)
            logger.debug(f"Cached result for {func.__name__}")

            return result

        return wrapper

    return decorator


class CachePatterns:
    """Keng tarqalgan cache patternlari"""

    @staticmethod
    def get_or_set(key: str, default_func, timeout: int = 3600):
        """
        Cache dan olish yoki funksiya natijasini saqlash

        Usage:
            users = CachePatterns.get_or_set(
                'bot_users:123',
                lambda: User.objects.filter(bot_id=123).all(),
                timeout=600
            )
        """
        cached = RedisCache.get(key)
        if cached is not None:
            return cached

        result = default_func()
        RedisCache.set(key, result, timeout)
        return result

    @staticmethod
    def cache_aside(key: str, db_func, timeout: int = 3600):
        """Cache-Aside pattern"""
        # Try cache first
        cached = RedisCache.get(key)
        if cached is not None:
            return cached

        # Cache miss - get from DB
        result = db_func()

        # Update cache
        if result is not None:
            RedisCache.set(key, result, timeout)

        return result


# Monitoring va statistika
class CacheStats:
    """Cache statistikasi"""

    @staticmethod
    def get_stats() -> dict:
        """Redis statistikasini olish"""
        try:
            from django_redis import get_redis_connection
            r = get_redis_connection("default")
            info = r.info()

            stats = {
                'used_memory': info.get('used_memory_human', 'N/A'),
                'total_commands': info.get('total_commands_processed', 0),
                'connected_clients': info.get('connected_clients', 0),
                'keys_count': r.dbsize(),
                'hit_rate': 0,
            }

            # Hit rate hisoblash
            hits = info.get('keyspace_hits', 0)
            misses = info.get('keyspace_misses', 0)
            if hits + misses > 0:
                stats['hit_rate'] = round(hits / (hits + misses) * 100, 2)

            return stats
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}

    @staticmethod
    def clear_cache_pattern(pattern: str):
        """Pattern bo'yicha cache tozalash"""
        try:
            from django_redis import get_redis_connection
            r = get_redis_connection("default")

            keys = r.keys(f"*{pattern}*")
            if keys:
                r.delete(*keys)
                logger.info(f"Cleared {len(keys)} keys matching pattern: {pattern}")
                return len(keys)
            return 0
        except Exception as e:
            logger.error(f"Error clearing cache pattern: {e}")
            return 0


# USAGE EXAMPLES:

# 1. Oddiy cache
def example_simple_cache():
    RedisCache.set('my_key', {'data': 'value'}, timeout=600)
    data = RedisCache.get('my_key')
    print(data)


# 2. Bot cache
def example_bot_cache():
    bot_data = {
        'id': 1,
        'username': 'my_bot',
        'enable_leo': True,
    }
    BotCache.cache_bot('bot_token_123', bot_data)

    # Keyinroq olish
    cached_bot = BotCache.get_cached_bot('bot_token_123')
    print(cached_bot)


# 3. Rate limiting
def example_rate_limit():
    user_id = 12345
    allowed, remaining = RateLimiter.check_rate_limit(
        user_id,
        'message',
        max_requests=20,
        window=60
    )

    if allowed:
        print(f"Request allowed. {remaining} requests remaining")
    else:
        print("Rate limit exceeded")


# 4. Function cache decorator
@cache_result(timeout=300, key_prefix="expensive_calc")
def expensive_calculation(param1, param2):
    # Bu faqat birinchi marta bajariladi
    # Keyingi chaqiruvlar cache dan olinadi
    import time
    time.sleep(2)  # Og'ir hisob-kitob simulatsiyasi
    return param1 + param2


# 5. Cache statistics
def example_stats():
    stats = CacheStats.get_stats()
    print(f"Cache hit rate: {stats['hit_rate']}%")
    print(f"Total keys: {stats['keys_count']}")