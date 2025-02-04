from server.database import Base, engine
from server.models import Service  # Импортируем модели после определения Base

# Создание всех таблиц
Base.metadata.create_all(bind=engine)

print("База данных и таблицы успешно созданы.")
