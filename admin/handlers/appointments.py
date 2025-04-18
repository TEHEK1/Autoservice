from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters.callback_data import CallbackData
import httpx
import logging
from datetime import datetime

from aiogram.fsm.state import StatesGroup, State

from ..config import API_URL
from . import clients, services

logger = logging.getLogger(__name__)

# Создаем роутер для записей
router = Router()

# Состояния для записей
class EditAppointmentState(StatesGroup):
    waiting_for_value = State()

class CreateAppointmentState(StatesGroup):
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_client = State()
    waiting_for_service = State()

class DeleteAppointmentState(StatesGroup):
    waiting_for_confirmation = State()

# Callback данные для записей
class AppointmentCallback(CallbackData, prefix="appointment"):
    id: int
    action: str

class ViewClientCallback(CallbackData, prefix="view_client"):
    appointment_id: int

class SelectClientCallback(CallbackData, prefix="select_client"):
    id: int

class SelectServiceCallback(CallbackData, prefix="select_service"):
    id: int

class EditAppointmentCallback(CallbackData, prefix="appointment"):
    id: int
    field: str

class EditAppointmentKeyCallback(CallbackData, prefix="appointment"):
    id: int
    key: str

class ClientCallback(CallbackData, prefix="client"):
    id: int

class ServiceCallback(CallbackData, prefix="service"):
    id: int

@router.message(Command("appointments"))
async def command_appointments(message: Message):
    """Показать список записей"""
    try:
        async with httpx.AsyncClient() as client:
            # Получаем список записей
            response = await client.get(f"{API_URL}/appointments")
            response.raise_for_status()
            appointments = response.json()
            
            if not appointments:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Создать запись", callback_data="create_appointment")]
                ])
                await message.answer("📝 Нет доступных записей", reply_markup=keyboard)
                return
            
            # Создаем кнопки для каждой записи
            buttons = []
            for appointment in appointments:
                try:
                    if not appointment.get('client_id'):
                        logger.warning(f"У записи {appointment['id']} отсутствует client_id")
                        continue
                        
                    client_response = await client.get(f"{API_URL}/clients/{appointment['client_id']}")
                    if client_response.status_code != 200:
                        logger.warning(f"Ошибка при получении клиента {appointment['client_id']}: {client_response.status_code}")
                        continue
                        
                    client_data = client_response.json()
                    if not client_data:
                        logger.warning(f"Получен пустой ответ для клиента {appointment['client_id']}")
                        continue
                    
                    scheduled_time = datetime.fromisoformat(appointment['scheduled_time'].replace('Z', '+00:00'))
                    formatted_time = scheduled_time.strftime("%d.%m.%Y %H:%M")
                    
                    buttons.append([
                        InlineKeyboardButton(
                            text=f"{client_data['name']} - {formatted_time}",
                            callback_data=AppointmentCallback(id=appointment['id'], action="view").pack()
                        )
                    ])
                except Exception as e:
                    logger.error(f"Ошибка при получении информации о клиенте {appointment.get('client_id', 'unknown')}: {e}")
                    continue
            
            if not buttons:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Создать запись", callback_data="create_appointment")]
                ])
                await message.answer("📝 Нет доступных записей", reply_markup=keyboard)
                return
            
            # Добавляем кнопки управления
            buttons.extend([
                [InlineKeyboardButton(text="➕ Создать запись", callback_data="create_appointment")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            await message.answer("📝 Список записей:", reply_markup=keyboard)
            
    except Exception as e:
        logger.error(f"Ошибка при получении списка записей: {e}")
        await message.answer("❌ Произошла ошибка при получении списка записей")

@router.callback_query(lambda c: c.data == "create_appointment")
async def process_create_appointment_callback(callback: types.CallbackQuery, state: FSMContext):
    """Начало создания записи"""
    await state.set_state(CreateAppointmentState.waiting_for_date)
    await callback.message.answer("📅 Введите дату в формате ДД.ММ.ГГГГ")

@router.message(CreateAppointmentState.waiting_for_date)
async def process_date(message: Message, state: FSMContext):
    """Обработка ввода даты"""
    try:
        date = datetime.strptime(message.text, "%d.%m.%Y")
        await state.update_data(date=date)
        await state.set_state(CreateAppointmentState.waiting_for_time)
        await message.answer("⏰ Введите время в формате ЧЧ:ММ")
    except ValueError:
        await message.answer("❌ Неверный формат даты. Введите дату в формате ДД.ММ.ГГГГ")

@router.message(CreateAppointmentState.waiting_for_time)
async def process_time(message: Message, state: FSMContext):
    """Обработка ввода времени"""
    try:
        time = datetime.strptime(message.text, "%H:%M")
        data = await state.get_data()
        date = data["date"]
        scheduled_time = datetime.combine(date.date(), time.time())
        await state.update_data(scheduled_time=scheduled_time)
        
        # Показываем список клиентов
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/clients")
            clients = response.json()
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"{client['name']} ({client['phone_number']})",
                    callback_data=SelectClientCallback(id=client["id"]).pack()
                )] for client in clients
            ])
            
            await state.set_state(CreateAppointmentState.waiting_for_client)
            await message.answer("👤 Выберите клиента:", reply_markup=keyboard)
    except ValueError:
        await message.answer("❌ Неверный формат времени. Введите время в формате ЧЧ:ММ")

