from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import logging

logger = logging.getLogger(__name__)

# Создаем роутер для главного меню
router = Router()

# Клавиатура главного меню
keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📝 Записи", callback_data="appointments")],
    [InlineKeyboardButton(text="👥 Клиенты", callback_data="clients")],
    [InlineKeyboardButton(text="🔧 Услуги", callback_data="services")],
    [InlineKeyboardButton(text="📅 Управление слотами", callback_data="time_slots")],
    [InlineKeyboardButton(text="💬 Сообщения", callback_data="messages")],
    [InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
])

@router.message(Command("start"))
async def command_start(message: Message):
    """Главное меню при запуске бота"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Записи", callback_data="appointments")],
        [InlineKeyboardButton(text="👥 Клиенты", callback_data="clients")],
        [InlineKeyboardButton(text="🔧 Услуги", callback_data="services")],
        [InlineKeyboardButton(text="📅 Управление слотами", callback_data="time_slots")],
        [InlineKeyboardButton(text="💬 Сообщения", callback_data="messages")]
    ])
    
    await message.answer(
        "👋 Добро пожаловать в панель администратора!\n\n"
        "Выберите раздел:",
        reply_markup=keyboard
    )

@router.callback_query(lambda c: c.data == "main_menu")
async def main_menu(callback: CallbackQuery):
    """Обработчик для возврата в главное меню"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Записи", callback_data="appointments")],
        [InlineKeyboardButton(text="👥 Клиенты", callback_data="clients")],
        [InlineKeyboardButton(text="🔧 Услуги", callback_data="services")],
        [InlineKeyboardButton(text="📅 Управление слотами", callback_data="time_slots")],
        [InlineKeyboardButton(text="💬 Сообщения", callback_data="messages")]
    ])
    
    await callback.message.answer(
        "👋 Главное меню\n\n"
        "Выберите раздел:",
        reply_markup=keyboard
    )
    
    await callback.answer()

@router.callback_query(F.data == "help")
async def show_help(callback: CallbackQuery):
    """Показ справки"""
    help_text = (
        "📚 Справка по использованию бота:\n\n"
        "📝 Записи - управление записями клиентов\n"
        "👥 Клиенты - управление клиентами\n"
        "🔧 Услуги - управление услугами\n\n"
        "Для начала работы используйте команду /start"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(help_text, reply_markup=keyboard)
    await callback.answer() 