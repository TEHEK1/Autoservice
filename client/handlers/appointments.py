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
from zoneinfo import ZoneInfo

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

# Callback данные для выбора даты слота
class SelectDateCallback(CallbackData, prefix="select_date"):
    date: str

# Callback данные для выбора слота
class SelectSlotCallback(CallbackData, prefix="select_slot"):
    slot_id: str  # Переименуем поле id в slot_id для предотвращения конфликтов

class CreateAppointmentState(StatesGroup):
    waiting_for_car = State()
    waiting_for_service = State()
    waiting_for_date = State()
    waiting_for_slot = State()

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
    
    # Получаем доступные даты из слотов
    try:
        # Получаем текущую дату
        now = datetime.now()
        
        # Создаем кнопки для следующих 7 дней
        dates = {}
        for i in range(7):
            date = now + timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            display_date = date.strftime("%d.%m.%Y (%a)")
            dates[date_str] = display_date
        
        if not dates:
            await callback.message.answer("❌ Нет доступных дат для записи. Пожалуйста, обратитесь к администратору.")
            await state.clear()
            await callback.answer()
            return
        
        # Создаем клавиатуру с доступными датами
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=display_date,
                callback_data=SelectDateCallback(date=date_str).pack()
            )] for date_str, display_date in sorted(dates.items())
        ])
        
        await callback.message.answer("Выберите дату:", reply_markup=keyboard)
        await state.set_state(CreateAppointmentState.waiting_for_date)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при получении доступных дат: {e}")
        await callback.message.answer("❌ Произошла ошибка при получении доступных дат")
        await state.clear()
        await callback.answer()

@router.callback_query(SelectDateCallback.filter(), CreateAppointmentState.waiting_for_date)
async def process_date_selection(callback: CallbackQuery, callback_data: SelectDateCallback, state: FSMContext):
    """Обработка выбора даты"""
    selected_date = callback_data.date
    await state.update_data(selected_date=selected_date)
    
    # Получаем слоты на выбранную дату
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Запрашиваем доступные слоты через API
            # Преобразуем дату в формат, который ожидает API (YYYY-MM-DD)
            try:
                # Сначала пробуем парсить в формате дд.мм.гггг
                api_date = datetime.strptime(selected_date, "%d.%m.%Y").strftime("%Y-%m-%d")
            except ValueError:
                # Если не получилось, значит дата уже в формате гггг-мм-дд
                api_date = selected_date
            
            response = await client.get(
                f"{API_URL}/working_periods/time_slots",
                params={"date": api_date}
            )
            response.raise_for_status()
            slots = response.json()
            
            if not slots:
                await callback.message.answer("❌ Нет доступных слотов на выбранную дату. Пожалуйста, выберите другую дату.")
                # Возвращаемся к выбору услуги
                await callback.message.edit_text("Выберите другую дату")
                await callback.answer()
                return
            
            # Фильтруем только доступные слоты
            available_slots = [slot for slot in slots if slot['is_available']]
            
            if not available_slots:
                await callback.message.answer("❌ Нет доступных слотов на выбранную дату. Пожалуйста, выберите другую дату.")
                # Возвращаемся к выбору услуги
                await callback.message.edit_text("Выберите другую дату")
                await callback.answer()
                return
            
            # Получаем часовой пояс клиента
            client_timezone = await get_client_timezone(callback.from_user.id)
            
            # Создаем клавиатуру со слотами
            keyboard = InlineKeyboardMarkup(inline_keyboard=[])
            
            # Сортируем слоты по времени
            available_slots.sort(key=lambda x: x['start_time'])
            
            # Добавляем кнопки для каждого доступного слота
            for slot in available_slots:
                # Преобразуем время слота в локальное время клиента
                slot_start = datetime.fromisoformat(slot['start_time'].replace('Z', '+00:00')).replace(tzinfo=ZoneInfo("UTC"))
                slot_end = datetime.fromisoformat(slot['end_time'].replace('Z', '+00:00')).replace(tzinfo=ZoneInfo("UTC"))
                
                slot_start_local = slot_start.astimezone(ZoneInfo(client_timezone))
                slot_end_local = slot_end.astimezone(ZoneInfo(client_timezone))
                
                # Форматируем время для отображения
                time_str = f"{slot_start_local.strftime('%H:%M')} - {slot_end_local.strftime('%H:%M')}"
                
                # Генерируем уникальный целочисленный ID для слота, если это строка или не число
                slot_id = slot['id']
                if not isinstance(slot_id, int):
                    try:
                        slot_id = int(slot_id)
                    except (ValueError, TypeError):
                        # Если не можем преобразовать в int, используем хеш строки как id
                        slot_id = abs(hash(str(slot['id']))) % (10 ** 9)
                
                keyboard.inline_keyboard.append([
                    InlineKeyboardButton(
                        text=time_str,
                        callback_data=AppointmentCallback(id=slot_id, action="select_time", value=slot_start_local.strftime("%H.%M")).pack()
                    )
                ])
            
            # Добавляем кнопку возврата
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text="◀️ Назад", callback_data="create_appointment")
            ])
            
            # Отображаем дату в формате ДД.ММ.ГГГГ
            display_date = selected_date
            if "-" in selected_date:
                # Если дата в формате YYYY-MM-DD, преобразуем в ДД.ММ.ГГГГ
                display_date = datetime.strptime(selected_date, "%Y-%m-%d").strftime("%d.%m.%Y")
            
            await callback.message.edit_text(
                f"Выбрана дата: {display_date}\n"
                f"Выберите время (ваш часовой пояс: {client_timezone}):",
                reply_markup=keyboard
            )
            
            await state.set_state(AppointmentState.waiting_for_time)
            await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при получении занятых слотов: {e}")
        await callback.message.answer("❌ Произошла ошибка. Пожалуйста, попробуйте позже.")
        await callback.answer()

