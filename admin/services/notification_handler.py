import aioredis
import json
import logging
from aiogram import Bot
from datetime import datetime
import httpx
import os
from ..config import API_URL

logger = logging.getLogger(__name__)

class NotificationHandler:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.redis = None
        self.pubsub = None

    async def start_listening(self):
        """Запуск прослушивания уведомлений"""
        try:
            redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
            self.redis = await aioredis.from_url(redis_url)
            self.pubsub = self.redis.pubsub()
            await self.pubsub.subscribe("notifications")
            
            while True:
                message = await self.pubsub.get_message(ignore_subscribe_messages=True)
                if message:
                    await self._handle_notification(message)
        except Exception as e:
            logger.error(f"Ошибка при прослушивании уведомлений: {e}")
            raise

    async def stop(self):
        """Остановка прослушивания уведомлений"""
        if self.pubsub:
            await self.pubsub.unsubscribe("notifications")
        if self.redis:
            await self.redis.close()

    async def _handle_notification(self, message):
        """Обработка уведомления"""
        try:
            data = json.loads(message["data"])
            notification_type = data.get("type")
            
            if notification_type == "new_message":
                await self._handle_new_message(data)
            elif notification_type == "appointment_reminder":
                await self._handle_appointment_reminder(data)
            elif notification_type == "appointment_status":
                await self._handle_appointment_status(data)
            elif notification_type == "new_appointment":
                await self._handle_new_appointment(data)
        except Exception as e:
            logger.error(f"Ошибка при обработке уведомления: {e}")

    async def _handle_new_message(self, data):
        """Обработка нового сообщения"""
        try:
            message = data.get("message", {})
            # Используем новую структуру сообщений
            user_id = message.get("user_id")
            is_from_admin = message.get("is_from_admin", 0)
            
            # Обрабатываем только сообщения от клиентов (не от админа)
            if user_id and is_from_admin == 0:
                # Получаем информацию о клиенте
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{API_URL}/clients/{user_id}")
                    if response.status_code == 200:
                        client_data = response.json()
                        client_name = client_data.get("name", "Неизвестный клиент")
                        
                        text = (
                            f"📨 Новое сообщение от клиента!\n\n"
                            f"👤 От: {client_name}\n"
                            f"📝 Текст: {message.get('text', '')}\n"
                            f"📅 Дата: {message.get('created_at', datetime.now().isoformat())}"
                        )
                        
                        # Отправляем сообщение администратору (в группу или лично)
                        admin_chat_id = 580866264  # ID администратора или группы (настроить в конфиге)
                        
                        await self.bot.send_message(chat_id=admin_chat_id, text=text)
                        logger.info(f"Отправлено уведомление администратору о новом сообщении от клиента {client_name}")
            else:
                logger.info("Получено сообщение от администратора, пропускаем отправку уведомления")
                
        except Exception as e:
            logger.error(f"Ошибка при обработке нового сообщения: {e}")

    async def _handle_appointment_reminder(self, data):
        """Обработка напоминания о записи"""
        try:
            appointment = data.get("appointment", {})
            user_id = appointment.get("client_id")
            
            if user_id:
                scheduled_time = datetime.fromisoformat(appointment.get("scheduled_time"))
                
                text = (
                    f"⏰ Напоминание о записи!\n\n"
                    f"📅 Дата: {scheduled_time.strftime('%d.%m.%Y')}\n"
                    f"⏰ Время: {scheduled_time.strftime('%H:%M')}\n"
                    f"🔧 Услуга: {appointment.get('service_name', 'Неизвестная услуга')}\n"
                    f"💰 Стоимость: {appointment.get('service_price', 0)} руб."
                )
                
                await self.bot.send_message(chat_id=user_id, text=text)
        except Exception as e:
            logger.error(f"Ошибка при обработке напоминания о записи: {e}")

    async def _handle_appointment_status(self, data):
        """Обработка изменения статуса записи"""
        try:
            appointment = data.get("appointment", {})
            user_id = appointment.get("client_id")
            status = appointment.get("status")
            
            if user_id and status:
                status_text = {
                    "confirmed": "✅ подтверждена",
                    "cancelled": "❌ отменена",
                    "completed": "✔️ выполнена"
                }.get(status, status)
                
                text = (
                    f"📝 Статус вашей записи изменен!\n\n"
                    f"📅 Дата: {appointment.get('scheduled_time', 'Неизвестно')}\n"
                    f"🔧 Услуга: {appointment.get('service_name', 'Неизвестная услуга')}\n"
                    f"📊 Новый статус: {status_text}"
                )
                
                await self.bot.send_message(chat_id=user_id, text=text)
        except Exception as e:
            logger.error(f"Ошибка при обработке изменения статуса записи: {e}")
            
    async def _handle_new_appointment(self, data):
        """Обработка уведомления о новой записи"""
        try:
            appointment = data.get("appointment", {})
            
            # Получаем информацию о клиенте
            async with httpx.AsyncClient() as client:
                client_response = await client.get(f"{API_URL}/clients/{appointment.get('client_id')}")
                service_response = await client.get(f"{API_URL}/services/{appointment.get('service_id')}")
                
                client_name = "Неизвестно"
                service_name = "Неизвестно"
                
                if client_response.status_code == 200:
                    client_data = client_response.json()
                    client_name = client_data.get("name", "Неизвестно")
                    
                if service_response.status_code == 200:
                    service_data = service_response.json()
                    service_name = service_data.get("name", "Неизвестно")
                    
                # Форматируем дату и время
                scheduled_time = datetime.fromisoformat(appointment.get("scheduled_time").replace('Z', '+00:00'))
                formatted_date = scheduled_time.strftime("%d.%m.%Y")
                formatted_time = scheduled_time.strftime("%H:%M")
                
                text = (
                    f"🆕 Новая запись требует подтверждения!\n\n"
                    f"👤 Клиент: {client_name}\n"
                    f"🔧 Услуга: {service_name}\n"
                    f"🚗 Модель авто: {appointment.get('car_model', 'Не указана')}\n"
                    f"📅 Дата: {formatted_date}\n"
                    f"⏰ Время: {formatted_time}\n"
                    f"📊 Статус: {appointment.get('status', 'pending')}"
                )
                
                # Создаем клавиатуру для быстрого подтверждения/отклонения
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="✅ Подтвердить",
                            callback_data=f"appointment_confirm_{appointment.get('id')}"
                        ),
                        InlineKeyboardButton(
                            text="❌ Отклонить",
                            callback_data=f"appointment_reject_{appointment.get('id')}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="👁️ Просмотреть детали",
                            callback_data=f"appointment_view_{appointment.get('id')}"
                        )
                    ]
                ])
                
                # Отправляем сообщение администраторам
                admin_chat_id = 580866264  # ID администратора или группы (настроить в конфиге)
                await self.bot.send_message(
                    chat_id=admin_chat_id,
                    text=text,
                    reply_markup=keyboard
                )
                
                logger.info(f"Отправлено уведомление администратору о новой записи от клиента {client_name}")
                
        except Exception as e:
            logger.error(f"Ошибка при обработке уведомления о новой записи: {e}") 