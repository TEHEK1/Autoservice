from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters.callback_data import CallbackData
import httpx
import logging

from aiogram.fsm.state import StatesGroup, State

from ..config import API_URL

logger = logging.getLogger(__name__)

# Создаем роутер для услуг
router = Router()

# Состояния для услуг
class EditServiceState(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_price = State()

class CreateServiceState(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_price = State()

class DeleteServiceState(StatesGroup):
    waiting_for_confirmation = State()

# Callback данные для услуг
class ServiceCallback(CallbackData, prefix="service"):
    id: int
    action: str

class EditServiceCallback(CallbackData, prefix="service"):
    id: int
    field: str

@router.message(Command("services"))
async def command_services(message: Message):
    """Показать список услуг"""
    try:
        async with httpx.AsyncClient() as client:
            # Получаем список услуг
            response = await client.get(f"{API_URL}/services")
            response.raise_for_status()
            services = response.json()
            
            if not services:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Создать услугу", callback_data="create_service")]
                ])
                await message.answer("🔧 Нет доступных услуг", reply_markup=keyboard)
                return
            
            # Создаем кнопки для каждой услуги
            buttons = []
            for service in services:
                buttons.append([
                    InlineKeyboardButton(
                        text=f"{service['name']} - {service['price']}₽",
                        callback_data=ServiceCallback(id=service['id'], action="view").pack()
                    )
                ])
            
            # Добавляем кнопки управления
            buttons.extend([
                [InlineKeyboardButton(text="➕ Создать услугу", callback_data="create_service")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            await message.answer("🔧 Список услуг:", reply_markup=keyboard)
            
    except Exception as e:
        logger.error(f"Ошибка при получении списка услуг: {e}")
        await message.answer("❌ Произошла ошибка при получении списка услуг")

@router.callback_query(lambda c: c.data == "create_service")
async def process_create_service_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите название услуги:")
    await state.set_state(CreateServiceState.waiting_for_name)
    await callback.answer()

@router.callback_query(ServiceCallback.filter(F.action == "view"))
async def process_service_selection(callback: CallbackQuery, callback_data: ServiceCallback):
    """Обработка выбора услуги"""
    try:
        service_id = callback_data.id
        logger.info(f"Получаем информацию об услуге {service_id}")
        
        async with httpx.AsyncClient() as http_client:
            # Получаем информацию об услуге
            response = await http_client.get(f"{API_URL}/services/{service_id}")
            response.raise_for_status()
            service = response.json()
            logger.info(f"Получена услуга: {service}")
            
            # Создаем клавиатуру с кнопками управления
            buttons = [
                [
                    InlineKeyboardButton(
                        text="✏️ Изменить название",
                        callback_data=ServiceCallback(action="edit_name", id=service_id).pack()
                    ),
                    InlineKeyboardButton(
                        text="📝 Изменить описание",
                        callback_data=ServiceCallback(action="edit_description", id=service_id).pack()
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="💰 Изменить цену",
                        callback_data=ServiceCallback(action="edit_price", id=service_id).pack()
                    ),
                    InlineKeyboardButton(
                        text="❌ Удалить услугу",
                        callback_data=ServiceCallback(action="delete", id=service_id).pack()
                    )
                ],
                [
                    InlineKeyboardButton(text="◀️ Назад к списку", callback_data="back_to_services"),
                    InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu")
                ]
            ]
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            
            # Формируем сообщение с информацией об услуге
            message = (
                f"🔧 Услуга #{service_id}\n\n"
                f"📝 Название: {service['name']}\n"
                f"📋 Описание: {service.get('description', 'Не указано')}\n"
                f"💰 Стоимость: {service['price']} руб.\n"
            )
            
            await callback.message.edit_text(message, reply_markup=keyboard)
            await callback.answer()
            
    except Exception as e:
        logger.error(f"Ошибка при просмотре услуги: {e}")
        await callback.answer("❌ Произошла ошибка при получении информации об услуге", show_alert=True)

@router.callback_query(ServiceCallback.filter(F.action.in_(["edit_name", "edit_description", "edit_price", "delete"])))
async def process_edit_service(callback: types.CallbackQuery, callback_data: ServiceCallback, state: FSMContext):
    """Обработка редактирования услуги"""
    service_id = callback_data.id
    action = callback_data.action
    
    if action == "delete":
        # Проверяем, есть ли связанные записи
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/appointments")
            response.raise_for_status()
            appointments = response.json()
            
            # Проверяем, есть ли записи с этой услугой
            service_appointments = [a for a in appointments if a['service_id'] == service_id]
            
            if service_appointments:
                await callback.message.answer(
                    "❌ Невозможно удалить услугу, так как есть связанные записи.\n"
                    "Сначала удалите или измените эти записи."
                )
                return
            
            # Если нет связанных записей, запрашиваем подтверждение
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_delete_service_{service_id}"),
                    InlineKeyboardButton(text="❌ Нет", callback_data="cancel_delete")
                ]
            ])
            await callback.message.answer(
                "⚠️ Вы уверены, что хотите удалить эту услугу?",
                reply_markup=keyboard
            )
            await state.set_state(DeleteServiceState.waiting_for_confirmation)
            await state.update_data(service_id=service_id)
    else:
        # Для других действий устанавливаем соответствующее состояние
        state_mapping = {
            "edit_name": (EditServiceState.waiting_for_name, "Введите новое название услуги:"),
            "edit_description": (EditServiceState.waiting_for_description, "Введите новое описание услуги:"),
            "edit_price": (EditServiceState.waiting_for_price, "Введите новую стоимость услуги (только число):")
        }
        
        if action in state_mapping:
            state_class, message_text = state_mapping[action]
            await state.set_state(state_class)
            await state.update_data(service_id=service_id)
            await callback.message.answer(message_text)
    
    await callback.answer()

