from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
import logging
from .config import TOKEN
from .services.notification_handler import NotificationHandler

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Регистрация всех роутеров
from .handlers import main_menu, registration, appointments, profile, messages
dp.include_router(main_menu.router)
dp.include_router(profile.router)
dp.include_router(registration.router)
dp.include_router(appointments.router)
dp.include_router(messages.router)

async def main():
    """Запуск бота"""
    logger.info("Starting bot...")
    
    # Запуск обработчика уведомлений
    notification_handler = NotificationHandler(bot)
    notification_task = asyncio.create_task(notification_handler.start_listening())
    
    try:
        await dp.start_polling(bot)
    finally:
        # Останавливаем обработчик уведомлений
        notification_task.cancel()
        try:
            await notification_task
        except asyncio.CancelledError:
            pass
        await notification_handler.stop()

if __name__ == "__main__":
    asyncio.run(main())
