from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, BigInteger
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

class ServiceOut(ServiceCreate):
    id: int
    model_config = {"from_attributes": True}

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=True, index=True)
    name = Column(String, nullable=True)
    phone_number = Column(String, unique=True, nullable=True, index=True)

    appointments = relationship("Appointment", back_populates="client")

class ClientCreate(BaseModel):
    name: str
    phone_number: Optional[str] = None
    telegram_id: Optional[int] = None

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
    created_at = Column(DateTime, default=datetime.utcnow)

class AppointmentCreate(BaseModel):
    client_id: int
    service_id: int
    car_model: Optional[str]
    scheduled_time: datetime

class AppointmentOut(AppointmentCreate):
    id: int
    created_at: datetime
    model_config = {"from_attributes": True}
