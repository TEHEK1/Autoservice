from typing import List

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from fastapi_cache import FastAPICache
from fastapi_cache.decorator import cache
from sqlalchemy.orm import Session

from server.database import get_db
from server.models import Appointment, AppointmentCreate, AppointmentOut

router = APIRouter()

@router.get("", response_model=List[AppointmentOut])
@cache(expire=600, namespace="appointments")
async def get_appointments(db: Session = Depends(get_db)):
    print("Берем не из кеша")
    result = db.query(Appointment).all()
    return result

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
        update: AppointmentCreate,
        db: Session = Depends(get_db)):
    to_update = db.query(Appointment).filter(Appointment.id == id).first()
    if not to_update:
        raise HTTPException(status_code=404, detail="Appointment not found")

    for key, value in update.model_dump(exclude_unset=True).items():
        setattr(to_update, key, value)

    await FastAPICache.clear("appointments")
    db.commit()
    db.refresh(to_update)
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