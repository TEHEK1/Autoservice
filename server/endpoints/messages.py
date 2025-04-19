from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import or_, and_
import json
import logging

from server.database import get_db
from server.models import Message, MessageCreate, MessageOut, MessageUpdate
from server.endpoints.notifications import send_notification

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/", response_model=MessageOut)
async def create_message(message: MessageCreate, db: Session = Depends(get_db)):
    """Создать новое сообщение"""
    try:
        db_message = Message(**message.model_dump())
        db.add(db_message)
        db.commit()
        db.refresh(db_message)
        
        # Отправляем уведомление о новом сообщении
        notification_data = {
            "type": "new_message",
            "message": {
                "id": db_message.id,
                "text": db_message.text,
                "user_id": db_message.user_id,
                "is_from_admin": db_message.is_from_admin,
                "created_at": db_message.created_at.isoformat()
            }
        }
        
        # Используем синхронную версию для избежания ошибок
        send_notification(notification_data)
        
        return db_message
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Ошибка при создании сообщения: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при создании сообщения")

@router.get("/", response_model=List[MessageOut])
def get_messages(
    user_id: Optional[int] = None,
    is_read: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Получить список сообщений"""
    try:
        query = db.query(Message)
        
        if user_id is not None:
            # Фильтруем сообщения для данного пользователя
            query = query.filter(Message.user_id == user_id)
        
        if is_read is not None:
            query = query.filter(Message.is_read == is_read)
            
        query = query.order_by(Message.created_at.desc())
        messages = query.offset(skip).limit(limit).all()
        
        return messages
    except SQLAlchemyError as e:
        logger.error(f"Ошибка при получении списка сообщений: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при получении списка сообщений")

@router.get("/{message_id}", response_model=MessageOut)
def get_message(message_id: int, db: Session = Depends(get_db)):
    """Получить сообщение по ID"""
    try:
        message = db.query(Message).filter(Message.id == message_id).first()
        if not message:
            raise HTTPException(status_code=404, detail="Сообщение не найдено")
        return message
    except SQLAlchemyError as e:
        logger.error(f"Ошибка при получении сообщения: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при получении сообщения")

@router.put("/{message_id}", response_model=MessageOut)
def update_message(message_id: int, message_update: MessageUpdate, db: Session = Depends(get_db)):
    """Обновить сообщение"""
    try:
        db_message = db.query(Message).filter(Message.id == message_id).first()
        if not db_message:
            raise HTTPException(status_code=404, detail="Сообщение не найдено")
        
        update_data = message_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_message, key, value)
            
        db.commit()
        db.refresh(db_message)
        return db_message
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Ошибка при обновлении сообщения: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при обновлении сообщения")

@router.delete("/{message_id}", response_model=dict)
def delete_message(message_id: int, db: Session = Depends(get_db)):
    """Удалить сообщение"""
    try:
        db_message = db.query(Message).filter(Message.id == message_id).first()
        if not db_message:
            raise HTTPException(status_code=404, detail="Сообщение не найдено")
        
        db.delete(db_message)
        db.commit()
        return {"message": "Сообщение успешно удалено"}
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Ошибка при удалении сообщения: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при удалении сообщения")

@router.get("/unread/{user_id}", response_model=int)
def get_unread_count(user_id: int, db: Session = Depends(get_db)):
    """Получить количество непрочитанных сообщений"""
    try:
        count = db.query(Message).filter(
            and_(
                Message.user_id == user_id,
                Message.is_read == 0,
                Message.is_from_admin == 1  # Считаем только сообщения от админа
            )
        ).count()
        return count
    except SQLAlchemyError as e:
        logger.error(f"Ошибка при получении количества непрочитанных сообщений: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при получении количества непрочитанных сообщений")

@router.put("/read/{message_id}", response_model=MessageOut)
def mark_as_read(message_id: int, db: Session = Depends(get_db)):
    """Пометить сообщение как прочитанное"""
    try:
        db_message = db.query(Message).filter(Message.id == message_id).first()
        if not db_message:
            raise HTTPException(status_code=404, detail="Сообщение не найдено")
        
        db_message.is_read = 1
        db.commit()
        db.refresh(db_message)
        return db_message
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Ошибка при пометке сообщения как прочитанного: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при пометке сообщения как прочитанного") 