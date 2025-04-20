from typing import Dict, Any, Awaitable, Callable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
import hashlib
import logging
from ..config import ADMIN_PASSWORD_HASH

logger = logging.getLogger(__name__)

# Словарь для хранения авторизованных пользователей
authorized_users = {}

def verify_password(password: str) -> bool:
    """Проверка пароля администратора"""
    # Хешируем введенный пароль
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    logger.info(f"Проверка пароля: {password_hash}")
    # Сравниваем хеши
    return password_hash == ADMIN_PASSWORD_HASH

class AuthMiddleware(BaseMiddleware):
    """Middleware для проверки авторизации администратора"""
    
    async def __call__(
        self, 
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем состояние FSM
        state = data.get('state')
        
        # Если сообщение содержит пароль, пропускаем проверку
        if isinstance(event, Message) and state:
            current_state = await state.get_state()
            logger.info(f"Текущее состояние: {current_state}")
            if current_state and 'waiting_for_password' in str(current_state):
                logger.info(f"Пропускаем проверку авторизации для состояния {current_state}")
                return await handler(event, data)
                
        # Пропускаем проверку для команды /start
        if isinstance(event, Message) and event.text and event.text.startswith('/start'):
            user_id = event.from_user.id
            logger.info(f"Пропускаем проверку авторизации для команды /start от пользователя {user_id}")
            return await handler(event, data)
                
        # Для всех остальных запросов проверяем авторизацию
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
        else:
            # Если не смогли определить пользователя
            logger.warning("Не удалось определить пользователя в запросе")
            return None
            
        # Проверяем авторизован ли пользователь
        if user_id not in authorized_users:
            logger.info(f"Пользователь {user_id} не авторизован - запрос отклонен")
            
            # Сообщаем пользователю о необходимости войти в систему
            if isinstance(event, Message):
                await event.answer("⚠️ Вы не авторизованы. Используйте команду /start для входа в систему.")
            elif isinstance(event, CallbackQuery):
                await event.answer("⚠️ Вы не авторизованы. Используйте команду /start для входа в систему.", show_alert=True)
                
            return None
            
        # Пользователь авторизован, пропускаем запрос дальше
        return await handler(event, data) 