@router.callback_query(lambda c: c.data == "back_to_services")
async def back_to_services(callback: types.CallbackQuery):
    """Возврат к списку услуг"""
    await command_services(callback.message)
    await callback.answer()

@router.callback_query(lambda c: c.data == "cancel_delete")
async def cancel_delete(callback: types.CallbackQuery, state: FSMContext):
    """Отмена удаления"""
    await state.clear()
    await callback.message.answer("❌ Удаление отменено")
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("confirm_delete_service_"))
async def confirm_delete_service(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждение удаления услуги"""
    service_id = int(callback.data.split("_")[-1])
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{API_URL}/services/{service_id}")
            response.raise_for_status()
            
            await callback.message.answer("✅ Услуга успешно удалена")
            await state.clear()
            
            # Возвращаемся к списку услуг
            await command_services(callback.message)
    except Exception as e:
        logger.error(f"Ошибка при удалении услуги: {e}")
        await callback.message.answer("❌ Произошла ошибка при удалении услуги")
    
    await callback.answer()

@router.message(EditServiceState.waiting_for_name)
async def process_edit_name(message: Message, state: FSMContext):
    """Обработка нового названия услуги"""
    data = await state.get_data()
    service_id = data.get('service_id')
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{API_URL}/services/{service_id}",
                json={"name": message.text}
            )
            response.raise_for_status()
            
            await message.answer("✅ Название услуги успешно обновлено")
            await state.clear()
            
            # Возвращаемся к списку услуг
            await command_services(message)
    except Exception as e:
        logger.error(f"Ошибка при обновлении названия услуги: {e}")
        await message.answer("❌ Произошла ошибка при обновлении названия услуги")

@router.message(EditServiceState.waiting_for_description)
async def process_edit_description(message: Message, state: FSMContext):
    """Обработка нового описания услуги"""
    data = await state.get_data()
    service_id = data.get('service_id')
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{API_URL}/services/{service_id}",
                json={"description": message.text}
            )
            response.raise_for_status()
            
            await message.answer("✅ Описание услуги успешно обновлено")
            await state.clear()
            
            # Возвращаемся к списку услуг
            await command_services(message)
    except Exception as e:
        logger.error(f"Ошибка при обновлении описания услуги: {e}")
        await message.answer("❌ Произошла ошибка при обновлении описания услуги")

@router.message(EditServiceState.waiting_for_price)
async def process_edit_price(message: Message, state: FSMContext):
    """Обработка новой цены услуги"""
    try:
        price = float(message.text)
        data = await state.get_data()
        service_id = data.get('service_id')
        
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{API_URL}/services/{service_id}",
                json={"price": price}
            )
            response.raise_for_status()
            
            await message.answer("✅ Стоимость услуги успешно обновлена")
            await state.clear()
            
            # Возвращаемся к списку услуг
            await command_services(message)
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректное число")
    except Exception as e:
        logger.error(f"Ошибка при обновлении стоимости услуги: {e}")
        await message.answer("❌ Произошла ошибка при обновлении стоимости услуги")

@router.message(CreateServiceState.waiting_for_name)
async def process_create_name(message: Message, state: FSMContext):
    """Обработка названия новой услуги"""
    await state.update_data(name=message.text)
    await message.answer("Введите описание услуги:")
    await state.set_state(CreateServiceState.waiting_for_description)

@router.message(CreateServiceState.waiting_for_description)
async def process_create_description(message: Message, state: FSMContext):
    """Обработка описания новой услуги"""
    await state.update_data(description=message.text)
    await message.answer("Введите стоимость услуги (только число):")
    await state.set_state(CreateServiceState.waiting_for_price)

@router.message(CreateServiceState.waiting_for_price)
async def process_create_price(message: Message, state: FSMContext):
    """Обработка цены новой услуги"""
    try:
        price = float(message.text)
        data = await state.get_data()
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_URL}/services",
                json={
                    "name": data['name'],
                    "description": data['description'],
                    "price": price
                }
            )
            response.raise_for_status()
            
            await message.answer("✅ Услуга успешно создана")
            await state.clear()
            
            # Возвращаемся к списку услуг
            await command_services(message)
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректное число")
    except Exception as e:
        logger.error(f"Ошибка при создании услуги: {e}")
        await message.answer("❌ Произошла ошибка при создании услуги") 