@router.callback_query(SelectClientCallback.filter(), CreateAppointmentState.waiting_for_client)
async def process_client_selection(callback: CallbackQuery, callback_data: SelectClientCallback, state: FSMContext):
    """Обработка выбора клиента"""
    await state.update_data(client_id=callback_data.id)
    
    # Показываем список услуг
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_URL}/services")
        services = response.json()
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{service['name']} - {service['price']}₽",
                callback_data=SelectServiceCallback(id=service["id"]).pack()
            )] for service in services
        ])
        
        await state.set_state(CreateAppointmentState.waiting_for_service)
        await callback.message.answer("🔧 Выберите услугу:", reply_markup=keyboard)

@router.callback_query(SelectServiceCallback.filter(), CreateAppointmentState.waiting_for_service)
async def process_service_selection(callback: CallbackQuery, callback_data: SelectServiceCallback, state: FSMContext):
    """Обработка выбора услуги и создание записи"""
    data = await state.get_data()
    
    # Создаем запись
    async with httpx.AsyncClient() as client:
        appointment_data = {
            "client_id": data["client_id"],
            "service_id": callback_data.id,
            "scheduled_time": data["scheduled_time"].isoformat(),
            "status": "pending",
            "car_model": None
        }
        
        response = await client.post(f"{API_URL}/appointments", json=appointment_data)
        if response.status_code == 200:
            await callback.message.answer("✅ Запись успешно создана!")
            # Показываем обновленный список записей
            await command_appointments(callback.message)
        else:
            await callback.message.answer("❌ Ошибка при создании записи")
    
    await state.clear()

@router.callback_query(lambda c: c.data == "delete_appointment")
async def process_delete_appointment_callback(callback: types.CallbackQuery):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_URL}/appointments")
            response.raise_for_status()
            appointments = response.json()

            if not appointments:
                await callback.message.answer("Нет доступных записей для удаления.")
                return

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=f"{a.get('date', 'Нет даты')} {a.get('time', 'Нет времени')} — {a.get('client_name', 'Нет клиента')}",
                            callback_data=AppointmentCallback(id=a['id'], action="delete").pack()
                        )
                    ] for a in appointments
                ]
            )

            await callback.message.answer("Выберите запись для удаления:", reply_markup=keyboard)
        except httpx.RequestError as e:
            await callback.message.answer(f"❌ Ошибка при получении списка записей: {str(e)}")
    
    await callback.answer()

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

