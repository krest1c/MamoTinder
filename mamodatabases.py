from aiogram import Bot, Dispatcher, F, Router
import re
from aiogram.enums.chat_member_status import ChatMemberStatus
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import message
import mamokeyboardsAmvera as kb
import sqlite3
import pytz
import random
from aiogram.utils.keyboard import InlineKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import asyncio
from time import sleep
import logging
from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton, 
                           InlineKeyboardMarkup, InlineKeyboardButton)
from aiogram.types import ReplyKeyboardRemove
import time
import datetime
import functools
from typing import Callable, Any
import traceback
from datetime import datetime, timedelta
from typing import Dict, Optional
import os
import sys



BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = "/data"  # ВСЕГДА используем /data для Amvera (persistent storage)

# Создаем поддиректории для лучшей организации
DB_DIR = os.path.join(DATA_DIR, "databases")
LOGS_DIR = os.path.join(DATA_DIR, "logs")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")

# Пути к файлам базы данных (определим после инициализации директорий)
DB_PATH = None
BACKUP_DB_PATH = None

# Глобальные флаги для контроля изменений
_directory_initialized = False

# Создаем все необходимые директории при запуске
def init_directories():
    """Инициализирует все необходимые директории для хранения данных"""
    global DB_DIR, LOGS_DIR, BACKUP_DIR, DB_PATH, BACKUP_DB_PATH, _directory_initialized
    
    if _directory_initialized:
        return
    
    directories = [DATA_DIR, DB_DIR, LOGS_DIR, BACKUP_DIR]
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            print(f"✅ Директория создана/проверена: {directory}")
        except Exception as e:
            print(f"❌ Ошибка при создании директории {directory}: {e}")
            # Для критических директорий пробуем альтернативные пути
            if "databases" in directory:
                DB_DIR = DATA_DIR
                print(f"⚠️ Используем основную директорию для БД: {DB_DIR}")
            elif "logs" in directory:
                LOGS_DIR = DATA_DIR
                print(f"⚠️ Используем основную директорию для логов: {LOGS_DIR}")
            elif "backups" in directory:
                BACKUP_DIR = DATA_DIR
                print(f"⚠️ Используем основную директорию для бэкапов: {BACKUP_DIR}")
    
    # Теперь определяем пути к файлам
    DB_PATH = os.path.join(DB_DIR, "mamobot.sql")
    BACKUP_DB_PATH = os.path.join(BACKUP_DIR, "mamobot_backup.sql")
    
    print(f"📁 Путь к базе данных: {DB_PATH}")
    print(f"📁 Путь к логам: {LOGS_DIR}")
    print(f"📁 Путь к бэкапам: {BACKUP_DIR}")
    
    _directory_initialized = True

# Инициализируем директории сразу при импорте
init_directories()