@router.callback_query(lambda c: c.data == "back_to_date_selection", CreateAppointmentState.waiting_for_slot)
async def back_to_date_selection(callback: CallbackQuery, state: FSMContext):
    """Возврат к выбору даты"""
    await process_service_selection(callback, callback_data=SelectServiceCallback(id=(await state.get_data())['service_id']), state=state)

@router.callback_query(SelectSlotCallback.filter(), CreateAppointmentState.waiting_for_slot)
async def process_slot_selection(callback: CallbackQuery, callback_data: SelectSlotCallback, state: FSMContext):
    """Обработка выбора слота"""
    try:
        # Получаем данные из состояния и выбранный слот
        data = await state.get_data()
        car_model = data['car_model']
        service_id = data['service_id']
        selected_date = data['selected_date']
        slot_id = callback_data.slot_id
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Получаем текущие слоты для перепроверки
            response = await client.get(
                f"{API_URL}/working_periods/time_slots",
                params={"date": selected_date}
            )
            response.raise_for_status()
            slots = response.json()
            
            # Находим выбранный слот
            selected_slot = None
            for slot in slots:
                if slot['id'] == slot_id:
                    selected_slot = slot
                    break
            
            if not selected_slot:
                raise ValueError("Выбранный слот не найден")
            
            if not selected_slot['is_available']:
                await callback.message.answer("❌ Выбранный слот уже занят. Пожалуйста, выберите другой слот.")
                # Возвращаемся к выбору времени
                await process_date_selection(callback, callback_data=SelectDateCallback(date=selected_date), state=state)
                await callback.answer()
                return
            
            # Получаем информацию о клиенте
            client_response = await client.get(
                f"{API_URL}/clients/search",
                params={"telegram_id": callback.from_user.id}
            )
            if client_response.status_code != 200:
                raise ValueError("Клиент не найден")
            
            client_data = client_response.json()
            if not client_data:
                await callback.message.answer("❌ Ошибка: вы не зарегистрированы. Пожалуйста, зарегистрируйтесь с помощью команды /start")
                await state.clear()
                await callback.answer()
                return
            
            # Получаем информацию о выбранной услуге
            service_response = await client.get(f"{API_URL}/services/{service_id}")
            service_response.raise_for_status()
            service = service_response.json()
            
            # Создаем запись
            slot_start = datetime.fromisoformat(selected_slot['start_time'].replace('Z', '+00:00'))
            
            appointment_response = await client.post(
                f"{API_URL}/appointments",
                json={
                    "client_id": client_data['id'],
                    "service_id": service_id,
                    "car_model": car_model,
                    "scheduled_time": selected_slot['start_time'],
                    "status": "pending"
                }
            )
            appointment_response.raise_for_status()
            
            # Получаем часовой пояс клиента
            client_timezone = await get_client_timezone(callback.from_user.id)
            
            # Форматируем сообщение для пользователя
            slot_start_local = slot_start.astimezone(ZoneInfo(client_timezone))
            formatted_time = slot_start_local.strftime("%d.%m.%Y %H:%M")
            
            await callback.message.answer(
                f"✅ Запись успешно создана!\n\n"
                f"🔧 Услуга: {service['name']}\n"
                f"🚗 Автомобиль: {car_model}\n"
                f"📅 Дата и время: {formatted_time}\n"
                f"💰 Стоимость: {service['price']} руб."
            )
            
            await state.clear()
            await callback.answer()
            
            # Получаем список записей пользователя
            message_text, keyboard = await get_appointments_list(callback.from_user.id)
            if keyboard:
                await callback.message.answer(message_text, reply_markup=keyboard)
            else:
                await callback.message.answer(message_text)
            
    except Exception as e:
        logger.error(f"Ошибка при создании записи: {e}")
        await callback.message.answer("❌ Произошла ошибка при создании записи. Пожалуйста, попробуйте позже.")
        await state.clear()
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
    
    # Получаем слоты на выбранную дату
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Запрашиваем доступные слоты через API
            # Преобразуем дату в формат, который ожидает API (YYYY-MM-DD)
            try:
                # Сначала пробуем парсить в формате дд.мм.гггг
                api_date = datetime.strptime(selected_date, "%d.%m.%Y").strftime("%Y-%m-%d")
            except ValueError:
                # Если не получилось, значит дата уже в формате гггг-мм-дд
                api_date = selected_date
            
            response = await client.get(
                f"{API_URL}/working_periods/time_slots",
                params={"date": api_date}
            )
            response.raise_for_status()
            slots = response.json()
            
            if not slots:
                await callback.message.answer("❌ Нет доступных слотов на выбранную дату. Пожалуйста, выберите другую дату.")
                # Возвращаемся к выбору услуги
                await callback.message.edit_text("Выберите другую дату")
                await callback.answer()
                return
            
            # Фильтруем только доступные слоты
            available_slots = [slot for slot in slots if slot['is_available']]
            
            if not available_slots:
                await callback.message.answer("❌ Нет доступных слотов на выбранную дату. Пожалуйста, выберите другую дату.")
                # Возвращаемся к выбору услуги
                await callback.message.edit_text("Выберите другую дату")
                await callback.answer()
                return
            
            # Получаем часовой пояс клиента
            client_timezone = await get_client_timezone(callback.from_user.id)
            
            # Создаем клавиатуру со слотами
            keyboard = InlineKeyboardMarkup(inline_keyboard=[])
            
            # Сортируем слоты по времени
            available_slots.sort(key=lambda x: x['start_time'])
            
            # Добавляем кнопки для каждого доступного слота
            for slot in available_slots:
                # Преобразуем время слота в локальное время клиента
                slot_start = datetime.fromisoformat(slot['start_time'].replace('Z', '+00:00')).replace(tzinfo=ZoneInfo("UTC"))
                slot_end = datetime.fromisoformat(slot['end_time'].replace('Z', '+00:00')).replace(tzinfo=ZoneInfo("UTC"))
                
                slot_start_local = slot_start.astimezone(ZoneInfo(client_timezone))
                slot_end_local = slot_end.astimezone(ZoneInfo(client_timezone))
                
                # Форматируем время для отображения
                time_str = f"{slot_start_local.strftime('%H:%M')} - {slot_end_local.strftime('%H:%M')}"
                
                # Генерируем уникальный целочисленный ID для слота, если это строка или не число
                slot_id = slot['id']
                if not isinstance(slot_id, int):
                    try:
                        slot_id = int(slot_id)
                    except (ValueError, TypeError):
                        # Если не можем преобразовать в int, используем хеш строки как id
                        slot_id = abs(hash(str(slot['id']))) % (10 ** 9)
                
                keyboard.inline_keyboard.append([
                    InlineKeyboardButton(
                        text=time_str,
                        callback_data=AppointmentCallback(id=slot_id, action="select_time", value=slot_start_local.strftime("%H.%M")).pack()
                    )
                ])
            
            # Добавляем кнопку возврата
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text="◀️ Назад", callback_data="create_appointment")
            ])
            
            # Отображаем дату в формате ДД.ММ.ГГГГ
            display_date = selected_date
            if "-" in selected_date:
                # Если дата в формате YYYY-MM-DD, преобразуем в ДД.ММ.ГГГГ
                display_date = datetime.strptime(selected_date, "%Y-%m-%d").strftime("%d.%m.%Y")
            
            await callback.message.edit_text(
                f"Выбрана дата: {display_date}\n"
                f"Выберите время (ваш часовой пояс: {client_timezone}):",
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
    slot_id = callback_data.id
    user_data = await state.get_data()
    
    # Проверяем наличие ключа date в данных состояния
    date_key = "date" if "date" in user_data else "selected_date"
    if date_key not in user_data:
        logger.error(f"Ошибка: данные о дате отсутствуют в состоянии: {user_data}")
        await callback.message.answer("❌ Произошла ошибка при создании записи. Пожалуйста, попробуйте заново.")
        await state.clear()
        await callback.answer()
        return
    
    # Формируем дату и время для записи
    selected_date = user_data[date_key]
    try:
        # Проверяем формат даты и преобразуем соответственно
        if "-" in selected_date:  # Формат YYYY-MM-DD
            date_obj = datetime.strptime(selected_date, "%Y-%m-%d")
            # Преобразуем дату в формат ДД.ММ.ГГГГ для отображения
            formatted_date = date_obj.strftime("%d.%m.%Y")
        else:  # Формат DD.MM.YYYY
            date_obj = datetime.strptime(selected_date, "%d.%m.%Y")
            formatted_date = selected_date
    except ValueError as e:
        logger.error(f"Ошибка при преобразовании даты '{selected_date}': {e}")
        await callback.message.answer("❌ Произошла ошибка при обработке даты. Пожалуйста, попробуйте заново.")
        await state.clear()
        await callback.answer()
        return
    
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
                    InlineKeyboardButton(text="✅ Подтвердить", callback_data=AppointmentCallback(id=slot_id, action="confirm", value="yes").pack()),
                    InlineKeyboardButton(text="❌ Отменить", callback_data=AppointmentCallback(id=slot_id, action="confirm", value="no").pack())
                ]
            ])
            
            await callback.message.edit_text(
                f"Проверьте данные записи:\n\n"
                f"Услуга: {service['name']}\n"
                f"Дата: {formatted_date}\n"
                f"Время: {selected_time}\n"
                f"Стоимость: {service['price']}₽\n\n"
                f"Подтвердить запись?",
                reply_markup=keyboard
            )
            
            # Сохраняем данные для создания записи
            await state.update_data(
                selected_date=selected_date,
                date=selected_date,
                formatted_date=formatted_date,  # Добавляем отформатированную дату для отображения
                scheduled_time=scheduled_time.isoformat(),
                client_id=client['id'],
                service_name=service['name'],
                service_price=service['price'],
                slot_id=slot_id,
                selected_time=selected_time
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
    slot_id = callback_data.id  # Это может быть преобразованный ID, а не оригинальный ID слота
    
    # Проверяем наличие ключа scheduled_time в данных состояния
    if 'scheduled_time' not in user_data:
        logger.error(f"Ошибка: данные о времени отсутствуют в состоянии: {user_data}")
        await callback.message.edit_text("❌ Произошла ошибка при создании записи. Пожалуйста, попробуйте заново.")
        await state.clear()
        await callback.answer()
        return
    
    date_str = datetime.fromisoformat(user_data['scheduled_time']).strftime("%Y-%m-%d")
    
    try:
        # Создаем запись
        async with httpx.AsyncClient() as client:
            # Получаем информацию о временных слотах на эту дату
            slot_response = await client.get(f"{API_URL}/working_periods/time_slots", 
                                          params={"date": date_str})
            slot_response.raise_for_status()
            slots = slot_response.json()
            
            # Вычисляем время начала выбранного слота
            if 'selected_time' not in user_data:
                logger.error(f"Ошибка: выбранное время отсутствует в состоянии: {user_data}")
                await callback.message.edit_text("❌ Произошла ошибка при создании записи. Пожалуйста, попробуйте заново.")
                await state.clear()
                await callback.answer()
                return
                
            time_parts = user_data['selected_time'].split(':')
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            
            # Фильтруем слоты, чтобы найти тот, который начинается в выбранное время
            available_slots = [slot for slot in slots if slot['is_available']]
            selected_slot = None
            
            for slot in available_slots:
                slot_start = datetime.fromisoformat(slot['start_time'].replace('Z', '+00:00')).replace(tzinfo=ZoneInfo("UTC"))
                # Получаем часовой пояс клиента
                client_timezone = await get_client_timezone(callback.from_user.id)
                slot_start_local = slot_start.astimezone(ZoneInfo(client_timezone))
                
                if slot_start_local.hour == hour and slot_start_local.minute == minute:
                    selected_slot = slot
                    break
            
            if not selected_slot:
                await callback.message.edit_text("❌ Ошибка: выбранный слот не найден. Пожалуйста, попробуйте заново.")
                await state.clear()
                await callback.answer()
                return
            
            # Проверяем наличие ключей в данных состояния
            if 'client_id' not in user_data or 'service_id' not in user_data:
                logger.error(f"Ошибка: данные о клиенте или услуге отсутствуют: {user_data}")
                await callback.message.edit_text("❌ Произошла ошибка при создании записи. Пожалуйста, попробуйте заново.")
                await state.clear()
                await callback.answer()
                return
                
            appointment_data = {
                "client_id": user_data['client_id'],
                "service_id": user_data['service_id'],
                "scheduled_time": selected_slot['start_time'],
                "status": "pending"
            }
            
            # Добавляем car_model в запись, если он есть
            if 'car_model' in user_data:
                appointment_data["car_model"] = user_data['car_model']
            
            response = await client.post(f"{API_URL}/appointments", json=appointment_data)
            response.raise_for_status()
            
            # Очищаем состояние
            await state.clear()
            
            # Показываем подтверждение
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
            
            # Получаем часовой пояс клиента для отображения времени
            client_timezone = await get_client_timezone(callback.from_user.id)
            slot_start = datetime.fromisoformat(selected_slot['start_time'].replace('Z', '+00:00')).replace(tzinfo=ZoneInfo("UTC"))
            slot_start_local = slot_start.astimezone(ZoneInfo(client_timezone))
            formatted_time = slot_start_local.strftime("%d.%m.%Y %H:%M")
            
            # Проверяем наличие ключей для отображения информации
            service_name = user_data.get('service_name', 'Не указана')
            service_price = user_data.get('service_price', 'Не указана')
            
            await callback.message.edit_text(
                f"✅ Запись успешно создана!\n\n"
                f"Услуга: {service_name}\n"
                f"Дата и время: {formatted_time}\n"
                f"Стоимость: {service_price}₽\n\n"
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
            
            # Получаем часовой пояс клиента
            client_timezone = await get_client_timezone(telegram_id)
            
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
                scheduled_time = datetime.fromisoformat(appointment['scheduled_time'].replace('Z', '+00:00')).replace(tzinfo=ZoneInfo("UTC"))
                local_time = scheduled_time.astimezone(ZoneInfo(client_timezone))
                formatted_time = local_time.strftime("%d.%m.%Y %H:%M")
                
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

async def get_appointment_info(appointment_id: int, telegram_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Получение информации о записи"""
    try:
        # Получаем часовой пояс клиента
        client_timezone = await get_client_timezone(telegram_id)
        
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
            
            # Форматируем дату и время с учетом часового пояса клиента
            scheduled_time = datetime.fromisoformat(appointment['scheduled_time'].replace('Z', '+00:00')).replace(tzinfo=ZoneInfo("UTC"))
            local_time = scheduled_time.astimezone(ZoneInfo(client_timezone))
            formatted_time = local_time.strftime("%d.%m.%Y %H:%M")
            
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
        
        # Получаем информацию о записи с учетом часового пояса клиента
        message_text, keyboard = await get_appointment_info(appointment_id, callback.from_user.id)
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

async def get_client_timezone(telegram_id: int) -> str:
    """Получение часового пояса клиента по его Telegram ID
    
    Args:
        telegram_id: ID пользователя в Telegram
        
    Returns:
        str: Часовой пояс клиента (например, 'Europe/Moscow')
    """
    try:
        async with httpx.AsyncClient() as http_client:
            # Получаем информацию о клиенте для часового пояса
            client_response = await http_client.get(
                f"{API_URL}/clients/search",
                params={"telegram_id": telegram_id}
            )
            client_response.raise_for_status()
            client_data = client_response.json()
            
            if not client_data:
                logger.error(f"Клиент не найден: {telegram_id}")
                return "Europe/Moscow"  # Возвращаем дефолтный часовой пояс
            
            # Получаем часовой пояс клиента
            client_timezone = client_data.get('timezone', 'Europe/Moscow')
            return client_timezone
    except Exception as e:
        logger.error(f"Ошибка при получении часового пояса: {e}")
        return "Europe/Moscow"  # Возвращаем дефолтный часовой пояс в случае ошибки 