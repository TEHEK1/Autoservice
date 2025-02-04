import logging
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.types import ContentType
from aiogram.utils import executor
from server.database import get_all_services, add_service
from config.settings import settings

# Логирование
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=settings.ADMIN_BOT_TOKEN)
dp = Dispatcher(bot)

# Стартовое сообщение
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer("Добро пожаловать в панель администратора! Используйте /add_service для добавления услуги.")

# Добавление услуги
@dp.message_handler(commands=["add_service"])
async def add_service_handler(message: types.Message):
    args = message.get_args().split(" ", 1)
    if len(args) == 2:
        service_name, service_price = args
        # Добавление услуги в базу данных
        add_service(service_name, service_price)
        await message.answer(f"Услуга '{service_name}' успешно добавлена.")
    else:
        await message.answer("Для добавления услуги используйте команду: /add_service <название> <цена>.")

# Запуск бота
async def on_startup(dp):
    logging.info("Starting admin bot...")

if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_startup)
