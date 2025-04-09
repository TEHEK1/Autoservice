from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends, Query
from fastapi_cache import FastAPICache
from fastapi_cache.decorator import cache
from sqlalchemy.orm import Session

from server.database import get_db
from server.models import Client, ClientCreate, ClientOut
router = APIRouter()

@router.get("", response_model=List[ClientOut])
@cache(expire=600, namespace="clients")
async def get_clients(db: Session = Depends(get_db)):
    print("Берем не из кеша")
    clients = db.query(Client).all()
    return clients

@router.get("/{id}", response_model=ClientOut)
@cache(expire=600, namespace="clients")
async def get_client(
        id: int,
        db: Session = Depends(get_db)):
    result = db.query(Client).filter(Client.id == id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Client not found")
    return result

@router.get("/search", response_model=ClientOut)
@cache(expire=600, namespace="clients")
def search_client(
    telegram_id: Optional[int] = Query(default=None),
    phone_number: Optional[str] = Query(default=None),
    db: Session = Depends(get_db)
):
    if not telegram_id and not phone_number:
        raise HTTPException(status_code=400, detail="Need at least one of telegram_id or phone_number")

    query = db.query(Client)
    if telegram_id is not None:
        query = query.filter(Client.telegram_id == telegram_id)
    if phone_number is not None:
        query = query.filter(Client.phone_number == phone_number)

    print(phone_number)
    client = query.first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    return client

@router.post("", response_model=ClientOut)
async def create_client(
        client: ClientCreate,
        db: Session = Depends(get_db)
):
    db_client = Client(**client.model_dump())
    db.add(db_client)
    await FastAPICache.clear("clients")
    db.commit()
    db.refresh(db_client)

    return db_client

@router.patch("/{id}", response_model=ClientOut)
async def update_client(
        id: int,
        update: ClientCreate,
        db: Session = Depends(get_db)):
    to_update = db.query(Client).filter(Client.id == id).first()
    if not to_update:
        raise HTTPException(status_code=404, detail="Client not found")

    for key, value in update.model_dump(exclude_unset=True).items():
        setattr(to_update, key, value)

    await FastAPICache.clear("clients")
    db.commit()
    db.refresh(to_update)
    return to_update

@router.patch("", response_model=ClientOut)
async def patch_clients(update_client: ClientCreate,
        id: Optional[int] = Query(default=None),
        telegram_id: Optional[int] = Query(default=None),
        phone_number: Optional[str] = Query(default=None),
        db: Session = Depends(get_db)):
    if not id and not telegram_id and not phone_number:
        raise HTTPException(status_code=400, detail="Need at least one of id, telegram_id or phone_number")

    query = db.query(Client)
    if id is not None:
        query = query.filter(Client.id == id)
    if telegram_id is not None:
        query = query.filter(Client.telegram_id == telegram_id)
    if phone_number is not None:
        query = query.filter(Client.phone_number == phone_number)

    client = query.first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    for key, value in update_client.model_dump(exclude_unset=True).items():
        setattr(client, key, value)

    await FastAPICache.clear("clients")
    db.commit()
    db.refresh(client)
    return client