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
    id: int
    action: str
    value: Optional[str] = None

# Callback данные для выбора услуги
class SelectServiceCallback(CallbackData, prefix="select_service"):
    id: int

# Рабочие часы сервиса (можно вынести в конфиг)
WORKING_HOURS = {
    "start": 9,  # 9:00
    "end": 18,   # 18:00
    "slot_duration": 60  # длительность слота в минутах
}

# Дни недели, когда сервис работает (0 = понедельник, 6 = воскресенье)
WORKING_DAYS = [0, 1, 2, 3, 4, 5]  # с понедельника по субботу

class CreateAppointmentState(StatesGroup):
    waiting_for_car = State()
    waiting_for_service = State()
    waiting_for_date = State()
    waiting_for_time = State()

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
async def process_create_appointment(callback: CallbackQuery, state: FSMContext):
    """Начало создания записи"""
    await callback.message.answer("Введите модель автомобиля:")
    await state.set_state(CreateAppointmentState.waiting_for_car)
    await callback.answer()

@router.message(CreateAppointmentState.waiting_for_car)
async def process_create_car(message: Message, state: FSMContext):
    """Обработка ввода модели автомобиля"""
    await state.update_data(car_model=message.text.strip())
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/services")
            response.raise_for_status()
            services = response.json()
            
            if not services:
                await message.answer("❌ Нет доступных услуг. Пожалуйста, обратитесь к администратору.")
                await state.clear()
                return
            
            buttons = []
            for service in services:
                buttons.append([
                    InlineKeyboardButton(
                        text=f"{service['name']} - {service['price']} руб.",
                        callback_data=SelectServiceCallback(id=service['id']).pack()
                    )
                ])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            await message.answer("Выберите услугу:", reply_markup=keyboard)
            await state.set_state(CreateAppointmentState.waiting_for_service)
            
    except Exception as e:
        logger.error(f"Ошибка при получении списка услуг: {e}")
        await message.answer("❌ Произошла ошибка при получении списка услуг")
        await state.clear()

@router.callback_query(SelectServiceCallback.filter(), CreateAppointmentState.waiting_for_service)
async def process_service_selection(callback: CallbackQuery, callback_data: SelectServiceCallback, state: FSMContext):
    """Обработка выбора услуги"""
    await state.update_data(service_id=callback_data.id)
    await callback.message.answer("Введите дату в формате ДД.ММ.ГГГГ:")
    await state.set_state(CreateAppointmentState.waiting_for_date)
    await callback.answer()

@router.message(CreateAppointmentState.waiting_for_date)
async def process_create_date(message: Message, state: FSMContext):
    """Обработка ввода даты"""
    try:
        date = datetime.strptime(message.text.strip(), "%d.%m.%Y")
        await state.update_data(date=date.strftime("%Y-%m-%d"))
        await message.answer("Введите время в формате ЧЧ:ММ:")
        await state.set_state(CreateAppointmentState.waiting_for_time)
    except ValueError:
        await message.answer("❌ Неверный формат даты. Введите дату в формате ДД.ММ.ГГГГ:")

@router.message(CreateAppointmentState.waiting_for_time)
async def process_create_time(message: Message, state: FSMContext):
    """Обработка ввода времени"""
    try:
        time = datetime.strptime(message.text.strip(), "%H:%M")
        data = await state.get_data()
        scheduled_time = f"{data['date']}T{time.strftime('%H:%M')}:00Z"
        
        # Получаем client_id
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/clients/search?telegram_id={message.from_user.id}")
            if response.status_code != 200:
                raise Exception("Клиент не найден")
            client_data = response.json()
            
            # Создаем запись
            response = await client.post(
                f"{API_URL}/appointments",
                json={
                    "client_id": client_data['id'],
                    "service_id": data['service_id'],
                    "car_model": data['car_model'],
                    "scheduled_time": scheduled_time,
                    "status": "pending"
                }
            )
            response.raise_for_status()
            
            await message.answer("✅ Запись успешно создана")
            await state.clear()
            
            # Возвращаемся к списку записей
            await command_appointments(message)
            
    except ValueError:
        await message.answer("❌ Неверный формат времени. Введите время в формате ЧЧ:ММ:")
    except Exception as e:
        logger.error(f"Ошибка при создании записи: {e}")
        await message.answer("❌ Произошла ошибка при создании записи")
        await state.clear()

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

