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
from .handlers import main_menu, appointments, clients, services, messages
dp.include_router(main_menu.router)
dp.include_router(appointments.router)
dp.include_router(clients.router)
dp.include_router(services.router)
dp.include_router(messages.router)

async def main():
    """Запуск бота"""
    logger.info("Starting bot...")
    
    # Запуск обработчика уведомлений
    from .services.notification_handler import NotificationHandler
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
