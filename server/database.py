from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Создаём Base, который будет использоваться для определения моделей
Base = declarative_base()

# Подключение к базе данных
DATABASE_URL = "postgresql://username:password@localhost/dbname"  # Укажите свои данные

engine = create_engine(DATABASE_URL, echo=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
