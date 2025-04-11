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

# Создаем общий роутер для главного меню
main_router = Router()

@main_router.callback_query(lambda c: c.data == "main_menu")
async def main_menu(callback: types.CallbackQuery):
    """Возврат в главное меню"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Мои записи", callback_data="my_appointments")],
        [InlineKeyboardButton(text="➕ Записаться на услугу", callback_data="create_appointment")]
    ])
    await callback.message.edit_text("🏠 Главное меню", reply_markup=keyboard)
    await callback.answer()

# Регистрация всех роутеров
dp.include_router(main_router)

# Импортируем и регистрируем остальные роутеры после создания основного
from .handlers import registration, appointments
dp.include_router(registration.router)
dp.include_router(appointments.router)

async def main():
    """Запуск бота"""
    logger.info("Starting bot...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
