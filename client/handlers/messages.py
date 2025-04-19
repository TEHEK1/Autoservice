from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging
import httpx
from datetime import datetime
import json
from typing import Union

from ..config import API_URL

router = Router()
logger = logging.getLogger(__name__)

class MessageState(StatesGroup):
    waiting_for_text = State()

class MessageCallback:
    def __init__(self, action: str, message_id: int = None):
        self.action = action
        self.message_id = message_id
    
    def pack(self) -> str:
        data = {"a": self.action}
        if self.message_id is not None:
            data["id"] = self.message_id
        return json.dumps(data)
    
    @classmethod
    def unpack(cls, callback_data: str) -> "MessageCallback":
        data = json.loads(callback_data)
        return cls(
            action=data.get("a", ""),
            message_id=data.get("id")
        )

# Клавиатура с сообщениями
def get_messages_keyboard(messages_list, client_id):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    for message in messages_list:
        # Статус сообщения (прочитано/не прочитано)
        status = "✓" if message.get("is_read") else "🆕"
        
        # Получаем начало текста сообщения для отображения в кнопке
        message_preview = message.get('text', '')[:20] + ('...' if len(message.get('text', '')) > 20 else '')
        
        # Форматируем дату
        created_at = message.get('created_at', '').split('T')[0]
        
        # Определяем тип сообщения (входящее/исходящее)
        message_type = "⬅️" if message.get("is_from_admin") == 1 else "➡️"
        
        # Добавляем кнопку для каждого сообщения
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{status} {message_type} {message_preview} ({created_at})",
                callback_data=MessageCallback(
                    action="view",
                    message_id=message.get("id")
                ).pack()
            )
        ])
    
    # Добавляем кнопки для создания нового сообщения и возврата в меню
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(
            text="✉️ Написать сообщение", 
            callback_data=MessageCallback(action="create").pack()
        )
    ])
    
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(
            text="🏠 В главное меню", 
            callback_data="main_menu"
        )
    ])
    
    return keyboard

@router.message(Command("messages"))
async def show_messages(message: types.Message):
    """Показать список сообщений"""
    await show_messages_list(message)

async def show_messages_list(message_or_callback: Union[types.Message, CallbackQuery]):
    """Общая функция для отображения списка сообщений"""
    try:
        # Получаем telegram_id пользователя
        user_id = message_or_callback.from_user.id
        client_id = await get_client_id_by_telegram(user_id)
        
        if not client_id:
            text = "Вы не зарегистрированы. Пожалуйста, пройдите регистрацию."
            if isinstance(message_or_callback, types.Message):
                await message_or_callback.answer(text)
            else:
                await message_or_callback.message.edit_text(text)
            return
        
        async with httpx.AsyncClient() as client:
            # Запрашиваем список сообщений для данного пользователя
            response = await client.get(f"{API_URL}/messages/?user_id={client_id}")
            
            if response.status_code == 200:
                messages = response.json()
                
                if not messages:
                    text = "У вас нет сообщений"
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(
                            text="✉️ Написать сообщение", 
                            callback_data=MessageCallback(action="create").pack()
                        )],
                        [InlineKeyboardButton(
                            text="🏠 В главное меню", 
                            callback_data="main_menu"
                        )]
                    ])
                else:
                    text = "📬 Ваши сообщения:"
                    keyboard = get_messages_keyboard(messages, client_id)
                
                if isinstance(message_or_callback, types.Message):
                    await message_or_callback.answer(text, reply_markup=keyboard)
                else:
                    await message_or_callback.message.edit_text(text, reply_markup=keyboard)
            else:
                error_text = "Ошибка при получении списка сообщений"
                if isinstance(message_or_callback, types.Message):
                    await message_or_callback.answer(error_text)
                else:
                    await message_or_callback.message.edit_text(error_text)
    except Exception as e:
        logger.error(f"Ошибка при получении списка сообщений: {e}")
        error_text = "Произошла ошибка при получении списка сообщений"
        if isinstance(message_or_callback, types.Message):
            await message_or_callback.answer(error_text)
        else:
            await message_or_callback.message.edit_text(error_text)

# Добавляем обработчик для колбэка из главного меню        
@router.callback_query(F.data == "messages")
async def handle_message_menu(callback: CallbackQuery):
    """Обработка перехода в раздел сообщений из главного меню"""
    await show_messages_list(callback)
        