#ЛОГИРОВАНИЕ
# Простой логгер для демонстрации
class SimpleLogger:
    def __init__(self):
        # Убедимся, что директории инициализированы
        if not _directory_initialized:
            init_directories()
            
        self.log_file = os.path.join(LOGS_DIR, 'bot_activity.log')
        self.error_log_file = os.path.join(LOGS_DIR, 'errors_detailed.log')
        
        print(f"📁 Путь к лог файлу: {self.log_file}")
        print(f"📁 Путь к файлу ошибок: {self.error_log_file}")
        
        # Создаем файлы логов если их нет
        self._ensure_log_files()
    
    def _ensure_log_files(self):
        """Создает файлы логов если они не существуют"""
        try:
            if not os.path.exists(self.log_file):
                with open(self.log_file, 'w', encoding='utf-8') as f:
                    f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [INFO] Лог файл создан\n")
                print(f"✅ Создан лог файл: {self.log_file}")
            
            if not os.path.exists(self.error_log_file):
                with open(self.error_log_file, 'w', encoding='utf-8') as f:
                    f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [INFO] Файл ошибок создан\n")
                print(f"✅ Создан файл ошибок: {self.error_log_file}")
                
        except Exception as e:
            print(f"❌ Ошибка при создании лог файлов: {e}")
            # Используем базовую директорию как запасной вариант
            self.log_file = os.path.join(BASE_DIR, 'bot_activity.log')
            self.error_log_file = os.path.join(BASE_DIR, 'errors_detailed.log')
    
    def log(self, level: str, message: str):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] [{level.upper()}] {message}\n"
        
        # Всегда выводим в консоль
        print(log_entry.strip())
        
        # Пытаемся записать в файл
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except Exception as e:
            # Если не удалось записать в основной файл, пробуем альтернативный
            print(f"⚠️ Не удалось записать в лог файл {self.log_file}: {e}")
            try:
                fallback_log = os.path.join(BASE_DIR, 'bot_activity_fallback.log')
                with open(fallback_log, 'a', encoding='utf-8') as f:
                    f.write(log_entry)
            except Exception as e2:
                print(f"❌ Не удалось записать и в запасной лог файл: {e2}")
    
    def info(self, message: str):
        self.log('INFO', message)
    
    def error(self, message: str):
        self.log('ERROR', message)
    
    def warning(self, message: str):
        self.log('WARNING', message)
    
    def log_error_details(self, error_msg: str, traceback_str: str, user_info: str = "", command_text: str = ""):
        """Детальное логирование ошибок в отдельный файл"""
        try:
            with open(self.error_log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*80}\n")
                f.write(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                if user_info:
                    f.write(f"Пользователь: {user_info}\n")
                if command_text:
                    f.write(f"Команда: {command_text}\n")
                f.write(f"Ошибка: {error_msg}\n")
                f.write(f"Трейсбэк:\n{traceback_str}\n")
                f.write(f"{'='*80}\n")
        except Exception as e:
            print(f"❌ Ошибка при записи детального лога: {e}")
    # В классе SimpleLogger добавьте этот метод (после __init__):
    def cleanup_old_logs(self, days: int = 7):
        """Удаляет лог файлы старше указанного количества дней"""
        try:
            import time
            from datetime import datetime, timedelta
            
            current_time = time.time()
            deleted_count = 0
            cutoff_time = current_time - (days * 24 * 60 * 60)
            
            self.info(f"🔄 Начинаю очистку логов старше {days} дней...")
            self.info(f"⏰ Текущее время: {datetime.now()}")
            self.info(f"⏰ Время отсечки: {datetime.fromtimestamp(cutoff_time)}")
            
            # Проверяем основные лог файлы логгера
            log_files = [self.log_file, self.error_log_file]
            
            for log_file in log_files:
                if os.path.exists(log_file):
                    file_mtime = os.path.getmtime(log_file)
                    file_age_days = (current_time - file_mtime) / (60 * 60 * 24)
                    file_mtime_str = datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M:%S')
                    
                    self.info(f"📄 Файл: {os.path.basename(log_file)}, "
                            f"Последнее изменение: {file_mtime_str}, "
                            f"Возраст: {file_age_days:.1f} дней, "
                            f"Удалять? {file_mtime < cutoff_time}")
                    
                    if file_mtime < cutoff_time:
                        try:
                            file_size = os.path.getsize(log_file)
                            os.remove(log_file)
                            deleted_count += 1
                            self.info(f"🗑️ Удален старый лог файл: {os.path.basename(log_file)} "
                                    f"(возраст: {file_age_days:.1f} дней, размер: {file_size} байт)")
                            
                            # Создаем новый пустой файл
                            with open(log_file, 'w', encoding='utf-8') as f:
                                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [INFO] Лог файл создан\n")
                            self.info(f"✅ Создан новый лог файл: {os.path.basename(log_file)}")
                            
                        except Exception as e:
                            self.error(f"❌ Не удалось удалить файл {log_file}: {e}")
                    else:
                        self.info(f"✅ Файл {os.path.basename(log_file)} не удален (возраст {file_age_days:.1f} дней)")
            
            # Также проверяем директорию логов на наличие других лог файлов
            if os.path.exists(LOGS_DIR):
                self.info(f"📁 Проверяю директорию логов: {LOGS_DIR}")
                
                for filename in os.listdir(LOGS_DIR):
                    if filename.endswith('.log'):
                        file_path = os.path.join(LOGS_DIR, filename)
                        if os.path.exists(file_path):
                            try:
                                file_mtime = os.path.getmtime(file_path)
                                file_age_days = (current_time - file_mtime) / (60 * 60 * 24)
                                file_mtime_str = datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M:%S')
                                
                                self.info(f"📄 Файл в директории: {filename}, "
                                        f"Последнее изменение: {file_mtime_str}, "
                                        f"Возраст: {file_age_days:.1f} дней, "
                                        f"Удалять? {file_mtime < cutoff_time}")
                                
                                if file_mtime < cutoff_time:
                                    file_size = os.path.getsize(file_path)
                                    os.remove(file_path)
                                    deleted_count += 1
                                    self.info(f"🗑️ Удален лог файл из директории: {filename} "
                                            f"(возраст: {file_age_days:.1f} дней, размер: {file_size} байт)")
                                else:
                                    self.info(f"✅ Файл {filename} не удален (возраст {file_age_days:.1f} дней)")
                                    
                            except Exception as e:
                                self.error(f"❌ Ошибка при обработке файла {filename}: {e}")
            else:
                self.warning(f"⚠️ Директория логов не существует: {LOGS_DIR}")
            
            self.info(f"📊 Итог очистки логов: удалено {deleted_count} файлов")
            return deleted_count
            
        except Exception as e:
            self.error(f"❌ Ошибка при очистке старых логов: {e}")
            import traceback
            self.error(f"Трейсбэк: {traceback.format_exc()}")
            return 0
# Инициализируем логгер
logger = SimpleLogger()

# Декоратор для логирования команд
def log_command(func: Callable) -> Callable:
    """
    Декоратор для автоматического логирования выполнения команд бота.
    Логирует: кто, какую команду выполнил, успешно или с ошибкой.
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        
        try:
            # Первый аргумент в хендлерах aiogram - обычно Message или CallbackQuery
            message = None
            for arg in args:
                if hasattr(arg, 'from_user') and hasattr(arg, 'text'):
                    message = arg
                    break
                elif hasattr(arg, 'from_user') and hasattr(arg, 'data'):
                    callback = arg
                    message = callback.message
                    break
            
            # Логируем начало выполнения
            if message:
                user_info = f"@{message.from_user.username}" if message.from_user.username else f"ID: {message.from_user.id}"
                command_text = message.text if hasattr(message, 'text') else f"callback: {callback.data}"
                
                logger.info(f"🟢 НАЧАЛО: {user_info} выполняет команду: {command_text[:100]}")
            
            # Выполняем оригинальную функцию
            result = await func(*args, **kwargs)
            
            # Рассчитываем время выполнения
            execution_time = time.time() - start_time
            
            # Логируем успешное завершение
            if message:
                user_info = f"@{message.from_user.username}" if message.from_user.username else f"ID: {message.from_user.id}"
                command_text = message.text if hasattr(message, 'text') else f"callback: {callback.data}"
                
                logger.info(f"✅ УСПЕХ: {user_info} выполнил команду за {execution_time:.2f}с: {command_text[:50]}")
            
            return result
            
        except Exception as e:
            # Рассчитываем время до ошибки
            execution_time = time.time() - start_time
            
            # Логируем ошибку
            error_trace = traceback.format_exc()
            
            if message:
                user_info = f"@{message.from_user.username}" if message.from_user.username else f"ID: {message.from_user.id}"
                command_text = message.text if hasattr(message, 'text') else "unknown command"
                
                error_msg = (
                    f"❌ ОШИБКА: {user_info} | Команда: {command_text[:50]} | "
                    f"Время: {execution_time:.2f}с | "
                    f"Ошибка: {type(e).__name__}: {str(e)[:200]}"
                )
                logger.error(error_msg)
                
                # Детальное логирование ошибки
                logger.log_error_details(
                    f"{type(e).__name__}: {str(e)}",
                    error_trace,
                    user_info,
                    command_text
                )
            
            # Пробрасываем ошибку дальше
            raise
    
    return wrapper
def validate_input(max_chars: int = 20, field_name: str = ""):
    """Декоратор для проверки ограничения количества символов"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                message = args[0] if len(args) > 0 else None
                
                if message and hasattr(message, 'text') and message.text:
                    # Проверяем отмену
                    if message.text == "❌ Отмена":
                        return await func(*args, **kwargs)
                    
                    # Проверяем длину текста
                    if len(message.text) > max_chars:
                        await message.reply(
                            f"⚠️ <b>Слишком длинный текст!</b>\n\n"
                            f"Для поля '{field_name}' максимально допустимо <b>{max_chars} символов</b>.\n"
                            f"Ваш текст содержит {len(message.text)} символов.\n\n"
                            f"Пожалуйста, введите текст короче:",
                            parse_mode="html"
                        )
                        return  # Не вызываем оригинальную функцию
                
                return await func(*args, **kwargs)
                
            except Exception as e:
                logger.error(f"Ошибка в декораторе validate_input: {str(e)}")
                return await func(*args, **kwargs)
            
        return wrapper
    return decorator
# Декоратор для логирования действий администраторов
def log_admin_action(action_description: str = ""):
    """
    Декоратор для логирования действий администраторов.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                # Получаем сообщение
                message = None
                for arg in args:
                    if hasattr(arg, 'from_user'):
                        message = arg
                        break
                
                if message and message.from_user.id == 1088006569:
                    user_info = f"@{message.from_user.username}" if message.from_user.username else f"ID: {message.from_user.id}"
                    
                    # Логируем начало админского действия
                    logger.warning(f"👑 АДМИН ДЕЙСТВИЕ: {user_info} | {action_description}")
                    
                    # Если есть reply_to_message, логируем цель
                    if hasattr(message, 'reply_to_message') and message.reply_to_message:
                        target_user = message.reply_to_message.from_user
                        target_info = f"@{target_user.username}" if target_user.username else f"ID: {target_user.id}"
                        logger.warning(f"   🎯 Цель: {target_info}")
                
                # Выполняем функцию
                return await func(*args, **kwargs)
                
            except Exception as e:
                if message and message.from_user.id == 1088006569:
                    user_info = f"@{message.from_user.username}" if message.from_user.username else f"ID: {message.from_user.id}"
                    logger.error(f"👑 ОШИБКА АДМИНА: {user_info} | {action_description} | Ошибка: {str(e)[:100]}")
                raise
            
        return wrapper
    return decorator

# Декоратор для логирования создания/удаления анкет
def log_profile_action(action_type: str):
    """
    Декоратор для логирования действий с анкетами.
    action_type: 'create', 'update', 'delete', 'view'
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                message = None
                for arg in args:
                    if hasattr(arg, 'from_user'):
                        message = arg
                        break
                
                if message:
                    user_info = f"@{message.from_user.username}" if message.from_user.username else f"ID: {message.from_user.id}"
                    
                    actions_ru = {
                        'create': 'создание анкеты',
                        'update': 'обновление анкеты',
                        'delete': 'удаление анкеты',
                        'view': 'просмотр анкеты'
                    }
                    
                    logger.info(f"📝 ПРОФИЛЬ: {user_info} | {actions_ru.get(action_type, action_type)}")
                
                return await func(*args, **kwargs)
                
            except Exception as e:
                if message:
                    user_info = f"@{message.from_user.username}" if message.from_user.username else f"ID: {message.from_user.id}"
                    logger.error(f"📝 ОШИБКА ПРОФИЛЯ: {user_info} | {action_type} | {str(e)[:100]}")
                raise
            
        return wrapper
    return decorator
def format_moscow_time(db_time_str: str) -> str:
    """
    Форматирует время из БД в московское время.
    Возвращает строку в формате: "DD.MM.YYYY в HH:MM (по МСК)"
    """
    try:
        if not db_time_str:
            return "Не указана"
        
        # Преобразуем строку из SQLite в datetime
        db_time = datetime.strptime(db_time_str, '%Y-%m-%d %H:%M:%S')
        
        # Создаем timezone UTC (время в БД хранится в UTC)
        utc_time = pytz.UTC.localize(db_time)
        
        # Конвертируем в московское время
        moscow_tz = pytz.timezone('Europe/Moscow')
        moscow_time = utc_time.astimezone(moscow_tz)
        
        # Форматируем для отображения
        return moscow_time.strftime('%d.%m.%Y в %H:%M (по МСК)')
        
    except Exception as e:
        logger.error(f"Ошибка при форматировании времени {db_time_str}: {e}")
        return db_time_str or "Не указана"
# Декоратор для логирования системы мутов
def log_mute_action(action: str):
    """
    Декоратор для логирования действий с мутами.
    action: 'mute', 'unmute', 'check'
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                message = None
                for arg in args:
                    if hasattr(arg, 'from_user'):
                        message = arg
                        break
                
                if message:
                    user_info = f"@{message.from_user.username}" if message.from_user.username else f"ID: {message.from_user.id}"
                    
                    # Получаем ID целевого пользователя из аргументов или состояния
                    target_id = None
                    if len(args) > 1 and isinstance(args[1], int):
                        target_id = args[1]
                    elif 'user_id' in kwargs:
                        target_id = kwargs['user_id']
                    
                    if target_id:
                        if action == 'mute':
                            logger.warning(f"🔇 МУТ: {user_info} замутил пользователя {target_id}")
                        elif action == 'unmute':
                            logger.warning(f"🔊 РАЗМУТ: {user_info} размутил пользователя {target_id}")
                        elif action == 'check':
                            logger.info(f"🔍 ПРОВЕРКА МУТА: {user_info} проверил пользователя {target_id}")
                
                return await func(*args, **kwargs)
                
            except Exception as e:
                if message:
                    user_info = f"@{message.from_user.username}" if message.from_user.username else f"ID: {message.from_user.id}"
                    logger.error(f"❌ ОШИБКА МУТА: {user_info} | {action} | {str(e)[:100]}")
                raise
            
        return wrapper
    return decorator


def db_operation(operation, params=None, fetch=False):
    """Безопасное выполнение операций с базой данных"""
    conn = None
    try:
        # Убедимся, что DB_PATH инициализирована
        if DB_PATH is None:
            init_directories()
            
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        cur = conn.cursor()
        
        if params:
            cur.execute(operation, params)
        else:
            cur.execute(operation)
            
        if fetch:
            result = cur.fetchall()
        else:
            result = None
            
        conn.commit()
        return result
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Ошибка базы данных: {str(e)}")
        raise e
    finally:
        if conn:
            conn.close()

class SquadStates(StatesGroup):
    selecting_gk = State()
    selecting_op = State()
    selecting_nap1 = State()
    selecting_nap2 = State()
    editing_squad = State()
    viewing_cards_for_position = State()



async def show_cards_for_next_position(message_or_callback, state: FSMContext, next_position: str):
    """Показывает карточки для следующей позиции при создании состава.
    Работает как с Message, так и с CallbackQuery объектами.
    """
    user_id = message_or_callback.from_user.id
    
    try:
        # Определяем, что перед нами: Message или CallbackQuery
        is_callback = hasattr(message_or_callback, 'data')
        
        # Получаем карточки пользователя
        user_cards_result = get_user_cards(user_id)
        
        if not user_cards_result:
            response_text = "❌ У вас нет карточек для следующей позиции!"
            if is_callback:
                await message_or_callback.message.edit_text(
                    response_text,
                    parse_mode="html"
                )
            else:
                await message_or_callback.reply(
                    response_text,
                    parse_mode="html"
                )
            return
        
        # Преобразуем результат
        user_cards = []
        for card_tuple in user_cards_result:
            if len(card_tuple) >= 4:
                nickname, club, card_position, rarity, _ = card_tuple
                card_info = get_card_by_nickname_db(nickname)
                if card_info:
                    user_cards.append({
                        'id': card_info['id'],
                        'nickname': nickname,
                        'club': club,
                        'position': card_position,
                        'rarity': rarity
                    })
        
        # Фильтруем по позиции
        position_keywords = {
            "gk": ["гк", "вратарь"],
            "op": ["оп", "защитник"],
            "nap1": ["нап", "нападающий"],
            "nap2": ["нап", "нападающий"]
        }
        
        keywords = position_keywords.get(next_position, ["нап"])
        position_cards = []
        
        for card in user_cards:
            card_position_lower = card['position'].lower() if card['position'] else ""
            for keyword in keywords:
                if keyword in card_position_lower:
                    position_cards.append(card)
                    break
        
        # Фильтруем уже выбранные карточки
        state_data = await state.get_data()
        selected_cards = state_data.get("selected_cards", {})
        selected_ids = set(selected_cards.values())
        
        available_cards = []
        for card in position_cards:
            if card['id'] not in selected_ids:
                available_cards.append(card)
        
        if not available_cards:
            response_text = (
                f"❌ Нет доступных карточек для позиции {next_position.upper()}!\n"
                f"Все карточки уже выбраны для других позиций."
            )
            if is_callback:
                await message_or_callback.message.edit_text(
                    response_text,
                    parse_mode="html"
                )
            else:
                await message_or_callback.reply(
                    response_text,
                    parse_mode="html"
                )
            return
        
        # Сохраняем доступные карточки
        await state.update_data({
            "available_cards": available_cards,
            "current_page": 0
        })
        
        # Формируем сообщение
        position_names = {
            "gk": "Вратарь (ГК)",
            "op": "Защитник (ОП)",
            "nap1": "Нападающий 1 (НАП)",
            "nap2": "Нападающий 2 (НАП)"
        }
        
        position_display = position_names.get(next_position, "Позиция")
        
        message_text = (
            f"<b>🏗️ СОЗДАНИЕ СОСТАВА</b>\n\n"
            f"<b>Выберите {position_display.lower()}:</b>\n\n"
            f"<i>Доступно карточек: {len(available_cards)}</i>\n\n"
        )
        
        # Показываем первые 5 карточек
        for i, card in enumerate(available_cards[:5], 1):
            rarity_display = 'Эпический' if card['rarity'].lower() in ['эпический', 'эпическая', 'эпик'] else card['rarity']
            message_text += (
                f"<b>{i}. {card['nickname']}</b>\n"
                f"   🏟️ {card['club']} | 💎 {rarity_display}\n"
                f"   🆔 <code>{card['id']}</code>\n\n"
            )
        
        message_text += (
            "<b>📝 КАК ВЫБРАТЬ:</b>\n"
            "Введите <b>ID карточки</b>, которую хотите выбрать\n\n"
            "<b>Пример ввода:</b> <code>123</code>\n\n"
            "<i>Для отмены введите 'отмена'</i>"
        )
        
        # Создаем клавиатуру
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="❌ Отменить создание",
                callback_data="sostav"
            )
        )
        
        if is_callback:
            await message_or_callback.message.edit_text(
                message_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
        else:
            await message_or_callback.reply(
                message_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
        
    except Exception as e:
        logger.error(f"Ошибка в show_cards_for_next_position: {e}")
        response_text = "❌ Ошибка при загрузке карточек"
        if is_callback:
            await message_or_callback.message.edit_text(
                response_text,
                parse_mode="html"
            )
        else:
            await message_or_callback.reply(
                response_text,
                parse_mode="html"
            )

def create_user_squad_table():
    """Создает таблицу для хранения составов пользователей"""
    try:
        db_operation('''
        CREATE TABLE IF NOT EXISTS user_squads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            gk_card_id INTEGER,
            op_card_id INTEGER,
            nap1_card_id INTEGER,
            nap2_card_id INTEGER,
            squad_name TEXT DEFAULT 'Мой состав',
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id),
            FOREIGN KEY (user_id) REFERENCES all_users (id),
            FOREIGN KEY (gk_card_id) REFERENCES players_catalog (id),
            FOREIGN KEY (op_card_id) REFERENCES players_catalog (id),
            FOREIGN KEY (nap1_card_id) REFERENCES players_catalog (id),
            FOREIGN KEY (nap2_card_id) REFERENCES players_catalog (id)
        )
        ''')
        logger.info("✅ Таблица user_squads создана/проверена")
    except Exception as e:
        logger.error(f"❌ Ошибка при создании таблицы user_squads: {e}")

def get_card_by_id(card_id: int):
    """Находит карточку по ID"""
    try:
        result = db_operation(
            """SELECT id, nickname, club, position, rarity 
               FROM players_catalog 
               WHERE id = ?""",
            (card_id,),
            fetch=True
        )
        
        if result:
            db_id, nickname, club, position, rarity = result[0]
            return {
                'id': db_id,
                'nickname': nickname,
                'club': club,
                'position': position,
                'rarity': rarity
            }
        return None
    except Exception as e:
        logger.error(f"Ошибка при поиске карточки по ID {card_id}: {e}")
        return None



def seed_players_catalog():
    """Заполняет и обновляет таблицу players_catalog данными игроков."""
    try:
        logger.info("📝 Начинаю обновление каталога игроков...")
        
        # Получаем текущих игроков (кортежи по 4 элемента: nickname, club, position, rarity)
        current_players = get_players_from_source()
        
        if not current_players:
            logger.error("❌ Не удалось получить данные игроков")
            return
        
        # Получаем существующих игроков из БД
        existing_players_result = db_operation(
            "SELECT id, nickname, club, position, rarity FROM players_catalog",
            fetch=True
        )
        
        # Создаем словарь никнейм → данные
        existing_players = {}
        if existing_players_result:
            for row in existing_players_result:
                card_id, nickname, club, position, rarity = row
                existing_players[nickname] = {
                    'id': card_id,
                    'club': club,
                    'position': position,
                    'rarity': rarity
                }
        
        added_count = 0
        updated_count = 0
        unchanged_count = 0
        
        # Обрабатываем всех игроков из конфигурации
        for player_data in current_players:
            try:
                # Распаковываем 4 элемента
                nickname, club, position, rarity = player_data
                
                # Нормализуем редкости
                rarity_mapping = {
                    'эпический': 'Эпический',
                    'эпическая': 'Эпический', 
                    'эпик': 'Эпический',
                    'редкий': 'Редкий',
                    'легендарный': 'Легендарный',
                    'суперлегендарный': 'Суперлегендарный',
                    'eea': 'EEA',
                }
                
                normalized_rarity = rarity_mapping.get(rarity.lower(), rarity)
                
                # Проверяем, существует ли игрок
                if nickname in existing_players:
                    existing_player = existing_players[nickname]
                    
                    # Проверяем, изменились ли данные
                    if (existing_player['club'] != club or 
                        existing_player['position'] != position or 
                        existing_player['rarity'] != normalized_rarity):
                        
                        # Обновляем данные игрока, но НЕ меняем ID
                        db_operation(
                            """UPDATE players_catalog 
                               SET club = ?, position = ?, rarity = ?
                               WHERE id = ?""",
                            (club, position, normalized_rarity, existing_player['id'])
                        )
                        updated_count += 1
                        logger.info(f"🔄 Обновлен игрок: {nickname} (ID: {existing_player['id']})")
                    else:
                        unchanged_count += 1
                        # logger.debug(f"⚪ Без изменений: {nickname}")
                        
                else:
                    # Добавляем нового игрока с автоинкрементным ID
                    db_operation(
                        """INSERT INTO players_catalog 
                           (nickname, club, position, rarity) 
                           VALUES (?, ?, ?, ?)""",
                        (nickname, club, position, normalized_rarity)
                    )
                    
                    added_count += 1
                    logger.info(f"✅ Добавлен новый игрок: {nickname}")
                    
            except sqlite3.IntegrityError:
                logger.warning(f"❌ Ошибка уникальности: {player_data[0]}")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось обработать игрока {player_data[0]}: {e}")
        
        # === УДАЛЕНИЕ ИГРОКОВ, ОТСУТСТВУЮЩИХ В КОНФИГУРАЦИИ ===
        current_nicknames = {p[0] for p in current_players}
        players_to_remove = []
        
        if existing_players_result:
            for db_player in existing_players_result:
                player_id, nickname, club, position, rarity = db_player
                if nickname not in current_nicknames:
                    players_to_remove.append({
                        'id': player_id,
                        'nickname': nickname,
                        'club': club,
                        'position': position,
                        'rarity': rarity
                    })
        
        removed_count = 0
        warned_count = 0
        
        if players_to_remove:
            logger.warning(f"⚠️ Найдено {len(players_to_remove)} игроков для удаления")
            
            for player_info in players_to_remove:
                player_id = player_info['id']
                nickname = player_info['nickname']
                
                try:
                    # Проверяем, есть ли у пользователей эта карточка
                    users_with_card = db_operation(
                        "SELECT COUNT(*) FROM user_cards WHERE card_id = ?",
                        (player_id,),
                        fetch=True
                    )
                    
                    users_count = users_with_card[0][0] if users_with_card else 0
                    
                    # Проверяем, есть ли карточка в продаже
                    sell_cards = db_operation(
                        "SELECT COUNT(*) FROM sell_cards WHERE card_id = ? AND is_available = 1",
                        (player_id,),
                        fetch=True
                    )
                    
                    sell_count = sell_cards[0][0] if sell_cards else 0
                    
                    if users_count == 0 and sell_count == 0:
                        # Если карточка ни у кого нет и не в продаже - можно удалить
                        db_operation(
                            "DELETE FROM players_catalog WHERE id = ?",
                            (player_id,)
                        )
                        logger.warning(f"🗑️ Удален игрок: {nickname} (ID: {player_id})")
                        removed_count += 1
                    else:
                        logger.warning(
                            f"⚠️ Не удаляю {nickname}: "
                            f"карточек у пользователей - {users_count}, "
                            f"в продаже - {sell_count}"
                        )
                        warned_count += 1
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка при проверке/удалении игрока {nickname}: {e}")
        
        # Проверяем итоговый результат
        result = db_operation("SELECT COUNT(*) FROM players_catalog", fetch=True)
        final_count = result[0][0] if result else 0
        
        # Логируем итог
        logger.info(
            f"📊 Обновление каталога завершено:\n"
            f"├─ ✅ Добавлено новых: {added_count}\n"
            f"├─ 🔄 Обновлено: {updated_count}\n"
            f"├─ ⚪ Без изменений: {unchanged_count}\n"
            f"├─ 🗑️ Удалено: {removed_count} (отсутствуют в конфигурации)\n"
            f"├─ ⚠️ Не удалено (есть у пользователей): {warned_count}\n"
            f"└─ 📈 Всего игроков в каталоге: {final_count}"
        )
        
        # Выводим предупреждение о важных изменениях
        if added_count > 0 or updated_count > 0 or removed_count > 0:
            logger.info("⚡ ВНИМАНИЕ: Были внесены изменения в каталог игроков!")
            
        return {
            'added': added_count,
            'updated': updated_count,
            'unchanged': unchanged_count,
            'removed': removed_count,
            'warned': warned_count,
            'total': final_count
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка при обновлении каталога игроков: {str(e)}")
        import traceback
        logger.error(f"Трейсбэк: {traceback.format_exc()}")
        return None
    


def get_players_from_source():
    """
    Получает данные игроков из источника.
    ВАЖНО: Измените эту функцию под ваш источник данных!
    """
    try:
        # === СПОСОБ 1: Из списка в коде (текущий способ) ===

        


        players_data = [
            # Industrial
             ('DonbazZ', 'Industrial', 'нападающий', 'эпический'),
            ('niu', 'Industrial', 'гк', 'эпический'),
            ('Bellingham', 'Santos', 'оп', 'Эпический'),
            ('etiqinha', 'Santos', 'Нап', 'Эпический'),
            ('веланн', 'Нави', 'Нападающий', 'Легендарный'),
            ('Guffy', 'Нави', 'Нападающий', 'Эпический'),
            ('Ekventor', 'ScB', 'Оп', 'Легендарный'),
            ('fley', 'ScB', 'Нап', 'Легендарный'),
            ('doyle', 'Da Boiz', 'Нап', 'Эпический'),
            ('минаку', 'Da Boiz', 'Нап', 'Эпический'),
            ('Rubix', 'Спартак', 'нап', 'эпический'),
            ('Xlebushek', 'Players club', 'гк', 'Эпический'),
            ('ftmmm', 'Баку', 'Нап', 'Эпический'),
            ('Nuk4ezz', 'Баку', 'Нап', 'Эпический'),
            ('Дагар', 'Империал', 'Нап', 'Легендарный'),
            ('wrнmwwk', 'Империал', 'Нап', 'Легендарный'),
            ('никси', 'Монако', 'Оп', 'Эпический'),
            ('playa', 'Монако', 'Оп', 'Эпический'),
            ('Легенда инсо', 'Мановер', 'Нап', 'Эпический'),
            ('Санчезз', 'Мановер', 'Нап', 'Эпический'),
            ('godxx', 'Ттх', 'Оп', 'Эпический'),
            ('Миракли', 'Ттх', 'Нап', 'Эпический'),
            ('Муса', 'Ювентус', 'Нап', 'Эпический'),
            ('Ручка (руль)', 'Ювентус', 'Оп', 'Эпический'),
            ('Jage', 'Хентус', 'Нап', 'Легендарный'),
            ('ситад', 'Хентус', 'Нап', 'Суперлегендарный'),
            ('Винтер', 'Бавария/рома/гамбург', 'Оп', 'Легендарный'),
            ('Сугар', 'Сочи', 'Нап', 'Легендарный'),
            ('MamoTinder', 'Рома', 'уник', 'Легендарный'),
            ('Денис(Hedisa)', 'Темп', 'Нап', 'Эпический'),
            ('BeetWeen', 'Темп', 'Гк', 'Легендарный'),
            ('Anonim', 'Spartak', 'Нап', 'Редкий'),
            ('igo53', 'Runa', 'Нап', 'Эпический'),
            ('MbT.Ikoni', 'Ак Темп', 'Оп', 'Редкий'),
            ('MbT.Fitlyy', 'Ак Темп', 'Оп', 'Редкий'),
            ('DarkBobr', 'Spartak', 'Нап', 'Редкий'),
            ('Sua', 'Ак Темп', 'Гк', 'Редкий'),
            ('Anxyy', 'Ак Темп', 'Оп', 'Редкий'),
            ('Мипи', 'Корнаго', 'Гк', 'Редкий'),
            ('Yuok', 'Кельн', 'Гк', 'Редкий'),
            ('Бронетапок', 'Милан(фейк)', 'Гк', 'Редкий'),
            ('runny', 'TG players', 'Нап', 'Редкий'),
            ('Bekach.Nemosh', 'TG players', 'Нап', 'Редкий'),
            ('spear', 'TG players', 'Нап', 'Редкий'),
            ('иnвалиd', 'TG players', 'Оп', 'Редкий'),
            ('Nurdastyyllee', 'TG players', 'Гк', 'Редкий'),
            ("ABV", 'Faceit player', 'Оп', 'легендарный'),
            ('Androed', 'TG players', 'Нап', 'Редкий'),
            ('Комерзанчик', 'TG players', 'Гк', 'Редкий'),
            ('Gold1', 'Виндикс', 'Гк', 'Редкий'),
            ('kapXriz', 'Old Shark', 'Нап', 'суперлегендарный'),
            ('V1ntage', 'TG players', 'Гк', 'Редкий'),
            ('de_jong', 'TG players', 'Оп', 'Редкий'),
            ('mariontochkaTT', 'TG players', 'Дизайнер', 'Редкий'),
            ('SoSSarS', 'Кадиз', 'Гк', 'Суперлегендарный'),
            ('robertik', 'Ак Корнаго', 'гк', 'легендарный'),
            ('デイビス', 'Spartak', 'Оп', 'суперлегендарный'),
            ('wqwwwqw', 'Рома', 'нап', 'эпический'),
            ('Claudihno', 'Рома', 'Гк', 'Легендарный'),
            ('Eboanchik', 'Аякс', 'Оп', 'Эпический'),
            ('Даки', 'Кадиз', 'Оп', 'Легендарный'),
            ('Dibala', 'Рома', 'Нап', 'Эпический'),
            ('Kyz9', 'Корнаго', 'Нап', 'Эпический'),
            ('Гасман', 'Spartak', 'Нап', 'Редкий'),
            ('Виглис', 'Нтак', 'Оп', 'Редкий'),
            ('Нефтехимик', 'Spartak', 'Нап', 'Эпический'),
            ('Sozgatel', 'Рома', 'Уник', 'Эпический'),
            ('Smixx', 'Рома', 'Нап', 'редкий'),
            ('Фрогги', 'Сельта', 'Нап', 'Редкий'),
            ('Era', 'Baku Fire', 'Нап', 'Легендарный'),
            ('Asencio', 'TG Players', 'ГК', 'Эпический'),
            ('Instazzy', 'Royal Rose', 'Нап', 'Легендарный'),
            ('.wertu', 'Кельн', 'Оп', 'эпический'),
            ('vp5', 'Royal Rose', 'ГК', 'эпический'),
            ('wernex', 'Royal Rose', 'Нап', 'Редкий'),
            ('spear', 'Барселона', 'Нап', 'Легендарный'),
            ('Gold1', 'Виндикс', 'ГК', 'Редкий'),
            ('oddesov', 'Кельн', 'ГК', 'Редкий'),
            ('вуфи', 'Хан Тенгри', 'Нап', 'Редкий'),
            ('zhurasliev', 'Кельн', 'ГК', 'редкий'),
            ('hanco', 'Ак Корнаго', 'Нап', 'Редкий'),
            ('watchmerock', 'Челси', 'Нап', 'Редкий'),
            ('Зуб', 'Spartak', 'ГК', 'Легендарный'),
            ('Ержан', 'ММГ', 'Нап', 'Редкий'),
            ('savage', 'Chelsea', 'нап', 'Эпический'),
            ('qitzer', 'Monaco', 'нап', 'Эпический'),
            ('Shkedd', 'Recceba', 'гк', 'редкий'),
            ('лолипоп', 'Recceba', 'гк', 'Редкий'),
            ('Тихоня', 'Трипл Дабл', 'нап', 'Легендарный'),
            ('pe1rusa', 'Росенбург', 'нап', 'Редкий'),
            ('madk1d', 'ЦСКА', 'нап', 'Редкий'),
            ('laqOfficial', 'Napoli', 'нап', 'Редкий'),
            ('escobaro', 'Челси', 'оп', 'Эпический'),
            ('ГенаШашлык', 'Soccer Aid', 'оп', 'Редкий'),
            ('forzaa.', 'Неаполь Корнаго', 'нап', 'эпический'),
            ('qwert1chka', 'Кадиз', 'нап', 'Легендарный'),
            ('メCrouchメ', 'A.Le Coq', 'гк', 'Редкий'),
            ('dimaxx', 'Recceba', 'нап', 'Редкий'),
            ('Тiмур', 'Железовская', 'нап', 'Легендарный'),
            ('граст', 'Скатина Юнайтед', 'нап', 'Редкий'),
            ('Forgt0wn', 'Мистик', 'гк', 'Редкий'),
            ('olise.невероятен', 'Рома', 'Нап', 'редкий'),
            ('sxane', 'KickOff', 'Оп', 'редкий'),
            ('леган', 'Империал Кровс', 'Гк', 'легендарный'),
            ('аджика', 'Royal Rose', 'нап', 'легендарный'), #джикия
            ('maestrol1mbo', 'KickOff', 'гк', 'редкий'),
            ('Бичуган', 'Империал Кровс', 'нап', 'суперлегендарный'),
            ('фоksh', 'АкНКор', 'Гк', 'редкий'),
            ('Кака', 'АкКор', 'Уник', 'редкий'),
            ('yaa_', 'Heerenveen', 'гк', 'редкий'),
            ('Суп', 'Сассуоло', 'нап', 'эпический'),
            ("RD_NEYMAR_11", "FC Barcelona","Нап","редкий"),
            #("","","",""),
            ("soZvl","Heerenveen","нап","редкий"),
            ("Malik","Revolution","нап","эпический"),
            ("смаш", "Кадиз", "нап", "легендарный"),
            ("MbT.Анрюха", "MB TEMP", "Нап", "эпический"),
            ("пати","Тимберленд","оп","легендарный"),
            (".froggy.","Barcelona","нап","редкий"),
            ("gyma","Nantes","нап","суперлегендарный"), #блас нант
            ("хелни" , "Дозенс", "нап", "легендарный"),
            ("Печенька.Cpertsysn", "Krasnodar", "Оп", "Легендарный"),
            ("Mut", "Renegades", "Оп", "эпический"),
            ("Gianluigi_Buffon", "Монолит", "Гк", "легендарный"), #буффон
            ("rockabye","Баку","нап","легендарный"), #бонмати
            ("inworld","Lozano United","Гк","легендарный"), #виртц
            ("Закоморный","Перфектленд","нап","эпический"),
            ("Agentツ","Herenveen","нап","легендарный"),
            ("Рейз","Бавария","нап","легендарный"),
            ("Черныйэ","Cavallo Volantes","оп", "эпический"),
            ("ферничек","Juventus","оп","эпический"),
            ("neLas","Juventus","гк","эпический"),
            ("Метидам","Корнаго","оп","редкий"),
            ("welann","Alianz","гк","эпический"),
            (".суетолог","Некст","гк","легендарный"),
            ("Змей","Krasnodar","нап","редкий"),
            ("Киззи","корнаго","нап","редкий"),
            ("Fat1k","Snowy Stars","нап","эпический"),
            ("шторм","TG players","нап","редкий"),
            ("xtellor","Milan","нап","эпический"),
            ("Denny","Cavallo volantes","нап","редкий"),
            ("Зизу","Columbus Crew","нап","редкий"),
            ("ABSOLUTE666","Columbus Crew","нап","редкий"),
            ("livra","Matrix","нап","легендарный"),
            ("Twins","Pari NN","нап","редкий"),
            ("fqzip","Pari NN","нап","редкий"),
            ("mani21","Old Shark","оп","редкий"),
            ("La_f1","Recceba Star","оп","редкий"),
            ("Sevenstyleee","Airaes","нап","эпический"),
            ("Fanatikk","Dandee","нап","редкий"),
            ("Expensive","Heerenveen","нап","редкий"),
            ("Rouk","TG Players","нап","редкий"),
            ("h1t","Columbus Crew","уник","легендарный"),
            ("пуля","Кельн","оп","эпический"),
            ("T.Kroos","Бавария","оп","редкий"),
            ("Floxxy","Stonava","уник","редкий"),
            ("ded.nisa1de","TG Players","уник","редкий"),
            ("ваки","Данди","гк","редкий"),
            ("весертор","Нави","гк","редкий"),
            ("Миринда","Олд Шарк","оп","редкий"),
            ("Энрике","Корнаго","нап","легендарный"), #родриго
            ("vacanty", "Олд Шарк", "уник", "легендарный"),
            ("Мираф", "Якудза", "нап", "легендарный"),
            ("Yaster"  , "Juventus" ,"нап", "суперлегендарный"), #неймар
            ("sudakov", "Оболонь Пиво", "нап", "редкий"),
            ("sylphie", "alash orda", "нап", "эпический"),
            ("makkaze", "Falcons", "нап", "эпический"),
            ("афина", "Олд Шарк", "гк", "легендарный"),
            ("ВеняКолбаска", "Corvett FC", "нап", "редкий"),
            ("канат", "Бавария", "нап", "редкий"),
            ("sh1ne", "RedMachine", "оп", "редкий"),
            ("vacanty", "Олд Шарк", "гк", "легендарный"),
            ("MbT.kw4xx, ", "MB TEMP", "нап", "эпический"),
            ("MbT.Kimmich", "MB TEMP", "оп", "эпический"),
             ("Molan", "Silent Owls", "нап", "EEA"),
            ("Ronny", "Aces & Eights", "нап", "EEA"),
            ("Beautiful", "Juventus", "нап", "EEA"),
            ("Revenge", "Snake Gaming", "нап", "EEA"),
            ("Lobsst", "Silent Owls", "нап", "EEA"),
            ("Remfalk", "Spitz", "нап", "EEA"),
            ("Zoodya", "CrowCrowd", "оп", "EEA"),
            ("Butragueno", "Juventus", "нап", "EEA"),
            ("Vahitov", "Snake Gaming", "нап", "EEA"),
            ("Levinha", "Barcelona", "нап", "EEA"),
            ("Roulip", "CSKA Moscow", "нап", "EEA"),
            ("Gyma", "Real Betis", "нап", "EEA"),
            ("Sitad", "Hentys", "нап", "EEA"),
            ("Mef", "Hentys", "оп", "EEA"),           
            ("MbT.Анрюха", "MB TEMP", "оп", "эпический"),
            ("lunyaa", "Spider", "оп", "легендарный"),
            ("vazovsky", "Red Machine", "нап", "редкий"),
            ("Junxs", "Albacete", "оп", "эпический"),
            ("deatek", "Bayern Munchen", "гк", "эпический"), 
            ("фуфел1337", "Данди Юнайтед", "оп", "редкий"), 
            ("Mafiozziii", "Ворскла", "нап", "эпический" ),
            ("Renkuro", "Blackpink","нап", "эпический"),
            ("exquisite", "Reveal", "гк", "редкий"),
            ("Kyle0", "Notfotes", "нап", "редкий"),
            ("Navas2022", "Flame Falcons", "гк", "редкий"),
            ("fxckest", "Cavallo Volantes", "нап", "редкий"),
            ("cor.x1wez", "FC Cornago", "нап", "эпический"),
            ("Birt", "Ак Нкорнаго", "нап", "редкий"),
            ("jawee", "Natus Vincere", "оп", "суперлегендарный"),
            ("nebo", "Old Shark", "нап", "суперлегендарный"),
            ("MbT.Flemeen (ФлемАнус)", "MB TEMP", "гк", "эпический"),
            ("Бобин", "Нави", "нап", "эпический"),


        ]

        return players_data
        
    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке игроков: {e}")
        return []










def update_purchase_history_table():
    """Обновляет таблицу purchase_history, добавляя поле card_id"""
    try:
        # Проверяем текущую структуру таблицы
        result = db_operation("PRAGMA table_info(purchase_history)", fetch=True)
        
        if not result:
            # Таблица не существует, создаем с правильной структурой
            db_operation('''CREATE TABLE IF NOT EXISTS purchase_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            card_id INTEGER NOT NULL,
            price INTEGER NOT NULL,
            purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            transaction_type TEXT NOT NULL,
            sell_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES all_users(id),
            FOREIGN KEY (card_id) REFERENCES players_catalog(id)
        )''')
            logger.info("✅ Таблица purchase_history создана с полем card_id")
            return True
        
        columns = [col[1] for col in result]  # Имена колонок
        
        # Проверяем, есть ли уже колонка card_id
        if 'card_id' not in columns:
            logger.info("🔄 Добавление поля card_id в таблицу purchase_history...")
            
            try:
                # Просто добавляем колонку в существующую таблицу
                db_operation('ALTER TABLE purchase_history ADD COLUMN card_id INTEGER DEFAULT 0')
                logger.info("✅ Колонка card_id добавлена в таблицу purchase_history")
                
                # Теперь обновляем существующие записи
                update_existing_card_ids()
                
                return True
            except Exception as e:
                logger.error(f"❌ Не удалось добавить колонку напрямую: {e}")
                logger.info("🔄 Попытка создать новую таблицу...")
                
                # Создаем новую таблицу
                db_operation('''
                CREATE TABLE IF NOT EXISTS purchase_history_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    sell_id INTEGER NOT NULL,
                    card_id INTEGER NOT NULL DEFAULT 0,
                    price INTEGER NOT NULL,
                    transaction_type TEXT DEFAULT 'admin_sell',
                    purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES all_users (id),
                    FOREIGN KEY (card_id) REFERENCES players_catalog (id)
                )
                ''')
                
                # Получаем данные из старой таблицы
                old_data = db_operation(
                    "SELECT id, user_id, sell_id, price, transaction_type, purchased_at FROM purchase_history",
                    fetch=True
                )
                
                # Вставляем данные в новую таблицу
                for row in old_data:
                    purchase_id, user_id, sell_id, price, transaction_type, purchased_at = row
                    db_operation(
                        """INSERT INTO purchase_history_new 
                           (id, user_id, sell_id, card_id, price, transaction_type, purchased_at)
                           VALUES (?, ?, ?, 0, ?, ?, ?)""",
                        (purchase_id, user_id, sell_id, price, transaction_type, purchased_at)
                    )
                
                # Удаляем старую таблицу
                db_operation('DROP TABLE purchase_history')
                
                # Переименовываем новую таблицу
                db_operation('ALTER TABLE purchase_history_new RENAME TO purchase_history')
                
                logger.info("✅ Таблица purchase_history обновлена с добавлением card_id")
                
                # Обновляем card_id для существующих записей
                update_existing_card_ids()
                
                return True
        else:
            logger.info("✅ Таблица purchase_history уже содержит поле card_id")
            
            # Проверяем, есть ли записи с card_id = 0 и обновляем их
            result = db_operation(
                "SELECT COUNT(*) FROM purchase_history WHERE card_id = 0",
                fetch=True
            )
            
            if result and result[0][0] > 0:
                logger.info(f"🔄 Найдено {result[0][0]} записей с card_id = 0, обновляю...")
                update_existing_card_ids()
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Ошибка при обновлении таблицы purchase_history: {e}")
        import traceback
        logger.error(f"Трейсбэк: {traceback.format_exc()}")
        return False
    
    
def update_existing_card_ids():
    """Обновляет card_id для существующих записей в истории покупок"""
    try:
        logger.info("🔄 Обновление card_id в истории покупок...")
        
        # Сначала обновляем админские продажи
        logger.info("🔄 Обновление админских продаж...")
        db_operation('''
        UPDATE purchase_history 
        SET card_id = (
            SELECT sc.card_id 
            FROM sell_cards sc 
            WHERE sc.card_id = purchase_history.sell_id  -- для sell_cards card_id является primary key
        )
        WHERE transaction_type = 'admin_sell' AND card_id = 0
          AND EXISTS (
              SELECT 1 FROM sell_cards sc 
              WHERE sc.card_id = purchase_history.sell_id
          )
        ''')
        
        # Обновляем пользовательские продажи
        logger.info("🔄 Обновление пользовательских продаж...")
        db_operation('''
        UPDATE purchase_history 
        SET card_id = (
            SELECT ust.card_id 
            FROM user_sell_transactions ust 
            WHERE ust.id = purchase_history.sell_id
        )
        WHERE transaction_type = 'user_sell' AND card_id = 0
          AND EXISTS (
              SELECT 1 FROM user_sell_transactions ust 
              WHERE ust.id = purchase_history.sell_id
          )
        ''')
        
        # Удаляем записи, для которых не удалось найти card_id (они некорректны)
        logger.info("🔄 Удаление некорректных записей...")
        deleted_count = db_operation(
            "DELETE FROM purchase_history WHERE card_id = 0",
            fetch=False
        )
        
        if deleted_count:
            logger.warning(f"🗑️ Удалено {deleted_count} некорректных записей из истории покупок")
        
        logger.info("✅ Card_id обновлены в истории покупок")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при обновлении card_id: {e}")
        import traceback
        logger.error(f"Трейсбэк: {traceback.format_exc()}")


# В класс SimpleLogger добавим метод:
def cleanup_old_logs(self, days: int = 7):
    """Удаляет лог файлы старше указанного количества дней"""
    try:
        current_time = time.time()
        deleted_count = 0
        
        # Проверяем оба лог файла
        log_files = [self.log_file, self.error_log_file]
        
        for log_file in log_files:
            if os.path.exists(log_file):
                # Получаем время последнего изменения
                file_mtime = os.path.getmtime(log_file)
                file_age_days = (current_time - file_mtime) / (60 * 60 * 24)
                
                if file_age_days > days:
                    os.remove(log_file)
                    deleted_count += 1
                    self.log('INFO', f"🗑️ Удален старый лог файл: {os.path.basename(log_file)} (возраст: {file_age_days:.1f} дней)")
                    
                    # Создаем новый пустой файл
                    with open(log_file, 'w', encoding='utf-8') as f:
                        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [INFO] Лог файл создан\n")
        
        # Также проверяем директорию логов на наличие других лог файлов
        if os.path.exists(LOGS_DIR):
            for filename in os.listdir(LOGS_DIR):
                if filename.endswith('.log'):
                    file_path = os.path.join(LOGS_DIR, filename)
                    if os.path.exists(file_path):
                        file_mtime = os.path.getmtime(file_path)
                        file_age_days = (current_time - file_mtime) / (60 * 60 * 24)
                        
                        if file_age_days > days:
                            os.remove(file_path)
                            deleted_count += 1
                            self.log('INFO', f"🗑️ Удален старый лог файл из директории: {filename} (возраст: {file_age_days:.1f} дней)")
        
        return deleted_count
        
    except Exception as e:
        self.log('ERROR', f"Ошибка при очистке старых логов: {e}")
        return 0

# А также статический метод для очистки всех логов:
def cleanup_all_logs(days: int = 7):
    """Очищает все лог файлы старше указанного количества дней"""
    try:
        logger_instance = SimpleLogger()
        deleted_count = logger_instance.cleanup_old_logs(days)
        return deleted_count
    except Exception as e:
        print(f"❌ Ошибка при очистке логов: {e}")
        return 0



def cleanup_old_bonus_entries():
    """Очищает устаревшие записи о бонусах (старше 30 дней)"""
    try:
        # Получаем текущее время в UTC
        utc_now = datetime.now(pytz.UTC)
        # Вычисляем дату 30 дней назад в UTC
        cutoff_date_utc = (utc_now - timedelta(days=30))
        
        # Форматируем дату для SQL запроса
        cutoff_date_str = cutoff_date_utc.strftime('%Y-%m-%d %H:%M:%S')
        
        deleted = db_operation(
            "DELETE FROM user_daily_bonus WHERE last_bonus_moscow < ?",
            (cutoff_date_str,)
        )
        
        if deleted:
            logger.info(f"🧹 Очищено {deleted} устаревших записей о бонусах")
        
        return deleted
    except Exception as e:
        logger.error(f"Ошибка при очистке старых бонусов: {e}")
        return 0
def check_and_fix_sell_status_on_startup():
    """
    Автоматически проверяет и исправляет некорректные статусы продаж при запуске бота.
    Исправляет карточки, помеченные как проданные (is_available=0), но без записи в истории покупок.
    """
    try:
        logger.info("🔍 Запуск проверки целостности статусов продаж...")
        
        # Находим карточки с несоответствием статуса и истории покупок
        problematic_cards = db_operation(
            """SELECT sc.id, sc.card_id, pc.nickname, sc.price, sc.added_at
               FROM sell_cards sc
               JOIN players_catalog pc ON sc.card_id = pc.id
               WHERE sc.is_available = 0 
                 AND sc.id NOT IN (
                     SELECT DISTINCT sell_id  -- Исправлено: был sell_id
                     FROM purchase_history 
                     WHERE sell_id IS NOT NULL
                 )""",
            fetch=True
        )
        
        if problematic_cards:
            logger.warning(f"⚠️ Найдено {len(problematic_cards)} некорректных записей продаж")
            
            for card in problematic_cards:
                sell_id, card_id, nickname, price, added_at = card
                
                logger.warning(
                    f"⚠️ Некорректная запись: ID={sell_id}, карточка='{nickname}', "
                    f"цена={price}, добавлена={added_at}"
                )
                
                # Автоматически исправляем статус
                db_operation(
                    "UPDATE sell_cards SET is_available = 1 WHERE id = ?",
                    (sell_id,)
                )
                
                logger.info(f"✅ Исправлена карточка ID {sell_id} ('{nickname}') - статус изменен на 'доступна'")
            
            # Логируем итог
            logger.info(f"✅ Исправлено {len(problematic_cards)} некорректных записей")
        else:
            logger.info("✅ Все статусы продаж корректны")
            
        return len(problematic_cards) if problematic_cards else 0
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при проверке статусов продаж: {e}")
        import traceback
        logger.error(f"Трейсбэк: {traceback.format_exc()}")
        return -1






def init_databases():
    """Инициализирует все таблицы базы данных и создает резервную копию"""
    logger.info("🔄 Инициализация базы данных...")
    
    try:
        # Убедимся, что DB_PATH инициализирована
        if DB_PATH is None:
            init_directories()
            
        # Проверяем существование базы данных
        if os.path.exists(DB_PATH):
            db_size = os.path.getsize(DB_PATH)
            logger.info(f"📁 База данных существует, размер: {db_size} байт")
        else:
            logger.info("📁 Создание новой базы данных")
        
        # Все таблицы создаем в одном файле mamobot.sql
        db_operation('''
        CREATE TABLE IF NOT EXISTS all_users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            country TEXT,
            first_name TEXT,
            is_premium TEXT,
            nickname TEXT UNIQUE,
            user_type TEXT DEFAULT 'player',  -- 'player' или 'owner'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        db_operation('''
        CREATE TABLE IF NOT EXISTS coin_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            source TEXT NOT NULL,
            operation_type TEXT NOT NULL,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES all_users (id)
        )
        ''')
        
        # Создайте индекс для быстрого поиска
        db_operation('''
        CREATE INDEX IF NOT EXISTS idx_coin_history_user_date 
        ON coin_history(user_id, created_at DESC)
        ''')
        # Таблица анкет игроков (ищущих клуб) - добавляем поле user_contact
        db_operation('''
        CREATE TABLE IF NOT EXISTS users_search_club (
            player_id INTEGER PRIMARY KEY,
            nickname TEXT UNIQUE,
            player_position TEXT,
            experience TEXT,
            clubs_played_before TEXT,
            user_contact TEXT,  -- Новое поле для автоматически полученного контакта
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player_id) REFERENCES all_users (id)
        )
        ''')
        db_operation('''
        CREATE TABLE IF NOT EXISTS purchase_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            sell_id INTEGER NOT NULL,          -- ID продажи (sell_cards.id или user_sell_transactions.id)
            card_id INTEGER NOT NULL,          -- ID карточки (players_catalog.id)
            price INTEGER NOT NULL,
            transaction_type TEXT DEFAULT 'admin_sell',  -- admin_sell или user_sell
            purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES all_users (id),
            FOREIGN KEY (card_id) REFERENCES players_catalog (id)
        )
        ''')
        
        # Создаем индекс для быстрого поиска
        db_operation('''
        CREATE INDEX IF NOT EXISTS idx_purchase_history_user 
        ON purchase_history(user_id, purchased_at DESC)
        ''')
        
        # Обновляем структуру таблицы если нужно
        update_purchase_history_table()
        db_operation('''
CREATE TABLE IF NOT EXISTS user_daily_bonus (
    user_id INTEGER PRIMARY KEY,
    last_bonus_moscow TIMESTAMP NOT NULL,  -- Храним время по МСК
    streak_days INTEGER DEFAULT 1,
    total_bonus_coins INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES all_users (id)
)
''')
        db_operation('''
        CREATE TABLE IF NOT EXISTS promocodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            coins INTEGER NOT NULL,
            max_uses INTEGER DEFAULT 0,  -- 0 = безлимитное использование
            used_count INTEGER DEFAULT 0,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (created_by) REFERENCES all_users (id)
        )
        ''')
        # В функции init_databases() замените таблицу user_sell_transactions:
        db_operation('''
CREATE TABLE IF NOT EXISTS user_sell_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- Добавляем автоинкрементный ID
    card_id INTEGER NOT NULL,  -- ID карточки из players_catalog
    seller_id INTEGER NOT NULL,
    buyer_id INTEGER,
    price INTEGER NOT NULL,
    status TEXT DEFAULT 'active', -- active, sold, cancelled
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sold_at TIMESTAMP,
    admin_notified BOOLEAN DEFAULT 0,
    FOREIGN KEY (seller_id) REFERENCES all_users (id),
    FOREIGN KEY (buyer_id) REFERENCES all_users (id),
    FOREIGN KEY (card_id) REFERENCES players_catalog (id)
)
''')

        db_operation('''
        CREATE INDEX IF NOT EXISTS idx_user_sell_status 
        ON user_sell_transactions(status, created_at DESC)
        ''')
        
        # Создаем частичный уникальный индекс для активных продаж
        db_operation('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_active_sell 
        ON user_sell_transactions(card_id) 
        WHERE status = 'active'
        ''')
        
        # Таблица использований промокодов (чтобы отслеживать, кто уже использовал)
        db_operation('''
        CREATE TABLE IF NOT EXISTS promocode_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            promocode_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(promocode_id, user_id),  -- Один пользователь не может использовать один промокод дважды
            FOREIGN KEY (promocode_id) REFERENCES promocodes (id),
            FOREIGN KEY (user_id) REFERENCES all_users (id)
        )
        ''')
        
        # Индексы для быстрого поиска
        db_operation('''
        CREATE INDEX IF NOT EXISTS idx_promocodes_code 
        ON promocodes(code, is_active)
        ''')
        
        db_operation('''
        CREATE INDEX IF NOT EXISTS idx_promocode_usage_user 
        ON promocode_usage(user_id, promocode_id)
        ''')
# Индекс для быстрого поиска
        db_operation('''
CREATE INDEX IF NOT EXISTS idx_user_daily_bonus_last_bonus 
ON user_daily_bonus(last_bonus_moscow)
''')

        db_operation('''
        CREATE TABLE IF NOT EXISTS sell_cards (
            card_id INTEGER PRIMARY KEY,  -- Используем card_id как primary key
            price INTEGER NOT NULL,
            comment TEXT,
            added_by_id INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_available BOOLEAN DEFAULT 1,
            FOREIGN KEY (card_id) REFERENCES players_catalog (id)
        )
        ''')
        # Таблица для коинов пользователей
        db_operation('''
        CREATE TABLE IF NOT EXISTS user_coins (
            user_id INTEGER PRIMARY KEY,
            coins INTEGER DEFAULT 5,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES all_users (id)
        )
        ''')
        
        # Таблица истории покупок
        db_operation('''
        CREATE TABLE IF NOT EXISTS purchase_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            sell_id INTEGER NOT NULL,
            price INTEGER NOT NULL,
            transaction_type TEXT DEFAULT 'admin_sell', -- admin_sell или user_sell
            purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES all_users (id),
            FOREIGN KEY (sell_id) REFERENCES sell_cards (id)
        )
        ''')
        db_operation('''
        CREATE TABLE IF NOT EXISTS muted_users (
            user_id INTEGER PRIMARY KEY,
            muted_by_id INTEGER NOT NULL,
            unmute_time TIMESTAMP NOT NULL,
            mute_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES all_users (id),
            FOREIGN KEY (muted_by_id) REFERENCES all_users (id)
        )
        ''')
        
        # Индекс для быстрого поиска по времени размута
        db_operation('''
        CREATE INDEX IF NOT EXISTS idx_muted_users_unmute_time 
        ON muted_users(unmute_time)
        ''')
        db_operation('''
        CREATE TABLE IF NOT EXISTS banned_users (
            user_id INTEGER PRIMARY KEY,
            banned_by_id INTEGER,
            ban_reason TEXT,
            banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES all_users (id)
        )
        ''')
        db_operation(''' 
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY,
            username TEXT,
            role TEXT NOT NULL
        )
        ''')
        # Таблица анкет овнеров (ищущих игроков) - добавляем поле user_contact
        db_operation('''
        CREATE TABLE IF NOT EXISTS owners_search_players (
            owner_id INTEGER PRIMARY KEY,
            club_name TEXT,
            needed_positions TEXT,
            owner_comment TEXT,
            user_contact TEXT,  -- Новое поле для автоматически полученного контакта
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES all_users (id)
        )
        ''')
        
        # Таблица для лайков от овнеров к игрокам
        db_operation('''
        CREATE TABLE IF NOT EXISTS owner_likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER,
            liked_player_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(owner_id, liked_player_id),
            FOREIGN KEY (owner_id) REFERENCES all_users (id),
            FOREIGN KEY (liked_player_id) REFERENCES all_users (id)
        )
        ''')
        
        # Таблица для лайков от игроков к клубам (новая таблица)
        db_operation('''
        CREATE TABLE IF NOT EXISTS player_likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER,
            liked_club_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(player_id, liked_club_id),
            FOREIGN KEY (player_id) REFERENCES all_users (id),
            FOREIGN KEY (liked_club_id) REFERENCES all_users (id)
        )
        ''')
        db_operation('''
        CREATE TABLE IF NOT EXISTS user_filters (
            user_id INTEGER PRIMARY KEY,
            filter_position TEXT DEFAULT 'all',  -- 'all', 'op', 'gk', 'nap', 'op+gk', 'op+nap', 'gk+nap', 'op+gk+nap'
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES all_users (id)
        )
        ''')
        db_operation('''
        CREATE TABLE IF NOT EXISTS players_catalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nickname TEXT UNIQUE,
            club TEXT,
            position TEXT,
            rarity TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        db_operation('''
        CREATE TABLE IF NOT EXISTS user_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            card_id INTEGER,
            received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, card_id),
            FOREIGN KEY (user_id) REFERENCES all_users (id),
            FOREIGN KEY (card_id) REFERENCES players_catalog (id)
        )
        ''')
        
        # ДОБАВЛЕНО: Таблица для отслеживания времени последнего получения карточки
        db_operation('''
        CREATE TABLE IF NOT EXISTS user_card_cooldowns (
            user_id INTEGER PRIMARY KEY,
            last_fammo_at TIMESTAMP,
            next_fammo_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES all_users (id)
        )
        ''')
        
        # ДОБАВЛЕНО: Индекс для cooldowns
        db_operation('''
        CREATE INDEX IF NOT EXISTS idx_user_cooldowns_next 
        ON user_card_cooldowns(next_fammo_at)
        ''')
        
        logger.info("✅ База данных инициализирована успешно")
        logger.info("🔍 Запуск проверки целостности продаж...")
        check_and_fix_sell_status_on_startup()
        cleanup_old_bonus_entries()
        create_user_squad_table()
        logger.info("✅ Таблицы промокодов инициализированы")
        update_purchase_history_table()
        logger.info("✅ База данных инициализирована успешно")
    except Exception as e:
        logger.error(f"❌ Ошибка при инициализации базы данных: {str(e)}")
        import traceback
        logger.error(f"Трейсбэк: {traceback.format_exc()}")
        raise


def load_players_catalog():
    """Загружает и обновляет каталог игроков при запуске бота."""
    try:
        logger.info("🔄 Загрузка каталога игроков...")
        
        # Проверяем, есть ли уже карточки в базе
        result = db_operation("SELECT COUNT(*) FROM players_catalog", fetch=True)
        existing_count = result[0][0] if result else 0
        
        if existing_count > 0:
            logger.info(f"📊 В базе уже есть {existing_count} карточек, обновляю...")
        else:
            logger.info("📝 База карточек пуста, создаю...")
        
        # Обновляем каталог
        seed_players_catalog()
        
        logger.info("✅ Каталог игроков загружен")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при загрузке каталога игроков: {e}")



def backup_database():
    """Создает резервную копию базы данных"""
    try:
        if DB_PATH is None:
            logger.error("DB_PATH не инициализирована для создания бэкапа")
            return
            
        if os.path.exists(DB_PATH):
            import shutil
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(BACKUP_DIR, f"mamobot_backup_{timestamp}.sql")
            shutil.copy2(DB_PATH, backup_file)
            logger.info(f"✅ Резервная копия создана: {backup_file}")
            
            # Удаляем старые резервные копии (оставляем последние 5)
            try:
                backup_files = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith("mamobot_backup_")])
                if len(backup_files) > 5:
                    for old_file in backup_files[:-5]:
                        os.remove(os.path.join(BACKUP_DIR, old_file))
                        logger.info(f"🗑️ Удалена старая резервная копия: {old_file}")
            except Exception as e:
                logger.error(f"Ошибка при удалении старых бэкапов: {e}")
    except Exception as e:
        logger.error(f"❌ Ошибка при создании резервной копии: {str(e)}")

# Инициализируем базу данных при импорте модуля
try:
    init_databases()
except Exception as e:
    logger.error(f"❌ Критическая ошибка при инициализации БД: {e}")
    # Не прерываем выполнение, возможно бот сможет работать
def save_user_filter(user_id: int, filter_position: str):
    """Сохраняет фильтр позиций пользователя"""
    try:
        db_operation(
            """INSERT OR REPLACE INTO user_filters (user_id, filter_position, updated_at) 
               VALUES (?, ?, CURRENT_TIMESTAMP)""",
            (user_id, filter_position)
        )
        logger.info(f"Фильтр пользователя {user_id} сохранен: {filter_position}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении фильтра пользователя {user_id}: {e}")

def get_user_filter(user_id: int) -> str:
    """Получает фильтр позиций пользователя"""
    try:
        result = db_operation(
            "SELECT filter_position FROM user_filters WHERE user_id = ?",
            (user_id,),
            fetch=True
        )
        if result:
            return result[0][0]
        return 'all'  # По умолчанию - все позиции
    except Exception as e:
        logger.error(f"Ошибка при получении фильтра пользователя {user_id}: {e}")
        return 'all'
    

# Добавьте эти функции в файл с базой данных после других функций



def get_user_squad(user_id: int):
    """Получает состав пользователя"""
    try:
        result = db_operation(
            """SELECT gk_card_id, op_card_id, nap1_card_id, nap2_card_id, squad_name
               FROM user_squads 
               WHERE user_id = ? AND is_active = 1""",
            (user_id,),
            fetch=True
        )
        
        if result:
            gk_card_id, op_card_id, nap1_card_id, nap2_card_id, squad_name = result[0]
            return {
                'gk_card_id': gk_card_id,
                'op_card_id': op_card_id,
                'nap1_card_id': nap1_card_id,
                'nap2_card_id': nap2_card_id,
                'squad_name': squad_name
            }
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении состава пользователя {user_id}: {e}")
        return None

def get_card_details(card_id: int):
    """Получает детали карточки по ID"""
    try:
        if not card_id:
            return None
            
        result = db_operation(
            """SELECT nickname, club, position, rarity
               FROM players_catalog 
               WHERE id = ?""",
            (card_id,),
            fetch=True
        )
        
        if result:
            nickname, club, position, rarity = result[0]
            return {
                'nickname': nickname,
                'club': club,
                'position': position,
                'rarity': rarity
            }
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении деталей карточки {card_id}: {e}")
        return None
def get_card_by_nickname_db(nickname: str):
    """Находит карточку игрока по никнейму в базе данных"""
    try:
        # Ищем точное совпадение
        result = db_operation(
            """SELECT id, nickname, club, position, rarity 
               FROM players_catalog 
               WHERE nickname = ? COLLATE NOCASE""",
            (nickname,),
            fetch=True
        )
        
        if result:
            card_id, nickname, club, position, rarity = result[0]
            return {
                'id': card_id,
                'nickname': nickname,
                'club': club,
                'position': position,
                'rarity': rarity
            }
        
        # Ищем частичное совпадение (регистронезависимо)
        result = db_operation(
            """SELECT id, nickname, club, position, rarity 
               FROM players_catalog 
               WHERE LOWER(nickname) LIKE LOWER(?) 
               ORDER BY 
                 CASE 
                   WHEN nickname LIKE ? THEN 1  # Начало строки
                   ELSE 2
                 END,
                 nickname""",
            (f"%{nickname}%", f"{nickname}%"),
            fetch=True
        )
        
        if result:
            card_id, nickname, club, position, rarity = result[0]
            return {
                'id': card_id,
                'nickname': nickname,
                'club': club,
                'position': position,
                'rarity': rarity
            }
        
        return None
        
    except Exception as e:
        logger.error(f"Ошибка при поиске карточки по нику '{nickname}': {e}")
        return None
def save_user_squad(user_id: int, gk_card_id: int = None, op_card_id: int = None, 
                    nap1_card_id: int = None, nap2_card_id: int = None, squad_name: str = "Мой состав"):
    """Сохраняет или обновляет состав пользователя"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Проверяем существование записи
        cursor.execute("SELECT id FROM user_squads WHERE user_id = ?", (user_id,))
        existing = cursor.fetchone()
        
        if existing:
            # Обновляем существующий состав
            cursor.execute("""
                UPDATE user_squads 
                SET gk_card_id = ?, op_card_id = ?, nap1_card_id = ?, nap2_card_id = ?,
                    squad_name = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (gk_card_id, op_card_id, nap1_card_id, nap2_card_id, squad_name, user_id))
        else:
            # Создаем новый состав
            cursor.execute("""
                INSERT INTO user_squads 
                (user_id, gk_card_id, op_card_id, nap1_card_id, nap2_card_id, squad_name)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, gk_card_id, op_card_id, nap1_card_id, nap2_card_id, squad_name))
        
        conn.commit()
        conn.close()
        return True, "Состав успешно сохранен"
        
    except Exception as e:
        logger.error(f"Ошибка при сохранении состава пользователя {user_id}: {e}")
        return False, f"Ошибка при сохранении: {str(e)[:100]}"
