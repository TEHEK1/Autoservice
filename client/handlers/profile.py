from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
import httpx
import logging
from ..config import API_URL

logger = logging.getLogger(__name__)

# Создаем роутер для профиля
router = Router()

# Состояния для редактирования профиля
class EditProfileState(StatesGroup):
    waiting_for_phone = State()
    waiting_for_name = State()
    waiting_for_timezone = State()

@router.message(Command("profile"))
async def command_profile(message: Message):
    """Показ настроек профиля"""
    try:
        async with httpx.AsyncClient() as client:
            # Получаем клиента по telegram_id
            client_response = await client.get(
                f"{API_URL}/clients/search",
                params={"telegram_id": str(message.from_user.id)}
            )
            client_response.raise_for_status()
            current_client = client_response.json()
            
            if not current_client:
                await message.answer("❌ Ошибка: клиент не найден. Пожалуйста, зарегистрируйтесь.")
                return
            
            # Создаем клавиатуру с настройками
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📱 Телефон", callback_data="edit_phone")],
                [InlineKeyboardButton(text="📝 Имя", callback_data="edit_name")],
                [InlineKeyboardButton(text="🌍 Часовой пояс", callback_data="edit_timezone")],
                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu")]
            ])
            
            await message.answer(
                f"👤 Настройки профиля\n\n"
                f"Имя: {current_client['name']}\n"
                f"Телефон: {current_client['phone_number']}\n"
                f"Часовой пояс: {current_client.get('timezone', 'Не указан')}\n"
                f"Telegram ID: {current_client.get('telegram_id', 'Не указан')}\n\n"
                f"Выберите настройку для изменения:",
                reply_markup=keyboard
            )
            
    except Exception as e:
        logger.error(f"Ошибка при получении настроек профиля: {e}")
        await message.answer("❌ Произошла ошибка при получении настроек профиля")

@router.callback_query(F.data == "edit_phone")
async def edit_phone(callback: CallbackQuery, state: FSMContext):
    """Начало изменения телефона"""
    await callback.message.edit_text("Введите новый номер телефона:")
    await state.set_state(EditProfileState.waiting_for_phone)
    await callback.answer()

@router.message(EditProfileState.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    """Обработка ввода нового телефона"""
    try:
        async with httpx.AsyncClient() as client:
            # Получаем клиента по telegram_id
            client_response = await client.get(
                f"{API_URL}/clients/search",
                params={"telegram_id": str(message.from_user.id)}
            )
            client_response.raise_for_status()
            current_client = client_response.json()
            
            if not current_client:
                await message.answer("❌ Ошибка: клиент не найден. Пожалуйста, зарегистрируйтесь.")
                return
            
            # Обновляем телефон
            response = await client.patch(
                f"{API_URL}/clients/{current_client['id']}",
                json={"phone_number": message.text}
            )
            response.raise_for_status()
            
            # Очищаем состояние
            await state.clear()
            
            # Показываем обновленные настройки
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📱 Телефон", callback_data="edit_phone")],
                [InlineKeyboardButton(text="📝 Имя", callback_data="edit_name")],
                [InlineKeyboardButton(text="🌍 Часовой пояс", callback_data="edit_timezone")],
                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu")]
            ])
            
            await message.answer(
                f"✅ Телефон успешно обновлен!\n\n"
                f"Имя: {current_client['name']}\n"
                f"Телефон: {message.text}\n"
                f"Часовой пояс: {current_client.get('timezone', 'Не указан')}\n"
                f"Telegram ID: {current_client.get('telegram_id', 'Не указан')}\n\n"
                f"Выберите настройку для изменения:",
                reply_markup=keyboard
            )
            
    except Exception as e:
        logger.error(f"Ошибка при обновлении телефона: {e}")
        await message.answer("❌ Произошла ошибка при обновлении телефона")
        await state.clear()

@router.callback_query(F.data == "edit_name")
async def edit_name(callback: CallbackQuery, state: FSMContext):
    """Начало изменения имени"""
    await callback.message.edit_text("Введите новое имя:")
    await state.set_state(EditProfileState.waiting_for_name)
    await callback.answer()

