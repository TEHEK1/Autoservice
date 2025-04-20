from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
import httpx
import logging
from ..config import API_URL
from ..middleware.auth_middleware import authorized_users

logger = logging.getLogger(__name__)

# Создаем роутер для профиля
router = Router()

# Часовой пояс администратора (по умолчанию)
ADMIN_TIMEZONE = "Europe/Moscow"

# Состояния для редактирования профиля
class EditProfileState(StatesGroup):
    waiting_for_timezone = State()

@router.message(Command("profile"))
async def command_profile(message: Message):
    """Показ настроек профиля администратора"""
    try:
        user_id = message.from_user.id
        
        # Проверяем, авторизован ли пользователь
        if user_id not in authorized_users:
            await message.answer("⚠️ Вы не авторизованы. Используйте команду /start для входа в систему.")
            return
            
        # Создаем клавиатуру с настройками
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌍 Часовой пояс", callback_data="admin_edit_timezone")],
            [InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu")]
        ])
        
        # Получаем текущий часовой пояс администратора
        timezone = authorized_users.get(user_id, {}).get('timezone', ADMIN_TIMEZONE)
        
        await message.answer(
            f"👤 Настройки профиля администратора\n\n"
            f"Часовой пояс: {timezone}\n"
            f"ID: {user_id}\n\n"
            f"Выберите настройку для изменения:",
            reply_markup=keyboard
        )
            
    except Exception as e:
        logger.error(f"Ошибка при получении настроек профиля: {e}")
        await message.answer("❌ Произошла ошибка при получении настроек профиля")

@router.callback_query(F.data == "admin_edit_timezone")
async def edit_timezone(callback: CallbackQuery, state: FSMContext):
    """Начало изменения часового пояса"""
    try:
        # Получаем список доступных часовых поясов
        timezones = [
            "Europe/Moscow",
            "Europe/Kiev",
            "Europe/Minsk",
            "Asia/Yekaterinburg",
            "Asia/Novosibirsk", 
            "Asia/Vladivostok"
        ]
        
        # Создаем клавиатуру с часовыми поясами
        buttons = []
        for tz in timezones:
            buttons.append([
                InlineKeyboardButton(
                    text=tz,
                    callback_data=f"admin_set_timezone_{tz}"
                )
            ])
        
        buttons.append([
            InlineKeyboardButton(text="◀️ Назад", callback_data="admin_profile")
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await callback.message.edit_text("🌍 Выберите часовой пояс:", reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при выборе часового пояса: {e}")
        await callback.message.answer("❌ Произошла ошибка при выборе часового пояса")

@router.callback_query(F.data.startswith("admin_set_timezone_"))
async def process_timezone_setting(callback: CallbackQuery):
    """Обработка установки часового пояса"""
    try:
        # Получаем выбранный часовой пояс
        timezone = callback.data.split("_")[-1]
        user_id = callback.from_user.id
        
        # Обновляем часовой пояс администратора в словаре авторизованных пользователей
        if user_id in authorized_users:
            if isinstance(authorized_users[user_id], dict):
                authorized_users[user_id]['timezone'] = timezone
            else:
                authorized_users[user_id] = {'timezone': timezone}
        
        await callback.message.edit_text(f"✅ Часовой пояс установлен: {timezone}")
        await callback.answer()
        
        # Возвращаемся к профилю
        await show_profile(callback)
            
    except Exception as e:
        logger.error(f"Ошибка при установке часового пояса: {e}")
        await callback.message.answer("❌ Произошла ошибка при установке часового пояса")

@router.callback_query(F.data == "admin_profile")
async def show_profile(callback: CallbackQuery):
    """Показ настроек профиля администратора"""
    try:
        user_id = callback.from_user.id
        
        # Проверяем, авторизован ли пользователь
        if user_id not in authorized_users:
            await callback.message.edit_text("⚠️ Вы не авторизованы. Используйте команду /start для входа в систему.")
            return
            
        # Создаем клавиатуру с настройками
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌍 Часовой пояс", callback_data="admin_edit_timezone")],
            [InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu")]
        ])
        
        # Получаем текущий часовой пояс администратора
        timezone = authorized_users.get(user_id, {}).get('timezone', ADMIN_TIMEZONE)
        
        await callback.message.edit_text(
            f"👤 Настройки профиля администратора\n\n"
            f"Часовой пояс: {timezone}\n"
            f"ID: {user_id}\n\n"
            f"Выберите настройку для изменения:",
            reply_markup=keyboard
        )
        await callback.answer()
            
    except Exception as e:
        logger.error(f"Ошибка при получении настроек профиля: {e}")
        await callback.message.edit_text("❌ Произошла ошибка при получении настроек профиля")
        await callback.answer()

def get_admin_timezone(user_id: int) -> str:
    """Получение часового пояса администратора по его ID
    
    Args:
        user_id: ID пользователя в Telegram
        
    Returns:
        str: Часовой пояс администратора (например, 'Europe/Moscow')
    """
    if user_id in authorized_users:
        if isinstance(authorized_users[user_id], dict):
            return authorized_users[user_id].get('timezone', ADMIN_TIMEZONE)
    return ADMIN_TIMEZONE 