@router.callback_query(lambda c: c.data.startswith("{"))
async def process_message_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка callback-запросов связанных с сообщениями"""
    try:
        # Распаковываем данные callback
        cb_data = MessageCallback.unpack(callback.data)
        
        # Различные действия в зависимости от типа callback
        if cb_data.action == "view":
            await view_message(callback, cb_data.message_id)
        elif cb_data.action == "create":
            await start_create_message(callback, state)
        elif cb_data.action == "reply":
            await start_reply_message(callback, cb_data.message_id, state)
        elif cb_data.action == "delete":
            await delete_message(callback, cb_data.message_id)
        elif cb_data.action == "back":
            await show_messages_list(callback)
    except Exception as e:
        logger.error(f"Ошибка при обработке callback сообщения: {e}")
        await callback.message.edit_text("Произошла ошибка. Пожалуйста, попробуйте позже.")

async def view_message(callback: CallbackQuery, message_id: int):
    """Просмотр детальной информации о сообщении и истории переписки"""
    try:
        # Получаем telegram_id пользователя
        user_id = callback.from_user.id
        client_id = await get_client_id_by_telegram(user_id)
        
        if not client_id:
            await callback.message.edit_text("Вы не зарегистрированы. Пожалуйста, пройдите регистрацию.")
            return
            
        async with httpx.AsyncClient() as client:
            # Получаем информацию о сообщении
            response = await client.get(f"{API_URL}/messages/{message_id}")
            
            if response.status_code == 200:
                message_data = response.json()
                
                # Получаем историю переписки
                history_response = await client.get(f"{API_URL}/messages/?user_id={client_id}")
                
                if history_response.status_code == 200:
                    messages_history = history_response.json()
                    
                    # Сортируем сообщения по дате (от старых к новым)
                    messages_history.sort(key=lambda x: x["created_at"])
                    
                    # Формируем текст с историей переписки
                    history_text = f"💬 Переписка с администратором:\n\n"
                    
                    for hist_msg in messages_history:
                        # Определяем направление сообщения
                        direction = "➡️ Вы:" if hist_msg["is_from_admin"] == 0 else "⬅️ Администратор:"
                        
                        # Форматируем дату
                        created_at = datetime.fromisoformat(hist_msg["created_at"])
                        date_str = created_at.strftime("%d.%m.%Y %H:%M")
                        
                        # Добавляем сообщение в историю
                        msg_text = hist_msg["text"]
                        # Выделяем текущее сообщение
                        if hist_msg["id"] == message_id:
                            msg_text = f"➤ {msg_text}"
                            
                        history_text += f"{direction} ({date_str})\n{msg_text}\n\n"
                    
                    # Создаем клавиатуру
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(
                            text="↩️ Ответить", 
                            callback_data=MessageCallback(action="reply", message_id=message_id).pack()
                        )],
                        [InlineKeyboardButton(
                            text="❌ Удалить", 
                            callback_data=MessageCallback(action="delete", message_id=message_id).pack()
                        )],
                        [InlineKeyboardButton(
                            text="🔙 Назад к списку", 
                            callback_data=MessageCallback(action="back").pack()
                        )]
                    ])
                    
                    await callback.message.edit_text(history_text, reply_markup=keyboard)
                    
                    # Если сообщение не прочитано и это входящее сообщение, помечаем его как прочитанное
                    if message_data["is_read"] == 0 and message_data["is_from_admin"] == 1:
                        await client.put(f"{API_URL}/messages/read/{message_id}")
                else:
                    await callback.message.edit_text("Ошибка при получении истории переписки")
            else:
                await callback.message.edit_text("Ошибка при получении информации о сообщении")
    except Exception as e:
        logger.error(f"Ошибка при просмотре сообщения: {e}")
        await callback.message.edit_text("Произошла ошибка при просмотре сообщения")

async def start_create_message(callback: CallbackQuery, state: FSMContext):
    """Начать создание нового сообщения"""
    await callback.message.edit_text("Введите текст сообщения:")
    await state.set_state(MessageState.waiting_for_text)

async def start_reply_message(callback: CallbackQuery, message_id: int, state: FSMContext):
    """Начать ответ на сообщение"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/messages/{message_id}")
            
            if response.status_code == 200:
                message_data = response.json()
                
                # Сохраняем информацию для последующего использования
                await state.update_data(
                    reply_to_id=message_id
                )
                
                await callback.message.edit_text("Введите текст сообщения:")
                await state.set_state(MessageState.waiting_for_text)
            else:
                await callback.message.edit_text("Ошибка при получении информации о сообщении")
    except Exception as e:
        logger.error(f"Ошибка при начале ответа на сообщение: {e}")
        await callback.message.edit_text("Произошла ошибка при начале ответа на сообщение")

async def delete_message(callback: CallbackQuery, message_id: int):
    """Удалить сообщение"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{API_URL}/messages/{message_id}")
            
            if response.status_code == 200:
                await callback.message.edit_text("✅ Сообщение успешно удалено")
                
                # Показываем список сообщений
                await show_messages_list(callback)
            else:
                await callback.message.edit_text("Ошибка при удалении сообщения")
    except Exception as e:
        logger.error(f"Ошибка при удалении сообщения: {e}")
        await callback.message.edit_text("Произошла ошибка при удалении сообщения")

@router.message(MessageState.waiting_for_text)
async def process_text(message: types.Message, state: FSMContext):
    """Обработать текст сообщения и отправить его"""
    try:
        data = await state.get_data()
        from_user_id = await get_client_id_by_telegram(message.from_user.id)
        
        if not from_user_id:
            await message.answer("Вы не зарегистрированы. Пожалуйста, пройдите регистрацию.")
            await state.clear()
            return
        
        message_data = {
            "text": message.text,
            "user_id": from_user_id,
            "is_from_admin": 0,  # Сообщение от клиента
            "is_read": 0
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{API_URL}/messages/", json=message_data)
            if response.status_code == 200:
                await message.answer("✅ Сообщение успешно отправлено")
                
                # Показываем список сообщений
                await show_messages(message)
            else:
                await message.answer("Ошибка при отправке сообщения")
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения: {e}")
        await message.answer("Произошла ошибка при отправке сообщения")
    finally:
        await state.clear()

async def get_client_id_by_telegram(telegram_id: int) -> int:
    """Получить ID клиента по Telegram ID"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/clients/search", params={"telegram_id": str(telegram_id)})
            if response.status_code == 200:
                client_data = response.json()
                return client_data.get("id")
            else:
                logger.error(f"Ошибка при получении ID клиента: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Ошибка при получении ID клиента: {e}")
    return None 