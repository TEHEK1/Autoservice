from aiogram import Bot, Dispatcher
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
from .handlers import main_menu, appointments, clients, services
dp.include_router(main_menu.router)
dp.include_router(appointments.router)
dp.include_router(clients.router)
dp.include_router(services.router)

async def main():
    """Запуск бота"""
    logger.info("Starting bot...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
