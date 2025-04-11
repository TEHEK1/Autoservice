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
                client_response = await client.get(f"{API_URL}/clients/{appointment['client_id']}")
                client = client_response.json()
                
                scheduled_time = datetime.fromisoformat(appointment['scheduled_time'].replace('Z', '+00:00'))
                formatted_time = scheduled_time.strftime("%d.%m.%Y %H:%M")
                
                buttons.append([
                    InlineKeyboardButton(
                        text=f"{client['name']} - {formatted_time}",
                        callback_data=AppointmentCallback(id=appointment['id'], action="view").pack()
                    )
                ])
            
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
    await callback.message.answer("Введите дату записи (в формате ДД.ММ.ГГГГ):")
    await state.set_state(CreateAppointmentState.waiting_for_date)
    await callback.answer()

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
        
        # Получаем информацию о записи и связанных данных
        async with httpx.AsyncClient() as http_client:
            # Получаем информацию о записи
            response = await http_client.get(f"{API_URL}/appointments/{appointment_id}")
            response.raise_for_status()
            appointment = response.json()
            logger.info(f"Получена запись: {appointment}")
            
            # Получаем информацию о клиенте
            client_response = await http_client.get(f"{API_URL}/clients/{appointment['client_id']}")
            client_response.raise_for_status()
            client_data = client_response.json()
            logger.info(f"Получен клиент: {client_data}")
            
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
                        text="🔄 Изменить статус",
                        callback_data=AppointmentCallback(action="edit_status", id=appointment_id).pack()
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="👤 Просмотр клиента",
                        callback_data=ViewClientCallback(appointment_id=appointment_id).pack()
                    ),
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
                f"👤 Клиент: {client_data['name']}\n"
                f"📱 Телефон: {client_data['phone_number']}\n"
                f"🚗 Автомобиль: {appointment.get('car_model', 'Не указан')}\n"
                f"{service_info}"
                f"📅 Дата и время: {formatted_time}\n"
                f"📊 Статус: {appointment.get('status', 'pending')}\n"
            )
            
            await callback.message.edit_text(message, reply_markup=keyboard)
            await callback.answer()
            
    except Exception as e:
        logger.error(f"Ошибка при просмотре записи: {e}")
        await callback.answer("❌ Произошла ошибка при получении информации о записи", show_alert=True)

@router.callback_query(AppointmentCallback.filter(F.action.in_(["edit_date", "edit_time", "edit_service", "edit_status", "delete"])))
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
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=status,
                        callback_data=AppointmentCallback(id=appointment_id, action=f"set_status_{status}").pack()
                    )
                ] for status in ["pending", "confirmed", "completed", "cancelled"]
            ]
        )
        await callback.message.edit_text("Выберите новый статус:", reply_markup=keyboard)
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
            service_response = await client.get(f"{API_URL}/services/{service_id}")
            service_response.raise_for_status()
            service = service_response.json()
            
            # Получаем текущую запись
            response = await client.get(f"{API_URL}/appointments/{appointment_id}")
            response.raise_for_status()
            appointment = response.json()
            
            # Обновляем запись с новой услугой
            update_data = {
                "client_id": appointment['client_id'],
                "service_id": service_id,
                "scheduled_time": appointment['scheduled_time'],
                "status": appointment.get('status', 'pending'),
                "car_model": appointment.get('car_model', '')
            }
            
            response = await client.patch(f"{API_URL}/appointments/{appointment_id}", json=update_data)
            response.raise_for_status()
            
            # Получаем обновленную запись
            response = await client.get(f"{API_URL}/appointments/{appointment_id}")
            response.raise_for_status()
            updated_appointment = response.json()
            
            # Получаем информацию о клиенте
            client_response = await client.get(f"{API_URL}/clients/{updated_appointment['client_id']}")
            client_response.raise_for_status()
            client_data = client_response.json()
            
            # Форматируем дату и время
            scheduled_time = datetime.fromisoformat(updated_appointment['scheduled_time'].replace('Z', '+00:00'))
            formatted_time = scheduled_time.strftime("%d.%m.%Y %H:%M")
            
            # Формируем сообщение с информацией о записи
            message = (
                f"📝 Запись #{appointment_id}\n\n"
                f"👤 Клиент: {client_data['name']}\n"
                f"📱 Телефон: {client_data['phone_number']}\n"
                f"🚗 Автомобиль: {updated_appointment.get('car_model', 'Не указан')}\n"
                f"🔧 Услуга: {service['name']}\n"
                f"💰 Стоимость: {service['price']} руб.\n"
                f"📅 Дата и время: {formatted_time}\n"
                f"📊 Статус: {updated_appointment.get('status', 'pending')}\n"
            )
            
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
                        text="🔄 Изменить статус",
                        callback_data=AppointmentCallback(action="edit_status", id=appointment_id).pack()
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="👤 Просмотр клиента",
                        callback_data=ViewClientCallback(appointment_id=appointment_id).pack()
                    ),
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
            
            await callback.message.edit_text(message, reply_markup=keyboard)
            await callback.answer("✅ Услуга успешно изменена!")
            
    except httpx.HTTPError as e:
        if e.response and e.response.status_code == 404:
            await callback.message.edit_text("❌ Услуга не найдена")
        else:
            await callback.message.edit_text(f"❌ Ошибка при обновлении услуги: {str(e)}")
    
    await state.clear()

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