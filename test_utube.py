import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
import yt_dlp
import subprocess

# Logging sozlamalari
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot tokenini kiriting
BOT_TOKEN = "5495221573:AAFG1Ml2ygmi-b3WGTJFcuFEjp9h1HUKz-Q"

# Bot va dispatcher - timeout oshirildi
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Papkalarni yaratish
os.makedirs("downloads", exist_ok=True)
os.makedirs("compressed", exist_ok=True)


async def video_yuklash_async(url: str, output_path: str) -> dict:
    """YouTube dan asinxron video yuklash"""
    try:
        # Asinxron yt-dlp ishlatish
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: video_yuklash_sync(url, output_path))
        return result
    except Exception as e:
        logger.error(f"Yuklashda xato: {e}")
        return {'success': False, 'error': str(e)}


def video_yuklash_sync(url: str, output_path: str) -> dict:
    """YouTube dan video yuklash (sync version)"""
    ydl_opts = {
        'format': 'best[ext=mp4][height<=720]/best[ext=mp4]/best',  # Max 720p
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return {
                'success': True,
                'title': info.get('title', 'Video'),
                'duration': info.get('duration', 0)
            }
    except Exception as e:
        logger.error(f"Yuklashda xato: {e}")
        return {'success': False, 'error': str(e)}


def video_davomiyligini_olish(input_file: str) -> float:
    """Video davomiyligini olish (soniyalarda)"""
    try:
        command = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            input_file
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except:
        return 0


async def video_siqish_async(input_file: str, output_file: str, max_size_mb: float = 49) -> bool:
    """FFmpeg yordamida asinxron videoni siqish"""
    try:
        # Video davomiyligini olish
        duration = video_davomiyligini_olish(input_file)
        if duration == 0:
            logger.error("Video davomiyligini aniqlab bo'lmadi")
            return False
        
        # Maqsadli hajm (bytes)
        target_size_bytes = max_size_mb * 1024 * 1024
        audio_bitrate = 96
        
        # Video uchun bitrate hisoblash
        total_bitrate = (target_size_bytes * 8) / duration / 1000
        video_bitrate = int(total_bitrate - audio_bitrate)
        
        if video_bitrate < 300:
            video_bitrate = 300
        if video_bitrate > 2500:
            video_bitrate = 2500
        
        logger.info(f"Siqish: {duration:.1f}s, bitrate={video_bitrate}k")
        
        # TEZ siqish parametrlari
        command = [
            'ffmpeg',
            '-i', input_file,
            '-vf', 'scale=-2:720',
            '-vcodec', 'libx264',
            '-b:v', f'{video_bitrate}k',
            '-maxrate', f'{int(video_bitrate * 1.3)}k',
            '-bufsize', f'{int(video_bitrate * 2)}k',
            '-preset', 'veryfast',
            '-tune', 'fastdecode',
            '-threads', '0',
            '-crf', '28',
            '-acodec', 'aac',
            '-b:a', f'{audio_bitrate}k',
            '-movflags', '+faststart',
            '-y',
            output_file
        ]
        
        # Asinxron FFmpeg ishga tushirish
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Process tugashini kutish
        await process.wait()
        
        if process.returncode != 0:
            stderr = await process.stderr.read()
            logger.error(f"FFmpeg xato: {stderr.decode()}")
            return False
        
        # Natija hajmini tekshirish
        output_size = os.path.getsize(output_file)
        logger.info(f"Siqilgan hajm: {output_size / (1024*1024):.2f} MB")
        
        if output_size > 50 * 1024 * 1024:
            logger.info("Hali katta, 480p superfast...")
            command_low = [
                'ffmpeg',
                '-i', input_file,
                '-vf', 'scale=-2:480',
                '-vcodec', 'libx264',
                '-b:v', f'{int(video_bitrate * 0.7)}k',
                '-preset', 'superfast',
                '-tune', 'fastdecode',
                '-threads', '0',
                '-crf', '30',
                '-acodec', 'aac',
                '-b:a', '64k',
                '-movflags', '+faststart',
                '-y',
                output_file
            ]
            
            process2 = await asyncio.create_subprocess_exec(
                *command_low,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process2.wait()
        
        return True
    except Exception as e:
        logger.error(f"Siqishda xato: {e}")
        return False


def fayl_hajmi_format(size_bytes: int) -> str:
    """Fayl hajmini MB formatida qaytarish"""
    return f"{size_bytes / (1024 * 1024):.2f} MB"


@dp.message(Command("start"))
async def start_handler(message: Message):
    """Start buyrug'i"""
    await message.answer(
        "🎥 <b>YouTube Видео Загрузчик</b>\n\n"
        "Отправьте мне ссылку на YouTube видео, и я скачаю его, "
        "сожму размер файла и отправлю вам!\n\n"
        "Например: https://www.youtube.com/watch?v=xxxxx",
        parse_mode="HTML"
    )


@dp.message(F.text)
async def video_handler(message: Message):
    """YouTube link qabul qilish va video qayta ishlash"""
    url = message.text.strip()
    
    # URL tekshirish
    if not ("youtube.com" in url or "youtu.be" in url):
        await message.answer("❌ Пожалуйста, отправьте правильную ссылку на YouTube!")
        return
    
    status_msg = await message.answer("⏳ Загрузка видео...")
    
    try:
        # Fayl nomlari
        video_id = url.split('=')[-1].split('&')[0]
        original_file = f"downloads/{video_id}_original.mp4"
        compressed_file = f"compressed/{video_id}_compressed.mp4"
        
        # 1. Video yuklash - har 15 soniyada status yangilash
        download_task = asyncio.create_task(video_yuklash_async(url, original_file))
        
        last_update = asyncio.get_event_loop().time()
        while not download_task.done():
            await asyncio.sleep(5)
            current_time = asyncio.get_event_loop().time()
            
            if current_time - last_update >= 15:
                try:
                    await status_msg.edit_text("📥 Загрузка видео... (Пожалуйста, подождите)")
                    last_update = current_time
                except Exception:
                    pass
        
        result = await download_task
        
        if not result['success']:
            await status_msg.edit_text(f"❌ Ошибка загрузки: {result.get('error', 'Неизвестная ошибка')}")
            return
        
        # Original fayl hajmi
        original_size = os.path.getsize(original_file)
        
        # Telegram 50MB limit tekshirish
        await status_msg.edit_text("🗜 Сжатие видео до 50 МБ...")
        
        # 2. Video siqish - har 30 soniyada status yangilash
        compress_task = asyncio.create_task(video_siqish_async(original_file, compressed_file))
        
        # Progress ko'rsatish
        last_update = asyncio.get_event_loop().time()
        while not compress_task.done():
            await asyncio.sleep(5)
            current_time = asyncio.get_event_loop().time()
            
            # Har 30 soniyada xabar yangilash (Telegram spam oldini olish)
            if current_time - last_update >= 30:
                try:
                    await status_msg.edit_text("🗜 Siqilmoqda... (Bu biroz vaqt olishi mumkin)")
                    last_update = current_time
                except Exception:
                    pass  # Agar edit ishlamasa, davom ettir
        
        # Natijani olish
        success = await compress_task
        
        if not success:
            await status_msg.edit_text("❌ Ошибка при сжатии!")
            return
        
        # Siqilgan fayl hajmi
        compressed_size = os.path.getsize(compressed_file)
        
        # Hajm farqi
        saved_percent = ((original_size - compressed_size) / original_size) * 100
        
        # 3. Videoni yuborish
        await status_msg.edit_text("📤 Отправка видео...")
        
        caption = (
            f"<b>{result['title']}</b>\n\n"
            f"📊 Оригинальный размер: {fayl_hajmi_format(original_size)}\n"
            f"🗜 Сжатый размер: {fayl_hajmi_format(compressed_size)}\n"
            f"💾 Сэкономлено: {saved_percent:.1f}%"
        )
        
        with open(compressed_file, 'rb') as video:
            await message.answer_video(
                video=video,
                caption=caption,
                parse_mode="HTML"
            )
        
        await status_msg.delete()
        
        # Fayllarni o'chirish
        try:
            os.remove(original_file)
            os.remove(compressed_file)
        except:
            pass
            
    except Exception as e:
        logger.error(f"Xato: {e}")
        await status_msg.edit_text(f"❌ Произошла ошибка: {str(e)}")


async def main():
    """Botni ishga tushirish"""
    logger.info("Bot ishga tushdi...")
    # Timeout oshirildi - uzoq jarayonlar uchun
    await dp.start_polling(bot, polling_timeout=60)


if __name__ == "__main__":
    asyncio.run(main())
