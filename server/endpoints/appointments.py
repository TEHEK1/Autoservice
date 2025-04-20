import logging
from typing import List, Optional
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends, Query
from fastapi_cache import FastAPICache
from fastapi_cache.decorator import cache
from sqlalchemy.orm import Session

from server.database import get_db
from server.models import Appointment, AppointmentCreate, AppointmentOut, AppointmentUpdate
from .notifications import NotificationPayload, delete_notification, schedule_notification
from .notifications import send_notification

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
router = APIRouter()

@router.get("", response_model=List[AppointmentOut])
@cache(expire=600, namespace="appointments")
async def get_appointments(client_id: Optional[int] = Query(default=None),
                           db: Session = Depends(get_db)):
    print("Берем не из кеша")
    query = db.query(Appointment)
    if client_id is not None:
        query = query.filter(Appointment.client_id == client_id)
    return query.all()

@router.get("/{id}", response_model=AppointmentOut)
@cache(expire=600, namespace="appointments")
async def get_appointment(id: int,
        db: Session = Depends(get_db)):
    result = db.query(Appointment).filter(Appointment.id == id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return result

@router.patch("/{id}", response_model=AppointmentOut)
async def patch_appointments(
        id: int,
        update: AppointmentUpdate,
        db: Session = Depends(get_db)):
    to_update = db.query(Appointment).filter(Appointment.id == id).first()
    if not to_update:
        raise HTTPException(status_code=404, detail="Appointment not found")

    # Конвертируем в Pydantic модель для удобной работы
    appointment_out = AppointmentOut.model_validate(to_update)
    old_scheduled_time = appointment_out.scheduled_time
    new_scheduled_time = update.scheduled_time

    # Обновляем SQLAlchemy модель
    for key, value in update.model_dump(exclude_unset=True).items():
        setattr(to_update, key, value)

    await FastAPICache.clear("appointments")
    db.commit()
    db.refresh(to_update)

    # Если обновляется scheduled_time, обновляем уведомления
    if new_scheduled_time is not None:
        # Удаляем старое уведомление если есть
        try:
            await delete_notification(
                f"notification_{appointment_out.client_id}_{(old_scheduled_time - timedelta(hours=1)).timestamp()}")
        except Exception as e:
            print(f"Ошибка при удалении старого уведомления: {e}")

        # Создаем новое уведомление
        notification = NotificationPayload(
            scheduled_time=new_scheduled_time - timedelta(hours=1),
            client_id=appointment_out.client_id,
            payload={"appointment_id": id}
        )
        await schedule_notification(notification)
    
    return to_update

@router.post("", response_model=AppointmentOut)
async def create_appointment(
        appointment: AppointmentCreate,
        db: Session = Depends(get_db)
):
    db_appointment = Appointment(**appointment.model_dump())
    db.add(db_appointment)
    await FastAPICache.clear("appointments")
    db.commit()
    db.refresh(db_appointment)
    
    # Создаем уведомление
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    
    # Убедимся, что время в UTC
    scheduled_time = appointment.scheduled_time
    if scheduled_time.tzinfo is None:
        scheduled_time = scheduled_time.replace(tzinfo=ZoneInfo("UTC"))
    else:
        # Если время в другом часовом поясе, конвертируем в UTC
        scheduled_time = scheduled_time.astimezone(ZoneInfo("UTC"))
    
    # Вычисляем время уведомления (за час до записи)
    notification_time = scheduled_time - timedelta(hours=1)
    
    notification = NotificationPayload(
        scheduled_time=notification_time,
        client_id=appointment.client_id,
        payload={"appointment_id": db_appointment.id}
    )
    logger.info(f"Создаем уведомление на {notification_time} UTC")
    print(f"Создаем уведомление на {notification_time} UTC")  # Добавляем print для отладки
    await schedule_notification(notification)
    
    # Отправляем немедленное уведомление администратору о новой записи
    admin_notification = {
        "type": "new_appointment",
        "appointment": {
            "id": db_appointment.id,
            "client_id": appointment.client_id,
            "service_id": appointment.service_id,
            "scheduled_time": scheduled_time.isoformat(),
            "status": appointment.status,
            "car_model": appointment.car_model
        }
    }
    
    # Отправляем уведомление через Redis
    logger.info("Отправляем уведомление администратору о новой записи")
    send_notification(admin_notification)
    
    return db_appointment

@router.delete("/{id}")
async def delete_appointment(id: int, db: Session = Depends(get_db)):
    appointment = db.query(Appointment).filter(Appointment.id == id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    db.delete(appointment)
    await FastAPICache.clear("appointments")
    db.commit()
    return {"message": "Appointment deleted successfully"}