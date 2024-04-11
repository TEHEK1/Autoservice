from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters.callback_data import CallbackData
import httpx
import logging
from datetime import datetime, timedelta
import calendar
from typing import List, Dict, Optional

from aiogram.fsm.state import StatesGroup, State

from ..config import API_URL

logger = logging.getLogger(__name__)

# Создаем роутер для регистрации клиентов
router = Router()

# Состояния для регистрации клиентов
class ClientRegistrationState(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_car = State()

# Callback данные для регистрации
class RegistrationCallback(CallbackData, prefix="registration"):
    action: str

@router.message(Command("start"))
async def command_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    try:
        # Проверяем, есть ли пользователь в базе данных
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_URL}/clients/search",
                params={"telegram_id": message.from_user.id}
            )
            
            if response.status_code == 200:
                # Пользователь уже зарегистрирован
                client_data = response.json()
                await message.answer(
                    f"Добро пожаловать, {client_data['name']}!\n"
                    f"Ваш номер телефона: {client_data['phone_number']}\n\n"
                    "Выберите действие:",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📝 Записаться", callback_data="create_appointment")],
                        [InlineKeyboardButton(text="📋 Мои записи", callback_data="my_appointments")]
                    ])
                )
                return
            
            # Если пользователь не найден, начинаем регистрацию
            await message.answer("Добро пожаловать! Для начала работы нужно зарегистрироваться.\nВведите ваше имя:")
            await state.set_state(ClientRegistrationState.waiting_for_name)
            
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            # Пользователь не найден, начинаем регистрацию
            await message.answer("Добро пожаловать! Для начала работы нужно зарегистрироваться.\nВведите ваше имя:")
            await state.set_state(ClientRegistrationState.waiting_for_name)
        else:
            logger.error(f"Ошибка при проверке регистрации клиента: {e}")
            await message.answer("❌ Произошла ошибка при проверке регистрации. Пожалуйста, попробуйте позже.")
    except Exception as e:
        logger.error(f"Ошибка при проверке регистрации клиента: {e}")
        await message.answer("❌ Произошла ошибка при проверке регистрации. Пожалуйста, попробуйте позже.")

@router.message(ClientRegistrationState.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    """Обработка ввода имени"""
    await state.update_data(name=message.text)
    
    # Предлагаем ввести номер телефона или поделиться контактом
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Поделиться контактом", callback_data="share_contact")]
    ])
    
    await message.answer(
        "Теперь введите ваш номер телефона или поделитесь контактом:",
        reply_markup=keyboard
    )
    await state.set_state(ClientRegistrationState.waiting_for_phone)

@router.callback_query(lambda c: c.data == "share_contact")
async def process_share_contact(callback: CallbackQuery, state: FSMContext):
    """Обработка запроса на поделиться контактом"""
    # Создаем обычную клавиатуру вместо инлайн-клавиатуры
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="📱 Поделиться контактом", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await callback.message.answer(
        "Пожалуйста, поделитесь вашим контактом:",
        reply_markup=keyboard
    )
    await callback.answer()

@router.message(ClientRegistrationState.waiting_for_phone, F.contact)
async def process_contact(message: Message, state: FSMContext):
    """Обработка полученного контакта"""
    phone = message.contact.phone_number
    await state.update_data(phone=phone)
    
    await message.answer("Введите модель вашего автомобиля:")
    await state.set_state(ClientRegistrationState.waiting_for_car)

@router.message(ClientRegistrationState.waiting_for_phone, F.text)
async def process_phone(message: Message, state: FSMContext):
    """Обработка ввода номера телефона"""
    phone = message.text
    await state.update_data(phone=phone)
    
    await message.answer("Введите модель вашего автомобиля:")
    await state.set_state(ClientRegistrationState.waiting_for_car)

@router.message(ClientRegistrationState.waiting_for_car)
async def process_car(message: Message, state: FSMContext):
    """Обработка ввода модели автомобиля"""
    car_model = message.text
    user_data = await state.get_data()
    
    try:
        # Регистрируем клиента в API
        async with httpx.AsyncClient() as client:
            client_data = {
                "name": user_data['name'],
                "phone_number": user_data['phone'],
                "car_model": car_model,
                "telegram_id": message.from_user.id
            }
            
            response = await client.post(f"{API_URL}/clients", json=client_data)
            response.raise_for_status()
            
            # Очищаем состояние
            await state.clear()
            
            # Показываем меню клиента
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📅 Мои записи", callback_data="my_appointments")],
                [InlineKeyboardButton(text="➕ Записаться на услугу", callback_data="create_appointment")]
            ])
            
            await message.answer(
                f"Регистрация успешно завершена, {user_data['name']}!\n\n"
                f"Выберите действие:",
                reply_markup=keyboard
            )
    except Exception as e:
        logger.error(f"Ошибка при регистрации клиента: {e}")
        await message.answer("❌ Произошла ошибка при регистрации. Пожалуйста, попробуйте позже.")
        await state.clear() 