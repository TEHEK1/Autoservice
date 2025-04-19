from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import logging

logger = logging.getLogger(__name__)

# Создаем роутер для главного меню
router = Router()

# Клавиатура главного меню
keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📝 Мои записи", callback_data="my_appointments")],
    [InlineKeyboardButton(text="➕ Создать запись", callback_data="create_appointment")],
    [InlineKeyboardButton(text="⚙️ Настройки", callback_data="profile")],
    [InlineKeyboardButton(text="📧 Сообщения", callback_data="messages")],
    [InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
])

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
        "📝 Мои записи - просмотр ваших записей на услуги\n"
        "➕ Создать запись - записаться на новую услугу\n"
        "⚙️ Настройки - изменение данных профиля\n\n"
        "Для начала работы используйте команду /start\n"
        "Для просмотра записей используйте команду /appointments"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(help_text, reply_markup=keyboard)
    await callback.answer() 