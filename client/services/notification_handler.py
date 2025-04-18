import asyncio
import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import aioredis
import os
from aiogram import Bot
from typing import Dict, Any, Optional

from ..config import API_URL

logger = logging.getLogger(__name__)

class NotificationHandler:
    """Обработчик уведомлений для клиентского бота"""
    
    def __init__(self, bot: Bot):
        """Инициализация обработчика уведомлений
        
        Args:
            bot (Bot): Экземпляр бота для отправки сообщений
        """
        self.bot = bot
        self.redis_conn = None
        self.pubsub = None
        
    async def start_listening(self) -> None:
        """Запускает прослушивание уведомлений из Redis"""
        logger.info("Запуск обработчика уведомлений...")
        
        # Инициализация Redis соединения
        self.redis_conn = await aioredis.from_url("redis://localhost:6379")
        self.pubsub = self.redis_conn.pubsub()
        await self.pubsub.subscribe("notifications")
        
        while True:
            try:
                message = await self.pubsub.get_message(ignore_subscribe_messages=True)
                if message and message["type"] == "message":
                    await self._handle_notification(message["data"])
            except Exception as e:
                logger.error(f"Ошибка при обработке уведомления: {e}")
                await asyncio.sleep(1)  # Пауза перед повторной попыткой
                
    async def _handle_notification(self, data: bytes) -> None:
        """Обрабатывает полученное уведомление
        
        Args:
            data (bytes): Данные уведомления в формате JSON
        """
        try:
            payload = json.loads(data)
            await self._send_telegram_notification(payload)
                
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка декодирования JSON: {e}")
        except Exception as e:
            logger.error(f"Ошибка при обработке уведомления: {e}")
            
    async def _send_telegram_notification(self, payload: Dict[str, Any]) -> None:
        """Отправляет уведомление в Telegram
        
        Args:
            payload (Dict[str, Any]): Данные уведомления
        """
        try:
            async with httpx.AsyncClient() as client:
                logger.info(f"payload = {payload}")
                client_id = payload.get("client_id")
                response = await client.get(f"{API_URL}/clients/{client_id}")
                response.raise_for_status()
                chat_id = response.json()["telegram_id"]
                appointment_id = payload.get("appointment_id")
                if appointment_id:
                    response = await client.get(f"{API_URL}/appointments/{appointment_id}")
                    response.raise_for_status()
                    appointment = response.json()
                    response = await client.get(f"{API_URL}/services/{appointment['service_id']}")
                    response.raise_for_status()
                    service = response.json()
                    response = await client.get(
                        f"{API_URL}/clients/search",
                        params={"telegram_id": str(chat_id)}
                    )
                    response.raise_for_status()
                    current_client = response.json()
                    client_timezone = current_client.get('timezone', 'Europe/Moscow')
                    scheduled_time = datetime.fromisoformat(appointment['scheduled_time'].replace('Z', '+00:00')).replace(tzinfo=ZoneInfo("UTC"))
                    local_time = scheduled_time.astimezone(ZoneInfo(client_timezone))
                    message = f"Вы записаны на услугу {service['name']} {local_time.strftime('%d.%m.%Y')} в {local_time.strftime('%H:%M')}"
                else:
                    message = payload.get("text")

                if not client_id or not message:
                    logger.error("Отсутствуют обязательные поля в payload")
                    return
                
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=message
                )
            
                logger.info(f"Отправлено уведомление в Telegram для chat_id: {chat_id}")
            
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления в Telegram: {e}")
            
    async def stop(self) -> None:
        """Останавливает обработчик уведомлений"""
        if self.redis_conn:
            await self.redis_conn.close() 