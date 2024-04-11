import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from aiogram import Router

# Получаем путь к корневой директории проекта
BASE_DIR = Path(__file__).resolve().parent.parent

# Загружаем переменные окружения из .env файла
load_dotenv(BASE_DIR / '.env')

# Получаем токен бота из переменных окружения
TOKEN = os.getenv("CLIENT_TOKEN_BOT")
if not TOKEN:
    raise ValueError("CLIENT_TOKEN_BOT не найден в переменных окружения")

# Получаем URL API из переменных окружения
API_URL = os.getenv("API_URL", "http://localhost:8000")
if not API_URL.startswith(('http://', 'https://')):
    raise ValueError("API_URL должен начинаться с http:// или https://")

# Настройки логирования
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Настройка логирования
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)

# Создаем роутер
router = Router() 