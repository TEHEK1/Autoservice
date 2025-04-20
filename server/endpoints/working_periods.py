import logging
from typing import List, Optional
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends, Query
from fastapi_cache import FastAPICache
from fastapi_cache.decorator import cache
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from server.database import get_db
from server.models import WorkingPeriod, WorkingPeriodCreate, WorkingPeriodOut, WorkingPeriodUpdate, Appointment, TimeSlot

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
router = APIRouter()

@router.get("", response_model=List[WorkingPeriodOut])
@cache(expire=300, namespace="working_periods")
async def get_working_periods(
    active_only: bool = Query(default=False),
    db: Session = Depends(get_db)
):
    """
    Получить список рабочих периодов.
    Можно фильтровать только активные периоды.
    """
    query = db.query(WorkingPeriod)
    
    # Фильтрация по активности
    if active_only:
        query = query.filter(WorkingPeriod.is_active == 1)
    
    # Сортировка по дате начала
    query = query.order_by(WorkingPeriod.start_date)
    
    return query.all()

@router.get("/time_slots", response_model=List[TimeSlot])
async def get_time_slots(
    date: Optional[str] = Query(default=None),
    db: Session = Depends(get_db)
):
    """
    Получить список доступных временных слотов на указанную дату.
    Слоты генерируются на основе рабочих периодов и существующих записей.
    """
    # Проверяем формат даты
    try:
        if date:
            target_date = datetime.strptime(date, "%Y-%m-%d")
        else:
            target_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Получаем следующий день
    next_day = target_date + timedelta(days=1)
    
    # Получаем рабочие периоды, которые включают указанную дату
    working_periods = db.query(WorkingPeriod).filter(
        WorkingPeriod.is_active == 1,
        WorkingPeriod.start_date <= target_date,
        WorkingPeriod.end_date >= target_date
    ).all()
    
    if not working_periods:
        return []
    
    # Получаем существующие записи на эту дату
    appointments = db.query(Appointment).filter(
        Appointment.scheduled_time >= target_date,
        Appointment.scheduled_time < next_day
    ).all()
    
    # Создаем словарь занятых временных интервалов
    busy_times = {}
    for appointment in appointments:
        # Предполагаем, что каждая запись занимает 1 час (можно настроить в зависимости от услуги)
        start_time = appointment.scheduled_time
        end_time = start_time + timedelta(minutes=60)  # Можно настроить в зависимости от услуги
        
        # Храним занятые интервалы
        busy_times[start_time.strftime("%H:%M")] = {
            "start": start_time,
            "end": end_time
        }
    
    # Генерируем доступные слоты для каждого рабочего периода
    available_slots = []
    
    for period in working_periods:
        # Парсим времена начала и окончания
        start_hour, start_minute = map(int, period.start_time.split(':'))
        end_hour, end_minute = map(int, period.end_time.split(':'))
        
        # Устанавливаем время начала и окончания для текущего дня
        current_time = target_date.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
        end_time = target_date.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
        
        # Генерируем слоты с учетом продолжительности
        while current_time + timedelta(minutes=period.slot_duration) <= end_time:
            slot_end = current_time + timedelta(minutes=period.slot_duration)
            current_time_str = current_time.strftime("%H:%M")
            
            # Проверяем, не занят ли этот временной слот
            is_available = True
            for busy_start, busy_data in busy_times.items():
                busy_start_time = busy_data["start"]
                busy_end_time = busy_data["end"]
                
                # Проверяем пересечение интервалов
                if (current_time < busy_end_time and slot_end > busy_start_time):
                    is_available = False
                    break
            
            # Если текущее время уже прошло, помечаем слот как недоступный
            if current_time <= datetime.now():
                is_available = False
            
            # Создаем слот и добавляем его в список
            slot = TimeSlot(
                id=f"{target_date.strftime('%Y-%m-%d')}_{current_time_str.replace(':', '-')}",
                start_time=current_time,
                end_time=slot_end,
                is_available=is_available
            )
            available_slots.append(slot)
            
            # Переходим к следующему слоту
            current_time = slot_end
    
    return available_slots

