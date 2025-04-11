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

# Создаем роутер для клиентов
router = Router()

# Состояния для клиентов
class EditClientState(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_car = State()

class CreateClientState(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_car = State()

class DeleteClientState(StatesGroup):
    waiting_for_confirmation = State()

# Callback данные для клиентов
class ClientCallback(CallbackData, prefix="client"):
    id: int
    action: str

class EditClientCallback(CallbackData, prefix="client"):
    id: int
    field: str

@router.message(Command("clients"))
async def command_clients(message: Message):
    """Показать список клиентов"""
    try:
        async with httpx.AsyncClient() as client:
            # Получаем список клиентов
            response = await client.get(f"{API_URL}/clients")
            response.raise_for_status()
            clients = response.json()
            
            if not clients:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Создать клиента", callback_data="create_client")]
                ])
                await message.answer("👤 Нет доступных клиентов", reply_markup=keyboard)
                return
            
            # Создаем кнопки для каждого клиента
            buttons = []
            for client in clients:
                buttons.append([
                    InlineKeyboardButton(
                        text=f"{client['name']} - {client['phone_number']}",
                        callback_data=ClientCallback(id=client['id'], action="view").pack()
                    )
                ])
            
            # Добавляем кнопки управления
            buttons.extend([
                [InlineKeyboardButton(text="➕ Создать клиента", callback_data="create_client")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            await message.answer("👤 Список клиентов:", reply_markup=keyboard)
            
    except Exception as e:
        logger.error(f"Ошибка при получении списка клиентов: {e}")
        await message.answer("❌ Произошла ошибка при получении списка клиентов")

@router.callback_query(lambda c: c.data == "create_client")
async def process_create_client_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите имя клиента:")
    await state.set_state(CreateClientState.waiting_for_name)
    await callback.answer()

@router.callback_query(ClientCallback.filter(F.action == "view"))
async def process_client_selection(callback: CallbackQuery, callback_data: ClientCallback):
    """Обработка выбора клиента"""
    try:
        client_id = callback_data.id
        logger.info(f"Получаем информацию о клиенте {client_id}")
        
        async with httpx.AsyncClient() as http_client:
            # Получаем информацию о клиенте
            response = await http_client.get(f"{API_URL}/clients/{client_id}")
            response.raise_for_status()
            client = response.json()
            logger.info(f"Получен клиент: {client}")
            
            # Создаем клавиатуру с кнопками управления
            buttons = [
                [
                    InlineKeyboardButton(
                        text="✏️ Изменить имя",
                        callback_data=ClientCallback(action="edit_name", id=client_id).pack()
                    ),
                    InlineKeyboardButton(
                        text="📱 Изменить телефон",
                        callback_data=ClientCallback(action="edit_phone", id=client_id).pack()
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🚗 Изменить автомобиль",
                        callback_data=ClientCallback(action="edit_car", id=client_id).pack()
                    ),
                    InlineKeyboardButton(
                        text="❌ Удалить клиента",
                        callback_data=ClientCallback(action="delete", id=client_id).pack()
                    )
                ],
                [
                    InlineKeyboardButton(text="◀️ Назад к списку", callback_data="back_to_clients"),
                    InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu")
                ]
            ]
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            
            # Формируем сообщение с информацией о клиенте
            message = (
                f"👤 Клиент #{client_id}\n\n"
                f"📝 Имя: {client['name']}\n"
                f"📱 Телефон: {client['phone_number']}\n"
                f"🚗 Автомобиль: {client.get('car_model', 'Не указан')}\n"
            )
            
            await callback.message.edit_text(message, reply_markup=keyboard)
            await callback.answer()
            
    except Exception as e:
        logger.error(f"Ошибка при просмотре клиента: {e}")
        await callback.answer("❌ Произошла ошибка при получении информации о клиенте", show_alert=True)

@router.callback_query(ClientCallback.filter(F.action.in_(["edit_name", "edit_phone", "edit_car", "delete"])))
async def process_edit_client(callback: types.CallbackQuery, callback_data: ClientCallback, state: FSMContext):
    """Обработка редактирования клиента"""
    client_id = callback_data.id
    action = callback_data.action
    
    if action == "delete":
        # Проверяем, есть ли связанные записи
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/appointments")
            response.raise_for_status()
            appointments = response.json()
            
            # Проверяем, есть ли записи с этим клиентом
            client_appointments = [a for a in appointments if a['client_id'] == client_id]
            
            if client_appointments:
                await callback.message.answer(
                    "❌ Невозможно удалить клиента, так как есть связанные записи.\n"
                    "Сначала удалите или измените эти записи."
                )
                return
            
            # Если нет связанных записей, запрашиваем подтверждение
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_delete_client_{client_id}"),
                    InlineKeyboardButton(text="❌ Нет", callback_data="cancel_delete")
                ]
            ])
            await callback.message.answer(
                "⚠️ Вы уверены, что хотите удалить этого клиента?",
                reply_markup=keyboard
            )
            await state.set_state(DeleteClientState.waiting_for_confirmation)
            await state.update_data(client_id=client_id)
    else:
        # Для других действий устанавливаем соответствующее состояние
        state_mapping = {
            "edit_name": (EditClientState.waiting_for_name, "Введите новое имя клиента:"),
            "edit_phone": (EditClientState.waiting_for_phone, "Введите новый номер телефона клиента:"),
            "edit_car": (EditClientState.waiting_for_car, "Введите новую модель автомобиля клиента:")
        }
        
        if action in state_mapping:
            state_class, message_text = state_mapping[action]
            await state.set_state(state_class)
            await state.update_data(client_id=client_id)
            await callback.message.answer(message_text)
    
    await callback.answer()