@router.callback_query(AppointmentCallback.filter(F.action.in_(["edit_date", "edit_time", "edit_service", "edit_status", "edit_car", "delete"])))
async def process_edit_appointment(callback: types.CallbackQuery, callback_data: AppointmentCallback, state: FSMContext):
    """Обработка редактирования записи"""
    appointment_id = callback_data.id
    action = callback_data.action
    
    if action == "edit_service":
        # Получаем список доступных услуг
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/services")
            response.raise_for_status()
            services = response.json()
            logger.info(f"Получен список услуг: {services}")
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=f"{service['name']} - {service['price']}₽",
                            callback_data=SelectServiceCallback(id=service['id']).pack()
                        )
                    ] for service in services
                ]
            )
            
            await callback.message.edit_text("Выберите новую услугу:", reply_markup=keyboard)
            await state.set_state(EditAppointmentState.waiting_for_value)
            await state.update_data(appointment_id=appointment_id, field="service")
    elif action == "edit_date":
        await callback.message.edit_text("Введите новую дату (в формате ДД.ММ.ГГГГ):")
        await state.set_state(EditAppointmentState.waiting_for_value)
        await state.update_data(appointment_id=appointment_id, field="date")
    elif action == "edit_time":
        await callback.message.edit_text("Введите новое время (в формате ЧЧ:ММ):")
        await state.set_state(EditAppointmentState.waiting_for_value)
        await state.update_data(appointment_id=appointment_id, field="time")
    elif action == "edit_status":
        await callback.message.edit_text("Введите новый статус (pending, confirmed, completed, cancelled):")
        await state.set_state(EditAppointmentState.waiting_for_value)
        await state.update_data(appointment_id=appointment_id, field="status")
    elif action == "edit_car":
        await callback.message.edit_text("Введите новую модель автомобиля:")
        await state.set_state(EditAppointmentState.waiting_for_value)
        await state.update_data(appointment_id=appointment_id, field="car_model")
    elif action == "delete":
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Да, удалить",
                        callback_data=AppointmentCallback(id=appointment_id, action="confirm_delete").pack()
                    ),
                    InlineKeyboardButton(
                        text="❌ Нет, отменить",
                        callback_data=AppointmentCallback(id=appointment_id, action="view").pack()
                    )
                ]
            ]
        )
        await callback.message.edit_text("Вы уверены, что хотите удалить эту запись?", reply_markup=keyboard)
    
    await callback.answer()

@router.callback_query(SelectServiceCallback.filter(), EditAppointmentState.waiting_for_value)
async def process_service_selection(callback: types.CallbackQuery, callback_data: SelectServiceCallback, state: FSMContext):
    data = await state.get_data()
    appointment_id = data['appointment_id']
    service_id = callback_data.id
    
    try:
        async with httpx.AsyncClient() as client:
            # Проверяем существование услуги
            logger.info(f"Запрос на получение услуги: GET {API_URL}/services/{service_id}")
            service_response = await client.get(f"{API_URL}/services/{service_id}")
            service_response.raise_for_status()
            service = service_response.json()
            logger.info(f"Получена услуга: {service}")
            
            # Получаем текущую запись
            logger.info(f"Запрос на получение записи: GET {API_URL}/appointments/{appointment_id}")
            appointment_response = await client.get(f"{API_URL}/appointments/{appointment_id}")
            appointment_response.raise_for_status()
            appointment = appointment_response.json()
            logger.info(f"Получена запись: {appointment}")
            
            # Обновляем запись с новой услугой
            update_data = {
                "service_id": service_id  # Используем ID из callback_data
            }
            logger.info(f"Запрос на обновление записи: PATCH {API_URL}/appointments/{appointment_id} с данными {update_data}")
            response = await client.patch(f"{API_URL}/appointments/{appointment_id}", json=update_data)
            response.raise_for_status()
            
            await callback.answer("✅ Услуга успешно изменена!")
            await state.clear()
            
            # Показываем обновленную информацию о записи
            message_text, keyboard = await get_appointment_info(appointment_id)
            await callback.message.edit_text(message_text, reply_markup=keyboard)
            
    except httpx.HTTPError as e:
        if e.response and e.response.status_code == 404:
            await callback.message.edit_text("❌ Услуга не найдена")
        else:
            await callback.message.edit_text(f"❌ Ошибка при обновлении услуги: {str(e)}")
    
    await callback.answer()

@router.callback_query(ViewClientCallback.filter())
async def view_appointment_client(callback: CallbackQuery, callback_data: ViewClientCallback):
    """Просмотр информации о клиенте записи"""
    try:
        async with httpx.AsyncClient() as http_client:
            # Получаем информацию о записи
            response = await http_client.get(f"{API_URL}/appointments/{callback_data.appointment_id}")
            response.raise_for_status()
            appointment = response.json()
            
            # Получаем информацию о клиенте
            client_response = await http_client.get(f"{API_URL}/clients/{appointment['client_id']}")
            client_response.raise_for_status()
            client = client_response.json()
            
            # Формируем сообщение с информацией о клиенте
            message = (
                f"👤 Информация о клиенте\n\n"
                f"Имя: {client['name']}\n"
                f"Телефон: {client['phone_number']}\n"
                f"Telegram ID: {client.get('telegram_id', 'Не указан')}\n"
            )
            
            # Создаем клавиатуру с кнопками
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="◀️ Назад к записи",
                            callback_data=AppointmentCallback(id=callback_data.appointment_id, action="view").pack()
                        )
                    ],
                    [
                        InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu")
                    ]
                ]
            )
            
            await callback.message.edit_text(message, reply_markup=keyboard)
            await callback.answer()
            
    except Exception as e:
        logger.error(f"Ошибка при просмотре клиента: {e}")
        await callback.answer("❌ Произошла ошибка при получении информации о клиенте", show_alert=True)

