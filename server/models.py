from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, BigInteger, Text
from sqlalchemy.orm import relationship

from server.database import Base

from pydantic import BaseModel

class Service(Base):
    __tablename__ = 'services'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String)
    price = Column(Float, nullable=False)
    orders = relationship("Appointment", back_populates="service")

class ServiceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float

class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None

class ServiceOut(ServiceCreate):
    id: int
    model_config = {"from_attributes": True}

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=True, index=True)
    name = Column(String, nullable=True)
    phone_number = Column(String, unique=True, nullable=True, index=True)
    timezone = Column(String, nullable=True, default="Europe/Moscow")

    appointments = relationship("Appointment", back_populates="client")
    messages = relationship("Message", back_populates="client")

class ClientCreate(BaseModel):
    name: str
    phone_number: Optional[str] = None
    telegram_id: Optional[int] = None
    timezone: Optional[str] = "Europe/Moscow"

class ClientUpdate(BaseModel):
    name: Optional[str] = None
    phone_number: Optional[str] = None
    telegram_id: Optional[int] = None
    timezone: Optional[str] = None

class ClientOut(ClientCreate):
    id: int
    model_config = {"from_attributes": True}

class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True)

    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    client = relationship("Client", back_populates="appointments")

    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    service = relationship("Service")

    car_model = Column(String, nullable=True)
    scheduled_time = Column(DateTime, nullable=False)
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)

class AppointmentCreate(BaseModel):
    client_id: int
    service_id: int
    car_model: Optional[str] = None
    scheduled_time: datetime
    status: str = "pending"

class AppointmentUpdate(BaseModel):
    client_id: Optional[int] = None
    service_id: Optional[int] = None
    car_model: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    status: Optional[str] = None

class AppointmentOut(AppointmentCreate):
    id: int
    created_at: datetime
    model_config = {"from_attributes": True}

class WorkingPeriod(Base):
    __tablename__ = "working_periods"

    id = Column(Integer, primary_key=True)
    start_date = Column(DateTime, nullable=False)  # Дата начала периода
    end_date = Column(DateTime, nullable=False)    # Дата окончания периода
    start_time = Column(String, nullable=False)    # Время начала работы (HH:MM)
    end_time = Column(String, nullable=False)      # Время окончания работы (HH:MM)
    slot_duration = Column(Integer, nullable=False, default=60)  # Длительность слота в минутах
    is_active = Column(Integer, nullable=False, default=1)     # Активен ли период
    created_at = Column(DateTime, default=datetime.utcnow)

class WorkingPeriodCreate(BaseModel):
    start_date: datetime
    end_date: datetime
    start_time: str
    end_time: str
    slot_duration: int = 60
    is_active: int = 1

class WorkingPeriodUpdate(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    slot_duration: Optional[int] = None
    is_active: Optional[int] = None

class WorkingPeriodOut(WorkingPeriodCreate):
    id: int
    created_at: datetime
    model_config = {"from_attributes": True}

# Схема представления слота (не хранится в БД, генерируется динамически)
class TimeSlot(BaseModel):
    id: str  # Уникальный идентификатор слота (не ID в БД)
    start_time: datetime
    end_time: datetime
    is_available: bool = True

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    text = Column(Text, nullable=False)
    
    user_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    client = relationship("Client", back_populates="messages")
    
    is_from_admin = Column(Integer, default=0)  # 0 - от клиента к админу, 1 - от админа к клиенту
    is_read = Column(Integer, default=0)  # 0 - не прочитано, 1 - прочитано
    created_at = Column(DateTime, default=datetime.utcnow)

class MessageCreate(BaseModel):
    text: str
    user_id: int
    is_from_admin: Optional[int] = 0
    is_read: Optional[int] = 0

class MessageUpdate(BaseModel):
    text: Optional[str] = None
    is_read: Optional[int] = None

class MessageOut(BaseModel):
    id: int
    text: str
    user_id: int
    is_from_admin: int
    is_read: int
    created_at: datetime
    model_config = {"from_attributes": True}