def get_user_cards(user_id: int):
    """Получает все карточки пользователя"""
    try:
        result = db_operation(
            """SELECT pc.nickname, pc.club, pc.position, pc.rarity, uc.received_at
               FROM user_cards uc
               JOIN players_catalog pc ON uc.card_id = pc.id
               WHERE uc.user_id = ?
               ORDER BY 
                 CASE pc.rarity 
                   WHEN 'EEA' THEN 1           -- Добавить эту строку
                   WHEN 'Суперлегендарный' THEN 2
                   WHEN 'Легендарный' THEN 3
                   WHEN 'Эпический' THEN 4
                   WHEN 'Редкий' THEN 5
                   ELSE 6
                 END,
                 pc.nickname""",
            (user_id,),
            fetch=True
        )
        return result if result else []
    except Exception as e:
        logger.error(f"Ошибка при получении карточек пользователя {user_id}: {e}")
        return []
def get_user_cards_by_position(user_id: int, position: str):
    """Получает карточки пользователя по позиции, включая карточки с редкостью "уник" """
    try:
        # Получаем ID карточек пользователя
        user_cards = get_user_cards(user_id)
        position_cards = []

        # Преобразуем позицию к нижнему регистру для сравнения
        position_lower = position.lower()

        for card in user_cards:
            nickname, club, card_position, rarity, _ = card
            card_position_lower = card_position.lower() if card_position else ""
            rarity_lower = rarity.lower() if rarity else ""

            # Проверяем, является ли карточка "уником" (универсалом)
            is_universal = "уник" in rarity_lower

            # Логика отбора карточек:
            # 1. Карточка подходит по позиции (обычная логика) ИЛИ
            # 2. Карточка является "уником"
            if (position_lower in card_position_lower) or is_universal:
                # Получаем ID карточки
                card_info = get_card_by_nickname_db(nickname)
                if card_info:
                    # Добавляем флаг, является ли карточка универсальной, для возможного использования в будущем
                    position_cards.append({
                        'id': card_info['id'],
                        'nickname': nickname,
                        'club': club,
                        'position': card_position,
                        'rarity': rarity,
                        'is_universal': is_universal  # Полезно для отладки или будущих фич
                    })

        return position_cards

    except Exception as e:
        logger.error(f"Ошибка при получении карточек по позиции для пользователя {user_id}: {e}")
        return []
        


# Не забудьте вызвать создание таблицы в init_databases()
# Добавьте в функцию init_databases():
# create_user_squad_table()