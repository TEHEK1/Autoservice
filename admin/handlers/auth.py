from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message
import logging

from ..middleware.auth_middleware import authorized_users, verify_password

logger = logging.getLogger(__name__)

# Создаем роутер для аутентификации
router = Router()

# Состояния для ввода пароля
class AuthState(StatesGroup):
    waiting_for_password = State()

@router.message(AuthState.waiting_for_password)
async def process_password(message: Message, state: FSMContext):
    """Обработка ввода пароля"""
    user_id = message.from_user.id
    password = message.text
    
    logger.info(f"Получен пароль от пользователя {user_id}")
    
    if verify_password(password):
        # Авторизуем пользователя
        authorized_users[user_id] = True
        
        # Сбрасываем состояние
        await state.clear()
        
        # Показываем главное меню
        from .main_menu import keyboard as main_menu_keyboard
        
        await message.answer(
            "✅ Авторизация успешна!\n\n"
            "Добро пожаловать в панель администратора!", 
            reply_markup=main_menu_keyboard
        )
        logger.info(f"Пользователь {user_id} успешно авторизован")
    else:
        # Отправляем сообщение об ошибке
        await message.answer("❌ Неверный пароль. Пожалуйста, введите правильный пароль:")
        # Состояние остается тем же - ожидание пароля
        logger.warning(f"Попытка авторизации с неверным паролем от пользователя {user_id}")

@router.message(Command("logout"))
async def cmd_logout(message: Message):
    """Обработка выхода из системы"""
    user_id = message.from_user.id
    
    if user_id in authorized_users:
        del authorized_users[user_id]
        await message.answer("🔒 Вы вышли из системы. Используйте /start для повторной авторизации.")
        logger.info(f"Пользователь {user_id} вышел из системы")
    else:
        await message.answer("ℹ️ Вы не авторизованы.") 