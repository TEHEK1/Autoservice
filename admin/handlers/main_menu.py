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
    [InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
])

@router.message(Command("start"))
async def command_start(message: Message):
    """Обработчик команды /start"""
    await message.answer(
        "👋 Добро пожаловать в бот автосервиса!\n\n"
        "Выберите действие:",
        reply_markup=keyboard
    )

@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery):
    """Возврат в главное меню"""
    await callback.message.edit_text(
        "👋 Добро пожаловать в бот автосервиса!\n\n"
        "Выберите действие:",
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