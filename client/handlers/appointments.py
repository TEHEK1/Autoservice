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

# Создаем роутер для записей
router = Router()

# Состояния для создания записи
class AppointmentState(StatesGroup):
    waiting_for_service = State()
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_confirmation = State()

# Callback данные для записей
class AppointmentCallback(CallbackData, prefix="appointment"):
    action: str
    value: Optional[str] = None

# Рабочие часы сервиса (можно вынести в конфиг)
WORKING_HOURS = {
    "start": 9,  # 9:00
    "end": 18,   # 18:00
    "slot_duration": 60  # длительность слота в минутах
}

# Дни недели, когда сервис работает (0 = понедельник, 6 = воскресенье)
WORKING_DAYS = [0, 1, 2, 3, 4, 5]  # с понедельника по субботу

@router.message(Command("create_appointment"))
async def command_create_appointment(message: Message, state: FSMContext):
    """Начало процесса создания записи через команду"""
    try:
        # Получаем список доступных услуг
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/services")
            response.raise_for_status()
            services = response.json()
            
            # Создаем клавиатуру с услугами
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"{service['name']} - {service['price']}₽",
                    callback_data=AppointmentCallback(action="select_service", value=str(service['id'])).pack()
                )] for service in services
            ])
            
            # Добавляем кнопку возврата в главное меню
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")
            ])
            
            await message.answer(
                "Выберите услугу:",
                reply_markup=keyboard
            )
            
            await state.set_state(AppointmentState.waiting_for_service)
    except Exception as e:
        logger.error(f"Ошибка при получении списка услуг: {e}")
        await message.answer("❌ Произошла ошибка при получении списка услуг. Пожалуйста, попробуйте позже.")

@router.callback_query(lambda c: c.data == "create_appointment")
async def create_appointment(callback: CallbackQuery, state: FSMContext):
    """Начало процесса создания записи"""
    try:
        # Получаем список доступных услуг
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/services")
            response.raise_for_status()
            services = response.json()
            
            # Создаем клавиатуру с услугами
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"{service['name']} - {service['price']}₽",
                    callback_data=AppointmentCallback(action="select_service", value=str(service['id'])).pack()
                )] for service in services
            ])
            
            # Добавляем кнопку возврата в главное меню
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")
            ])
            
            await callback.message.edit_text(
                "Выберите услугу:",
                reply_markup=keyboard
            )
            
            await state.set_state(AppointmentState.waiting_for_service)
            await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при получении списка услуг: {e}")
        await callback.message.answer("❌ Произошла ошибка при получении списка услуг. Пожалуйста, попробуйте позже.")
        await callback.answer()

@router.callback_query(AppointmentCallback.filter(F.action == "select_service"))
async def select_service(callback: CallbackQuery, state: FSMContext, callback_data: AppointmentCallback):
    """Обработка выбора услуги"""
    service_id = callback_data.value
    await state.update_data(service_id=service_id)
    
    # Получаем информацию об услуге
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/services/{service_id}")
            response.raise_for_status()
            service = response.json()
            
            # Создаем клавиатуру с датами (следующие 14 дней)
            keyboard = InlineKeyboardMarkup(inline_keyboard=[])
            current_date = datetime.now()
            
            # Добавляем даты на следующие 14 дней
            for i in range(14):
                date = current_date + timedelta(days=i)
                # Проверяем, является ли день рабочим
                if date.weekday() in WORKING_DAYS:
                    date_str = date.strftime("%d.%m.%Y")
                    keyboard.inline_keyboard.append([
                        InlineKeyboardButton(
                            text=date_str,
                            callback_data=AppointmentCallback(action="select_date", value=date_str).pack()
                        )
                    ])
            
            # Добавляем кнопку возврата
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text="◀️ Назад", callback_data="create_appointment")
            ])
            
            await callback.message.edit_text(
                f"Выбрана услуга: {service['name']}\n"
                f"Выберите дату:",
                reply_markup=keyboard
            )
            
            await state.set_state(AppointmentState.waiting_for_date)
            await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при получении информации об услуге: {e}")
        await callback.message.answer("❌ Произошла ошибка. Пожалуйста, попробуйте позже.")
        await callback.answer()

