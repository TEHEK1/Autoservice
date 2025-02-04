import os

class Settings:
    BOT_TOKEN = os.getenv("BOT_TOKEN")  # Токен Telegram-бота для клиентов
    ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN")  # Токен Telegram-бота для админов
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./database.db")  # URL базы данных
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")  # URL Redis
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")  # Уровень логирования
    ADMINS = list(map(int, os.getenv("ADMINS", "").split(",")))  # Список ID администраторов

settings = Settings()