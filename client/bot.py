from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
import logging
from .config import TOKEN

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Регистрация всех роутеров
from .handlers import main_menu, registration, appointments, profile
dp.include_router(main_menu.router)
dp.include_router(profile.router)
dp.include_router(registration.router)
dp.include_router(appointments.router)

async def main():
    """Запуск бота"""
    logger.info("Starting bot...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