@router.message(EditProfileState.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    """Обработка ввода нового имени"""
    try:
        async with httpx.AsyncClient() as client:
            # Получаем клиента по telegram_id
            client_response = await client.get(
                f"{API_URL}/clients/search",
                params={"telegram_id": str(message.from_user.id)}
            )
            client_response.raise_for_status()
            current_client = client_response.json()
            
            if not current_client:
                await message.answer("❌ Ошибка: клиент не найден. Пожалуйста, зарегистрируйтесь.")
                return
            
            # Обновляем имя
            response = await client.patch(
                f"{API_URL}/clients/{current_client['id']}",
                json={"name": message.text}
            )
            response.raise_for_status()
            
            # Очищаем состояние
            await state.clear()
            
            # Показываем обновленные настройки
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📱 Телефон", callback_data="edit_phone")],
                [InlineKeyboardButton(text="📝 Имя", callback_data="edit_name")],
                [InlineKeyboardButton(text="🌍 Часовой пояс", callback_data="edit_timezone")],
                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu")]
            ])
            
            await message.answer(
                f"✅ Имя успешно обновлено!\n\n"
                f"Имя: {message.text}\n"
                f"Телефон: {current_client['phone_number']}\n"
                f"Часовой пояс: {current_client.get('timezone', 'Не указан')}\n"
                f"Telegram ID: {current_client.get('telegram_id', 'Не указан')}\n\n"
                f"Выберите настройку для изменения:",
                reply_markup=keyboard
            )
            
    except Exception as e:
        logger.error(f"Ошибка при обновлении имени: {e}")
        await message.answer("❌ Произошла ошибка при обновлении имени")
        await state.clear()

@router.callback_query(F.data == "edit_timezone")
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
                    callback_data=f"set_timezone_{tz}"
                )
            ])
        
        buttons.append([
            InlineKeyboardButton(text="◀️ Назад", callback_data="profile")
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await callback.message.edit_text("🌍 Выберите часовой пояс:", reply_markup=keyboard)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при выборе часового пояса: {e}")
        await callback.message.answer("❌ Произошла ошибка при выборе часового пояса")

@router.callback_query(F.data.startswith("set_timezone_"))
async def process_timezone_setting(callback: CallbackQuery):
    """Обработка установки часового пояса"""
    try:
        # Получаем выбранный часовой пояс
        timezone = callback.data.split("_")[-1]
        
        # Обновляем часовой пояс клиента
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{API_URL}/clients",
                params={"telegram_id": callback.from_user.id},
                json={"timezone": timezone}
            )
            response.raise_for_status()
            
            await callback.message.edit_text(f"✅ Часовой пояс установлен: {timezone}")
            await callback.answer()
            
            # Возвращаемся к профилю
            await show_profile(callback)
            
    except Exception as e:
        logger.error(f"Ошибка при установке часового пояса: {e}")
        await callback.message.answer("❌ Произошла ошибка при установке часового пояса")

@router.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery):
    """Показ настроек профиля"""
    try:
        async with httpx.AsyncClient() as client:
            # Получаем клиента по telegram_id
            client_response = await client.get(
                f"{API_URL}/clients/search",
                params={"telegram_id": str(callback.from_user.id)}
            )
            client_response.raise_for_status()
            current_client = client_response.json()
            
            if not current_client:
                await callback.message.edit_text("❌ Ошибка: клиент не найден. Пожалуйста, зарегистрируйтесь.")
                return
            
            # Создаем клавиатуру с настройками
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📱 Телефон", callback_data="edit_phone")],
                [InlineKeyboardButton(text="📝 Имя", callback_data="edit_name")],
                [InlineKeyboardButton(text="🌍 Часовой пояс", callback_data="edit_timezone")],
                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu")]
            ])
            
            await callback.message.edit_text(
                f"�� Настройки профиля\n\n"
                f"Имя: {current_client['name']}\n"
                f"Телефон: {current_client['phone_number']}\n"
                f"Часовой пояс: {current_client.get('timezone', 'Не указан')}\n"
                f"Telegram ID: {current_client.get('telegram_id', 'Не указан')}\n\n"
                f"Выберите настройку для изменения:",
                reply_markup=keyboard
            )
            await callback.answer()
            
    except Exception as e:
        logger.error(f"Ошибка при получении настроек профиля: {e}")
        await callback.message.edit_text("❌ Произошла ошибка при получении настроек профиля")
        await callback.answer() 