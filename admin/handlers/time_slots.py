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

from ..config import API_URL

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
        # Получаем список рабочих периодов
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{API_URL}/working_periods")
            response.raise_for_status()
            periods = response.json()
            
            if not periods:
                # Если периодов нет, предлагаем создать их
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Создать рабочий период", callback_data="create_working_period")],
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="time_slots")]
                ])
                await callback.message.answer("❌ Нет рабочих периодов", reply_markup=keyboard)
                await callback.answer()
                return
            
            # Формируем сообщение с рабочими периодами
            message_text = "📅 Рабочие периоды:\n\n"
            
            # Создаем кнопки для каждого периода
            keyboard = []
            
            for period in periods:
                # Форматируем даты и времена
                start_date = datetime.fromisoformat(period['start_date'].replace('Z', '+00:00')).strftime("%d.%m.%Y")
                end_date = datetime.fromisoformat(period['end_date'].replace('Z', '+00:00')).strftime("%d.%m.%Y")
                
                status = "🟢 Активен" if period['is_active'] == 1 else "🔴 Не активен"
                
                # Добавляем информацию о периоде в сообщение
                message_text += f"• {start_date} - {end_date}: {period['start_time']}-{period['end_time']}, {period['slot_duration']} мин. {status}\n"
                
                # Добавляем кнопку
                keyboard.append([
                    InlineKeyboardButton(
                        text=f"✏️ {start_date} - {end_date}",
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
    # Получаем текущую дату
    now = datetime.now()
    
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
    
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await callback.message.answer("📅 Выберите дату для просмотра слотов:", reply_markup=markup)
    
    await callback.answer()

@router.callback_query(ViewSlotsCallback.filter())
async def view_slots_for_date(callback: CallbackQuery, callback_data: ViewSlotsCallback):
    """Показывает доступные слоты для выбранной даты"""
    try:
        selected_date = callback_data.date
        
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
                    [InlineKeyboardButton(text="◀️ Назад к выбору даты", callback_data="view_time_slots")]
                ])
                await callback.message.answer("❌ Нет слотов на выбранную дату", reply_markup=keyboard)
                await callback.answer()
                return
            
            # Форматируем дату для отображения
            display_date = datetime.strptime(selected_date, "%Y-%m-%d").strftime("%d.%m.%Y")
            
            # Формируем сообщение со списком слотов
            message_text = f"📅 Слоты на {display_date}:\n\n"
            
            for slot in slots:
                start_time = datetime.fromisoformat(slot['start_time'].replace('Z', '+00:00')).strftime("%H:%M")
                end_time = datetime.fromisoformat(slot['end_time'].replace('Z', '+00:00')).strftime("%H:%M")
                
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
        
        # Получаем информацию о периоде
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{API_URL}/working_periods/{period_id}")
            response.raise_for_status()
            period = response.json()
            
            # Форматируем даты и времена
            start_date = datetime.fromisoformat(period['start_date'].replace('Z', '+00:00')).strftime("%d.%m.%Y")
            end_date = datetime.fromisoformat(period['end_date'].replace('Z', '+00:00')).strftime("%d.%m.%Y")
            
            # Формируем сообщение о периоде
            message_text = f"📅 Рабочий период:\n\n"
            message_text += f"Начало: {start_date}\n"
            message_text += f"Окончание: {end_date}\n"
            message_text += f"Время работы: {period['start_time']} - {period['end_time']}\n"
            message_text += f"Длительность слота: {period['slot_duration']} мин.\n"
            message_text += f"Статус: {'🟢 Активен' if period['is_active'] == 1 else '🔴 Не активен'}\n"
            
            # Создаем кнопки редактирования
            keyboard = [
                [InlineKeyboardButton(text="✏️ Изменить даты", callback_data=WorkingPeriodCallback(id=period_id, action="edit_dates").pack())],
                [InlineKeyboardButton(text="✏️ Изменить время", callback_data=WorkingPeriodCallback(id=period_id, action="edit_times").pack())],
                [InlineKeyboardButton(text="✏️ Изменить длительность слота", callback_data=WorkingPeriodCallback(id=period_id, action="edit_duration").pack())],
                [InlineKeyboardButton(
                    text="🔴 Деактивировать" if period['is_active'] == 1 else "🟢 Активировать", 
                    callback_data=WorkingPeriodCallback(id=period_id, action="toggle_active").pack()
                )],
                [InlineKeyboardButton(text="❌ Удалить", callback_data=WorkingPeriodCallback(id=period_id, action="delete").pack())],
                [InlineKeyboardButton(text="◀️ Назад", callback_data="working_periods")]
            ]
            
            markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
            await callback.message.answer(message_text, reply_markup=markup)
            
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

@router.message(CreateWorkingPeriodState.waiting_for_start_date)
async def process_start_date(message: Message, state: FSMContext):
    """Обработка ввода начальной даты"""
    try:
        start_date = datetime.strptime(message.text.strip(), "%d.%m.%Y")
        await state.update_data(start_date=start_date.isoformat())
        
        await message.answer("Введите конечную дату в формате ДД.ММ.ГГГГ:")
        await state.set_state(CreateWorkingPeriodState.waiting_for_end_date)
        
    except ValueError:
        await message.answer("❌ Неверный формат даты. Введите дату в формате ДД.ММ.ГГГГ:")

@router.message(CreateWorkingPeriodState.waiting_for_end_date)
async def process_end_date(message: Message, state: FSMContext):
    """Обработка ввода конечной даты"""
    try:
        end_date = datetime.strptime(message.text.strip(), "%d.%m.%Y")
        data = await state.get_data()
        start_date = datetime.fromisoformat(data['start_date'])
        
        # Проверяем, что конечная дата не раньше начальной
        if end_date.date() < start_date.date():
            await message.answer("❌ Конечная дата не может быть раньше начальной. Введите корректную дату:")
            return
        
        await state.update_data(end_date=end_date.isoformat())
        
        await message.answer("Введите начальное время работы в формате ЧЧ:ММ:")
        await state.set_state(CreateWorkingPeriodState.waiting_for_start_time)
        
    except ValueError:
        await message.answer("❌ Неверный формат даты. Введите дату в формате ДД.ММ.ГГГГ:")

@router.message(CreateWorkingPeriodState.waiting_for_start_time)
async def process_start_time(message: Message, state: FSMContext):
    """Обработка ввода начального времени"""
    try:
        # Проверяем формат времени
        time_parts = message.text.strip().split(':')
        if len(time_parts) != 2:
            raise ValueError("Invalid time format")
        
        start_hour, start_minute = map(int, time_parts)
        if not (0 <= start_hour < 24 and 0 <= start_minute < 60):
            raise ValueError("Invalid time values")
        
        await state.update_data(start_time=f"{start_hour:02d}:{start_minute:02d}")
        
        await message.answer("Введите конечное время работы в формате ЧЧ:ММ:")
        await state.set_state(CreateWorkingPeriodState.waiting_for_end_time)
        
    except ValueError:
        await message.answer("❌ Неверный формат времени. Введите время в формате ЧЧ:ММ:")

@router.message(CreateWorkingPeriodState.waiting_for_end_time)
async def process_end_time(message: Message, state: FSMContext):
    """Обработка ввода конечного времени"""
    try:
        # Проверяем формат времени
        time_parts = message.text.strip().split(':')
        if len(time_parts) != 2:
            raise ValueError("Invalid time format")
        
        end_hour, end_minute = map(int, time_parts)
        if not (0 <= end_hour < 24 and 0 <= end_minute < 60):
            raise ValueError("Invalid time values")
        
        data = await state.get_data()
        start_time = data['start_time']
        start_hour, start_minute = map(int, start_time.split(':'))
        
        # Проверяем, что конечное время позже начального
        if end_hour < start_hour or (end_hour == start_hour and end_minute <= start_minute):
            await message.answer("❌ Конечное время должно быть позже начального. Введите корректное время:")
            return
        
        await state.update_data(end_time=f"{end_hour:02d}:{end_minute:02d}")
        
        await message.answer(
            "Введите продолжительность одного слота в минутах (например, 60):"
        )
        await state.set_state(CreateWorkingPeriodState.waiting_for_duration)
        
    except ValueError:
        await message.answer("❌ Неверный формат времени. Введите время в формате ЧЧ:ММ:")

@router.message(CreateWorkingPeriodState.waiting_for_duration)
async def process_duration(message: Message, state: FSMContext):
    """Обработка ввода продолжительности слота"""
    try:
        duration = int(message.text.strip())
        
        if duration < 15 or duration > 240:
            await message.answer("❌ Продолжительность слота должна быть от 15 до 240 минут. Введите корректную продолжительность:")
            return
        
        data = await state.get_data()
        
        # Создаем рабочий период
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
        logger.error(f"Ошибка при создании рабочего периода: {e}")
        await message.answer("❌ Произошла ошибка при создании рабочего периода. Пожалуйста, попробуйте позже.")
        await state.clear() 