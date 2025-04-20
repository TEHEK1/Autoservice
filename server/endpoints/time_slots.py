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
from server.models import TimeSlot, TimeSlotCreate, TimeSlotOut, TimeSlotUpdate, Appointment

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
router = APIRouter()

@router.get("", response_model=List[TimeSlotOut])
@cache(expire=300, namespace="time_slots")
async def get_time_slots(
    date: Optional[str] = Query(default=None),
    available_only: bool = Query(default=False),
    db: Session = Depends(get_db)
):
    """
    Получить список доступных временных слотов.
    Можно фильтровать по дате (YYYY-MM-DD) и доступности.
    """
    query = db.query(TimeSlot)
    
    # Фильтрация по дате
    if date:
        try:
            filter_date = datetime.strptime(date, "%Y-%m-%d")
            next_day = filter_date + timedelta(days=1)
            query = query.filter(
                TimeSlot.start_time >= filter_date,
                TimeSlot.start_time < next_day
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Фильтрация по доступности
    if available_only:
        query = query.filter(TimeSlot.is_available == True)
    
    # Сортировка по времени начала
    query = query.order_by(TimeSlot.start_time)
    
    return query.all()

@router.get("/{id}", response_model=TimeSlotOut)
@cache(expire=300, namespace="time_slots")
async def get_time_slot(id: int, db: Session = Depends(get_db)):
    """
    Получить информацию о конкретном временном слоте
    """
    time_slot = db.query(TimeSlot).filter(TimeSlot.id == id).first()
    if not time_slot:
        raise HTTPException(status_code=404, detail="Time slot not found")
    return time_slot

@router.post("", response_model=TimeSlotOut)
async def create_time_slot(
    time_slot: TimeSlotCreate,
    db: Session = Depends(get_db)
):
    """
    Создать новый временной слот
    """
    db_time_slot = TimeSlot(**time_slot.model_dump())
    db.add(db_time_slot)
    await FastAPICache.clear("time_slots")
    db.commit()
    db.refresh(db_time_slot)
    return db_time_slot

@router.post("/batch", response_model=List[TimeSlotOut])
async def create_time_slots_batch(
    start_date: str,
    end_date: str,
    start_time: str,
    end_time: str,
    slot_duration: int = 60,  # в минутах
    db: Session = Depends(get_db)
):
    """
    Пакетное создание временных слотов в заданном диапазоне дат и времени
    """
    try:
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        
        start_hour, start_minute = map(int, start_time.split(':'))
        end_hour, end_minute = map(int, end_time.split(':'))
        
    except ValueError:
        raise HTTPException(
            status_code=400, 
            detail="Invalid date or time format. Use YYYY-MM-DD for dates and HH:MM for times."
        )
    
    # Проверяем, что конечная дата не раньше начальной
    if end_date_obj < start_date_obj:
        raise HTTPException(status_code=400, detail="End date must be after start date")
    
    # Ограничиваем максимальное количество дней для одного запроса
    days_diff = (end_date_obj - start_date_obj).days + 1
    if days_diff > 60:  # Максимальное количество дней для одного запроса
        raise HTTPException(
            status_code=400, 
            detail="Date range too large. Maximum range is 60 days."
        )
    
    created_slots = []
    current_date = start_date_obj
    
    # Для более эффективной вставки данных будем использовать bulk_save_objects
    slots_to_create = []
    
    # Для каждого дня в диапазоне
    while current_date <= end_date_obj:
        # Устанавливаем начальное время для текущего дня
        current_time = current_date.replace(
            hour=start_hour, 
            minute=start_minute, 
            second=0, 
            microsecond=0
        )
        
        # Устанавливаем конечное время для текущего дня
        day_end_time = current_date.replace(
            hour=end_hour, 
            minute=end_minute, 
            second=0, 
            microsecond=0
        )
        
        # Создаем слоты для текущего дня
        while current_time + timedelta(minutes=slot_duration) <= day_end_time:
            slot_end_time = current_time + timedelta(minutes=slot_duration)
            
            # Создаем объект слота для пакетной вставки
            slots_to_create.append(
                TimeSlot(
                    start_time=current_time,
                    end_time=slot_end_time,
                    is_available=True
                )
            )
            
            current_time = slot_end_time
        
        # Переходим к следующему дню
        current_date += timedelta(days=1)
    
    # Выполняем вставку всех слотов за один запрос
    if slots_to_create:
        db.bulk_save_objects(slots_to_create)
        db.commit()
        
        # Получаем созданные слоты
        # Не самый эффективный способ, но нам нужно вернуть созданные слоты с их ID
        new_slots = db.query(TimeSlot).filter(
            TimeSlot.start_time >= start_date_obj,
            TimeSlot.start_time <= end_date_obj.replace(hour=23, minute=59, second=59),
            TimeSlot.start_time.between(
                start_date_obj.replace(hour=start_hour, minute=start_minute),
                end_date_obj.replace(hour=end_hour, minute=end_minute)
            )
        ).all()
        
        await FastAPICache.clear("time_slots")
        return new_slots
    
    return []

@router.patch("/{id}", response_model=TimeSlotOut)
async def update_time_slot(
    id: int,
    time_slot_update: TimeSlotUpdate,
    db: Session = Depends(get_db)
):
    """
    Обновить информацию о временном слоте
    """
    db_time_slot = db.query(TimeSlot).filter(TimeSlot.id == id).first()
    if not db_time_slot:
        raise HTTPException(status_code=404, detail="Time slot not found")
    
    # Обновляем атрибуты слота
    for key, value in time_slot_update.model_dump(exclude_unset=True).items():
        setattr(db_time_slot, key, value)
    
    await FastAPICache.clear("time_slots")
    db.commit()
    db.refresh(db_time_slot)
    return db_time_slot

@router.delete("/{id}")
async def delete_time_slot(id: int, db: Session = Depends(get_db)):
    """
    Удалить временной слот
    """
    db_time_slot = db.query(TimeSlot).filter(TimeSlot.id == id).first()
    if not db_time_slot:
        raise HTTPException(status_code=404, detail="Time slot not found")
    
    # Проверяем, не занят ли слот
    if db_time_slot.appointment_id:
        raise HTTPException(
            status_code=400, 
            detail="Cannot delete a time slot with an associated appointment"
        )
    
    db.delete(db_time_slot)
    await FastAPICache.clear("time_slots")
    db.commit()
    return {"message": "Time slot deleted successfully"}

@router.post("/{id}/book", response_model=TimeSlotOut)
async def book_time_slot(
    id: int,
    appointment_id: int,
    db: Session = Depends(get_db)
):
    """
    Забронировать временной слот для записи
    """
    # Проверяем существование слота
    db_time_slot = db.query(TimeSlot).filter(TimeSlot.id == id).first()
    if not db_time_slot:
        raise HTTPException(status_code=404, detail="Time slot not found")
    
    # Проверяем, доступен ли слот
    if not db_time_slot.is_available:
        raise HTTPException(status_code=400, detail="Time slot is not available")
    
    # Проверяем существование записи
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    # Обновляем слот
    db_time_slot.is_available = False
    db_time_slot.appointment_id = appointment_id
    
    # Обновляем время записи
    appointment.scheduled_time = db_time_slot.start_time
    
    await FastAPICache.clear("time_slots")
    await FastAPICache.clear("appointments")
    db.commit()
    db.refresh(db_time_slot)
    
    return db_time_slot 