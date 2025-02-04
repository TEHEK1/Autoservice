import logging
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.types import ContentType
from aiogram.utils import executor
from server.database import get_user, create_user
from config.settings import settings

# Логирование
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher(bot)

# Стартовое сообщение
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer("Добро пожаловать в наш автосервис! Напишите /services для выбора услуги.")

# Обработка команды /services
@dp.message_handler(commands=["services"])
async def list_services(message: types.Message):
    await message.answer(
        "Выберите услугу:",
        parse_mode=ParseMode.MARKDOWN,
    )

# Обработка обычных сообщений
@dp.message_handler(content_types=ContentType.TEXT)
async def handle_text(message: types.Message):
    pass

# Запуск бота
async def on_startup(dp):
    logging.info("Starting bot...")

if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_startup)
