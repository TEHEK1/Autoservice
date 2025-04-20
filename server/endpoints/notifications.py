from datetime import datetime
import logging
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Any, List, Optional
import json
import redis
from rq_scheduler import Scheduler
import os
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
router = APIRouter()

# Получаем URL Redis из переменной окружения или используем значение по умолчанию
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_conn = redis.Redis.from_url(REDIS_URL)
scheduler = Scheduler(connection=redis_conn)

class NotificationPayload(BaseModel):
    scheduled_time: datetime
    client_id: int
    payload: dict[str, Any]

class NotificationInfo(BaseModel):
    id: str
    scheduled_time: datetime
    client_id: int
    payload: dict[str, Any]

@router.get("", response_model=List[NotificationInfo])
async def get_notifications(client_id: Optional[int] = Query(default=None)):
    """Получает список всех запланированных уведомлений"""
    try:
        jobs = scheduler.get_jobs()
        notifications = []
        for job in jobs:
            if job.func_name == "send_notification":
                payload = job.args[0]
                # Фильтруем по client_id, если он указан
                if client_id is None or payload.get("client_id") == client_id:
                    notifications.append(NotificationInfo(
                        id=job.id,
                        scheduled_time=job.scheduled_time,
                        client_id=payload.get("client_id"),
                        payload=payload
                    ))
        return notifications
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{id}", response_model=NotificationInfo)
async def get_notification(id: str):
    """Получает информацию о конкретном уведомлении"""
    try:
        job = scheduler.get_job(id)
        if not job:
            raise HTTPException(status_code=404, detail="Уведомление не найдено")
        
        payload = job.args[0]
        return NotificationInfo(
            id=job.id,
            scheduled_time=job.scheduled_time,
            client_id=payload.get("client_id"),
            payload=payload
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/schedule")
async def schedule_notification(notification: NotificationPayload):
    """Создает отложенное уведомление"""
    try:
        # Добавляем client_id в payload
        notification.payload["client_id"] = notification.client_id
        
        # Убедимся, что время в UTC
        if notification.scheduled_time.tzinfo is None:
            notification.scheduled_time = notification.scheduled_time.replace(tzinfo=ZoneInfo("UTC"))
        else:
            # Если время в другом часовом поясе, конвертируем в UTC
            notification.scheduled_time = notification.scheduled_time.astimezone(ZoneInfo("UTC"))
        
        logger.info(f"Планируем уведомление на {notification.scheduled_time} UTC")
        
        # Создаем задачу в планировщике
        scheduler.schedule(
            scheduled_time=notification.scheduled_time,
            func=send_notification,
            args=[notification.payload],
            id=f"notification_{notification.client_id}_{notification.scheduled_time.timestamp()}"
        )
        return {"status": "success", "message": "Уведомление запланировано"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{id}")
async def update_notification(id: str, notification: NotificationPayload):
    """Обновляет запланированное уведомление"""
    try:
        # Удаляем старую задачу
        scheduler.cancel(id)
        
        # Добавляем client_id в payload
        notification.payload["client_id"] = notification.client_id
        
        # Создаем новую задачу
        scheduler.schedule(
            scheduled_time=notification.scheduled_time,
            func=send_notification,
            args=[notification.payload],
            id=id
        )
        logger.info(f"notification_{notification.client_id}_{notification.scheduled_time}")
        
        return {"status": "success", "message": "Уведомление обновлено"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{id}")
async def delete_notification(id: str):
    """Удаляет запланированное уведомление"""
    try:
        scheduler.cancel(id)
        return {"status": "success", "message": "Уведомление удалено"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def send_notification(payload: dict):
    """Отправляет уведомление в Redis Pub/Sub канал"""
    try:
        redis_conn.publish("notifications", json.dumps(payload))
        logger.info(f"Отправил уведомление клиентской части: {payload}")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления: {e}")
        
    return {"status": "sent"} 