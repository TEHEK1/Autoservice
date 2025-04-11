from typing import List

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from fastapi_cache import FastAPICache
from fastapi_cache.decorator import cache
from sqlalchemy.orm import Session

from server.database import get_db
from server.models import Service, ServiceCreate, ServiceOut

router = APIRouter()

@router.get("", response_model=List[ServiceOut])
@cache(expire=600, namespace="services")
async def get_services(db: Session = Depends(get_db)):
    print("Берем не из кеша")
    result = db.query(Service).all()
    return result

@router.post("", response_model=ServiceOut)
async def create_service(
        service: ServiceCreate,
        db: Session = Depends(get_db)):
    db_service = Service(**service.model_dump())
    db.add(db_service)
    await FastAPICache.clear("services")
    db.commit()
    db.refresh(db_service)
    return db_service

@router.get("/{id}", response_model=ServiceOut)
@cache(expire=600, namespace="services")
async def get_service(
        id: int,
        db: Session = Depends(get_db)):
    result = db.query(Service).filter(Service.id == id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Service not found")
    return result

@router.patch("/{id}", response_model=ServiceOut)
async def update_service(
        id: int,
        update: ServiceCreate,
        db: Session = Depends(get_db)):
    to_update = db.query(Service).filter(Service.id == id).first()
    if not to_update:
        raise HTTPException(status_code=404, detail="Service not found")

    for key, value in update.model_dump(exclude_unset=True).items():
        setattr(to_update, key, value)

    await FastAPICache.clear("services")
    db.commit()
    db.refresh(to_update)
    return to_update

@router.delete("/{id}")
async def delete_service(id: int, db: Session = Depends(get_db)):
    service = db.query(Service).filter(Service.id == id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    if service.orders:
        raise HTTPException(
            status_code=400, 
            detail="Cannot delete service with existing appointments. Delete appointments first."
        )
    
    db.delete(service)
    await FastAPICache.clear("services")
    db.commit()
    return {"message": "Service deleted successfully"}