from aiogram import Router, types, F
from aiogram.filters import Command, StateFilter
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

async def get_client_info(client_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Получение информации о клиенте"""
    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(f"{API_URL}/clients/{client_id}")
            response.raise_for_status()
            client = response.json()
            
            buttons = [
                [
                    InlineKeyboardButton(
                        text="✏️ Изменить имя",
                        callback_data=ClientCallback(action="edit_name", id=client_id).pack()
                    ),
                    InlineKeyboardButton(
                        text="📝 Изменить телефон",
                        callback_data=ClientCallback(action="edit_phone", id=client_id).pack()
                    )
                ],
                [
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
            
            message_text = (
                f"👤 Клиент #{client_id}\n\n"
                f"📝 Имя: {client['name']}\n"
                f"📱 Телефон: {client['phone_number']}\n"
            )
            
            return message_text, keyboard
            
    except Exception as e:
        logger.error(f"Ошибка при получении информации о клиенте: {e}")
        raise

@router.message(Command("clients"))
async def command_clients(message: Message):
    """Показать список клиентов"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/clients")
            response.raise_for_status()
            clients = response.json()
            
            if not clients:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Создать клиента", callback_data="create_client")],
                    [InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu")]
                ])
                await message.answer("👤 Нет доступных клиентов", reply_markup=keyboard)
                return
            
            buttons = []
            for client in clients:
                buttons.append([
                    InlineKeyboardButton(
                        text=f"{client['name']} - {client['phone_number']}",
                        callback_data=ClientCallback(id=client['id'], action="view").pack()
                    )
                ])
            
            buttons.extend([
                [InlineKeyboardButton(text="➕ Создать клиента", callback_data="create_client")],
                [InlineKeyboardButton(text="🏠 В главное меню", callback_data="main_menu")]
            ])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
            await message.answer("👤 Список клиентов:", reply_markup=keyboard)
            
    except Exception as e:
        logger.error(f"Ошибка при получении списка клиентов: {e}")
        await message.answer("❌ Произошла ошибка при получении списка клиентов")

@router.callback_query(ClientCallback.filter(F.action == "edit_name"))
async def process_edit_name(callback: CallbackQuery, callback_data: ClientCallback, state: FSMContext):
    """Обработка изменения имени клиента"""
    try:
        client_id = callback_data.id
        await state.set_state("editing_name")
        await state.update_data(client_id=client_id)
        await callback.message.answer("Введите новое имя клиента:")
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при начале редактирования имени: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

@router.message(StateFilter("editing_name"))
async def process_name_edit(message: Message, state: FSMContext):
    """Обработка нового имени клиента"""
    try:
        data = await state.get_data()
        client_id = data.get('client_id')
        
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{API_URL}/clients/{client_id}",
                json={"name": message.text.strip()}
            )
            response.raise_for_status()
            
            await message.answer("✅ Имя клиента успешно обновлено")
            await state.clear()
            
            message_text, keyboard = await get_client_info(client_id)
            await message.answer(message_text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка при обновлении имени клиента: {e}")
        await message.answer("❌ Произошла ошибка при обновлении имени клиента")

@router.callback_query(lambda c: c.data == "create_client")
async def process_create_client(callback: CallbackQuery, state: FSMContext):
    """Обработка создания клиента"""
    await callback.message.answer("Введите имя клиента:")
    await state.set_state("creating_name")
    await callback.answer()

@router.message(StateFilter("creating_name"))
async def process_create_name(message: Message, state: FSMContext):
    """Обработка имени нового клиента"""
    await state.update_data(name=message.text.strip())
    await message.answer("Введите номер телефона клиента:")
    await state.set_state("creating_phone")

@router.message(StateFilter("creating_phone"))
async def process_create_phone(message: Message, state: FSMContext):
    """Обработка телефона нового клиента"""
    try:
        data = await state.get_data()
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_URL}/clients",
                json={
                    "name": data['name'],
                    "phone_number": message.text.strip()
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

@router.callback_query(ClientCallback.filter(F.action == "view"))
async def process_client_selection(callback: CallbackQuery, callback_data: ClientCallback):
    """Обработка выбора клиента"""
    try:
        client_id = callback_data.id
        message_text, keyboard = await get_client_info(client_id)
        await callback.message.answer(message_text, reply_markup=keyboard)
        await callback.answer()
            
    except Exception as e:
        logger.error(f"Ошибка при просмотре клиента: {e}")
        await callback.answer("❌ Произошла ошибка при получении информации о клиенте", show_alert=True)

@router.callback_query(ClientCallback.filter(F.action == "delete"))
async def process_delete(callback: CallbackQuery, callback_data: ClientCallback, state: FSMContext):
    """Обработка удаления клиента"""
    try:
        client_id = callback_data.id
        
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
                    InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_delete_{client_id}"),
                    InlineKeyboardButton(text="❌ Нет", callback_data="cancel_delete")
                ]
            ])
            await callback.message.answer(
                "⚠️ Вы уверены, что хотите удалить этого клиента?",
                reply_markup=keyboard
            )
            await state.set_state("waiting_for_confirmation")
            await state.update_data(client_id=client_id)
    except Exception as e:
        logger.error(f"Ошибка при начале удаления клиента: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

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

@router.callback_query(lambda c: c.data.startswith("confirm_delete_"))
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

@router.callback_query(ClientCallback.filter(F.action == "edit_phone"))
async def process_edit_phone(callback: CallbackQuery, callback_data: ClientCallback, state: FSMContext):
    """Обработка изменения телефона клиента"""
    try:
        client_id = callback_data.id
        await state.set_state("editing_phone")
        await state.update_data(client_id=client_id)
        await callback.message.answer("Введите новый номер телефона клиента:")
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при начале редактирования телефона: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

@router.message(StateFilter("editing_phone"))
async def process_phone_edit(message: Message, state: FSMContext):
    """Обработка нового телефона клиента"""
    try:
        data = await state.get_data()
        client_id = data.get('client_id')
        
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{API_URL}/clients/{client_id}",
                json={"phone_number": message.text.strip()}
            )
            response.raise_for_status()
            
            await message.answer("✅ Телефон клиента успешно обновлен")
            await state.clear()
            
            message_text, keyboard = await get_client_info(client_id)
            await message.answer(message_text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка при обновлении телефона клиента: {e}")
        await message.answer("❌ Произошла ошибка при обновлении телефона клиента") 