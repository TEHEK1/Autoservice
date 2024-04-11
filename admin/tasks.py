import os
import logging
from datetime import datetime
from aiogram import Bot
from typing import Dict, Any

logger = logging.getLogger(__name__)

def send_notification(appointment_data: Dict[str, Any], notification_type: str) -> None:
    """Отправляет уведомление клиенту"""
    try:
        bot = Bot(token=os.getenv('BOT_TOKEN'))
        
        appointment_time = datetime.fromisoformat(appointment_data["appointment_time"])
        time_str = appointment_time.strftime("%d.%m.%Y %H:%M")
        
        if notification_type == "day":
            message = (
                f"Напоминание! Завтра в {time_str} у вас запись на {appointment_data['service']['name']}. "
                f"Не забудьте о записи!"
            )
        else:  # hour
            message = (
                f"Напоминание! Через час в {time_str} у вас запись на {appointment_data['service']['name']}. "
                f"Не забудьте о записи!"
            )
            
        bot.send_message(
            chat_id=appointment_data["client"]["telegram_id"],
            text=message
        )
        
        logger.info(f"Отправлено уведомление {notification_type} для записи {appointment_data['id']}")
        
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления: {e}")
    finally:
        if 'bot' in locals():
            bot.session.close() 