@router.callback_query(lambda c: c.data == "back_to_clients")
async def back_to_clients(callback: types.CallbackQuery):
    """Возврат к списку клиентов"""
    await command_clients(callback.message)
    await callback.answer()

@router.callback_query(lambda c: c.data == "cancel_delete")
async def cancel_delete(callback: types.CallbackQuery, state: FSMContext):
    """Отмена удаления"""
    await state.clear()
    await callback.message.answer("❌ Удаление отменено")
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("confirm_delete_client_"))
async def confirm_delete_client(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждение удаления клиента"""
    client_id = int(callback.data.split("_")[-1])
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{API_URL}/clients/{client_id}")
            response.raise_for_status()
            
            await callback.message.answer("✅ Клиент успешно удален")
            await state.clear()
            
            # Возвращаемся к списку клиентов
            await command_clients(callback.message)
    except Exception as e:
        logger.error(f"Ошибка при удалении клиента: {e}")
        await callback.message.answer("❌ Произошла ошибка при удалении клиента")
    
    await callback.answer()

@router.message(EditClientState.waiting_for_name)
async def process_edit_name(message: Message, state: FSMContext):
    """Обработка нового имени клиента"""
    data = await state.get_data()
    client_id = data.get('client_id')
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{API_URL}/clients/{client_id}",
                json={"name": message.text}
            )
            response.raise_for_status()
            
            await message.answer("✅ Имя клиента успешно обновлено")
            await state.clear()
            
            # Возвращаемся к списку клиентов
            await command_clients(message)
    except Exception as e:
        logger.error(f"Ошибка при обновлении имени клиента: {e}")
        await message.answer("❌ Произошла ошибка при обновлении имени клиента")

@router.message(EditClientState.waiting_for_phone)
async def process_edit_phone(message: Message, state: FSMContext):
    """Обработка нового телефона клиента"""
    data = await state.get_data()
    client_id = data.get('client_id')
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{API_URL}/clients/{client_id}",
                json={"phone_number": message.text}
            )
            response.raise_for_status()
            
            await message.answer("✅ Телефон клиента успешно обновлен")
            await state.clear()
            
            # Возвращаемся к списку клиентов
            await command_clients(message)
    except Exception as e:
        logger.error(f"Ошибка при обновлении телефона клиента: {e}")
        await message.answer("❌ Произошла ошибка при обновлении телефона клиента")

@router.message(EditClientState.waiting_for_car)
async def process_edit_car(message: Message, state: FSMContext):
    """Обработка новой модели автомобиля клиента"""
    data = await state.get_data()
    client_id = data.get('client_id')
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{API_URL}/clients/{client_id}",
                json={"car_model": message.text}
            )
            response.raise_for_status()
            
            await message.answer("✅ Модель автомобиля клиента успешно обновлена")
            await state.clear()
            
            # Возвращаемся к списку клиентов
            await command_clients(message)
    except Exception as e:
        logger.error(f"Ошибка при обновлении модели автомобиля клиента: {e}")
        await message.answer("❌ Произошла ошибка при обновлении модели автомобиля клиента")

@router.message(CreateClientState.waiting_for_name)
async def process_create_name(message: Message, state: FSMContext):
    """Обработка имени нового клиента"""
    await state.update_data(name=message.text)
    await message.answer("Введите номер телефона клиента:")
    await state.set_state(CreateClientState.waiting_for_phone)

@router.message(CreateClientState.waiting_for_phone)
async def process_create_phone(message: Message, state: FSMContext):
    """Обработка телефона нового клиента"""
    await state.update_data(phone_number=message.text)
    await message.answer("Введите модель автомобиля клиента:")
    await state.set_state(CreateClientState.waiting_for_car)

@router.message(CreateClientState.waiting_for_car)
async def process_create_car(message: Message, state: FSMContext):
    """Обработка модели автомобиля нового клиента"""
    try:
        data = await state.get_data()
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_URL}/clients",
                json={
                    "name": data['name'],
                    "phone_number": data['phone_number'],
                    "car_model": message.text
                }
            )
            response.raise_for_status()
            
            await message.answer("✅ Клиент успешно создан")
            await state.clear()
            
            # Возвращаемся к списку клиентов
            await command_clients(message)
    except Exception as e:
        logger.error(f"Ошибка при создании клиента: {e}")
        await message.answer("❌ Произошла ошибка при создании клиента") 