import os
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram import Router, Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

# ===================================
# REDIS FSM STORAGE
# ===================================

# Redis sozlamalari
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)

# Redis connection
redis = Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    db=1,
    decode_responses=False
)

# Redis Storage - FSM state
storage = RedisStorage(redis=redis)

print(f"✅ Redis FSM Storage configured: {REDIS_HOST}:{REDIS_PORT} (DB 1)")

# ===================================
# BOT VA DISPATCHER
# ===================================

bot_session = AiohttpSession()

# Main bot
main_bot_token = os.getenv('BOT_TOKEN', '8397910467:AAHAzSvYAZ_Gc0-J0wBSKIPZ9w2E74SRc8Q')
main_bot = Bot(token=main_bot_token, session=bot_session)

# Dispatcher - Redis storage
dp = Dispatcher(storage=storage)

print(f"✅ Dispatcher configured with Redis storage")

# ===================================
# ROUTERS
# ===================================

client_bot_router = Router()
main_bot_router = Router()

# Router
# dp.include_router(client_bot_router)
# dp.include_router(main_bot_router)

# ===================================
# YORDAMCHI FUNKSIYALAR
# ===================================

async def close_storage():
    """Storage va redis ni to'g'ri yopish"""
    try:
        await storage.close()
        await redis.close()
        print("✅ Redis storage closed")
    except Exception as e:
        print(f"❌ Error closing storage: {e}")


async def clear_all_states():
    """Barcha state larni tozalash (agar kerak bo'lsa)"""
    try:
        await redis.flushdb()
        print("✅ All FSM states cleared")
    except Exception as e:
        print(f"❌ Error clearing states: {e}")