@router.callback_query(lambda c: c.data == "back_to_appointments")
async def back_to_appointments(callback: types.CallbackQuery):
    """Возврат к списку записей"""
    await command_appointments(callback.message)
    await callback.answer()

@router.callback_query(lambda c: c.data == "appointments")
async def appointments_menu(callback: types.CallbackQuery):
    """Показать список записей"""
    await command_appointments(callback.message)
    await callback.answer()

@router.callback_query(lambda c: c.data == "clients")
async def clients_menu(callback: types.CallbackQuery):
    """Показать список клиентов"""
    await clients.command_clients(callback.message)
    await callback.answer()

@router.callback_query(lambda c: c.data == "services")
async def services_menu(callback: types.CallbackQuery):
    """Показать список услуг"""
    await services.command_services(callback.message)
    await callback.answer()

@router.callback_query(AppointmentCallback.filter(F.action == "confirm_delete"))
async def process_confirm_delete(callback: types.CallbackQuery, callback_data: AppointmentCallback):
    """Обработка подтверждения удаления записи"""
    try:
        appointment_id = callback_data.id
        async with httpx.AsyncClient() as client:
            # Удаляем запись
            response = await client.delete(f"{API_URL}/appointments/{appointment_id}")
            response.raise_for_status()
            
            await callback.message.edit_text("✅ Запись успешно удалена")
            
            # Показываем обновленный список записей
            await command_appointments(callback.message)
            
    except Exception as e:
        logger.error(f"Ошибка при удалении записи: {e}")
        await callback.message.edit_text("❌ Произошла ошибка при удалении записи")
    
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
            
            if not appointment:
                raise ValueError(f"Запись с ID {appointment_id} не найдена")
            
            # Получаем информацию о клиенте
            client_info = "👤 Клиент: Не найден\n📱 Телефон: Не указан\n"
            if appointment.get('client_id'):
                try:
                    client_response = await http_client.get(f"{API_URL}/clients/{appointment['client_id']}")
                    if client_response.status_code == 200:
                        client_data = client_response.json()
                        if client_data:
                            client_info = (
                                f"👤 Клиент: {client_data['name']}\n"
                                f"📱 Телефон: {client_data['phone_number']}\n"
                            )
                except Exception as e:
                    logger.error(f"Ошибка при получении информации о клиенте {appointment['client_id']}: {e}")
            
            # Получаем информацию об услуге
            service_info = "🔧 Услуга: Не найдена\n"
            if appointment.get('service_id'):
                try:
                    service_response = await http_client.get(f"{API_URL}/services/{appointment['service_id']}")
                    if service_response.status_code == 200:
                        service = service_response.json()
                        if service:
                            service_info = f"🔧 Услуга: {service['name']}\n💰 Стоимость: {service['price']} руб.\n"
                except Exception as e:
                    logger.error(f"Ошибка при получении информации об услуге {appointment['service_id']}: {e}")
            
            # Форматируем дату и время
            scheduled_time = datetime.fromisoformat(appointment['scheduled_time'].replace('Z', '+00:00'))
            formatted_time = scheduled_time.strftime("%d.%m.%Y %H:%M")
            
            # Создаем клавиатуру с кнопками управления
            buttons = [
                [
                    InlineKeyboardButton(
                        text="📅 Изменить дату",
                        callback_data=AppointmentCallback(action="edit_date", id=appointment_id).pack()
                    ),
                    InlineKeyboardButton(
                        text="⏰ Изменить время",
                        callback_data=AppointmentCallback(action="edit_time", id=appointment_id).pack()
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔧 Изменить услугу",
                        callback_data=AppointmentCallback(action="edit_service", id=appointment_id).pack()
                    ),
                    InlineKeyboardButton(
                        text="🚗 Изменить авто",
                        callback_data=AppointmentCallback(action="edit_car", id=appointment_id).pack()
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔄 Изменить статус",
                        callback_data=AppointmentCallback(action="edit_status", id=appointment_id).pack()
                    ),
                    InlineKeyboardButton(
                        text="👤 Просмотр клиента",
                        callback_data=ViewClientCallback(appointment_id=appointment_id).pack()
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="❌ Удалить запись",
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
                f"{client_info}"
                f"🚗 Автомобиль: {appointment.get('car_model', 'Не указан')}\n"
                f"{service_info}"
                f"📅 Дата и время: {formatted_time}\n"
                f"📊 Статус: {appointment.get('status', 'Не указан')}\n"
            )
            
            return message, keyboard
            
    except Exception as e:
        logger.error(f"Ошибка при получении информации о записи: {e}")
        raise

@router.message(EditAppointmentState.waiting_for_value)
async def process_edit_value(message: Message, state: FSMContext):
    """Обработка нового значения для редактирования записи"""
    try:
        data = await state.get_data()
        appointment_id = data['appointment_id']
        field = data['field']
        
        if field == "date":
            # Парсим дату
            try:
                date_obj = datetime.strptime(message.text.strip(), "%d.%m.%Y")
            except ValueError:
                await message.answer("❌ Неверный формат даты. Используйте формат ДД.ММ.ГГГГ")
                return
                
            # Получаем текущую запись
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{API_URL}/appointments/{appointment_id}")
                response.raise_for_status()
                appointment = response.json()
                
                # Обновляем только дату, сохраняя время
                current_time = datetime.fromisoformat(appointment['scheduled_time'].replace('Z', '+00:00'))
                new_datetime = datetime.combine(date_obj.date(), current_time.time())
                
                # Обновляем запись
                update_data = {
                    "scheduled_time": new_datetime.isoformat()
                }
                
                response = await client.patch(f"{API_URL}/appointments/{appointment_id}", json=update_data)
                response.raise_for_status()
                
                await message.answer("✅ Дата успешно обновлена")
                await state.clear()
                
                # Показываем обновленную информацию о записи
                message_text, keyboard = await get_appointment_info(appointment_id)
                await message.answer(message_text, reply_markup=keyboard)
                
        elif field == "time":
            # Парсим время
            try:
                time_obj = datetime.strptime(message.text.strip(), "%H:%M")
            except ValueError:
                await message.answer("❌ Неверный формат времени. Используйте формат ЧЧ:ММ")
                return
                
            # Получаем текущую запись
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{API_URL}/appointments/{appointment_id}")
                response.raise_for_status()
                appointment = response.json()
                
                # Обновляем только время, сохраняя дату
                current_datetime = datetime.fromisoformat(appointment['scheduled_time'].replace('Z', '+00:00'))
                new_datetime = datetime.combine(current_datetime.date(), time_obj.time())
                
                # Обновляем запись
                update_data = {
                    "scheduled_time": new_datetime.isoformat()
                }
                
                response = await client.patch(f"{API_URL}/appointments/{appointment_id}", json=update_data)
                response.raise_for_status()
                
                await message.answer("✅ Время успешно обновлено")
                await state.clear()
                
                # Показываем обновленную информацию о записи
                message_text, keyboard = await get_appointment_info(appointment_id)
                await message.answer(message_text, reply_markup=keyboard)
                
        elif field == "status":
            # Проверяем валидность статуса
            status = message.text.strip().lower()
            valid_statuses = ["pending", "confirmed", "completed", "cancelled"]
            
            if status not in valid_statuses:
                await message.answer("❌ Неверный статус. Допустимые значения: pending, confirmed, completed, cancelled")
                return
                
            # Обновляем статус
            async with httpx.AsyncClient() as client:
                update_data = {
                    "status": status
                }
                
                response = await client.patch(f"{API_URL}/appointments/{appointment_id}", json=update_data)
                response.raise_for_status()
                
                await message.answer("✅ Статус успешно обновлен")
                await state.clear()
                
                # Показываем обновленную информацию о записи
                message_text, keyboard = await get_appointment_info(appointment_id)
                await message.answer(message_text, reply_markup=keyboard)
                
        elif field == "car_model":
            # Обновляем модель автомобиля
            async with httpx.AsyncClient() as client:
                update_data = {
                    "car_model": message.text.strip()
                }
                
                response = await client.patch(f"{API_URL}/appointments/{appointment_id}", json=update_data)
                response.raise_for_status()
                
                await message.answer("✅ Модель автомобиля успешно обновлена")
                await state.clear()
                
                # Показываем обновленную информацию о записи
                message_text, keyboard = await get_appointment_info(appointment_id)
                await message.answer(message_text, reply_markup=keyboard)
                
    except Exception as e:
        logger.error(f"Ошибка при обновлении {field}: {e}")
        await message.answer(f"❌ Произошла ошибка при обновлении {field}") 