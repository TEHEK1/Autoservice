from sqlalchemy.orm import Session
from .models import Service

# Функция добавления новой услуги
def add_service(db: Session, service_name: str, service_price: int):
    db_service = Service(name=service_name, price=service_price)
    db.add(db_service)
    db.commit()
    db.refresh(db_service)
    return db_service

# Функция получения всех услуг
def get_all_services(db: Session):
    return db.query(Service).all()