async def get_appointments_list(telegram_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Получение списка записей клиента"""
    try:
        async with httpx.AsyncClient() as client:
            # Получаем клиента по telegram_id
            client_response = await client.get(
                f"{API_URL}/clients/search",
                params={"telegram_id": str(telegram_id)}
            )
            client_response.raise_for_status()
            current_client = client_response.json()
            
            if not current_client:
                return "❌ Ошибка: клиент не найден. Пожалуйста, зарегистрируйтесь.", None
            
            # Получаем записи клиента через фильтр
            appointments_response = await client.get(
                f"{API_URL}/appointments",
                params={"client_id": current_client['id']}
            )
            appointments_response.raise_for_status()
            appointments = appointments_response.json()
            
            if not appointments:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Создать запись", callback_data="create_appointment")]
                ])
                return "📝 Нет доступных записей", keyboard
            
            # Сортируем записи по дате
            appointments.sort(key=lambda x: datetime.fromisoformat(x['scheduled_time'].replace('Z', '+00:00')))
            
            # Получаем информацию об услугах
            services_response = await client.get(f"{API_URL}/services")
            services_response.raise_for_status()
            services = {s['id']: s for s in services_response.json()}
            
            # Создаем кнопки для каждой записи
            buttons = []
            for appointment in appointments:
                service = services[appointment['service_id']]
                scheduled_time = datetime.fromisoformat(appointment['scheduled_time'].replace('Z', '+00:00'))
                formatted_time = scheduled_time.strftime("%d.%m.%Y %H:%M")
                
                buttons.append([
                    InlineKeyboardButton(
                        text=f"{formatted_time} - {service['name']}",
                        callback_data=AppointmentCallback(id=appointment['id'], action="view").pack()
                    )
                ])
            
            buttons.extend([
                [InlineKeyboardButton(text="➕ Создать запись", callback_data="create_appointment")],
                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu")]
            ])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            return "📝 Список записей:", keyboard
            
    except Exception as e:
        logger.error(f"Ошибка при получении списка записей: {e}")
        return "❌ Произошла ошибка при получении списка записей", None

@router.message(Command("appointments"))
async def command_appointments(message: Message):
    """Показать список записей"""
    message_text, keyboard = await get_appointments_list(message.from_user.id)
    if keyboard:
        await message.answer(message_text, reply_markup=keyboard)
    else:
        await message.answer(message_text)

@router.callback_query(F.data == "my_appointments")
async def show_my_appointments(callback: CallbackQuery):
    """Показ записей клиента"""
    message_text, keyboard = await get_appointments_list(callback.from_user.id)
    if keyboard:
        await callback.message.edit_text(message_text, reply_markup=keyboard)
    else:
        await callback.message.edit_text(message_text)
    await callback.answer()

@router.callback_query(lambda c: c.data == "back_to_appointments")
async def back_to_appointments(callback: types.CallbackQuery):
    """Возврат к списку записей"""
    message_text, keyboard = await get_appointments_list(callback.from_user.id)
    if keyboard:
        await callback.message.edit_text(message_text, reply_markup=keyboard)
    else:
        await callback.message.edit_text(message_text)
    await callback.answer()

async def get_appointment_info(appointment_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Получение информации о записи"""
    try:
        async with httpx.AsyncClient() as http_client:
            # Получаем информацию о записи
            response = await http_client.get(f"{API_URL}/appointments/{appointment_id}")
            response.raise_for_status()
            appointment = response.json()
            logger.info(f"Получена запись: {appointment}")
            
            # Получаем информацию об услуге
            try:
                service_response = await http_client.get(f"{API_URL}/services/{appointment['service_id']}")
                service_response.raise_for_status()
                service = service_response.json()
                logger.info(f"Получена услуга: {service}")
                service_info = f"🔧 Услуга: {service['name']}\n💰 Стоимость: {service['price']} руб.\n"
            except httpx.HTTPError:
                logger.warning(f"Услуга с ID {appointment['service_id']} не найдена")
                service_info = "🔧 Услуга: Не найдена\n"
            
            # Форматируем дату и время
            scheduled_time = datetime.fromisoformat(appointment['scheduled_time'].replace('Z', '+00:00'))
            formatted_time = scheduled_time.strftime("%d.%m.%Y %H:%M")
            
            # Создаем клавиатуру с кнопками управления
            buttons = [
                [
                    InlineKeyboardButton(
                        text="❌ Отменить запись",
                        callback_data=AppointmentCallback(action="delete", id=appointment_id).pack()
                    )
                ],
                [
                    InlineKeyboardButton(text="◀️ Назад к списку", callback_data="back_to_appointments"),
                    InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu")
                ]
            ]
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            
            # Формируем сообщение с информацией о записи
            message = (
                f"📝 Запись #{appointment_id}\n\n"
                f"🚗 Автомобиль: {appointment.get('car_model', 'Не указан')}\n"
                f"{service_info}"
                f"📅 Дата и время: {formatted_time}\n"
                f"📊 Статус: {appointment.get('status', 'Не указан')}\n"
            )
            
            return message, keyboard
            
    except Exception as e:
        logger.error(f"Ошибка при получении информации о записи: {e}")
        raise

@router.callback_query(AppointmentCallback.filter(F.action == "view"))
async def process_appointment_selection(callback: CallbackQuery, callback_data: AppointmentCallback):
    """Обработка выбора записи"""
    try:
        appointment_id = callback_data.id
        logger.info(f"Получаем информацию о записи {appointment_id}")
        
        # Получаем информацию о записи
        message_text, keyboard = await get_appointment_info(appointment_id)
        await callback.message.edit_text(message_text, reply_markup=keyboard)
        await callback.answer()
            
    except Exception as e:
        logger.error(f"Ошибка при просмотре записи: {e}")
        await callback.answer("❌ Произошла ошибка при получении информации о записи", show_alert=True)

@router.callback_query(AppointmentCallback.filter(F.action == "delete"))
async def process_delete(callback: types.CallbackQuery, callback_data: AppointmentCallback, state: FSMContext):
    """Обработка удаления записи"""
    try:
        appointment_id = callback_data.id
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Да, отменить",
                        callback_data=AppointmentCallback(id=appointment_id, action="confirm_delete").pack()
                    ),
                    InlineKeyboardButton(
                        text="❌ Нет, оставить",
                        callback_data=AppointmentCallback(id=appointment_id, action="view").pack()
                    )
                ]
            ]
        )
        await callback.message.edit_text("Вы уверены, что хотите отменить эту запись?", reply_markup=keyboard)
        await callback.answer()
            
    except Exception as e:
        logger.error(f"Ошибка при удалении записи: {e}")
        await callback.answer("❌ Произошла ошибка при удалении записи", show_alert=True)

@router.callback_query(AppointmentCallback.filter(F.action == "confirm_delete"))
async def confirm_delete(callback: types.CallbackQuery, callback_data: AppointmentCallback):
    """Подтверждение удаления записи"""
    try:
        appointment_id = callback_data.id
        
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{API_URL}/appointments/{appointment_id}")
            response.raise_for_status()
            
            await callback.message.edit_text("✅ Запись успешно отменена")
            await callback.answer()
            
            # Возвращаемся к списку записей
            await command_appointments(callback.message)
            
    except Exception as e:
        logger.error(f"Ошибка при удалении записи: {e}")
        await callback.answer("❌ Произошла ошибка при удалении записи", show_alert=True) 