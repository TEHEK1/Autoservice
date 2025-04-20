from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData
import httpx
import logging
from datetime import datetime, timedelta
import calendar
from typing import List, Dict, Optional
from zoneinfo import ZoneInfo

from ..config import API_URL
from .profile import get_admin_timezone

logger = logging.getLogger(__name__)
router = Router()

# Состояния для создания рабочего периода
class CreateWorkingPeriodState(StatesGroup):
    waiting_for_start_date = State()
    waiting_for_end_date = State()
    waiting_for_start_time = State()
    waiting_for_end_time = State()
    waiting_for_duration = State()

# Состояния для удаления рабочего периода
class DeleteWorkingPeriodState(StatesGroup):
    waiting_for_confirmation = State()

# Callback данные для рабочих периодов
class WorkingPeriodCallback(CallbackData, prefix="working_period"):
    id: int
    action: str

# Callback данные для просмотра слотов для определенной даты
class ViewSlotsCallback(CallbackData, prefix="view_slots"):
    date: str

@router.message(Command("time_slots"))
async def command_time_slots(message: Message):
    """Обработчик команды /time_slots"""
    await show_time_slots_menu(message)

@router.callback_query(F.data == "time_slots")
async def callback_time_slots(callback: CallbackQuery):
    """Обработчик нажатия на кнопку 'Управление слотами'"""
    await show_time_slots_menu(callback.message)
    await callback.answer()