@router.callback_query(AppointmentCallback.filter(F.action == "select_date"))
async def select_date(callback: CallbackQuery, state: FSMContext, callback_data: AppointmentCallback):
    """Обработка выбора даты"""
    selected_date = callback_data.value
    await state.update_data(date=selected_date)
    
    # Получаем занятые слоты на выбранную дату
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/appointments")
            response.raise_for_status()
            appointments = response.json()
            
            # Фильтруем записи на выбранную дату
            date_obj = datetime.strptime(selected_date, "%d.%m.%Y")
            booked_slots = []
            for appointment in appointments:
                appointment_date = datetime.fromisoformat(appointment['scheduled_time'].replace('Z', '+00:00'))
                if appointment_date.date() == date_obj.date():
                    booked_slots.append(appointment_date.hour)
            
            # Создаем клавиатуру со свободными слотами
            keyboard = InlineKeyboardMarkup(inline_keyboard=[])
            
            # Генерируем слоты с учетом рабочего времени
            for hour in range(WORKING_HOURS["start"], WORKING_HOURS["end"]):
                if hour not in booked_slots:
                    time_str = f"{hour:02d}.00"
                    keyboard.inline_keyboard.append([
                        InlineKeyboardButton(
                            text=f"{hour:02d}:00",
                            callback_data=AppointmentCallback(action="select_time", value=time_str).pack()
                        )
                    ])
            
            # Добавляем кнопку возврата
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text="◀️ Назад", callback_data="create_appointment")
            ])
            
            await callback.message.edit_text(
                f"Выбрана дата: {selected_date}\n"
                f"Выберите время:",
                reply_markup=keyboard
            )
            
            await state.set_state(AppointmentState.waiting_for_time)
            await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при получении занятых слотов: {e}")
        await callback.message.answer("❌ Произошла ошибка. Пожалуйста, попробуйте позже.")
        await callback.answer()

@router.callback_query(AppointmentCallback.filter(F.action == "select_time"))
async def select_time(callback: CallbackQuery, state: FSMContext, callback_data: AppointmentCallback):
    """Обработка выбора времени"""
    selected_time = callback_data.value.replace(".", ":")
    user_data = await state.get_data()
    
    # Формируем дату и время для записи
    date_obj = datetime.strptime(user_data['date'], "%d.%m.%Y")
    hour, minute = map(int, selected_time.split(':'))
    scheduled_time = date_obj.replace(hour=hour, minute=minute)
    
    # Получаем информацию об услуге
    try:
        async with httpx.AsyncClient() as client:
            service_response = await client.get(f"{API_URL}/services/{user_data['service_id']}")
            service_response.raise_for_status()
            service = service_response.json()
            
            # Получаем информацию о клиенте
            client_response = await client.get(
                f"{API_URL}/clients/search",
                params={"telegram_id": str(callback.from_user.id)}
            )
            client_response.raise_for_status()
            client = client_response.json()
            
            if not client:
                await callback.message.answer("❌ Ошибка: клиент не найден. Пожалуйста, зарегистрируйтесь.")
                await state.clear()
                return
            
            # Создаем клавиатуру для подтверждения
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Подтвердить", callback_data=AppointmentCallback(action="confirm", value="yes").pack()),
                    InlineKeyboardButton(text="❌ Отменить", callback_data=AppointmentCallback(action="confirm", value="no").pack())
                ]
            ])
            
            await callback.message.edit_text(
                f"Проверьте данные записи:\n\n"
                f"Услуга: {service['name']}\n"
                f"Дата: {user_data['date']}\n"
                f"Время: {selected_time}\n"
                f"Стоимость: {service['price']}₽\n\n"
                f"Подтвердить запись?",
                reply_markup=keyboard
            )
            
            # Сохраняем данные для создания записи
            await state.update_data(
                scheduled_time=scheduled_time.isoformat(),
                client_id=client['id'],
                service_name=service['name'],
                service_price=service['price']
            )
            
            await state.set_state(AppointmentState.waiting_for_confirmation)
            await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при подготовке подтверждения: {e}")
        await callback.message.answer("❌ Произошла ошибка. Пожалуйста, попробуйте позже.")
        await callback.answer()