@router.get("/{id}", response_model=WorkingPeriodOut)
@cache(expire=300, namespace="working_periods")
async def get_working_period(
    id: int,
    db: Session = Depends(get_db)
):
    """
    Получить информацию о конкретном рабочем периоде
    """
    period = db.query(WorkingPeriod).filter(WorkingPeriod.id == id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Working period not found")
    return period

@router.post("", response_model=WorkingPeriodOut)
async def create_working_period(
    period: WorkingPeriodCreate,
    db: Session = Depends(get_db)
):
    """
    Создать новый рабочий период
    """
    # Проверяем, что конечная дата не раньше начальной
    if period.end_date < period.start_date:
        raise HTTPException(status_code=400, detail="End date must be after start date")
    
    # Проверяем формат времени
    try:
        start_hour, start_minute = map(int, period.start_time.split(':'))
        end_hour, end_minute = map(int, period.end_time.split(':'))
        
        if not (0 <= start_hour < 24 and 0 <= start_minute < 60 and 0 <= end_hour < 24 and 0 <= end_minute < 60):
            raise ValueError("Invalid time values")
            
        # Проверяем, что конечное время позже начального
        start_time_minutes = start_hour * 60 + start_minute
        end_time_minutes = end_hour * 60 + end_minute
        
        if end_time_minutes <= start_time_minutes:
            raise HTTPException(status_code=400, detail="End time must be after start time")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid time format. Use HH:MM")
    
    # Проверяем продолжительность слота
    if period.slot_duration < 15 or period.slot_duration > 240:
        raise HTTPException(status_code=400, detail="Slot duration must be between 15 and 240 minutes")
    
    # Создаем рабочий период
    db_period = WorkingPeriod(**period.model_dump())
    db.add(db_period)
    await FastAPICache.clear("working_periods")
    db.commit()
    db.refresh(db_period)
    
    return db_period

@router.patch("/{id}", response_model=WorkingPeriodOut)
async def update_working_period(
    id: int,
    period_update: WorkingPeriodUpdate,
    db: Session = Depends(get_db)
):
    """
    Обновить информацию о рабочем периоде
    """
    # Проверяем существование периода
    db_period = db.query(WorkingPeriod).filter(WorkingPeriod.id == id).first()
    if not db_period:
        raise HTTPException(status_code=404, detail="Working period not found")
    
    # Получаем данные для обновления
    update_data = period_update.model_dump(exclude_unset=True)
    
    # Если есть обновления времени, проверяем их формат
    if "start_time" in update_data or "end_time" in update_data:
        start_time = update_data.get("start_time", db_period.start_time)
        end_time = update_data.get("end_time", db_period.end_time)
        
        try:
            start_hour, start_minute = map(int, start_time.split(':'))
            end_hour, end_minute = map(int, end_time.split(':'))
            
            if not (0 <= start_hour < 24 and 0 <= start_minute < 60 and 0 <= end_hour < 24 and 0 <= end_minute < 60):
                raise ValueError("Invalid time values")
                
            # Проверяем, что конечное время позже начального
            start_time_minutes = start_hour * 60 + start_minute
            end_time_minutes = end_hour * 60 + end_minute
            
            if end_time_minutes <= start_time_minutes:
                raise HTTPException(status_code=400, detail="End time must be after start time")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid time format. Use HH:MM")
    
    # Если есть обновления дат, проверяем их
    if "start_date" in update_data or "end_date" in update_data:
        start_date = update_data.get("start_date", db_period.start_date)
        end_date = update_data.get("end_date", db_period.end_date)
        
        if end_date < start_date:
            raise HTTPException(status_code=400, detail="End date must be after start date")
    
    # Если есть обновление продолжительности слота, проверяем его
    if "slot_duration" in update_data:
        if update_data["slot_duration"] < 15 or update_data["slot_duration"] > 240:
            raise HTTPException(status_code=400, detail="Slot duration must be between 15 and 240 minutes")
    
    # Обновляем поля
    for key, value in update_data.items():
        setattr(db_period, key, value)
    
    await FastAPICache.clear("working_periods")
    db.commit()
    db.refresh(db_period)
    
    return db_period

@router.delete("/{id}")
async def delete_working_period(
    id: int,
    db: Session = Depends(get_db)
):
    """
    Удалить рабочий период
    """
    # Проверяем существование периода
    db_period = db.query(WorkingPeriod).filter(WorkingPeriod.id == id).first()
    if not db_period:
        raise HTTPException(status_code=404, detail="Working period not found")
    
    # Удаляем период
    db.delete(db_period)
    await FastAPICache.clear("working_periods")
    db.commit()
    
    return {"message": "Working period deleted successfully"} 