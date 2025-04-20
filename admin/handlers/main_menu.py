from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import logging

from ..middleware.auth_middleware import authorized_users
from .auth import AuthState

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
    [InlineKeyboardButton(text="👤 Профиль", callback_data="admin_profile")],
    [InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
])

@router.message(Command("start"))
async def command_start(message: Message, state: FSMContext):
    """Главное меню при запуске бота"""
    user_id = message.from_user.id
    logger.info(f"Команда /start от пользователя {user_id}")
    
    # Проверяем, авторизован ли пользователь
    if user_id not in authorized_users:
        logger.info(f"Пользователь {user_id} не авторизован, запрашиваем пароль")
        # Запрашиваем пароль
        await message.answer("🔒 Добро пожаловать в панель администратора!\n\nДля доступа введите пароль:")
        # Устанавливаем состояние ожидания пароля
        await state.set_state(AuthState.waiting_for_password)
        return
    
    # Если пользователь авторизован, показываем главное меню
    logger.info(f"Пользователь {user_id} авторизован, показываем меню")
    await message.answer(
        "👋 Добро пожаловать в панель администратора!\n\n"
        "Выберите раздел:",
        reply_markup=keyboard
    )

@router.callback_query(lambda c: c.data == "main_menu")
async def main_menu(callback: CallbackQuery):
    """Обработчик для возврата в главное меню"""
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

@router.callback_query(F.data == "admin_profile")
async def profile_menu(callback: CallbackQuery):
    """Обработчик для перехода в меню профиля"""
    from .profile import show_profile
    await show_profile(callback)
    await callback.answer() 