async def show_time_slots_menu(message: Message):
    """Показывает меню управления рабочими периодами"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Настройка рабочих периодов", callback_data="working_periods")],
        [InlineKeyboardButton(text="🔍 Просмотр доступных слотов", callback_data="view_time_slots")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])
    
    await message.answer(
        "📅 Управление расписанием\n\n"
        "Выберите действие:",
        reply_markup=keyboard
    )

@router.callback_query(F.data == "working_periods")
async def show_working_periods(callback: CallbackQuery):
    """Показывает список рабочих периодов"""
    try:
        # Получаем часовой пояс администратора
        admin_timezone = get_admin_timezone(callback.from_user.id)
        
        # Получаем список рабочих периодов
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{API_URL}/working_periods")
            response.raise_for_status()
            periods = response.json()
            
            if not periods:
                # Если периодов нет, предлагаем создать их
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Создать рабочий период", callback_data="create_working_period")],
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="time_slots")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ])
                await callback.message.answer("❌ Нет рабочих периодов", reply_markup=keyboard)
                await callback.answer()
                return
            
            # Формируем сообщение с рабочими периодами
            message_text = "📅 Рабочие периоды:\n\n"
            
            # Создаем кнопки для каждого периода
            keyboard = []
            
            for period in periods:
                # Форматируем даты с учетом часового пояса администратора
                start_date = datetime.fromisoformat(period['start_date'].replace('Z', '+00:00')).replace(tzinfo=ZoneInfo("UTC"))
                end_date = datetime.fromisoformat(period['end_date'].replace('Z', '+00:00')).replace(tzinfo=ZoneInfo("UTC"))
                
                # Конвертируем в часовой пояс администратора
                start_date_local = start_date.astimezone(ZoneInfo(admin_timezone))
                end_date_local = end_date.astimezone(ZoneInfo(admin_timezone))
                
                # Форматируем для отображения
                start_date_formatted = start_date_local.strftime("%d.%m.%Y")
                end_date_formatted = end_date_local.strftime("%d.%m.%Y")
                
                # Преобразуем время в местное время
                start_time_parts = period['start_time'].split(':')
                end_time_parts = period['end_time'].split(':')
                
                # Создаем временные объекты datetime с сегодняшней датой для преобразования времени
                today_utc = datetime.now(ZoneInfo("UTC")).replace(hour=int(start_time_parts[0]), minute=int(start_time_parts[1]), second=0, microsecond=0)
                today_utc_end = datetime.now(ZoneInfo("UTC")).replace(hour=int(end_time_parts[0]), minute=int(end_time_parts[1]), second=0, microsecond=0)
                
                # Конвертируем в местное время
                today_local = today_utc.astimezone(ZoneInfo(admin_timezone))
                today_local_end = today_utc_end.astimezone(ZoneInfo(admin_timezone))
                
                # Получаем отформатированное время
                start_time_formatted = today_local.strftime("%H:%M")
                end_time_formatted = today_local_end.strftime("%H:%M")
                
                status = "🟢 Активен" if period['is_active'] == 1 else "🔴 Не активен"
                
                # Добавляем информацию о периоде в сообщение с конвертированным временем
                message_text += f"• {start_date_formatted} - {end_date_formatted}: {start_time_formatted}-{end_time_formatted}, {period['slot_duration']} мин. {status}\n"
                
                # Добавляем кнопку
                keyboard.append([
                    InlineKeyboardButton(
                        text=f"✏️ {start_date_formatted} - {end_date_formatted}",
                        callback_data=WorkingPeriodCallback(id=period['id'], action="edit").pack()
                    )
                ])
            
            # Добавляем кнопки управления
            keyboard.extend([
                [InlineKeyboardButton(text="➕ Создать рабочий период", callback_data="create_working_period")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="time_slots")]
            ])
            
            markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            await callback.message.answer(message_text, reply_markup=markup)
        
    except Exception as e:
        logger.error(f"Ошибка при получении списка рабочих периодов: {e}")
        await callback.message.answer("❌ Произошла ошибка при получении списка рабочих периодов")
    
    await callback.answer()

@router.callback_query(F.data == "view_time_slots")
async def view_time_slots_dates(callback: CallbackQuery):
    """Показывает выбор даты для просмотра доступных слотов"""
    # Получаем часовой пояс администратора
    admin_timezone = get_admin_timezone(callback.from_user.id)
    
    # Получаем текущую дату в часовом поясе администратора
    now = datetime.now(ZoneInfo(admin_timezone))
    
    # Создаем кнопки для следующих 7 дней
    keyboard = []
    for i in range(7):
        date = now + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        display_date = date.strftime("%d.%m.%Y (%a)")
        
        keyboard.append([
            InlineKeyboardButton(
                text=display_date,
                callback_data=ViewSlotsCallback(date=date_str).pack()
            )
        ])
    
    # Добавляем кнопки управления
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="time_slots")])
    keyboard.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")])
    
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.answer("📅 Выберите дату для просмотра слотов:", reply_markup=markup)
    
    await callback.answer()

@router.callback_query(ViewSlotsCallback.filter())
async def view_slots_for_date(callback: CallbackQuery, callback_data: ViewSlotsCallback):
    """Показывает доступные слоты для выбранной даты"""
    try:
        selected_date = callback_data.date
        
        # Получаем часовой пояс администратора
        admin_timezone = get_admin_timezone(callback.from_user.id)
        
        # Получаем слоты для выбранной даты
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{API_URL}/working_periods/time_slots",
                params={"date": selected_date}
            )
            response.raise_for_status()
            slots = response.json()
            
            if not slots:
                # Если слотов на эту дату нет
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад к выбору даты", callback_data="view_time_slots")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ])
                await callback.message.answer("❌ Нет слотов на выбранную дату", reply_markup=keyboard)
                await callback.answer()
                return
            
            # Форматируем дату для отображения с учетом часового пояса
            display_date = datetime.strptime(selected_date, "%Y-%m-%d").strftime("%d.%m.%Y")
            
            # Формируем сообщение со списком слотов
            message_text = f"📅 Слоты на {display_date}:\n\n"
            
            for slot in slots:
                # Форматируем время с учетом часового пояса администратора
                start_time_utc = datetime.fromisoformat(slot['start_time'].replace('Z', '+00:00')).replace(tzinfo=ZoneInfo("UTC"))
                end_time_utc = datetime.fromisoformat(slot['end_time'].replace('Z', '+00:00')).replace(tzinfo=ZoneInfo("UTC"))
                
                # Конвертируем в часовой пояс администратора
                start_time_local = start_time_utc.astimezone(ZoneInfo(admin_timezone))
                end_time_local = end_time_utc.astimezone(ZoneInfo(admin_timezone))
                
                start_time = start_time_local.strftime("%H:%M")
                end_time = end_time_local.strftime("%H:%M")
                
                time_range = f"{start_time} - {end_time}"
                status = "🟢 Свободен" if slot['is_available'] else "🔴 Занят"
                
                # Добавляем информацию о слоте в сообщение
                message_text += f"• {time_range}: {status}\n"
            
            # Создаем клавиатуру
            keyboard = [
                [InlineKeyboardButton(text="◀️ Назад к выбору даты", callback_data="view_time_slots")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ]
            
            markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            await callback.message.answer(message_text, reply_markup=markup)
        
    except Exception as e:
        logger.error(f"Ошибка при получении слотов для даты {callback_data.date}: {e}")
        await callback.message.answer("❌ Произошла ошибка при получении слотов")
    
    await callback.answer()

@router.callback_query(WorkingPeriodCallback.filter(F.action == "edit"))
async def edit_working_period(callback: CallbackQuery, callback_data: WorkingPeriodCallback):
    """Показывает меню редактирования рабочего периода"""
    try:
        period_id = callback_data.id
        
        # Получаем часовой пояс администратора
        admin_timezone = get_admin_timezone(callback.from_user.id)
        
        # Получаем информацию о периоде
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{API_URL}/working_periods/{period_id}")
            response.raise_for_status()
            period = response.json()
            
            # Форматируем даты с учетом часового пояса администратора
            start_date = datetime.fromisoformat(period['start_date'].replace('Z', '+00:00')).replace(tzinfo=ZoneInfo("UTC"))
            end_date = datetime.fromisoformat(period['end_date'].replace('Z', '+00:00')).replace(tzinfo=ZoneInfo("UTC"))
            
            # Конвертируем в часовой пояс администратора
            start_date_local = start_date.astimezone(ZoneInfo(admin_timezone))
            end_date_local = end_date.astimezone(ZoneInfo(admin_timezone))
            
            # Форматируем для отображения
            start_date_formatted = start_date_local.strftime("%d.%m.%Y")
            end_date_formatted = end_date_local.strftime("%d.%m.%Y")
            
            # Преобразуем время в местное время
            start_time_parts = period['start_time'].split(':')
            end_time_parts = period['end_time'].split(':')
            
            # Создаем временные объекты datetime с сегодняшней датой для преобразования времени
            today_utc = datetime.now(ZoneInfo("UTC")).replace(hour=int(start_time_parts[0]), minute=int(start_time_parts[1]), second=0, microsecond=0)
            today_utc_end = datetime.now(ZoneInfo("UTC")).replace(hour=int(end_time_parts[0]), minute=int(end_time_parts[1]), second=0, microsecond=0)
            
            # Конвертируем в местное время
            today_local = today_utc.astimezone(ZoneInfo(admin_timezone))
            today_local_end = today_utc_end.astimezone(ZoneInfo(admin_timezone))
            
            # Получаем отформатированное время
            start_time_formatted = today_local.strftime("%H:%M")
            end_time_formatted = today_local_end.strftime("%H:%M")
            
            # Формируем сообщение о периоде
            message_text = f"📅 Рабочий период:\n\n"
            message_text += f"Начало: {start_date_formatted}\n"
            message_text += f"Окончание: {end_date_formatted}\n"
            message_text += f"Время работы: {start_time_formatted} - {end_time_formatted}\n"
            message_text += f"Длительность слота: {period['slot_duration']} мин.\n"
            message_text += f"Статус: {'🟢 Активен' if period['is_active'] == 1 else '🔴 Не активен'}\n"
            
            # Создаем клавиатуру для редактирования
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✏️ Изменить даты", callback_data=WorkingPeriodCallback(id=period_id, action="edit_dates").pack())],
                [InlineKeyboardButton(text="✏️ Изменить время", callback_data=WorkingPeriodCallback(id=period_id, action="edit_times").pack())],
                [InlineKeyboardButton(text="✏️ Изменить длительность слота", callback_data=WorkingPeriodCallback(id=period_id, action="edit_duration").pack())],
                [
                    InlineKeyboardButton(
                        text="🟢 Активировать" if period['is_active'] == 0 else "🔴 Деактивировать",
                        callback_data=WorkingPeriodCallback(id=period_id, action="toggle_active").pack()
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="❌ Удалить",
                        callback_data=WorkingPeriodCallback(id=period_id, action="delete").pack()
                    )
                ],
                [
                    InlineKeyboardButton(text="◀️ Назад", callback_data="working_periods"),
                    InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
                ]
            ])
            
            await callback.message.edit_text(message_text, reply_markup=keyboard)
            await callback.answer()
            
    except Exception as e:
        logger.error(f"Ошибка при получении информации о рабочем периоде: {e}")
        await callback.message.answer("❌ Произошла ошибка при получении информации о рабочем периоде")
        await callback.answer()

@router.callback_query(WorkingPeriodCallback.filter(F.action == "toggle_active"))
async def toggle_active_period(callback: CallbackQuery, callback_data: WorkingPeriodCallback):
    """Переключает активность рабочего периода"""
    try:
        period_id = callback_data.id
        
        # Получаем текущий статус периода
        async with httpx.AsyncClient(timeout=30.0) as client:
            get_response = await client.get(f"{API_URL}/working_periods/{period_id}")
            get_response.raise_for_status()
            period = get_response.json()
            
            # Меняем активность на противоположную
            new_active = 0 if period['is_active'] == 1 else 1
            
            # Обновляем период
            update_response = await client.patch(
                f"{API_URL}/working_periods/{period_id}",
                json={"is_active": new_active}
            )
            update_response.raise_for_status()
            
            # Выводим сообщение об успехе
            status_text = "активирован" if new_active == 1 else "деактивирован"
            await callback.message.answer(f"✅ Рабочий период успешно {status_text}")
            
            # Возвращаемся к списку периодов
            await show_working_periods(callback)
            
    except Exception as e:
        logger.error(f"Ошибка при изменении активности рабочего периода: {e}")
        await callback.message.answer("❌ Произошла ошибка при изменении активности рабочего периода")
    
    await callback.answer()

@router.callback_query(WorkingPeriodCallback.filter(F.action == "delete"))
async def delete_working_period(callback: CallbackQuery, callback_data: WorkingPeriodCallback, state: FSMContext):
    """Подтверждение удаления рабочего периода"""
    period_id = callback_data.id
    
    try:
        # Получаем информацию о периоде
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{API_URL}/working_periods/{period_id}")
            response.raise_for_status()
            period = response.json()
            
            # Форматируем даты
            start_date = datetime.fromisoformat(period['start_date'].replace('Z', '+00:00')).strftime("%d.%m.%Y")
            end_date = datetime.fromisoformat(period['end_date'].replace('Z', '+00:00')).strftime("%d.%m.%Y")
            
            # Сохраняем id периода в состояние
            await state.update_data(period_id=period_id)
            
            # Создаем клавиатуру для подтверждения
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Да", callback_data="confirm_delete_period"),
                    InlineKeyboardButton(text="❌ Отмена", callback_data=WorkingPeriodCallback(id=period_id, action="edit").pack())
                ]
            ])
            
            await callback.message.answer(
                f"❓ Вы действительно хотите удалить рабочий период {start_date} - {end_date}?",
                reply_markup=keyboard
            )
            
            await state.set_state(DeleteWorkingPeriodState.waiting_for_confirmation)
            
    except Exception as e:
        logger.error(f"Ошибка при получении информации о рабочем периоде {period_id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при получении информации о рабочем периоде")
    
    await callback.answer()

@router.callback_query(F.data == "confirm_delete_period", DeleteWorkingPeriodState.waiting_for_confirmation)
async def confirm_delete_period(callback: CallbackQuery, state: FSMContext):
    """Подтверждение удаления рабочего периода"""
    data = await state.get_data()
    period_id = data['period_id']
    
    try:
        # Удаляем период
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(f"{API_URL}/working_periods/{period_id}")
            response.raise_for_status()
            
            await callback.message.answer("✅ Рабочий период успешно удален")
            
            # Возвращаемся к списку периодов
            await show_working_periods(callback)
            
    except Exception as e:
        logger.error(f"Ошибка при удалении рабочего периода {period_id}: {e}")
        await callback.message.answer("❌ Произошла ошибка при удалении рабочего периода")
    
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "create_working_period")
async def create_working_period(callback: CallbackQuery, state: FSMContext):
    """Начало процесса создания рабочего периода"""
    await callback.message.answer(
        "📅 Создание рабочего периода\n\n"
        "Введите начальную дату в формате ДД.ММ.ГГГГ:"
    )
    await state.set_state(CreateWorkingPeriodState.waiting_for_start_date)
    await callback.answer()

@router.callback_query(WorkingPeriodCallback.filter(F.action == "edit_dates"))
async def edit_period_dates(callback: CallbackQuery, callback_data: WorkingPeriodCallback, state: FSMContext):
    """Начало редактирования дат рабочего периода"""
    try:
        period_id = callback_data.id
        
        # Получаем информацию о периоде
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{API_URL}/working_periods/{period_id}")
            response.raise_for_status()
            period = response.json()
        
        # Сохраняем ID периода в состоянии
        await state.update_data(period_id=period_id, original_period=period)
        
        await callback.message.answer("Введите новую начальную дату в формате ДД.ММ.ГГГГ:")
        await state.set_state(CreateWorkingPeriodState.waiting_for_start_date)
        
    except Exception as e:
        logger.error(f"Ошибка при начале редактирования дат рабочего периода: {e}")
        await callback.message.answer("❌ Произошла ошибка при получении информации о рабочем периоде")
    
    await callback.answer()

@router.callback_query(WorkingPeriodCallback.filter(F.action == "edit_times"))
async def edit_period_times(callback: CallbackQuery, callback_data: WorkingPeriodCallback, state: FSMContext):
    """Начало редактирования времени рабочего периода"""
    try:
        period_id = callback_data.id
        
        # Получаем информацию о периоде
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{API_URL}/working_periods/{period_id}")
            response.raise_for_status()
            period = response.json()
        
        # Сохраняем ID периода и текущие данные в состоянии
        await state.update_data(
            period_id=period_id, 
            original_period=period,
            start_date=period["start_date"],
            end_date=period["end_date"]
        )
        
        await callback.message.answer("Введите новое начальное время работы в формате ЧЧ:ММ:")
        await state.set_state(CreateWorkingPeriodState.waiting_for_start_time)
        
    except Exception as e:
        logger.error(f"Ошибка при начале редактирования времени рабочего периода: {e}")
        await callback.message.answer("❌ Произошла ошибка при получении информации о рабочем периоде")
    
    await callback.answer()

@router.callback_query(WorkingPeriodCallback.filter(F.action == "edit_duration"))
async def edit_period_duration(callback: CallbackQuery, callback_data: WorkingPeriodCallback, state: FSMContext):
    """Начало редактирования длительности слота"""
    try:
        period_id = callback_data.id
        
        # Получаем информацию о периоде
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{API_URL}/working_periods/{period_id}")
            response.raise_for_status()
            period = response.json()
        
        # Сохраняем ID периода и текущие данные в состоянии
        await state.update_data(
            period_id=period_id, 
            original_period=period,
            start_date=period["start_date"],
            end_date=period["end_date"],
            start_time=period["start_time"],
            end_time=period["end_time"]
        )
        
        await callback.message.answer(f"Текущая длительность слота: {period['slot_duration']} мин.\nВведите новую длительность слота в минутах (от 15 до 240):")
        await state.set_state(CreateWorkingPeriodState.waiting_for_duration)
        
    except Exception as e:
        logger.error(f"Ошибка при начале редактирования длительности слота: {e}")
        await callback.message.answer("❌ Произошла ошибка при получении информации о рабочем периоде")
    
    await callback.answer()

@router.message(CreateWorkingPeriodState.waiting_for_start_date)
async def process_start_date(message: Message, state: FSMContext):
    """Обработка ввода начальной даты"""
    try:
        # Получаем часовой пояс администратора
        admin_timezone = get_admin_timezone(message.from_user.id)
        
        # Парсим дату с учетом часового пояса администратора
        local_date = datetime.strptime(message.text.strip(), "%d.%m.%Y")
        # Устанавливаем часовой пояс администратора и время 00:00:00
        local_date = local_date.replace(hour=0, minute=0, second=0, microsecond=0)
        local_date = local_date.replace(tzinfo=ZoneInfo(admin_timezone))
        
        # Конвертируем в UTC
        utc_date = local_date.astimezone(ZoneInfo("UTC"))
        
        # Сохраняем дату в UTC
        await state.update_data(start_date=utc_date.isoformat())
        
        await message.answer("Введите конечную дату в формате ДД.ММ.ГГГГ:")
        await state.set_state(CreateWorkingPeriodState.waiting_for_end_date)
        
    except ValueError:
        await message.answer("❌ Неверный формат даты. Введите дату в формате ДД.ММ.ГГГГ:")
        
@router.message(CreateWorkingPeriodState.waiting_for_end_date)
async def process_end_date(message: Message, state: FSMContext):
    """Обработка ввода конечной даты"""
    try:
        # Получаем часовой пояс администратора
        admin_timezone = get_admin_timezone(message.from_user.id)
        
        # Парсим дату с учетом часового пояса администратора
        local_end_date = datetime.strptime(message.text.strip(), "%d.%m.%Y")
        # Устанавливаем часовой пояс администратора и время 23:59:59
        local_end_date = local_end_date.replace(hour=23, minute=59, second=59, microsecond=0)
        local_end_date = local_end_date.replace(tzinfo=ZoneInfo(admin_timezone))
        
        # Конвертируем в UTC
        utc_end_date = local_end_date.astimezone(ZoneInfo("UTC"))
        
        data = await state.get_data()
        start_date = datetime.fromisoformat(data['start_date'])
        
        # Проверяем, что конечная дата не раньше начальной
        if utc_end_date.date() < start_date.date():
            await message.answer("❌ Конечная дата не может быть раньше начальной. Введите корректную дату:")
            return
        
        await state.update_data(end_date=utc_end_date.isoformat())
        
        # Проверяем, редактируем ли существующий период или создаем новый
        if 'period_id' in data and 'original_period' in data:
            # Если это редактирование дат, обновляем период
            period_id = data['period_id']
            original_period = data['original_period']
            
            # Сохраняем оригинальные значения для других полей
            update_data = {
                "start_date": data['start_date'],
                "end_date": utc_end_date.isoformat(),
                "start_time": original_period['start_time'],
                "end_time": original_period['end_time'],
                "slot_duration": original_period['slot_duration']
            }
            
            # Обновляем рабочий период
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.patch(
                    f"{API_URL}/working_periods/{period_id}",
                    json=update_data
                )
                response.raise_for_status()
                
                await message.answer("✅ Даты рабочего периода успешно обновлены")
                
                # Показываем список рабочих периодов
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📅 Просмотреть рабочие периоды", callback_data="working_periods")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ])
                
                await message.answer("Выберите действие:", reply_markup=keyboard)
                await state.clear()
        else:
            # Для создания нового периода запрашиваем время
            await message.answer("Введите начальное время работы в формате ЧЧ:ММ:")
            await state.set_state(CreateWorkingPeriodState.waiting_for_start_time)
        
    except ValueError:
        await message.answer("❌ Неверный формат даты. Введите дату в формате ДД.ММ.ГГГГ:")
    except Exception as e:
        logger.error(f"Ошибка при обработке даты: {e}")
        await message.answer("❌ Произошла ошибка при обработке даты. Пожалуйста, попробуйте позже.")

@router.message(CreateWorkingPeriodState.waiting_for_start_time)
async def process_start_time(message: Message, state: FSMContext):
    """Обработка ввода начального времени"""
    try:
        # Получаем часовой пояс администратора
        admin_timezone = get_admin_timezone(message.from_user.id)
        
        # Проверяем формат времени
        time_parts = message.text.strip().split(':')
        if len(time_parts) != 2:
            raise ValueError("Invalid time format")
        
        start_hour, start_minute = map(int, time_parts)
        if not (0 <= start_hour < 24 and 0 <= start_minute < 60):
            raise ValueError("Invalid time values")
        
        # Создаем временный объект datetime для преобразования времени из местного в UTC
        # Используем текущую дату просто как базу для преобразования времени
        local_time = datetime.now(ZoneInfo(admin_timezone)).replace(
            hour=start_hour, 
            minute=start_minute, 
            second=0, 
            microsecond=0
        )
        
        # Конвертируем в UTC
        utc_time = local_time.astimezone(ZoneInfo("UTC"))
        
        # Сохраняем только время в формате ЧЧ:ММ
        utc_time_str = utc_time.strftime("%H:%M")
        
        await state.update_data(start_time=utc_time_str)
        
        await message.answer("Введите конечное время работы в формате ЧЧ:ММ:")
        await state.set_state(CreateWorkingPeriodState.waiting_for_end_time)
        
    except ValueError:
        await message.answer("❌ Неверный формат времени. Введите время в формате ЧЧ:ММ:")

@router.message(CreateWorkingPeriodState.waiting_for_end_time)
async def process_end_time(message: Message, state: FSMContext):
    """Обработка ввода конечного времени"""
    try:
        # Получаем часовой пояс администратора
        admin_timezone = get_admin_timezone(message.from_user.id)
        
        # Проверяем формат времени
        time_parts = message.text.strip().split(':')
        if len(time_parts) != 2:
            raise ValueError("Invalid time format")
        
        end_hour, end_minute = map(int, time_parts)
        if not (0 <= end_hour < 24 and 0 <= end_minute < 60):
            raise ValueError("Invalid time values")
        
        data = await state.get_data()
        start_time = data['start_time']
        
        # Создаем временные объекты datetime для сравнения времени
        # Нам нужно привести оба времени к одной дате в местном времени для сравнения
        today_local = datetime.now(ZoneInfo(admin_timezone)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        
        # Преобразуем start_time из UTC в объект datetime в местном времени
        start_hour_utc, start_minute_utc = map(int, start_time.split(':'))
        start_time_utc = datetime.now(ZoneInfo("UTC")).replace(
            hour=start_hour_utc, minute=start_minute_utc, second=0, microsecond=0
        )
        start_time_local = start_time_utc.astimezone(ZoneInfo(admin_timezone))
        
        # Создаем объект для введенного end_time в местном времени
        end_time_local = today_local.replace(hour=end_hour, minute=end_minute)
        
        # Проверяем, что конечное время позже начального
        if end_time_local.time() <= start_time_local.time():
            await message.answer("❌ Конечное время должно быть позже начального. Введите корректное время:")
            return
        
        # Преобразуем end_time из местного времени в UTC
        end_time_with_tz = datetime.now(ZoneInfo(admin_timezone)).replace(
            hour=end_hour, minute=end_minute, second=0, microsecond=0
        )
        end_time_utc = end_time_with_tz.astimezone(ZoneInfo("UTC"))
        end_time_utc_str = end_time_utc.strftime("%H:%M")
        
        await state.update_data(end_time=end_time_utc_str)
        
        # Проверяем, редактируем ли существующий период или создаем новый
        if 'period_id' in data and 'slot_duration' in data.get('original_period', {}):
            # Если это редактирование и у нас уже есть длительность слота, то обновляем период
            period_id = data['period_id']
            update_data = {
                "start_time": data['start_time'],
                "end_time": end_time_utc_str
            }
            
            # Обновляем рабочий период
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.patch(
                    f"{API_URL}/working_periods/{period_id}",
                    json=update_data
                )
                response.raise_for_status()
                
                await message.answer("✅ Время работы успешно обновлено")
                
                # Показываем список рабочих периодов
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📅 Просмотреть рабочие периоды", callback_data="working_periods")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ])
                
                await message.answer("Выберите действие:", reply_markup=keyboard)
                await state.clear()
        else:
            # Для создания нового периода или если нет информации о длительности слота
            await message.answer(
                "Введите продолжительность одного слота в минутах (например, 60):"
            )
            await state.set_state(CreateWorkingPeriodState.waiting_for_duration)
        
    except ValueError:
        await message.answer("❌ Неверный формат времени. Введите время в формате ЧЧ:ММ:")
    except Exception as e:
        logger.error(f"Ошибка при обработке времени: {e}")
        await message.answer("❌ Произошла ошибка при обработке времени. Пожалуйста, попробуйте позже.")

@router.message(CreateWorkingPeriodState.waiting_for_duration)
async def process_duration(message: Message, state: FSMContext):
    """Обработка ввода продолжительности слота"""
    try:
        duration = int(message.text.strip())
        
        if duration < 15 or duration > 240:
            await message.answer("❌ Продолжительность слота должна быть от 15 до 240 минут. Введите корректную продолжительность:")
            return
        
        data = await state.get_data()
        
        # Проверяем, редактируем ли существующий период или создаем новый
        if 'period_id' in data:
            # Редактирование существующего периода
            period_id = data['period_id']
            update_data = {
                "slot_duration": duration
            }
            
            # Добавляем остальные поля, если они есть в состоянии
            if 'start_date' in data:
                update_data["start_date"] = data['start_date']
            if 'end_date' in data:
                update_data["end_date"] = data['end_date']
            if 'start_time' in data:
                update_data["start_time"] = data['start_time']
            if 'end_time' in data:
                update_data["end_time"] = data['end_time']
            
            # Обновляем рабочий период
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.patch(
                    f"{API_URL}/working_periods/{period_id}",
                    json=update_data
                )
                response.raise_for_status()
                
                await message.answer("✅ Рабочий период успешно обновлен")
                
                # Показываем список рабочих периодов
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📅 Просмотреть рабочие периоды", callback_data="working_periods")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ])
                
                await message.answer("Выберите действие:", reply_markup=keyboard)
        else:
            # Создание нового периода
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{API_URL}/working_periods",
                    json={
                        "start_date": data['start_date'],
                        "end_date": data['end_date'],
                        "start_time": data['start_time'],
                        "end_time": data['end_time'],
                        "slot_duration": duration,
                        "is_active": 1
                    }
                )
                response.raise_for_status()
                
                await message.answer("✅ Рабочий период успешно создан")
                
                # Показываем список рабочих периодов
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📅 Просмотреть рабочие периоды", callback_data="working_periods")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ])
                
                await message.answer("Выберите действие:", reply_markup=keyboard)
        
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Пожалуйста, введите число для продолжительности слота:")
    except Exception as e:
        logger.error(f"Ошибка при обновлении рабочего периода: {e}")
        await message.answer("❌ Произошла ошибка при обновлении рабочего периода. Пожалуйста, попробуйте позже.")
        await state.clear() 