@router.callback_query(AppointmentCallback.filter(F.action == "confirm"))
async def confirm_appointment(callback: CallbackQuery, state: FSMContext, callback_data: AppointmentCallback):
    """Обработка подтверждения записи"""
    if callback_data.value == "no":
        await callback.message.edit_text("Запись отменена.")
        await state.clear()
        await callback.answer()
        return
    
    user_data = await state.get_data()
    
    try:
        # Создаем запись
        async with httpx.AsyncClient() as client:
            appointment_data = {
                "client_id": user_data['client_id'],
                "service_id": user_data['service_id'],
                "scheduled_time": user_data['scheduled_time'],
                "status": "pending"
            }
            
            response = await client.post(f"{API_URL}/appointments", json=appointment_data)
            response.raise_for_status()
            
            # Очищаем состояние
            await state.clear()
            
            # Показываем подтверждение
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
            
            await callback.message.edit_text(
                f"✅ Запись успешно создана!\n\n"
                f"Услуга: {user_data['service_name']}\n"
                f"Дата: {user_data['date']}\n"
                f"Время: {user_data['scheduled_time'].split('T')[1][:5]}\n"
                f"Стоимость: {user_data['service_price']}₽\n\n"
                f"Мы ждем вас в указанное время!",
                reply_markup=keyboard
            )
            await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при создании записи: {e}")
        await callback.message.edit_text("❌ Произошла ошибка при создании записи. Пожалуйста, попробуйте позже.")
        await state.clear()
        await callback.answer()

@router.callback_query(lambda c: c.data == "my_appointments")
async def show_my_appointments(callback: CallbackQuery):
    """Показ записей клиента"""
    try:
        # Получаем список записей
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
            
            # Получаем записи клиента
            appointments_response = await client.get(f"{API_URL}/appointments")
            appointments_response.raise_for_status()
            all_appointments = appointments_response.json()
            
            # Фильтруем записи текущего клиента
            client_appointments = [a for a in all_appointments if a['client_id'] == current_client['id']]
            
            if not client_appointments:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Записаться на услугу", callback_data="create_appointment")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ])
                
                await callback.message.edit_text(
                    "У вас пока нет записей.\n"
                    "Хотите записаться на услугу?",
                    reply_markup=keyboard
                )
                return
            
            # Сортируем записи по дате
            client_appointments.sort(key=lambda x: datetime.fromisoformat(x['scheduled_time'].replace('Z', '+00:00')))
            
            # Получаем информацию об услугах
            services_response = await client.get(f"{API_URL}/services")
            services_response.raise_for_status()
            services = {s['id']: s for s in services_response.json()}
            
            # Формируем сообщение с записями
            message_text = "📅 Ваши записи:\n\n"
            
            for appointment in client_appointments:
                service = services[appointment['service_id']]
                appointment_time = datetime.fromisoformat(appointment['scheduled_time'].replace('Z', '+00:00'))
                
                message_text += (
                    f"🔹 {appointment_time.strftime('%d.%m.%Y %H:%M')}\n"
                    f"   Услуга: {service['name']}\n"
                    f"   Статус: {appointment['status']}\n"
                    f"   Стоимость: {service['price']}₽\n\n"
                )
            
            # Создаем клавиатуру
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Новая запись", callback_data="create_appointment")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
            
            await callback.message.edit_text(message_text, reply_markup=keyboard)
            await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при получении записей: {e}")
        await callback.message.edit_text("❌ Произошла ошибка при получении записей. Пожалуйста, попробуйте позже.")
        await callback.answer() 