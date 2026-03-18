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
from mamodatabases import SimpleLogger, LOGS_DIR
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
from mamodatabases import db_operation, logger, log_command, BASE_DIR, log_admin_action, get_card_by_nickname_db, get_user_cards

router_admins = Router()
router_admins.message.filter(F.chat.type == "private")
router_admins.callback_query.filter(F.message.chat.type == "private")
public_router_admins = Router()

#===========================

#===========================

class SupportStates(StatesGroup):
    nickname_of_user = State()
    viewing_players = State()
    waiting_for_player_message = State()  # НОВОЕ состояние для сообщения игроку
    waiting_for_request = State()
    # Состояния для поиска клубов (игроком)
    viewing_clubs = State()
    waiting_for_club_message = State()  # НОВОЕ состояние для сообщения клубу
    # Состояния для анкеты игрока
    anketa_nickname = State()
    anketa_position = State()
    anketa_experience = State()
    anketa_clubs = State()  # Убрали anketa_contact
    anketa_position_selection = State()
    # Состояния для анкеты овнера
    owner_club_name = State()
    owner_needed_positions = State()  # Теперь это будет хранить выбранные позиции
    owner_positions_selection = State()
    owner_comment = State()  # Убрали owner_contact
    
    waiting_for_donate = State()
    # Состояния для поиска игроков (овнером)
    viewing_players = State()
    
    # Состояния для поиска клубов (игроком) - новые состояния
    viewing_clubs = State()
    
    waiting_report = State()
    waiting_for_id1 = State()
    waiting_for_id2 = State()
    waiting_id_for_mute1 = State()
    waiting_id_for_mute2 = State()
    waiting_for_message_for_rassilka = State()
    waiting_for_ban_id1 = State()
    waiting_for_ban_id2 = State()
    waiting_filter_position = State()  # Новое состояние для выбора фильтра позиций
scheduler = None
scheduler_initialized = False
# КОНСТАНТЫ ДЛЯ AMVERA С ПОСТОЯННЫМ ХРАНИЛИЩЕМ
# Все данные сохраняем в /data, который монтируется как постоянное хранилище

#==============

def get_user_coins(user_id: int) -> int:
    """Получает количество коинов пользователя"""
    try:
        result = db_operation(
            "SELECT coins FROM user_coins WHERE user_id = ?",
            (user_id,),
            fetch=True
        )
        if result:
            return result[0][0]
        # Если пользователя нет в таблице, создаем запись с 5 коинами
        db_operation(
            "INSERT OR IGNORE INTO user_coins (user_id, coins) VALUES (?, 5)",
            (user_id,)
        )
        return 5
    except Exception as e:
        logger.error(f"Ошибка при получении коинов пользователя {user_id}: {e}")
        return 5

def update_user_coins(user_id: int, coins: int):
    """Обновляет количество коинов пользователя"""
    try:
        db_operation(
            """INSERT OR REPLACE INTO user_coins (user_id, coins, updated_at) 
               VALUES (?, ?, CURRENT_TIMESTAMP)""",
            (user_id, coins)
        )
        logger.info(f"Коины пользователя {user_id} обновлены: {coins}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при обновлении коинов пользователя {user_id}: {e}")
        return False

def add_user_coins(user_id: int, amount: int):
    """Добавляет коины пользователю"""
    current = get_user_coins(user_id)
    new_amount = current + amount
    return update_user_coins(user_id, new_amount)

def subtract_user_coins(user_id: int, amount: int):
    """Вычитает коины у пользователя"""
    current = get_user_coins(user_id)
    if current < amount:
        return False, "Недостаточно коинов"
    new_amount = current - amount
    success = update_user_coins(user_id, new_amount)
    return success, "Успешно" if success else "Ошибка обновления"
           #   8056665318
group_of_admins = -1003615487276

DEFAULT_SENIOR_ADMIN_ID = 1088006569

# Уровни доступа для ролей (чем выше значение, тем больше прав)
ROLE_LEVELS = {
    "модератор": 1,
    "помощник-администратора": 2,
    "младший-администратор": 3,
    "старший-администратор": 4
}
def require_role(required_role: str):
    """Декоратор для проверки прав доступа к команде"""
    def decorator(handler):
        async def wrapper(message: Message, *args, **kwargs):
            user_id = message.from_user.id
            
            # Специальный доступ для изначального администратора
            if user_id == DEFAULT_SENIOR_ADMIN_ID:
                # Фильтруем только нужные аргументы для handler
                filtered_kwargs = {}
                # Проверяем, какие параметры ожидает handler
                import inspect
                handler_params = inspect.signature(handler).parameters
                
                for param_name in handler_params:
                    if param_name in kwargs:
                        filtered_kwargs[param_name] = kwargs[param_name]
                
                return await handler(message, *args, **filtered_kwargs)
            
            # Проверка наличия нужной роли
            if not has_permission(user_id, required_role):
                await message.reply("🚫 Недостаточно прав для выполнения этой команды.")
                return
            
            # Фильтруем только нужные аргументы для handler
            filtered_kwargs = {}
            # Проверяем, какие параметры ожидает handler
            import inspect
            handler_params = inspect.signature(handler).parameters
            
            for param_name in handler_params:
                if param_name in kwargs:
                    filtered_kwargs[param_name] = kwargs[param_name]
            
            return await handler(message, *args, **filtered_kwargs)
        return wrapper
    return decorator
# Проверка на администратора с получением роли
def get_admin_role(user_id: int) -> str | None:
    """Получает роль администратора"""
    if user_id == DEFAULT_SENIOR_ADMIN_ID:
        return "старший-администратор"
    
    try:
        result = db_operation(
            "SELECT role FROM admins WHERE id = ?",
            (user_id,),
            fetch=True
        )
        return result[0][0] if result else None
    except Exception as e:
        logger.error(f"Ошибка при получении роли администратора {user_id}: {e}")
        return None

def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    return get_admin_role(user_id) is not None

def has_permission(user_id: int, required_role: str) -> bool:
    """Проверяет, имеет ли пользователь достаточный уровень доступа"""
    user_role = get_admin_role(user_id)
    if not user_role:
        return False
    
    # Специальная проверка для изначального администратора
    if user_id == DEFAULT_SENIOR_ADMIN_ID:
        return True
    
    required_level = ROLE_LEVELS.get(required_role, 0)
    user_level = ROLE_LEVELS.get(user_role, 0)
    
    return user_level >= required_level

# Декоратор для проверки прав доступа


# Состояния для админ-панели
class AdminStates(StatesGroup):
    wait_for_add = State()
    waiting_for_ban_id1 = State()
    waiting_for_ban_id2 = State()
    waiting_id_for_mute1 = State()
    waiting_id_for_mute2 = State()
    waiting_for_id1 = State()
    waiting_for_id2 = State()
    waiting_for_message_for_rassilka = State()

# ========================
# КОМАНДЫ ДОБАВЛЕНИЯ АДМИНИСТРАТОРОВ
# ========================

@router_admins.message(Command("allcards"))
@require_role("младший-администратор")
@log_admin_action("Просмотр всех карточек")
async def allcards_command(message: Message):
    """Показать все карточки с пагинацией (только для админов)"""
    
    try:
        # Получаем все карточки из базы
        all_cards = get_all_cards_from_db()
        
        if not all_cards:
            await message.reply("📭 В базе данных нет карточек.")
            return
        
        total_cards = len(all_cards)
        
        # Показываем первую страницу
        await show_cards_page(message, all_cards, page=0, total_pages=(total_cards + 9) // 10)
        
    except Exception as e:
        logger.error(f"❌ Ошибка в команде /allcards: {e}")
        await message.reply(f"❌ Ошибка: {str(e)[:100]}")
@router_admins.callback_query(F.data.startswith("allcards_page_"))
async def allcards_page_callback(callback: CallbackQuery):
    """Переключение страниц в /allcards"""
    try:
        page = int(callback.data.split("_")[2])
        all_cards = get_all_cards_from_db()
        
        if not all_cards:
            await callback.answer("Нет карточек", show_alert=True)
            return
        
        total_cards = len(all_cards)
        total_pages = (total_cards + 9) // 10
        
        await show_cards_page(callback, all_cards, page, total_pages)
        
    except Exception as e:
        logger.error(f"Ошибка в allcards_page_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@router_admins.callback_query(F.data.startswith("allcards_refresh_"))
async def allcards_refresh_callback(callback: CallbackQuery):
    """Обновление страницы /allcards"""
    try:
        page = int(callback.data.split("_")[2])
        all_cards = get_all_cards_from_db()
        
        if not all_cards:
            await callback.answer("Нет карточек", show_alert=True)
            return
        
        total_cards = len(all_cards)
        total_pages = (total_cards + 9) // 10
        
        await show_cards_page(callback, all_cards, page, total_pages)
        await callback.answer("🔄 Обновлено")
        
    except Exception as e:
        logger.error(f"Ошибка в allcards_refresh_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)
@router_admins.message(Command("clean_logs"))
@require_role("старший-администратор")
@log_admin_action("Очистка логов")
async def clean_logs_command(message: Message):
    """Очистка логов старше 7 дней"""
    try:
        # Показываем подтверждение
        confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑️ Удалить логи старше 7 дней", 
                    callback_data="clean_logs_confirm"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⚠️ Удалить ВСЕ логи", 
                    callback_data="clean_logs_all"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена", 
                    callback_data="clean_logs_cancel"
                )
            ]
        ])
        
        # Получаем информацию о логах
        log_info = get_log_files_info()
        
        await message.reply(
            f"📊 <b>ОЧИСТКА ЛОГОВ</b>\n\n"
            f"{log_info}\n\n"
            f"<b>Выберите действие:</b>\n"
            f"• 🗑️ <b>Удалить логи старше 7 дней</b> - безопасная очистка\n"
            f"• ⚠️ <b>Удалить ВСЕ логи</b> - полная очистка\n"
            f"• ❌ <b>Отмена</b> - отмена операции\n\n"
            f"<i>Логи старше 7 дней удаляются автоматически ежедневно.</i>",
            parse_mode="HTML",
            reply_markup=confirm_keyboard
        )
        
    except Exception as e:
        logger.error(f"Ошибка в команде /clean_logs: {e}")
        await message.reply(f"❌ Ошибка: {str(e)[:100]}")

def get_log_files_info() -> str:
    """Получает информацию о лог файлах"""
    try:
        logs_dir = LOGS_DIR
        total_size = 0
        file_count = 0
        files_info = []
        
        if os.path.exists(logs_dir):
            for filename in os.listdir(logs_dir):
                if filename.endswith('.log'):
                    file_path = os.path.join(logs_dir, filename)
                    if os.path.exists(file_path):
                        file_size = os.path.getsize(file_path)
                        file_mtime = time.localtime(os.path.getmtime(file_path))
                        file_mtime_dt = datetime.fromtimestamp(os.path.getmtime(file_path))
                        file_age = datetime.now() - file_mtime_dt
                        
                        total_size += file_size
                        file_count += 1
                        
                        # Определяем цвет в зависимости от возраста
                        if file_age.days > 7:
                            age_color = "🔴"
                        elif file_age.days > 3:
                            age_color = "🟡"
                        else:
                            age_color = "🟢"
                        
                        files_info.append(
                            f"{age_color} <code>{filename}</code>\n"
                            f"   📏 Размер: {format_size(file_size)}\n"
                            f"   📅 Возраст: {file_age.days} дней\n"
                        )
        
        # Проверяем основные лог файлы логгера
        logger_instance = SimpleLogger()
        main_log_files = [logger_instance.log_file, logger_instance.error_log_file]
        
        for log_file in main_log_files:
            if os.path.exists(log_file):
                file_size = os.path.getsize(log_file)
                file_mtime_dt = datetime.fromtimestamp(os.path.getmtime(log_file))
                file_age = datetime.now() - file_mtime_dt
                
                total_size += file_size
                file_count += 1
                
                filename = os.path.basename(log_file)
                
                if file_age.days > 7:
                    age_color = "🔴"
                elif file_age.days > 3:
                    age_color = "🟡"
                else:
                    age_color = "🟢"
                
                files_info.append(
                    f"{age_color} <code>{filename}</code>\n"
                    f"   📏 Размер: {format_size(file_size)}\n"
                    f"   📅 Возраст: {file_age.days} дней\n"
                )
        
        info_text = (
            f"📁 <b>Директория логов:</b> <code>{logs_dir}</code>\n"
            f"📊 <b>Всего файлов:</b> {file_count}\n"
            f"💾 <b>Общий размер:</b> {format_size(total_size)}\n"
        )
        
        if files_info:
            info_text += f"\n<b>Файлы:</b>\n" + "\n".join(files_info)
        
        return info_text
        
    except Exception as e:
        logger.error(f"Ошибка при получении информации о логах: {e}")
        return "❌ Не удалось получить информацию о логах"

def format_size(size_bytes: int) -> str:
    """Форматирует размер в читаемый вид"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

@router_admins.callback_query(F.data == "clean_logs_confirm")
async def confirm_clean_logs(callback: CallbackQuery):
    """Подтверждение очистки логов старше 7 дней"""
    try:
        await callback.message.edit_text("🔄 Удаляю логи старше 7 дней...")
        
        # Очищаем логи
        from mamodatabases import cleanup_all_logs
        deleted_count = cleanup_all_logs(days=7)
        
        await callback.message.edit_text(
            f"✅ <b>Очистка логов завершена!</b>\n\n"
            f"🗑️ <b>Удалено файлов:</b> {deleted_count}\n\n"
            f"<i>Логи старше 7 дней успешно удалены.</i>",
            parse_mode="HTML"
        )
        
        logger.warning(f"👑 АДМИН: {callback.from_user.id} очистил логи старше 7 дней. Удалено: {deleted_count} файлов")
        
    except Exception as e:
        logger.error(f"Ошибка при очистке логов: {e}")
        await callback.message.edit_text(
            f"❌ <b>Ошибка при очистке логов:</b>\n\n"
            f"<code>{str(e)[:200]}</code>",
            parse_mode="HTML"
        )

@router_admins.callback_query(F.data == "clean_logs_all")
async def confirm_clean_all_logs(callback: CallbackQuery):
    """Подтверждение очистки ВСЕХ логов"""
    try:
        # Запрашиваем дополнительное подтверждение
        confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="☠️ ДА, УДАЛИТЬ ВСЕ", 
                    callback_data="clean_logs_all_final"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ ОТМЕНА", 
                    callback_data="clean_logs_cancel"
                )
            ]
        ])
        
        await callback.message.edit_text(
            f"⚠️ <b>ВНИМАНИЕ! КРИТИЧЕСКОЕ ДЕЙСТВИЕ</b>\n\n"
            f"Вы собираетесь удалить <b>ВСЕ</b> лог файлы!\n\n"
            f"Это действие:\n"
            f"• Удалит всю историю логов\n"
            f"• Нельзя будет отменить\n"
            f"• Может затруднить отладку проблем\n\n"
            f"<b>Вы уверены, что хотите продолжить?</b>",
            parse_mode="HTML",
            reply_markup=confirm_keyboard
        )
        
    except Exception as e:
        logger.error(f"Ошибка при подтверждении удаления всех логов: {e}")
        await callback.message.edit_text(f"❌ Ошибка: {str(e)[:100]}")

@router_admins.callback_query(F.data == "clean_logs_all_final")
async def clean_all_logs_final(callback: CallbackQuery):
    """Финальное удаление всех логов"""
    try:
        await callback.message.edit_text("☠️ Удаляю ВСЕ лог файлы...")
        
        # Получаем информацию перед удалением
        logs_dir = LOGS_DIR
        total_deleted = 0
        total_size = 0
        
        if os.path.exists(logs_dir):
            # Удаляем все .log файлы
            for filename in os.listdir(logs_dir):
                if filename.endswith('.log'):
                    file_path = os.path.join(logs_dir, filename)
                    if os.path.exists(file_path):
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        total_deleted += 1
                        total_size += file_size
        
        # Также удаляем основные лог файлы
        logger_instance = SimpleLogger()
        log_files = [logger_instance.log_file, logger_instance.error_log_file]
        
        for log_file in log_files:
            if os.path.exists(log_file):
                file_size = os.path.getsize(log_file)
                os.remove(log_file)
                total_deleted += 1
                total_size += file_size
        
        await callback.message.edit_text(
            f"☠️ <b>ВСЕ логи удалены!</b>\n\n"
            f"🗑️ <b>Удалено файлов:</b> {total_deleted}\n"
            f"💾 <b>Освобождено места:</b> {format_size(total_size)}\n\n"
            f"<i>Созданы новые чистые лог файлы.</i>",
            parse_mode="HTML"
        )
        
        logger.warning(f"👑 АДМИН: {callback.from_user.id} удалил ВСЕ логи. Удалено: {total_deleted} файлов")
        
    except Exception as e:
        logger.error(f"Ошибка при удалении всех логов: {e}")
        await callback.message.edit_text(
            f"❌ <b>Ошибка при удалении логов:</b>\n\n"
            f"<code>{str(e)[:200]}</code>",
            parse_mode="HTML"
        )

@router_admins.callback_query(F.data == "clean_logs_cancel")
async def cancel_clean_logs(callback: CallbackQuery):
    """Отмена очистки логов"""
    await callback.message.edit_text("❌ Очистка логов отменена.")

def cleanup_old_logs_manually(days: int = 7) -> int:
    """Ручная очистка логов старше указанного количества дней"""
    try:
        from mamodatabases import cleanup_all_logs
        deleted_count = cleanup_all_logs(days)
        logger.info(f"🗑️ Ручная очистка логов: удалено {deleted_count} файлов старше {days} дней")
        return deleted_count
    except Exception as e:
        logger.error(f"Ошибка при ручной очистке логов: {e}")
        return 0
def get_user_info(user_id: int):
    """Получает информацию о пользователе"""
    try:
        result = db_operation(
            """SELECT username, first_name, user_type 
               FROM all_users 
               WHERE id = ?""",
            (user_id,),
            fetch=True
        )
        
        if result:
            username, first_name, user_type = result[0]
            return {
                'username': username,
                'first_name': first_name,
                'user_type': user_type
            }
        return None
        
    except Exception as e:
        logger.error(f"Ошибка при получении информации о пользователе {user_id}: {e}")
        return None
    
def get_purchase_history(user_id: int = None, limit: int = 10):
    """Получает историю покупок"""
    try:
        if user_id:
            result = db_operation(
                """SELECT ph.id, ph.user_id, ph.card_id, ph.price, 
                          ph.purchased_at, ph.transaction_type, ph.sell_id,
                          pc.nickname, pc.club, pc.position, pc.rarity
                   FROM purchase_history ph
                   JOIN players_catalog pc ON ph.card_id = pc.id
                   WHERE ph.user_id = ?
                   ORDER BY ph.purchased_at DESC
                   LIMIT ?""",
                (user_id, limit),
                fetch=True
            )
        else:
            result = db_operation(
                """SELECT ph.id, ph.user_id, ph.card_id, ph.price, 
                          ph.purchased_at, ph.transaction_type, ph.sell_id,
                          pc.nickname, pc.club, pc.position, pc.rarity
                   FROM purchase_history ph
                   JOIN players_catalog pc ON ph.card_id = pc.id
                   ORDER BY ph.purchased_at DESC
                   LIMIT ?""",
                (limit,),
                fetch=True
            )
        
        if not result:
            return []
        
        history = []
        for row in result:
            (purchase_id, user_id_val, card_id, price, purchased_at, 
             transaction_type, sell_id, nickname, club, position, rarity) = row
            
            history.append({
                'purchase_id': purchase_id,
                'user_id': user_id_val,
                'card_id': card_id,
                'price': price,
                'purchased_at': purchased_at,
                'transaction_type': transaction_type,
                'sell_id': sell_id,  # ДОБАВЛЕНО
                'nickname': nickname,
                'club': club,
                'position': position,
                'rarity': rarity
            })
        
        return history
        
    except Exception as e:
        logger.error(f"❌ Ошибка при получении истории покупок: {e}")
        return []
@router_admins.message(Command("addcoins"))
@require_role("старший-администратор")
@log_admin_action("Добавление коинов пользователю")
async def addcoins_command(message: Message):
    """Добавить коины пользователю"""
    command_text = message.text.strip()
    args = command_text.split()
    
    if len(args) < 3:
        await message.reply(
            "💰 <b>ИСПОЛЬЗОВАНИЕ КОМАНДЫ:</b>\n\n"
            "<code>/addcoins [id_пользователя] [количество] (комментарий)</code>\n\n"
            "<b>Примеры:</b>\n"
            "• <code>/addcoins 123456789 10 Бонус за активность</code>\n"
            "• <code>/addcoins 987654321 50 Выигрыш в конкурсе</code>\n"
            "• <code>/addcoins 555555555 -20 Штраф за нарушение</code>\n"
            "• <code>/addcoins 111111111 100 Административный бонус</code>\n\n"
            "<b>Примечания:</b>\n"
            "1. ID пользователя можно узнать через /users или /getid\n"
            "2. Количество может быть отрицательным для вычитания коинов\n"
            "3. Комментарий необязателен (макс 200 символов)\n"
            "4. Минимальный баланс пользователя: 0 коинов\n\n"
            "<i>Команда доступна только старшим администраторам</i>",
            parse_mode="html"
        )
        return
    
    try:
        target_user_id = int(args[1])
        coins_amount = int(args[2])
        comment = " ".join(args[3:]) if len(args) > 3 else "Административное изменение"
        
        # Проверка на максимальную длину комментария
        if len(comment) > 200:
            comment = comment[:197] + "..."
        
        # Проверяем существование пользователя
        user_info = get_user_info(target_user_id)
        if not user_info:
            await message.reply(
                f"❌ <b>Пользователь не найден!</b>\n\n"
                f"Пользователь с ID <code>{target_user_id}</code> не зарегистрирован в системе.\n\n"
                f"<i>Пользователь должен сначала выполнить /start в боте</i>",
                parse_mode="html"
            )
            return
        
        user_display = f"@{user_info['username']}" if user_info['username'] else user_info['first_name'] or f"ID: {target_user_id}"
        
        # Получаем текущие коины пользователя
        current_coins = get_user_coins(target_user_id)
        
        # Вычисляем новые коины
        new_coins = current_coins + coins_amount
        
        # Проверяем, чтобы баланс не стал отрицательным
        if new_coins < 0:
            await message.reply(
                f"❌ <b>Невозможно выполнить операцию!</b>\n\n"
                f"<b>Пользователь:</b> {user_display}\n"
                f"<b>Текущие МамоКоины:</b> {current_coins}\n"
                f"<b>Попытка изменить на:</b> {coins_amount}\n"
                f"<b>Результат:</b> {new_coins} (не может быть меньше 0)\n\n"
                f"<i>Максимально можно вычесть: {current_coins} коинов</i>",
                parse_mode="html"
            )
            return
        
        # Обновляем коины
        success = update_user_coins(target_user_id, new_coins)
        
        if not success:
            await message.reply(
                f"❌ <b>Ошибка при обновлении коинов!</b>\n\n"
                f"Не удалось обновить баланс пользователя.\n"
                f"<i>Проверьте логи для подробностей</i>",
                parse_mode="html"
            )
            return
        
        # Форматируем сообщение об успехе
        operation_type = "добавлено" if coins_amount > 0 else "вычтено" if coins_amount < 0 else "изменено"
        amount_abs = abs(coins_amount)
        operation_icon = "➕" if coins_amount > 0 else "➖" if coins_amount < 0 else "🔄"
        
        # Получаем информацию о карточках пользователя для статистики
        card_stats = get_user_card_stats(target_user_id)
        purchase_history = get_purchase_history(target_user_id, limit=5)
        total_spent = sum(purchase['price'] for purchase in purchase_history) if purchase_history else 0
        
        success_message = (
            f"{operation_icon} <b>БАЛАНС ОБНОВЛЕН!</b>\n\n"
            f"<b>👤 Пользователь:</b> {user_display}\n"
            f"<b>🆔 ID:</b> <code>{target_user_id}</code>\n"
            f"<b>🎮 Тип:</b> {user_info['user_type']}\n\n"
            f"<b>💰 Было коинов:</b> {current_coins}\n"
            f"<b>{operation_icon} {operation_type.capitalize()}:</b> {amount_abs} коинов\n"
            f"<b>💰 Стало коинов:</b> {new_coins}\n\n"
            f"<b>📊 Дополнительная статистика:</b>\n"
            f"• <b>Всего карточек:</b> {card_stats['user_cards'] if card_stats else 0}\n"
            f"• <b>Потрачено на покупки:</b> {total_spent} коинов\n"
            f"• <b>Последние покупки:</b> {len(purchase_history)}\n\n"
            f"<b>📝 Комментарий:</b> {comment}\n\n"
            f"<b>👑 Операция выполнена:</b> @{message.from_user.username or message.from_user.first_name}\n"
            f"<b>⏰ Время:</b> {datetime.now().strftime('%H:%M %d.%m.%Y')}"
        )
        
        # Создаем inline-клавиатуру с действиями
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="🔍 Проверить пользователя",
                callback_data=f"checkuser_{target_user_id}"
            ),
            InlineKeyboardButton(
                text="💰 Добавить еще",
                callback_data=f"quick_addcoins_{target_user_id}"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="📊 Статистика",
                callback_data=f"coins_stats_{target_user_id}"
            )
        )
        
        await message.reply(success_message, parse_mode="html", reply_markup=builder.as_markup())
        
        # Логируем операцию
        logger.warning(
            f"👑 Админ {message.from_user.id} {operation_type} {amount_abs} коинов пользователю {target_user_id} "
            f"({user_display}). Было: {current_coins}, Стало: {new_coins}. Комментарий: {comment}"
        )
        
        # Отправляем уведомление пользователю (если возможно)
        try:
            user_notification = (
                f"{operation_icon} <b>ВАШ БАЛАНС ИЗМЕНЕН</b>\n\n"
                f"Администратором Вам {operation_type}  <b>{amount_abs} коинов</b>.\n\n"
                f"<b>📊 Статистика:</b>\n"
                f"• <b>Было:</b> {current_coins} коинов\n"
                f"• <b>Стало:</b> {new_coins} коинов\n"
                f"• <b>Изменение:</b> {coins_amount} коинов\n\n"
                f"<b>📝 Причина:</b> {comment}\n\n"
                f"<i>Используйте /trade для просмотра доступных карточек</i>"
            )
            
            await message.bot.send_message(
                chat_id=target_user_id,
                text=user_notification,
                parse_mode="html"
            )
            
            # Добавляем запись в историю операций с коинами
            try:
                db_operation(
                    """INSERT INTO coin_history (user_id, admin_id, amount, comment, new_balance) 
                       VALUES (?, ?, ?, ?, ?)""",
                    (target_user_id, message.from_user.id, coins_amount, comment, new_coins)
                )
            except Exception as history_error:
                # Если таблицы нет или ошибка, просто логируем
                logger.warning(f"Не удалось записать в историю коинов: {history_error}")
                
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление пользователю {target_user_id}: {e}")
        
    except ValueError:
        await message.reply(
            "❌ <b>Неверный формат параметров!</b>\n\n"
            "ID пользователя и количество коинов должны быть числами.\n"
            "Пример: <code>/addcoins 123456789 50 Бонус</code>\n\n"
            "<i>Для вычитания используйте отрицательное число: /addcoins 123456789 -20 Штраф</i>",
            parse_mode="html"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка в команде /addcoins: {e}")
        await message.reply(
            f"❌ Произошла ошибка: {str(e)[:100]}",
            parse_mode="html"
        )

@router_admins.callback_query(F.data.startswith("admin_addcoins_"))
async def admin_addcoins_callback(callback: CallbackQuery):
    """Кнопка изменения коинов"""
    try:
        target_user_id = int(callback.data.split("_")[2])
        await callback.answer(f"Используйте /addcoins {target_user_id} [количество] [комментарий]")
    except:
        await callback.answer("❌ Ошибка", show_alert=True)

@router_admins.callback_query(F.data.startswith("admin_addcard_"))
async def admin_addcard_callback(callback: CallbackQuery):
    """Кнопка добавления карточки"""
    try:
        target_user_id = int(callback.data.split("_")[2])
        await callback.answer(f"Используйте /addcard [ник_игрока] {target_user_id}")
    except:
        await callback.answer("❌ Ошибка", show_alert=True)

@router_admins.callback_query(F.data.startswith("admin_stats_"))
async def admin_stats_callback(callback: CallbackQuery):
    """Кнопка подробной статистики"""
    try:
        target_user_id = int(callback.data.split("_")[2])
        # Получаем статистику карточек
        card_stats = get_user_card_stats(target_user_id)
        user_coins = get_user_coins(target_user_id)
        
        if card_stats:
            stats_text = (
                f"📊 <b>ПОДРОБНАЯ СТАТИСТИКА</b>\n\n"
                f"<b>МамоКоины:</b> {user_coins}\n"
                f"<b>Всего карточек:</b> {card_stats['user_cards']}/{card_stats['total_cards']}\n"
                f"<b>Завершено:</b> {card_stats['completion_percentage']}%\n\n"
            )
            
            if card_stats['rarity_stats']:
                stats_text += "<b>Карточки по редкостям:</b>\n"
                for rarity, count in card_stats['rarity_stats'].items():
                    display_rarity = 'Эпический' if rarity == 'эпическая' else rarity
                    stats_text += f"• {display_rarity}: {count}\n"
            
            await callback.message.answer(stats_text, parse_mode="html")
            await callback.answer()
        else:
            await callback.answer("Нет статистики", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка в admin_stats_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)



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

@router_admins.message(Command("checkuser"))
@require_role("младший-администратор")
@log_admin_action("Проверка пользователя")
async def checkuser_command(message: Message):
    """Показать ВСЮ информацию о пользователе"""
    command_text = message.text.strip()
    args = command_text.split()
    
    if len(args) < 2:
        await message.reply(
            "🔍 <b>ПОЛНАЯ ПРОВЕРКА ПОЛЬЗОВАТЕЛЯ</b>\n\n"
            "<code>/checkuser [id_пользователя]</code>\n\n"
            "<b>Примеры:</b>\n"
            "• <code>/checkuser 123456789</code>\n"
            "• <code>/checkuser 987654321</code>\n\n"
            "<b>Что показывает:</b>\n"
            "1. Основную информацию\n"
            "2. Все карточки в коллекции\n"
            "3. Коины и статистику\n"
            "4. Историю покупок\n"
            "5. Анкету (если есть)\n"
            "6. Статус бана/мута\n\n"
            "<i>Команда доступна администраторам</i>",
            parse_mode="html"
        )
        return
    
    try:
        target_user_id = int(args[1])
        
        # Получаем базовую информацию о пользователе
        user_info = get_user_info(target_user_id)
        
        if not user_info:
            await message.reply(
                f"❌ <b>Пользователь не найден!</b>\n\n"
                f"Пользователь с ID <code>{target_user_id}</code> не зарегистрирован в системе.\n\n"
                f"<i>Пользователь должен сначала выполнить /start в боте</i>",
                parse_mode="html"
            )
            return
        
        user_display = f"@{user_info['username']}" if user_info['username'] else user_info['first_name'] or f"ID: {target_user_id}"
        user_type = user_info['user_type']
        
        # Получаем коины пользователя
        user_coins = get_user_coins(target_user_id)
        
        # Получаем ВСЕ карточки пользователя
        user_cards = get_user_cards(target_user_id)
        
        # Получаем историю покупок
        purchase_history = get_purchase_history(target_user_id, limit=50)  # Увеличиваем лимит
        
        # Получаем статистику коллекции
        card_stats = get_user_card_stats(target_user_id)
        
        # Получаем информацию о бане/муте (если есть)
        ban_info = get_ban_info(target_user_id)
        mute_info = get_mute_info(target_user_id)
        
        # Получаем анкету пользователя (игрока или владельца)
        profile_info = None
        profile_type = None
        
        if user_type == 'player':
            # Ищем анкету игрока
            result = db_operation(
                """SELECT nickname, player_position, experience, clubs_played_before, user_contact, created_at 
                   FROM users_search_club 
                   WHERE player_id = ?""",
                (target_user_id,),
                fetch=True
            )
            if result:
                nickname, position, experience, clubs, contact, created_at = result[0]
                profile_info = {
                    'type': 'player',
                    'nickname': nickname or 'Не указан',
                    'position': position or 'Не указана',
                    'experience': experience or 'Не указан',
                    'clubs': clubs or 'Не указаны',
                    'contact': contact or 'Не указан',
                    'created_at': created_at or 'Не указана'
                }
                profile_type = 'player'
                
        elif user_type == 'owner':
            # Ищем анкету владельца
            result = db_operation(
                """SELECT club_name, needed_positions, owner_comment, user_contact, created_at 
                   FROM owners_search_players 
                   WHERE owner_id = ?""",
                (target_user_id,),
                fetch=True
            )
            if result:
                club_name, positions, comment, contact, created_at = result[0]
                profile_info = {
                    'type': 'owner',
                    'club_name': club_name or 'Не указан',
                    'needed_positions': positions or 'Не указаны',
                    'comment': comment or 'Не указан',
                    'contact': contact or 'Не указан',
                    'created_at': created_at or 'Не указана'
                }
                profile_type = 'owner'
        
        # Получаем дату регистрации пользователя
        reg_info = db_operation(
            "SELECT created_at FROM all_users WHERE id = ?",
            (target_user_id,),
            fetch=True
        )
        registration_date = reg_info[0][0] if reg_info else "Неизвестно"
        
        # Начинаем формировать сообщение
        messages = []  # Будем хранить части сообщения
        
        # Часть 1: Основная информация
        part1 = (
            f"👤 <b>ПОЛНАЯ ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ</b>\n\n"
            f"<b>Основная информация:</b>\n"
            f"• <b>Имя:</b> {user_display}\n"
            f"• <b>ID:</b> <code>{target_user_id}</code>\n"
            f"• <b>Тип:</b> {user_type}\n"
            f"• <b>МамоКоины:</b> {user_coins}\n"
            f"• <b>Дата регистрации:</b> {registration_date[:16] if registration_date != 'Неизвестно' else 'Неизвестно'}\n"
        )
        
        # Добавляем информацию о бане/муте
        if ban_info:
            banned_at = format_moscow_time(ban_info['banned_at']) if ban_info['banned_at'] else "Не указана"
            part1 += f"• <b>🚫 Статус:</b> ЗАБАНЕН\n"
            part1 += f"• <b>Причина бана:</b> {ban_info['ban_reason']}\n"
            part1 += f"• <b>Дата бана:</b> {banned_at}\n"
        
        if mute_info:
            unmute_time = format_moscow_time(mute_info['unmute_time']) if mute_info['unmute_time'] else "Не указано"
            part1 += f"• <b>🔇 Статус:</b> В МУТЕ (до {unmute_time})\n"
            part1 += f"• <b>Причина мута:</b> {mute_info.get('mute_reason', 'Не указана')}\n"
        
        messages.append(part1)
        
        # Часть 2: Статистика коллекции
        # Внутри checkuser_command, где показывается статистика коллекции:
        if card_stats:
            part2 = f"\n<b>📊 СТАТИСТИКА КОЛЛЕКЦИИ:</b>\n"
            part2 += f"• <b>Всего карточек:</b> {card_stats['user_cards']}/{card_stats['total_cards']}\n"
            part2 += f"• <b>Завершено:</b> {card_stats['completion_percentage']}%\n"
    
    # Статистика по редкостям - теперь проверяем, что есть данные
        if card_stats['rarity_stats'] and isinstance(card_stats['rarity_stats'], dict):
            part2 += f"• <b>По редкостям:</b>\n"
            rarity_icons = {
                'Редкий': '🟢',
                'Эпический': '🟣', 
                'Легендарный': '🟡',
                'Суперлегендарный': '🔴'
            }
            
            # Отсортируем редкости в нужном порядке
            rarity_order = ['EEA', 'Суперлегендарный', 'Легендарный', 'Эпический', 'Редкий']
            
            for rarity in rarity_order:
                if rarity in card_stats['rarity_stats']:
                    count = card_stats['rarity_stats'][rarity]
                    icon = rarity_icons.get(rarity, '⚪')
                    part2 += f"  {icon} {rarity}: {count}\n"
        else:
            part2 += f"• <b>По редкостям:</b> <i>данные отсутствуют</i>\n"
        
        messages.append(part2)
        
        # Часть 3: ВСЕ карточки пользователя
        if user_cards:
            # Группируем карточки по редкости для лучшего отображения
            cards_by_rarity = {}
            for card in user_cards:
                nickname, club, position, rarity, received_at = card
                if rarity == 'эпическая':
                    rarity = 'Эпический'
                
                if rarity not in cards_by_rarity:
                    cards_by_rarity[rarity] = []
                cards_by_rarity[rarity].append((nickname, club, position, received_at))
            
            part3 = f"\n<b>🃏 ВСЕ КАРТОЧКИ ({len(user_cards)} шт.):</b>\n"
            
            # Порядок отображения редкостей
            rarity_order = ['EEA', 'Суперлегендарный', 'Легендарный', 'Эпический', 'Редкий']
            rarity_icons = {
                'Редкий': '🟢',
                'Эпический': '🟣',
                'Легендарный': '🟡',
                'Суперлегендарный': '🔴'
            }
            
            total_shown = 0
            max_cards_to_show = 50  # Максимум карточек в одном сообщении
            
            for rarity in rarity_order:
                if rarity in cards_by_rarity and cards_by_rarity[rarity]:
                    icon = rarity_icons.get(rarity, '⚪')
                    part3 += f"\n{icon} <b>{rarity}</b> ({len(cards_by_rarity[rarity])}):\n"
                    
                    for idx, (nickname, club, position, received_at) in enumerate(cards_by_rarity[rarity], 1):
                        if total_shown < max_cards_to_show:
                            part3 += f"  {idx}. <b>{nickname}</b> - {position} ({club})\n"
                            total_shown += 1
                        else:
                            remaining = len(user_cards) - max_cards_to_show
                            part3 += f"\n<i>... и еще {remaining} карточек</i>\n"
                            break
                    if total_shown >= max_cards_to_show:
                        break
            
            messages.append(part3)
        
        # Часть 4: История покупок
        if purchase_history:
            total_spent = sum(purchase['price'] for purchase in purchase_history)
            part4 = f"\n<b>🛒 ИСТОРИЯ ПОКУПОК ({len(purchase_history)}):</b>\n"
            part4 += f"• <b>Всего потрачено:</b> {total_spent} коинов\n\n"
            
            # Показываем последние 10 покупок
            for i, purchase in enumerate(purchase_history[:10], 1):
                rarity_display = 'Эпический' if purchase['rarity'] == 'эпическая' else purchase['rarity']
                part4 += (
                    f"{i}. <b>{purchase['nickname']}</b>\n"
                    f"   💰 {purchase['price']} коинов | 💎 {rarity_display}\n"
                    f"   📅 {purchase['purchased_at'][:16]}\n"
                )
                if i < min(10, len(purchase_history)):
                    part4 += "   ─────────────\n"
            
            if len(purchase_history) > 10:
                part4 += f"\n<i>... и еще {len(purchase_history) - 10} покупок</i>\n"
            
            messages.append(part4)
        else:
            messages.append(f"\n<b>🛒 ИСТОРИЯ ПОКУПОК:</b>\n<i>Пользователь еще ничего не покупал</i>\n")
        
        # Часть 5: Анкета пользователя
        if profile_info:
            part5 = f"\n<b>📝 АНКЕТА ПОЛЬЗОВАТЕЛЯ ({'Игрок' if profile_type == 'player' else 'Владелец клуба'}):</b>\n"
            
            if profile_type == 'player':
                part5 += (
                    f"• <b>Никнейм:</b> {profile_info['nickname']}\n"
                    f"• <b>Позиция:</b> {profile_info['position']}\n"
                    f"• <b>Опыт:</b> {profile_info['experience']}\n"
                    f"• <b>Предыдущие клубы:</b> {profile_info['clubs']}\n"
                    f"• <b>Контакт:</b> {profile_info['contact']}\n"
                    f"• <b>Дата создания:</b> {profile_info['created_at'][:16]}\n"
                )
            else:  # owner
                part5 += (
                    f"• <b>Название клуба:</b> {profile_info['club_name']}\n"
                    f"• <b>Нужные позиции:</b> {profile_info['needed_positions']}\n"
                    f"• <b>Комментарий:</b> {profile_info['comment']}\n"
                    f"• <b>Контакт:</b> {profile_info['contact']}\n"
                    f"• <b>Дата создания:</b> {profile_info['created_at'][:16]}\n"
                )
            
            messages.append(part5)
        else:
            messages.append(f"\n<b>📝 АНКЕТА:</b>\n<i>Пользователь не заполнял анкету</i>\n")
        
        # Отправляем сообщения частями (если слишком длинные)
        for i, msg_part in enumerate(messages):
            try:
                if i == 0:
                    # Первое сообщение с кнопками
                    builder = InlineKeyboardBuilder()
                    builder.row(
                        InlineKeyboardButton(
                            text="💰 Изменить МамоКоины",
                            callback_data=f"admin_addcoins_{target_user_id}"
                        ),
                        InlineKeyboardButton(
                            text="🃏 Добавить карточку",
                            callback_data=f"admin_addcard_{target_user_id}"
                        )
                    )
                    builder.row(
                        InlineKeyboardButton(
                            text="📊 Подробная статистика",
                            callback_data=f"admin_stats_{target_user_id}"
                        )
                    )
                    
                    await message.reply(
                        msg_part,
                        parse_mode="html",
                        reply_markup=builder.as_markup()
                    )
                else:
                    # Последующие сообщения без кнопок
                    await message.answer(msg_part, parse_mode="html")
                
                # Пауза между сообщениями
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Ошибка при отправке части сообщения {i}: {e}")
                continue
        
        # Логируем запрос
        logger.info(f"👑 Админ {message.from_user.id} запросил полную информацию о пользователе {target_user_id}")
        
    except ValueError:
        await message.reply(
            "❌ <b>Неверный формат!</b>\n\n"
            "ID пользователя должен быть числом.\n"
            "Пример: <code>/checkuser 123456789</code>",
            parse_mode="html"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка в команде /checkuser: {e}")
        await message.reply(
            f"❌ Произошла ошибка при получении информации: {str(e)[:100]}",
            parse_mode="html"
        )

@router_admins.message(Command("addcoins"))
@require_role("старший-администратор")
@log_admin_action("Добавление коинов пользователю")
async def addcoins_command(message: Message):
    """Добавить коины пользователю"""
    command_text = message.text.strip()
    args = command_text.split()
    
    if len(args) < 3:
        await message.reply(
            "💰 <b>ИСПОЛЬЗОВАНИЕ КОМАНДЫ:</b>\n\n"
            "<code>/addcoins [id_пользователя] [количество] (комментарий)</code>\n\n"
            "<b>Примеры:</b>\n"
            "• <code>/addcoins 123456789 10 Бонус за активность</code>\n"
            "• <code>/addcoins 987654321 50 Выигрыш в конкурсе</code>\n"
            "• <code>/addcoins 555555555 -20 Штраф за нарушение</code>\n"
            "• <code>/addcoins 111111111 100 Административный бонус</code>\n\n"
            "<b>Примечания:</b>\n"
            "1. ID пользователя можно узнать через /users или /getid\n"
            "2. Количество может быть отрицательным для вычитания коинов\n"
            "3. Комментарий необязателен (макс 200 символов)\n"
            "4. Минимальный баланс пользователя: 0 коинов\n\n"
            "<i>Команда доступна только старшим администраторам</i>",
            parse_mode="html"
        )
        return
    
    try:
        target_user_id = int(args[1])
        coins_amount = int(args[2])
        comment = " ".join(args[3:]) if len(args) > 3 else "Административное изменение"
        
        # Проверка на максимальную длину комментария
        if len(comment) > 200:
            comment = comment[:197] + "..."
        
        # Проверяем существование пользователя
        user_info = get_user_info(target_user_id)
        if not user_info:
            await message.reply(
                f"❌ <b>Пользователь не найден!</b>\n\n"
                f"Пользователь с ID <code>{target_user_id}</code> не зарегистрирован в системе.\n\n"
                f"<i>Пользователь должен сначала выполнить /start в боте</i>",
                parse_mode="html"
            )
            return
        
        user_display = f"@{user_info['username']}" if user_info['username'] else user_info['first_name'] or f"ID: {target_user_id}"
        
        # Получаем текущие коины пользователя
        current_coins = get_user_coins(target_user_id)
        
        # Вычисляем новые коины
        new_coins = current_coins + coins_amount
        
        # Проверяем, чтобы баланс не стал отрицательным
        if new_coins < 0:
            await message.reply(
                f"❌ <b>Невозможно выполнить операцию!</b>\n\n"
                f"<b>Пользователь:</b> {user_display}\n"
                f"<b>Текущие МамоКоины:</b> {current_coins}\n"
                f"<b>Попытка изменить на:</b> {coins_amount}\n"
                f"<b>Результат:</b> {new_coins} (не может быть меньше 0)\n\n"
                f"<i>Максимально можно вычесть: {current_coins} коинов</i>",
                parse_mode="html"
            )
            return
        
        # Обновляем коины
        success = update_user_coins(target_user_id, new_coins)
        
        if not success:
            await message.reply(
                f"❌ <b>Ошибка при обновлении коинов!</b>\n\n"
                f"Не удалось обновить баланс пользователя.\n"
                f"<i>Проверьте логи для подробностей</i>",
                parse_mode="html"
            )
            return
        
        # Форматируем сообщение об успехе
        operation_type = "добавлено" if coins_amount > 0 else "вычтено" if coins_amount < 0 else "изменено"
        amount_abs = abs(coins_amount)
        operation_icon = "➕" if coins_amount > 0 else "➖" if coins_amount < 0 else "🔄"
        
        # Получаем информацию о карточках пользователя для статистики
        card_stats = get_user_card_stats(target_user_id)
        purchase_history = get_purchase_history(target_user_id, limit=5)
        total_spent = sum(purchase['price'] for purchase in purchase_history) if purchase_history else 0
        
        success_message = (
            f"{operation_icon} <b>БАЛАНС ОБНОВЛЕН!</b>\n\n"
            f"<b>👤 Пользователь:</b> {user_display}\n"
            f"<b>🆔 ID:</b> <code>{target_user_id}</code>\n"
            f"<b>🎮 Тип:</b> {user_info['user_type']}\n\n"
            f"<b>💰 Было коинов:</b> {current_coins}\n"
            f"<b>{operation_icon} {operation_type.capitalize()}:</b> {amount_abs} коинов\n"
            f"<b>💰 Стало коинов:</b> {new_coins}\n\n"
            f"<b>📊 Дополнительная статистика:</b>\n"
            f"• <b>Всего карточек:</b> {card_stats['user_cards'] if card_stats else 0}\n"
            f"• <b>Потрачено на покупки:</b> {total_spent} коинов\n"
            f"• <b>Последние покупки:</b> {len(purchase_history)}\n\n"
            f"<b>📝 Комментарий:</b> {comment}\n\n"
            f"<b>👑 Операция выполнена:</b> @{message.from_user.username or message.from_user.first_name}\n"
            f"<b>⏰ Время:</b> {datetime.now().strftime('%H:%M %d.%m.%Y')}"
        )
        
        # Создаем inline-клавиатуру с действиями
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="🔍 Проверить пользователя",
                callback_data=f"checkuser_{target_user_id}"
            ),
            InlineKeyboardButton(
                text="💰 Добавить еще",
                callback_data=f"quick_addcoins_{target_user_id}"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="📊 Статистика",
                callback_data=f"coins_stats_{target_user_id}"
            )
        )
        
        await message.reply(success_message, parse_mode="html", reply_markup=builder.as_markup())
        
        # Логируем операцию
        logger.warning(
            f"👑 Админ {message.from_user.id} {operation_type} {amount_abs} коинов пользователю {target_user_id} "
            f"({user_display}). Было: {current_coins}, Стало: {new_coins}. Комментарий: {comment}"
        )
        
        # Отправляем уведомление пользователю (если возможно)
        try:
            user_notification = (
                f"{operation_icon} <b>ВАШ БАЛАНС ИЗМЕНЕН</b>\n\n"
                f"Администратором Вам {operation_type}  <b>{amount_abs} коинов</b>.\n\n"
                f"<b>📊 Статистика:</b>\n"
                f"• <b>Было:</b> {current_coins} коинов\n"
                f"• <b>Стало:</b> {new_coins} коинов\n"
                f"• <b>Изменение:</b> {coins_amount} коинов\n\n"
                f"<b>📝 Причина:</b> {comment}\n\n"
                f"<i>Используйте /trade для просмотра доступных карточек</i>"
            )
            
            await message.bot.send_message(
                chat_id=target_user_id,
                text=user_notification,
                parse_mode="html"
            )
            
            # Добавляем запись в историю операций с коинами
            try:
                db_operation(
                    """INSERT INTO coin_history (user_id, admin_id, amount, comment, new_balance) 
                       VALUES (?, ?, ?, ?, ?)""",
                    (target_user_id, message.from_user.id, coins_amount, comment, new_coins)
                )
            except Exception as history_error:
                # Если таблицы нет или ошибка, просто логируем
                logger.warning(f"Не удалось записать в историю коинов: {history_error}")
                
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление пользователю {target_user_id}: {e}")
        
    except ValueError:
        await message.reply(
            "❌ <b>Неверный формат параметров!</b>\n\n"
            "ID пользователя и количество коинов должны быть числами.\n"
            "Пример: <code>/addcoins 123456789 50 Бонус</code>\n\n"
            "<i>Для вычитания используйте отрицательное число: /addcoins 123456789 -20 Штраф</i>",
            parse_mode="html"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка в команде /addcoins: {e}")
        await message.reply(
            f"❌ Произошла ошибка: {str(e)[:100]}",
            parse_mode="html"
        )

@router_admins.callback_query(F.data.startswith("admin_addcoins_"))
async def admin_addcoins_callback(callback: CallbackQuery):
    """Кнопка изменения коинов"""
    try:
        target_user_id = int(callback.data.split("_")[2])
        await callback.answer(f"Используйте /addcoins {target_user_id} [количество] [комментарий]")
    except:
        await callback.answer("❌ Ошибка", show_alert=True)

@router_admins.callback_query(F.data.startswith("admin_addcard_"))
async def admin_addcard_callback(callback: CallbackQuery):
    """Кнопка добавления карточки"""
    try:
        target_user_id = int(callback.data.split("_")[2])
        await callback.answer(f"Используйте /addcard [ник_игрока] {target_user_id}")
    except:
        await callback.answer("❌ Ошибка", show_alert=True)

@router_admins.callback_query(F.data.startswith("admin_stats_"))
async def admin_stats_callback(callback: CallbackQuery):
    """Кнопка подробной статистики"""
    try:
        target_user_id = int(callback.data.split("_")[2])
        # Получаем статистику карточек
        card_stats = get_user_card_stats(target_user_id)
        user_coins = get_user_coins(target_user_id)
        
        if card_stats:
            stats_text = (
                f"📊 <b>ПОДРОБНАЯ СТАТИСТИКА</b>\n\n"
                f"<b>МамоКоины:</b> {user_coins}\n"
                f"<b>Всего карточек:</b> {card_stats['user_cards']}/{card_stats['total_cards']}\n"
                f"<b>Завершено:</b> {card_stats['completion_percentage']}%\n\n"
            )
            
            if card_stats['rarity_stats']:
                stats_text += "<b>Карточки по редкостям:</b>\n"
                for rarity, count in card_stats['rarity_stats'].items():
                    display_rarity = 'Эпический' if rarity == 'эпическая' else rarity
                    stats_text += f"• {display_rarity}: {count}\n"
            
            await callback.message.answer(stats_text, parse_mode="html")
            await callback.answer()
        else:
            await callback.answer("Нет статистики", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка в admin_stats_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)
@router_admins.message(Command("ap"))
@log_command
@require_role("модератор")
async def admin_panel_command(message: Message):
    """Панель администратора со списком команд"""
    user_role = get_admin_role(message.from_user.id)
    
    # Определяем доступные команды в зависимости от роли
    commands = {
        "старший-администратор": [
            "👥 /all_users - выводит БД со всеми людьми, запустившими бота",
            "📄 /all_ankets - выводит все анкеты игроков и владельцев",
            "🗑️ /deleteanket - удаляет анкеты пользователя по ID",
            "📢 /rassilka - рассылка всем пользователям",
            "⛔ /ban - бан пользователя",
            "✅ /unban - разбан пользователя",
            "👨‍💼 /admins - список всех администраторов",
            "👑 /addadmin - добавить нового администратора",
            "🗑️ /deladmin - удалить администратора по ID",
            "📡 /test_broadcast - принудительный запуск рассылки",
            "🔄 /reset [id] - сброс колдауна для ФМАМОКАРТЫ юзеру с ID",
            "🔄 /reload_cards - сброс колдауна для всех игроков",
            "➕ /addcard [ник_игрока] [id_пользователя] - добавить карточку пользователю",
            "➖ /deletecard [ник_игрока] [id_пользователя] - удалить карточку у пользователя",
            "🎁 /giveallcards [id_пользователя] - выдать все карточки пользователю",
            "🗑️ /deleteallcards [id_пользователя] - удалить все карточки у пользователя ",
            "➕ /addsellcard - добавление АДМИНСКИХ карточки на продажу",
            "➖ /dellsellcard - удаление АДМИНСКИХ карточек с продажи",
            "➕ /addcoins - добавляет мамокоины игроку",
            "📃 /update_catalog - обновление каталогов с игроками",
            "📢 /remove_all_sales - удаление всех продаж",
            "➖ /remove_user_sale [id] - удаление пользовательской карточки с продажи",
            "🔄 /resetelo [id] - очистка эло",
            "📡 /setelo [id] [num] - установить кол-во эло",
            "➕ /addelo [id] [num] - добавить кол-во эло",
            "🔊 /viewelo [id] - посмотреть эло юзера + статистика",
            "➖ /resethistory [id] - удалить историю матчей юзера",
            "⏱️ /clean_logs - удаление логов старше 7 дней",
        ],
        # ... остальные роли без изменений
        "младший-администратор": [
            "🔇 /muteplayer - запрет игроку писать репорты",
            "🔊 /unmuteplayer - снятие запрета",
            "⏱️ /scheduler_status - статус ежедневных рассылок",
            "🃏 /getcard - посмотреть карту любого игрока",
            "📚 /allcards - посмотреть все карты",
            "✅ /checkuser - просмотр полной информации о пользователе",
            "📢 /addpromo - добавить промокод",
            "➖ /deletepromo - удалить промокод",
            "📋 /allpromocodes - просмотр всех активных промокодов",

        ],
        "помощник-администратора": [
            "✉️ /writeto - отправление сообщения пользователю",
            "🔍 /checkmute - проверка мутов",
            "📋 /mutedlist - список всех замученных пользователей",
            "📃 /banlist - список банов",
            "🗑️ /sellhistory - просмотр истории продаж карточек",
            "📃 /sell_monitor - монитор продаж (для дебуга)",
            "👨‍💼 /viewsellcards - просмотр карточек , выставленных на продажу",
            "📃 /leaderboard_stats - подробная статистика для админов",
        ],
        "модератор": [
            "📜 /ap - все доступные команды"
        ]
    }
    
    # Формируем список доступных команд
    available_commands = []
    for role, min_level in ROLE_LEVELS.items():
        if ROLE_LEVELS[user_role] >= min_level:
            available_commands.extend(commands.get(role, []))
    
    # Убираем дубликаты
    available_commands = list(dict.fromkeys(available_commands))
    
    response = (
        f"🔺 <b>Панель администратора</b>\n\n"
        f"👤 <b>Пользователь:</b> {message.from_user.username or message.from_user.id}\n"
        f"👑 <b>Роль:</b> {user_role}\n\n"
        f"📖 <b>Доступные команды:</b>\n\n"
    )
    
    for cmd in available_commands:
        response += f"{cmd}\n"

    await message.reply("🔺<b>Вы успешно вошли в систему администрирования.</b>",parse_mode="html")
    print(f"Пользователь @{message.from_user.username} | ID: {message.from_user.id} вошел в систему администрирования.")
    await asyncio.sleep(2)
    await message.reply(response, parse_mode="HTML")




@router_admins.message(Command("addadmin"))
@require_role("старший-администратор")
async def addadmin_command(message: Message, state: FSMContext):
    """Добавление нового администратора"""
    await message.reply(
        "👑 <b>Добавление администратора</b>\n\n"
        "Отправьте сообщение в формате:\n"
        "<code>ID, username, роль</code>\n\n"
        "Пример: <code>123456789, username, модератор</code>\n\n"
        "<b>Доступные роли:</b>\n"
        "• модератор\n"
        "• помощник-администратора\n"
        "• младший-администратор\n"
        "• старший-администратор",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.wait_for_add)

@router_admins.message(AdminStates.wait_for_add)
@require_role("старший-администратор")
async def process_add_admin(message: Message, state: FSMContext):
    """Обработка добавления администратора"""
    try:
        parts = message.text.lower().split(",")
        if len(parts) != 3:
            await message.reply(
                "❌ Неверный формат данных!\n"
                "Используйте: ID, username, роль\n"
                "Пример: 123456789, user123, модератор"
            )
            await state.clear()
            return
        
        addID = int(parts[0].strip())
        username = parts[1].strip()
        role = parts[2].strip()
        
        # Проверяем, что роль валидна
        if role not in ROLE_LEVELS:
            await message.reply(
                f"❌ Неверная роль!\n"
                f"Доступные роли: {', '.join(ROLE_LEVELS.keys())}"
            )
            await state.clear()
            return
        
        # Проверяем, не пытаемся ли изменить изначального администратора
        if addID == DEFAULT_SENIOR_ADMIN_ID:
            await message.reply("❌ Нельзя изменять данные изначального администратора!")
            await state.clear()
            return
        
        # SQL запрос для добавления администратора
        db_operation(
            "INSERT OR REPLACE INTO admins (id, username, role) VALUES (?, ?, ?)",
            (addID, username if username != "none" else None, role)
        )
        
        # Логируем действие
        logger.info(
            f"👑 АДМИН: {message.from_user.id} добавил нового администратора: "
            f"ID={addID}, username=@{username}, role={role}"
        )
        
        await message.reply(
            f"✅ <b>Администратор успешно добавлен!</b>\n\n"
            f"🆔 ID: <code>{addID}</code>\n"
            f"📛 Username: @{username if username != 'none' else 'нет'}\n"
            f"👑 Роль: {role}",
            parse_mode="HTML"
        )
        
    except ValueError:
        await message.reply(
            "❌ Неверный формат ID!\n"
            "ID должен быть числом."
        )
    except Exception as e:
        logger.error(f"Ошибка при добавлении администратора: {e}")
        await message.reply(f"❌ Ошибка: {str(e)[:100]}")
    finally:
        await state.clear()




@router_admins.message(Command("deladmin"))
@require_role("старший-администратор")
async def deladmin_command(message: Message):
    """Удаление администратора по ID"""
    args = message.text.split()
    
    if len(args) < 2:
        await message.reply(
            "❌ Использование: /deladmin [ID_администратора]\n\n"
            "Пример: /deladmin 123456789\n\n"
            "<b>Внимание:</b>\n"
            "• Нельзя удалить изначального администратора (системного)\n"
            "• Эта команда удаляет администратора из таблицы admins",
            parse_mode="HTML"
        )
        return
    
    try:
        admin_id_to_delete = int(args[1])
        
        # Проверяем, не пытаемся ли удалить системного администратора
        if admin_id_to_delete == DEFAULT_SENIOR_ADMIN_ID:
            await message.reply(
                "❌ <b>Нельзя удалить изначального администратора!</b>\n\n"
                "Этот администратор является системным и защищен от удаления.",
                parse_mode="HTML"
            )
            return
        
        # Проверяем, существует ли такой администратор
        admin_exists = db_operation(
            "SELECT username, role FROM admins WHERE id = ?",
            (admin_id_to_delete,),
            fetch=True
        )
        
        if not admin_exists:
            await message.reply(
                f"❌ Администратор с ID <code>{admin_id_to_delete}</code> не найден в базе данных.",
                parse_mode="HTML"
            )
            return
        
        username = admin_exists[0][0] or "нет username"
        role = admin_exists[0][1]
        
        # Запрашиваем подтверждение
        confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"delete_admin:{admin_id_to_delete}")],
            [InlineKeyboardButton(text="❌ Нет, отменить", callback_data="cancel_delete_admin")]
        ])
        
        await message.reply(
            f"⚠️ <b>Удаление администратора</b>\n\n"
            f"👑 Роль: {role}\n"
            f"📛 Username: @{username}\n"
            f"🆔 ID: <code>{admin_id_to_delete}</code>\n\n"
            f"<b>Вы уверены, что хотите удалить этого администратора?</b>\n\n"
            f"После удаления он потеряет все права доступа.",
            parse_mode="HTML",
            reply_markup=confirm_keyboard
        )
        
    except ValueError:
        await message.reply("❌ Неверный формат ID. ID должен быть числом.")
    except Exception as e:
        logger.error(f"Ошибка при выполнении команды /deladmin: {e}")
        await message.reply(f"❌ Ошибка: {str(e)[:100]}")


@router_admins.message(Command("all_users_count"))
@log_command
async def all_users_count_command(message: Message):
    """Показывает количество зарегистрированных пользователей"""
    try:
        # Получаем количество пользователей из базы данных
        result = db_operation("SELECT COUNT(*) FROM all_users", fetch=True)
        
        if result:
            count = result[0][0]
            
            # Получаем дополнительную статистику
            active_users = db_operation(
                "SELECT COUNT(DISTINCT user_id) FROM user_coins", 
                fetch=True
            )
            active_count = active_users[0][0] if active_users else 0
            
            # Получаем количество пользователей с карточками
            users_with_cards = db_operation(
                "SELECT COUNT(DISTINCT user_id) FROM user_cards", 
                fetch=True
            )
            cards_count = users_with_cards[0][0] if users_with_cards else 0
            
            # Получаем количество анкет
            player_profiles = db_operation(
                "SELECT COUNT(*) FROM users_search_club", 
                fetch=True
            )
            player_count = player_profiles[0][0] if player_profiles else 0
            
            owner_profiles = db_operation(
                "SELECT COUNT(*) FROM owners_search_players", 
                fetch=True
            )
            owner_count = owner_profiles[0][0] if owner_profiles else 0
            
            # Формируем ответ
            response_text = (
                f"📊 <b>СТАТИСТИКА ПОЛЬЗОВАТЕЛЕЙ</b>\n\n"
                f"👥 <b>Всего зарегистрировано:</b> {count}\n"
                f"💰 <b>Активные (с балансом):</b> {active_count}\n"
                f"🃏 <b>Имеют карточки:</b> {cards_count}\n\n"
                f"📝 <b>Анкеты:</b>\n"
                f"   👤 <b>Игроков (ищут клуб):</b> {player_count}\n"
                f"   👑 <b>Овнеров (ищут игроков):</b> {owner_count}\n\n"
                f"<i>Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}</i>"
            )
            
            await message.reply(response_text, parse_mode="html")
        else:
            await message.reply("❌ Не удалось получить статистику пользователей")
            
    except Exception as e:
        logger.error(f"Ошибка в команде all_users_count: {e}")
        await message.reply("❌ Произошла ошибка при получении статистики")

@router_admins.callback_query(F.data.startswith("delete_admin:"))
async def confirm_delete_admin(callback: CallbackQuery):
    """Подтверждение удаления администратора"""
    try:
        admin_id_to_delete = int(callback.data.split(":")[1])
        admin_remover_id = callback.from_user.id
        
        # Проверяем, не пытаемся ли удалить системного администратора (дополнительная проверка)
        if admin_id_to_delete == DEFAULT_SENIOR_ADMIN_ID:
            await callback.message.edit_text(
                "❌ <b>Нельзя удалить изначального администратора!</b>",
                parse_mode="HTML"
            )
            await callback.answer("Запрещено удалять системного администратора!", show_alert=True)
            return
        
        # Получаем информацию об удаляемом администраторе для логирования
        admin_info = db_operation(
            "SELECT username, role FROM admins WHERE id = ?",
            (admin_id_to_delete,),
            fetch=True
        )
        
        if not admin_info:
            await callback.message.edit_text(
                f"❌ Администратор с ID <code>{admin_id_to_delete}</code> уже был удален или не существует.",
                parse_mode="HTML"
            )
            await callback.answer("Администратор не найден", show_alert=True)
            return
        
        username = admin_info[0][0] or "нет username"
        role = admin_info[0][1]
        
        # Удаляем администратора из базы данных
        db_operation(
            "DELETE FROM admins WHERE id = ?",
            (admin_id_to_delete,)
        )
        
        # Формируем сообщение об успехе
        response = (
            f"✅ <b>Администратор успешно удален!</b>\n\n"
            f"👑 Роль: {role}\n"
            f"📛 Username: @{username}\n"
            f"🆔 ID: <code>{admin_id_to_delete}</code>\n\n"
            f"<i>Пользователь больше не имеет прав администратора.</i>"
        )
        
        # Логируем действие
        logger.warning(
            f"👑 АДМИН: Пользователь {admin_remover_id} удалил администратора: "
            f"ID={admin_id_to_delete}, username=@{username}, role={role}"
        )
        
        # Обновляем сообщение
        await callback.message.edit_text(response, parse_mode="HTML")
        await callback.answer("✅ Администратор удален", show_alert=False)
        
    except Exception as e:
        logger.error(f"Ошибка при удалении администратора: {e}")
        await callback.message.edit_text("❌ Ошибка при удалении администратора.")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

@router_admins.callback_query(F.data == "cancel_delete_admin")
async def cancel_delete_admin(callback: CallbackQuery):
    """Отмена удаления администратора"""
    await callback.message.edit_text("❌ Удаление администратора отменено.")
    await callback.answer("Удаление отменено", show_alert=False)

# ========================
# КОМАНДЫ АДМИНИСТРИРОВАНИЯ
# ========================

@router_admins.message(Command("admins"))
@require_role("старший-администратор")
@log_command
async def admins_command(message: Message):
    """Просмотр списка администраторов"""
    try:
        # Сначала получаем всех администраторов из базы данных
        admins_from_db = db_operation(
            """SELECT id, username, role 
               FROM admins 
               ORDER BY 
                   CASE role 
                       WHEN 'старший-администратор' THEN 1
                       WHEN 'младший-администратор' THEN 2
                       WHEN 'помощник-администратора' THEN 3
                       WHEN 'модератор' THEN 4
                       ELSE 5
                   END,
                   id""",
            fetch=True
        )
        
        # Создаем полный список, добавляя системного администратора в начало
        admins_list = []
        
        # Добавляем системного администратора первым
        admins_list.append((DEFAULT_SENIOR_ADMIN_ID, 'системный', 'старший-администратор'))
        
        # Добавляем остальных администраторов
        if admins_from_db:
            admins_list.extend(admins_from_db)
        
        if len(admins_list) == 1 and admins_list[0][0] == DEFAULT_SENIOR_ADMIN_ID:
            await message.reply("📭 В базе данных нет других администраторов.")
            return
        
        # Формируем сообщение со списком администраторов
        response = "👑 <b>Список администраторов:</b>\n\n"
        
        for i, (admin_id, username, role) in enumerate(admins_list, 1):
            # Определяем иконку в зависимости от роли
            icons = {
                'старший-администратор': "👑",
                'младший-администратор': "🛡️",
                'помощник-администратора': "🛠️",
                'модератор': "👤"
            }
            icon = icons.get(role, "👤")
            
            # Форматируем username
            if admin_id == DEFAULT_SENIOR_ADMIN_ID:
                username_display = "системный (неизменяемый)"
            else:
                username_display = f"@{username}" if username else "нет username"
            
            response += (
                f"{icon} <b>#{i}: {role}</b>\n"
                f"   🆔 ID: <code>{admin_id}</code>\n"
                f"   📛 Username: {username_display}\n"
                f"   ━━━━━━━━━━━━━━━━━━\n"
            )
        
        # Добавляем статистику
        total_admins = len(admins_list)
        senior_count = sum(1 for _, _, role in admins_list if role == 'старший-администратор')
        junior_count = sum(1 for _, _, role in admins_list if role == 'младший-администратор')
        assistant_count = sum(1 for _, _, role in admins_list if role == 'помощник-администратора')
        moderator_count = sum(1 for _, _, role in admins_list if role == 'модератор')
        
        response += (
            f"\n📊 <b>Статистика:</b>\n"
            f"👑 Старших администраторов: {senior_count}\n"
            f"🛡️ Младших администраторов: {junior_count}\n"
            f"🛠️ Помощников администратора: {assistant_count}\n"
            f"👤 Модераторов: {moderator_count}\n"
            f"📈 Всего администраторов: {total_admins}"
        )
        
        await message.reply(response, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка при выполнении команды /admins: {e}")
        await message.reply(f"❌ Ошибка: {str(e)[:100]}")


# ========================
# СИСТЕМА БАНОВ
# ========================

def is_user_banned(user_id: int) -> bool:
    """Проверяет, забанен ли пользователь"""
    try:
        result = db_operation(
            "SELECT user_id FROM banned_users WHERE user_id = ?",
            (user_id,),
            fetch=True
        )
        return bool(result)
    except Exception as e:
        logger.error(f"Ошибка при проверке бана пользователя {user_id}: {e}")
        return False

def ban_user(user_id: int, banned_by_id: int, ban_reason: str) -> bool:
    """Добавляет пользователя в бан-лист"""
    try:
        # Проверяем, не забанен ли уже пользователь
        if is_user_banned(user_id):
            logger.warning(f"Пользователь {user_id} уже забанен")
            return False
        
        # Удаляем все данные пользователя из баз данных
        db_operation("DELETE FROM users_search_club WHERE player_id = ?", (user_id,))
        db_operation("DELETE FROM owners_search_players WHERE owner_id = ?", (user_id,))
        db_operation("DELETE FROM owner_likes WHERE owner_id = ?", (user_id,))
        db_operation("DELETE FROM owner_likes WHERE liked_player_id = ?", (user_id,))
        db_operation("DELETE FROM player_likes WHERE player_id = ?", (user_id,))
        db_operation("DELETE FROM player_likes WHERE liked_club_id = ?", (user_id,))
        
        # Добавляем в бан-лист
        db_operation(
            "INSERT INTO banned_users (user_id, banned_by_id, ban_reason) VALUES (?, ?, ?)",
            (user_id, banned_by_id, ban_reason)
        )
        
        logger.info(f"Пользователь {user_id} забанен. Причина: {ban_reason}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при бане пользователя {user_id}: {e}")
        return False

def unban_user(user_id: int) -> bool:
    """Удаляет пользователя из бан-листа"""
    try:
        if not is_user_banned(user_id):
            logger.warning(f"Пользователь {user_id} не забанен")
            return False
        
        db_operation("DELETE FROM banned_users WHERE user_id = ?", (user_id,))
        logger.info(f"Пользователь {user_id} разбанен")
        return True
    except Exception as e:
        logger.error(f"Ошибка при разбане пользователя {user_id}: {e}")
        return False

def get_ban_info(user_id: int):
    """Получает информацию о бане пользователя"""
    try:
        result = db_operation(
            "SELECT banned_by_id, ban_reason, banned_at FROM banned_users WHERE user_id = ?",
            (user_id,),
            fetch=True
        )
        if result:
            return {
                'banned_by_id': result[0][0],
                'ban_reason': result[0][1],
                'banned_at': result[0][2]
            }
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении информации о бане пользователя {user_id}: {e}")
        return None

@router_admins.message(Command("ban"))
@require_role("старший-администратор")
@log_command
async def ban_command(message: Message, state: FSMContext):
    """Начало процесса бана пользователя"""
    await message.reply(
        "⛔ <b>Вы используете команду BAN</b>\n\n"
        "Вы собираетесь полностью ограничить пользователя в использовании бота.\n\n"
        "Введите ID пользователя для бана:",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_ban_id1)

@router_admins.message(AdminStates.waiting_for_ban_id1)
@require_role("старший-администратор")
async def process_ban_user_id(message: Message, state: FSMContext):
    """Обработка ID пользователя для бана"""
    try:
        user_id = int(message.text.strip())
        
        # Проверяем, не пытаемся ли забанить администратора
        if get_admin_role(user_id) is not None:
            await message.reply("❌ Нельзя забанить администратора!")
            await state.clear()
            return
        
        # Проверяем, не забанен ли уже
        if is_user_banned(user_id):
            ban_info = get_ban_info(user_id)
            if ban_info:
                await message.reply(
                    f"⚠️ Пользователь {user_id} уже забанен.\n"
                    f"Причина: {ban_info['ban_reason']}\n"
                    f"Дата: {ban_info['banned_at']}"
                )
            else:
                await message.reply(f"⚠️ Пользователь {user_id} уже забанен.")
            await state.clear()
            return
        
        await state.update_data(ban_user_id=user_id)
        await message.reply(
            f"🆔 ID пользователя для бана: {user_id}\n\n"
            "Введите причину бана:"
        )
        await state.set_state(AdminStates.waiting_for_ban_id2)
        
    except ValueError:
        await message.reply("❌ Неверный формат ID. Введите число.")
        await state.clear()

@router_admins.message(AdminStates.waiting_for_ban_id2)
@require_role("старший-администратор")
async def process_ban_reason(message: Message, state: FSMContext):
    """Обработка причины бана и подтверждение"""
    ban_reason = message.text.strip()
    data = await state.get_data()
    user_id = data.get('ban_user_id')
    
    if not user_id:
        await message.reply("❌ Ошибка: ID пользователя не найден.")
        await state.clear()
        return
    
    # Запрашиваем подтверждение
    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Забанить", callback_data=f"ban_confirm:{user_id}:{ban_reason}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="ban_cancel")]
    ])
    
    await message.reply(
        f"⚠️ <b>Подтвердите бан пользователя</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"📝 Причина: {ban_reason}\n\n"
        f"<b>Это действие:</b>\n"
        f"• Удалит все данные пользователя\n"
        f"• Заблокирует доступ к боту\n"
        f"• Отправит уведомление пользователю",
        parse_mode="HTML",
        reply_markup=confirm_keyboard
    )
    await state.clear()

@router_admins.callback_query(F.data.startswith("ban_confirm:"))
async def confirm_ban(callback: CallbackQuery, bot: Bot):
    """Подтверждение бана"""
    try:
        parts = callback.data.split(":")
        user_id = int(parts[1])
        ban_reason = ":".join(parts[2:])
        admin_id = callback.from_user.id
        
        # Выполняем бан
        if ban_user(user_id, admin_id, ban_reason):
            # Отправляем сообщение забаненному пользователю
            try:
                await bot.send_message(
                    user_id,
                    f"🚫 <b>Вы забанены в боте</b>\n\n"
                    f"<b>Причина:</b> {ban_reason}\n\n"
                    f"<i>Для обжалования обратитесь в поддержку.</i>",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
            
            # Отправляем подтверждение администратору
            await callback.message.edit_text(
                f"✅ Пользователь {user_id} успешно забанен!\n\n"
                f"📝 Причина: {ban_reason}\n"
                f"👮‍♂️ Забанил: {admin_id}",
                parse_mode="HTML"
            )
            
            logger.warning(f"👑 АДМИН: Пользователь {admin_id} забанил пользователя {user_id}")
            
        else:
            await callback.message.edit_text(f"❌ Не удалось забанить пользователя {user_id}.")
        
    except Exception as e:
        logger.error(f"Ошибка при подтверждении бана: {e}")
        await callback.message.edit_text("❌ Ошибка при выполнении бана.")

@router_admins.callback_query(F.data == "ban_cancel")
async def cancel_ban(callback: CallbackQuery):
    """Отмена бана"""
    await callback.message.edit_text("❌ Бан отменен.")

@router_admins.message(Command("unban"))
@require_role("старший-администратор")
@log_command
async def unban_command(message: Message):
    """Разбан пользователя"""
    args = message.text.split()
    
    if len(args) < 2:
        await message.reply(
            "❌ Использование: /unban [ID_пользователя]\n\n"
            "Пример: /unban 123456789"
        )
        return
    
    try:
        user_id = int(args[1])
        
        # Проверяем, забанен ли пользователь
        if not is_user_banned(user_id):
            await message.reply(f"ℹ️ Пользователь {user_id} не забанен.")
            return
        
        # Выполняем разбан
        if unban_user(user_id):
            await message.reply(f"✅ Пользователь {user_id} успешно разбанен!")
            logger.warning(f"👑 АДМИН: {message.from_user.id} разбанил пользователя {user_id}")
        else:
            await message.reply(f"❌ Не удалось разбанить пользователя {user_id}.")
            
    except ValueError:
        await message.reply("❌ Неверный формат ID.")
    except Exception as e:
        logger.error(f"Ошибка при разбане: {e}")
        await message.reply(f"❌ Ошибка: {str(e)[:100]}")

@router_admins.message(Command("banlist"))
@require_role("помощник-администратора")
@log_command
async def banlist_command(message: Message):
    """Просмотр списка забаненных пользователей"""
    try:
        banned_users = db_operation(
            """SELECT bu.user_id, bu.ban_reason, bu.banned_at, 
                      au.username, au.first_name,
                      ab.username as banned_by_username
               FROM banned_users bu
               LEFT JOIN all_users au ON bu.user_id = au.id
               LEFT JOIN all_users ab ON bu.banned_by_id = ab.id
               ORDER BY bu.banned_at DESC""",
            fetch=True
        )
        
        if not banned_users:
            await message.reply("📭 Список забаненных пользователей пуст.")
            return
        
        response = "🚫 <b>Список забаненных пользователей:</b>\n\n"
        
        for i, (user_id, reason, banned_at, username, first_name, banned_by_username) in enumerate(banned_users, 1):
            user_display = f"@{username}" if username else f"{first_name or f'ID: {user_id}'}"
            banned_by_display = f"@{banned_by_username}" if banned_by_username else "Система"
            
            response += (
                f"🔹 <b>#{i}: {user_display}</b>\n"
                f"   🆔 ID: <code>{user_id}</code>\n"
                f"   📅 Забанен: {banned_at}\n"
                f"   👮‍♂️ Забанил: {banned_by_display}\n"
                f"   📝 Причина: {reason or 'Не указана'}\n"
                f"   ━━━━━━━━━━━━━━━━━━\n"
            )
        
        await message.reply(response, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка при получении списка забаненных: {e}")
        await message.reply(f"❌ Ошибка: {str(e)[:100]}")








def mute_user(user_id: int, admin_id: int, minutes: int, mute_reason: str = None) -> datetime:
    """Добавить мут пользователю в базе данных"""
    try:
        from datetime import datetime, timedelta
        
        # Вычисляем время размута
        now = datetime.now(pytz.UTC)
        unmute_time = now + timedelta(minutes=minutes)
        
        # Форматируем для SQLite
        unmute_time_str = unmute_time.strftime('%Y-%m-%d %H:%M:%S')
        
        # Сохраняем в базу данных
        db_operation(
            """INSERT OR REPLACE INTO muted_users 
               (user_id, muted_by_id, unmute_time, mute_reason) 
               VALUES (?, ?, ?, ?)""",
            (user_id, admin_id, unmute_time_str, mute_reason)
        )
        
        logger.info(f"🔇 Пользователь {user_id} замучен администратором {admin_id} на {minutes} минут. Причина: {mute_reason}")
        return unmute_time
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении мута для пользователя {user_id}: {e}")
        raise

def unmute_user(user_id: int) -> bool:
    """Снять мут с пользователя"""
    try:
        result = db_operation(
            "DELETE FROM muted_users WHERE user_id = ?",
            (user_id,)
        )
        
        if result is not None:
            logger.info(f"🔊 Пользователь {user_id} размучен")
            return True
        return False
        
    except Exception as e:
        logger.error(f"Ошибка при снятии мута с пользователя {user_id}: {e}")
        return False

def is_muted(user_id: int) -> bool:
    """Проверить, находится ли пользователь в муте"""
    try:
        result = db_operation(
            "SELECT unmute_time FROM muted_users WHERE user_id = ?",
            (user_id,),
            fetch=True
        )
        
        if not result:
            return False
        
        unmute_time_str = result[0][0]
        
        # Преобразуем строку времени в datetime
        unmute_time = datetime.strptime(unmute_time_str, '%Y-%m-%d %H:%M:%S')
        unmute_time = pytz.UTC.localize(unmute_time)
        
        # Проверяем не истек ли мут
        now = datetime.now(pytz.UTC)
        
        if now > unmute_time:
            # Удаляем истекший мут
            unmute_user(user_id)
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при проверке мута пользователя {user_id}: {e}")
        return False

def get_mute_info(user_id: int):
    """Получить информацию о муте пользователя"""
    try:
        result = db_operation(
            """SELECT muted_by_id, unmute_time, mute_reason, created_at 
               FROM muted_users 
               WHERE user_id = ?""",
            (user_id,),
            fetch=True
        )
        
        if not result:
            return None
        
        muted_by_id, unmute_time_str, mute_reason, created_at = result[0]
        
        # Преобразуем строку времени в datetime
        unmute_time = datetime.strptime(unmute_time_str, '%Y-%m-%d %H:%M:%S')
        unmute_time = pytz.UTC.localize(unmute_time)
        
        # Получаем информацию о том, кто замутил
        admin_info = db_operation(
            "SELECT username FROM all_users WHERE id = ?",
            (muted_by_id,),
            fetch=True
        )
        
        admin_username = admin_info[0][0] if admin_info else None
        
        return {
            'muted_by_id': muted_by_id,
            'muted_by_username': admin_username,
            'unmute_time': unmute_time,
            'mute_reason': mute_reason,
            'created_at': created_at
        }
        
    except Exception as e:
        logger.error(f"Ошибка при получении информации о муте пользователя {user_id}: {e}")
        return None

def get_all_muted_users():
    """Получить список всех замученных пользователей"""
    try:
        # Получаем только активные муты (которые еще не истекли)
        now = datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S')
        
        result = db_operation(
            """SELECT mu.user_id, mu.muted_by_id, mu.unmute_time, mu.mute_reason, 
                      mu.created_at, au.username, au.first_name,
                      ab.username as admin_username
               FROM muted_users mu
               LEFT JOIN all_users au ON mu.user_id = au.id
               LEFT JOIN all_users ab ON mu.muted_by_id = ab.id
               WHERE mu.unmute_time > ?
               ORDER BY mu.unmute_time ASC""",
            (now,),
            fetch=True
        )
        
        muted_list = []
        for row in result:
            muted_list.append({
                'user_id': row[0],
                'muted_by_id': row[1],
                'unmute_time': row[2],
                'mute_reason': row[3],
                'created_at': row[4],
                'username': row[5],
                'first_name': row[6],
                'admin_username': row[7]
            })
        
        return muted_list
        
    except Exception as e:
        logger.error(f"Ошибка при получении списка мутов: {e}")
        return []

def cleanup_expired_mutes():
    """Очистка истекших мутов из базы данных"""
    try:
        now = datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S')
        
        result = db_operation(
            "SELECT COUNT(*) FROM muted_users WHERE unmute_time <= ?",
            (now,),
            fetch=True
        )
        
        expired_count = result[0][0] if result else 0
        
        if expired_count > 0:
            db_operation(
                "DELETE FROM muted_users WHERE unmute_time <= ?",
                (now,)
            )
            logger.info(f"🗑️ Очищено {expired_count} истекших мутов")
        
        return expired_count
        
    except Exception as e:
        logger.error(f"Ошибка при очистке истекших мутов: {e}")
        return 0


@router_admins.message(Command("muteplayer"))
@require_role("младший-администратор")
async def muteplayer_command(message: Message, state: FSMContext):
    """Выдача мута пользователю"""
    await message.reply("🔇 Введите ID пользователя для мута:")
    await state.set_state(AdminStates.waiting_id_for_mute1)

@router_admins.message(AdminStates.waiting_id_for_mute1)
@require_role("младший-администратор")
async def process_mute_user_id(message: Message, state: FSMContext):
    """Обработка ID пользователя для мута"""
    try:
        user_id = int(message.text.strip())
        await state.update_data(mute_user_id=user_id)
        await message.reply(
            f"🆔 ID пользователя для мута: {user_id}\n\n"
            "Введите время мута в минутах (максимум 10080 - 7 дней):"
        )
        await state.set_state(AdminStates.waiting_id_for_mute2)
    except ValueError:
        await message.reply("❌ Неверный формат ID. Введите число.")
        await state.clear()

@router_admins.message(AdminStates.waiting_id_for_mute2)
@require_role("младший-администратор")
async def process_mute_time(message: Message, state: FSMContext):
    """Обработка времени мута"""
    try:
        minutes = int(message.text.strip())
        
        if minutes <= 0:
            await message.reply("❌ Время мута должно быть положительным числом!")
            await state.clear()
            return
            
        if minutes > 10080:
            await message.reply("⚠️ Максимальное время мута - 7 дней (10080 минут)")
            minutes = 10080
        
        data = await state.get_data()
        user_id = data.get('mute_user_id')
        
        if not user_id:
            await message.reply("❌ Ошибка: ID пользователя не найден.")
            await state.clear()
            return
        
        # Проверяем, замучен ли уже пользователь
        if is_muted(user_id):
            mute_info = get_mute_info(user_id)
            unmute_time = mute_info['unmute_time'].strftime("%d.%m.%Y %H:%M")
            await message.reply(f"⚠️ Этот пользователь уже в муте! Мут снимется {unmute_time}")
            await state.clear()
            return
        
        # Добавляем мут
        unmute_time = mute_user(user_id, message.from_user.id, minutes)
        unmute_time_str = unmute_time.strftime("%d.%m.%Y в %H:%M")
        
        # Форматируем время для вывода
        if minutes < 60:
            time_text = f"{minutes} минут"
        elif minutes < 1440:
            hours = minutes // 60
            time_text = f"{hours} час(ов)"
        else:
            days = minutes // 1440
            time_text = f"{days} день(дней)"
        
        await message.reply(
            f"✅ <b>Пользователь с ID {user_id} замучен на {time_text}!</b>\n"
            f"⏰ Мут снимется: {unmute_time_str}",
            parse_mode="HTML"
        )
        
        logger.info(f"🔇 АДМИН: {message.from_user.id} замутил пользователя {user_id} на {minutes} минут")
        
    except ValueError:
        await message.reply("❌ Неверный формат времени. Введите число минут!")
    except Exception as e:
        logger.error(f"Ошибка при выдаче мута: {e}")
        await message.reply(f"❌ Ошибка: {str(e)[:100]}")
    finally:
        await state.clear()

@router_admins.message(Command("unmuteplayer"))
@require_role("младший-администратор")
async def unmuteplayer_command(message: Message):
    """Снятие мута с пользователя"""
    args = message.text.split()
    
    if len(args) < 2:
        await message.reply("❌ Использование: /unmuteplayer [ID_пользователя]")
        return
    
    try:
        user_id = int(args[1])
        
        if unmute_user(user_id):
            await message.reply(f"✅ Мут с пользователя {user_id} успешно снят!")
            logger.info(f"🔊 АДМИН: {message.from_user.id} снял мут с пользователя {user_id}")
        else:
            await message.reply(f"ℹ️ Пользователь {user_id} не в муте!")
            
    except ValueError:
        await message.reply("❌ Неверный формат ID!")

@router_admins.message(Command("checkmute"))
@require_role("помощник-администратора")
async def checkmute_command(message: Message):
    """Проверка статуса мута"""
    args = message.text.split()
    
    if len(args) < 2:
        await message.reply("❌ Использование: /checkmute [ID_пользователя]")
        return
    
    try:
        user_id = int(args[1])
        
        if is_muted(user_id):
            mute_info = get_mute_info(user_id)
            unmute_time = mute_info['unmute_time'].strftime("%d.%m.%Y в %H:%M")
            time_left = mute_info['unmute_time'] - datetime.now()
            hours_left = int(time_left.total_seconds() // 3600)
            minutes_left = int((time_left.total_seconds() % 3600) // 60)
            
            await message.reply(
                f"🔇 <b>Пользователь {user_id} в муте!</b>\n"
                f"⏰ Снимется: {unmute_time}\n"
                f"⏳ Осталось: {hours_left}ч {minutes_left}м",
                parse_mode="HTML"
            )
        else:
            await message.reply(f"✅ Пользователь {user_id} не в муте!")
            
    except ValueError:
        await message.reply("❌ Неверный формат ID!")

@router_admins.message(Command("mutedlist"))
@require_role("помощник-администратора")
@log_admin_action("Просмотр списка замученных пользователей")
async def mutedlist_command(message: Message):
    """Просмотр списка всех замученных пользователей"""
    try:
        # Очищаем истекшие муты перед показом
        expired_count = cleanup_expired_mutes()
        if expired_count > 0:
            logger.info(f"Очищено {expired_count} истекших мутов перед показом списка")
        
        # Получаем список активных мутов
        muted_users_list = get_all_muted_users()
        
        if not muted_users_list:
            await message.reply(
                "📭 <b>Список замученных пользователей пуст.</b>\n\n"
                "<i>В данный момент нет пользователей с активными мутами.</i>",
                parse_mode="HTML"
            )
            return
        
        total_muted = len(muted_users_list)
        
        # Группируем по длительности мута (краткосрочные, средние, долгосрочные)
        now = datetime.now(pytz.UTC)
        short_term = []    # до 1 часа
        medium_term = []   # 1-24 часа
        long_term = []     # более 24 часов
        
        for mute_info in muted_users_list:
            try:
                unmute_time = datetime.strptime(mute_info['unmute_time'], '%Y-%m-%d %H:%M:%S')
                unmute_time = pytz.UTC.localize(unmute_time)
                time_left = unmute_time - now
                hours_left = time_left.total_seconds() / 3600
                
                if hours_left < 1:
                    short_term.append(mute_info)
                elif hours_left < 24:
                    medium_term.append(mute_info)
                else:
                    long_term.append(mute_info)
            except Exception as e:
                logger.error(f"Ошибка при обработке мута пользователя {mute_info.get('user_id')}: {e}")
                continue
        
        # Формируем основное сообщение
        response = (
            f"📋 <b>СПИСОК ЗАМУЧЕННЫХ ПОЛЬЗОВАТЕЛЕЙ</b>\n\n"
            f"👥 <b>Всего активных мутов:</b> {total_muted}\n"
            f"⏱️ <b>Краткосрочные (до 1ч):</b> {len(short_term)}\n"
            f"⏳ <b>Средние (1-24ч):</b> {len(medium_term)}\n"
            f"⏰ <b>Долгосрочные (>24ч):</b> {len(long_term)}\n\n"
        )
        
        # Отправляем основную информацию
        await message.reply(response, parse_mode="HTML")
        
        # Отправляем подробную информацию частями
        if short_term:
            await send_muted_users_chunk(
                message, 
                short_term, 
                "🔴 КРАТКОСРОЧНЫЕ МУТЫ (до 1 часа)",
                now
            )
        
        if medium_term:
            await send_muted_users_chunk(
                message, 
                medium_term, 
                "🟡 СРЕДНИЕ МУТЫ (1-24 часа)",
                now
            )
        
        if long_term:
            await send_muted_users_chunk(
                message, 
                long_term, 
                "🟢 ДОЛГОСРОЧНЫЕ МУТЫ (более 24 часов)",
                now
            )
        
        # Отправляем статистику
        stats_response = (
            f"📊 <b>СТАТИСТИКА МУТОВ</b>\n\n"
            f"👮‍♂️ <b>Администраторов выдавших муты:</b> {len(set(m['muted_by_id'] for m in muted_users_list))}\n"
            f"📅 <b>Самый старый мут:</b> {min(m['created_at'] for m in muted_users_list)[:10]}\n"
            f"🕐 <b>Самый новый мут:</b> {max(m['created_at'] for m in muted_users_list)[:10]}\n\n"
            f"<i>Для снятия мута используйте /unmuteplayer [ID]\n"
            f"Для проверки конкретного пользователя: /checkmute [ID]</i>"
        )
        
        await message.reply(stats_response, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка при получении списка мутов: {e}")
        await message.reply(
            f"❌ <b>Ошибка при получении списка мутов:</b>\n\n"
            f"<code>{str(e)[:200]}</code>\n\n"
            f"<i>Попробуйте позже или обратитесь к старшему администратору.</i>",
            parse_mode="HTML"
        )

async def send_muted_users_chunk(message: Message, muted_list: list, title: str, now: datetime):
    """Отправляет часть списка замученных пользователей"""
    try:
        response = f"{title}\n{'━' * 40}\n\n"
        
        for i, mute_info in enumerate(muted_list, 1):
            try:
                # Форматируем время размута
                unmute_time = datetime.strptime(mute_info['unmute_time'], '%Y-%m-%d %H:%M:%S')
                unmute_time = pytz.UTC.localize(unmute_time)
                unmute_time_moscow = unmute_time.astimezone(pytz.timezone('Europe/Moscow'))
                unmute_time_str = unmute_time_moscow.strftime("%d.%m %H:%M")
                
                # Вычисляем оставшееся время
                time_left = unmute_time - now
                hours_left = int(time_left.total_seconds() // 3600)
                minutes_left = int((time_left.total_seconds() % 3600) // 60)
                
                # Форматируем оставшееся время
                if hours_left > 0:
                    time_left_str = f"{hours_left}ч {minutes_left}м"
                else:
                    time_left_str = f"{minutes_left}м"
                
                # Информация о пользователе
                user_display = (
                    f"@{mute_info['username']}" if mute_info['username'] 
                    else f"{mute_info['first_name'] or f'ID: {mute_info['user_id']}'}"
                )
                
                # Информация об администраторе
                admin_display = (
                    f"@{mute_info['admin_username']}" if mute_info['admin_username']
                    else f"ID: {mute_info['muted_by_id']}"
                )
                
                response += (
                    f"<b>#{i}. {user_display}</b>\n"
                    f"   🆔 ID: <code>{mute_info['user_id']}</code>\n"
                    f"   ⏰ Снимется: {unmute_time_str} (через {time_left_str})\n"
                    f"   👮‍♂️ Замутил: {admin_display}\n"
                )
                
                if mute_info['mute_reason']:
                    reason_short = mute_info['mute_reason'][:50] + "..." if len(mute_info['mute_reason']) > 50 else mute_info['mute_reason']
                    response += f"   📝 Причина: {reason_short}\n"
                
                response += f"   📅 Дата мута: {mute_info['created_at'][:10]}\n"
                response += f"   ━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                
                # Если накопилось достаточно информации, отправляем
                if i % 5 == 0 or i == len(muted_list):
                    await message.reply(response, parse_mode="HTML")
                    response = ""
                    await asyncio.sleep(0.5)  # Задержка чтобы не получить flood control
                    
            except Exception as e:
                logger.error(f"Ошибка при форматировании информации о муте: {e}")
                continue
                
        # Отправляем остаток если есть
        if response.strip():
            await message.reply(response, parse_mode="HTML")
            
    except Exception as e:
        logger.error(f"Ошибка при отправке части списка мутов: {e}")
        await message.reply(f"❌ Ошибка при формировании списка мутов: {str(e)[:100]}")

# ========================
# КОМАНДЫ УПРАВЛЕНИЯ
# ========================

@router_admins.message(Command("writeto"))
@require_role("помощник-администратора")
@log_command
async def writeto_command(message: Message, state: FSMContext):
    """Отправка сообщения пользователю"""
    await message.reply(
        "✉️ <b>Отправка сообщения пользователю</b>\n\n"
        "Введите ID пользователя:",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_id1)

@router_admins.message(AdminStates.waiting_for_id1)
@require_role("помощник-администратора")
async def process_writeto_user_id(message: Message, state: FSMContext):
    """Обработка ID пользователя для отправки сообщения"""
    try:
        user_id = int(message.text.strip())
        await state.update_data(writeto_user_id=user_id)
        await message.reply(
            f"🆔 ID пользователя: {user_id}\n\n"
            "Введите сообщение для отправки:"
        )
        await state.set_state(AdminStates.waiting_for_id2)
    except ValueError:
        await message.reply("❌ Неверный формат ID. Введите число.")
        await state.clear()

@router_admins.message(AdminStates.waiting_for_id2)
@require_role("помощник-администратора")
async def process_writeto_message(message: Message, state: FSMContext, bot: Bot):
    """Обработка и отправка сообщения"""
    message_text = message.text.strip()
    data = await state.get_data()
    user_id = data.get('writeto_user_id')
    
    if not user_id:
        await message.reply("❌ Ошибка: ID пользователя не найден.")
        await state.clear()
        return
    
    try:
        await bot.send_message(
            user_id,
            f"🔻 <b>Сообщение от администрации:</b>\n\n{message_text}",
            parse_mode="HTML"
        )
        
        await message.reply(
            f"✅ <b>Сообщение успешно отправлено!</b>\n\n"
            f"🆔 Получатель: {user_id}\n"
            f"📝 Текст: {message_text[:50]}...",
            parse_mode="HTML"
        )
        
        logger.info(f"✉️ АДМИН: {message.from_user.id} отправил сообщение пользователю {user_id}")
        
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")
        await message.reply(f"❌ Не удалось отправить сообщение. Возможно, пользователь заблокировал бота.")
    
    await state.clear()

@router_admins.message(Command("deleteanket"))
@require_role("старший-администратор")
@log_command
async def delete_anket_command(message: Message):
    """Удаление анкет пользователя"""
    args = message.text.split()
    
    if len(args) < 2:
        await message.reply(
            "❌ Использование: /deleteanket [ID_пользователя]\n\n"
            "Пример: /deleteanket 123456789\n\n"
            "Удаляет все анкеты пользователя и связанные лайки."
        )
        return
    
    try:
        user_id = int(args[1])
        
        # Проверяем, существует ли пользователь
        user_exists = db_operation(
            "SELECT id, username, first_name FROM all_users WHERE id = ?",
            (user_id,),
            fetch=True
        )
        
        if not user_exists:
            await message.reply(f"❌ Пользователь с ID {user_id} не найден.")
            return
        
        user_info = user_exists[0]
        username = user_info[1] or "нет"
        first_name = user_info[2] or "не указано"
        
        # Запрашиваем подтверждение
        confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"delete_anket:{user_id}")],
            [InlineKeyboardButton(text="❌ Нет, отменить", callback_data="cancel_delete")]
        ])
        
        await message.reply(
            f"⚠️ <b>Удаление анкет пользователя</b>\n\n"
            f"👤 Пользователь: {first_name}\n"
            f"📛 Username: @{username}\n"
            f"🆔 ID: <code>{user_id}</code>\n\n"
            f"<b>Будет удалено:</b>\n"
            f"• Анкета игрока\n"
            f"• Анкета владельца клуба\n"
            f"• Все связанные лайки\n\n"
            f"Подтвердите действие:",
            parse_mode="HTML",
            reply_markup=confirm_keyboard
        )
        
    except ValueError:
        await message.reply("❌ Неверный формат ID.")
    except Exception as e:
        logger.error(f"Ошибка при удалении анкет: {e}")
        await message.reply(f"❌ Ошибка: {str(e)[:100]}")

@router_admins.callback_query(F.data.startswith("delete_anket:"))
async def confirm_delete_anket(callback: CallbackQuery):
    """Подтверждение удаления анкет"""
    try:
        user_id = int(callback.data.split(":")[1])
        admin_id = callback.from_user.id
        
        # Удаляем анкеты
        deleted_items = []
        
        # Удаляем анкету игрока
        player_anket = db_operation(
            "SELECT nickname FROM users_search_club WHERE player_id = ?",
            (user_id,),
            fetch=True
        )
        if player_anket:
            db_operation("DELETE FROM users_search_club WHERE player_id = ?", (user_id,))
            deleted_items.append("анкета игрока")
        
        # Удаляем анкету владельца
        owner_anket = db_operation(
            "SELECT club_name FROM owners_search_players WHERE owner_id = ?",
            (user_id,),
            fetch=True
        )
        if owner_anket:
            db_operation("DELETE FROM owners_search_players WHERE owner_id = ?", (user_id,))
            deleted_items.append("анкета владельца клуба")
        
        # Удаляем лайки
        db_operation("DELETE FROM owner_likes WHERE owner_id = ? OR liked_player_id = ?", (user_id, user_id))
        db_operation("DELETE FROM player_likes WHERE player_id = ? OR liked_club_id = ?", (user_id, user_id))
        
        if deleted_items:
            response = f"✅ <b>Анкеты успешно удалены!</b>\n\nУдалено: {', '.join(deleted_items)}"
            logger.info(f"🗑️ АДМИН: {admin_id} удалил анкеты пользователя {user_id}")
        else:
            response = "ℹ️ У пользователя не было анкет для удаления."
        
        await callback.message.edit_text(response, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка при удалении анкет: {e}")
        await callback.message.edit_text("❌ Ошибка при удалении анкет.")

@router_admins.callback_query(F.data == "cancel_delete")
async def cancel_delete_anket(callback: CallbackQuery):
    """Отмена удаления анкет"""
    await callback.message.edit_text("❌ Удаление анкет отменено.")

@router_admins.message(Command("all_users"))
@require_role("старший-администратор")
@log_command
async def all_users_command(message: Message):
    """Просмотр всех пользователей"""
    try:
        await message.reply("🔄 Загружаю список пользователей...")
        
        users = db_operation(
            "SELECT id, username, first_name, user_type, created_at FROM all_users ORDER BY created_at DESC",
            fetch=True
        )
        
        if not users:
            await message.reply("📭 Пользователей нет в базе.")
            return
        
        total_users = len(users)
        users_per_part = 10
        
        for i in range(0, total_users, users_per_part):
            chunk = users[i:i + users_per_part]
            
            response = f"📊 <b>Пользователи ({i//users_per_part + 1}/{(total_users + users_per_part - 1)//users_per_part}):</b>\n\n"
            
            for j, user in enumerate(chunk, i + 1):
                user_id, username, first_name, user_type, created_at = user
                
                response += (
                    f"👤 <b>#{j}</b>\n"
                    f"🆔 ID: <code>{user_id}</code>\n"
                    f"📛 Username: @{username or 'нет'}\n"
                    f"👤 Имя: {first_name or 'не указано'}\n"
                    f"📊 Тип: {user_type or 'не указан'}\n"
                    f"📅 Создан: {created_at}\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                )
            
            if i + users_per_part >= total_users:
                response += f"\n📈 <b>Всего пользователей: {total_users}</b>"
            
            await message.reply(response, parse_mode="HTML")
            await asyncio.sleep(0.5)
            
    except Exception as e:
        logger.error(f"Ошибка при загрузке пользователей: {e}")
        await message.reply(f"❌ Ошибка: {str(e)[:100]}")
#=======================


#=======================

@router_admins.message(Command("all_ankets"))
@require_role("старший-администратор")
@log_command
async def all_ankets_command(message: Message):
    """Просмотр всех анкет"""
    try:
        await message.reply("🔄 Загружаю анкеты...")
        
        # Анкеты игроков
        players = db_operation(
            "SELECT player_id, nickname, player_position, created_at FROM users_search_club ORDER BY created_at DESC",
            fetch=True
        )
        
        # Анкеты владельцев
        owners = db_operation(
            "SELECT owner_id, club_name, needed_positions, created_at FROM owners_search_players ORDER BY created_at DESC",
            fetch=True
        )
        
        if not players and not owners:
            await message.reply("📭 Анкет нет в базе.")
            return
        
        # Отправляем анкеты игроков
        if players:
            total_players = len(players)
            
            for i in range(0, total_players, 10):
                chunk = players[i:i + 10]
                
                response = f"👤 <b>Анкеты игроков ({(i//10) + 1}/{(total_players + 9)//10}):</b>\n\n"
                
                for j, player in enumerate(chunk, i + 1):
                    player_id, nickname, position, created_at = player
                    
                    # Получаем имя пользователя
                    user_info = db_operation(
                        "SELECT first_name FROM all_users WHERE id = ?",
                        (player_id,),
                        fetch=True
                    )
                    first_name = user_info[0][0] if user_info else "Неизвестно"
                    
                    response += (
                        f"⚽ <b>#{j}</b>\n"
                        f"👤 Игрок: {first_name}\n"
                        f"🆔 ID: <code>{player_id}</code>\n"
                        f"🎮 Никнейм: {nickname or 'не указан'}\n"
                        f"📍 Позиция: {position or 'не указана'}\n"
                        f"📅 Создана: {created_at}\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                    )
                
                if i + 10 >= total_players:
                    response += f"\n📊 <b>Всего анкет игроков: {total_players}</b>"
                
                await message.reply(response, parse_mode="HTML")
                await asyncio.sleep(0.5)
        
        # Отправляем анкеты владельцев
        if owners:
            total_owners = len(owners)
            
            for i in range(0, total_owners, 10):
                chunk = owners[i:i + 10]
                
                response = f"👑 <b>Анкеты владельцев ({(i//10) + 1}/{(total_owners + 9)//10}):</b>\n\n"
                
                for j, owner in enumerate(chunk, i + 1):
                    owner_id, club_name, positions, created_at = owner
                    
                    # Получаем имя пользователя
                    user_info = db_operation(
                        "SELECT first_name FROM all_users WHERE id = ?",
                        (owner_id,),
                        fetch=True
                    )
                    first_name = user_info[0][0] if user_info else "Неизвестно"
                    
                    response += (
                        f"🏆 <b>#{j}</b>\n"
                        f"👑 Владелец: {first_name}\n"
                        f"🆔 ID: <code>{owner_id}</code>\n"
                        f"🏟️ Клуб: {club_name or 'не указан'}\n"
                        f"📍 Ищем: {positions or 'не указано'}\n"
                        f"📅 Создана: {created_at}\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                    )
                
                if i + 10 >= total_owners:
                    response += f"\n📊 <b>Всего анкет владельцев: {total_owners}</b>"
                
                await message.reply(response, parse_mode="HTML")
                await asyncio.sleep(0.5)
        
        # Общая статистика
        total_ankets = len(players) + len(owners)
        await message.reply(
            f"📈 <b>Общая статистика:</b>\n\n"
            f"👤 Игроков: {len(players)}\n"
            f"👑 Владельцев: {len(owners)}\n"
            f"📊 Всего анкет: {total_ankets}",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при загрузке анкет: {e}")
        await message.reply(f"❌ Ошибка: {str(e)[:100]}")

@router_admins.message(Command("rassilka"))
@require_role("старший-администратор")
@log_command
async def rassilka_command(message: Message, state: FSMContext):
    """Начало рассылки"""
    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Начать рассылку", callback_data="start_broadcast")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_broadcast")]
    ])
    
    await message.reply(
        "📢 <b>Массовая рассылка</b>\n\n"
        "Вы уверены, что хотите начать рассылку всем пользователям?\n\n"
        "Введите сообщение для рассылки:",
        parse_mode="HTML",
        reply_markup=confirm_keyboard
    )
    await state.set_state(AdminStates.waiting_for_message_for_rassilka)

@router_admins.callback_query(F.data == "start_broadcast")
async def start_broadcast_confirmation(callback: CallbackQuery):
    """Подтверждение начала рассылки"""
    await callback.message.edit_text("📝 Введите сообщение для рассылки:")
    await callback.answer()

@router_admins.callback_query(F.data == "cancel_broadcast")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    """Отмена рассылки"""
    await callback.message.edit_text("❌ Рассылка отменена.")
    await state.clear()
    await callback.answer()

@router_admins.message(AdminStates.waiting_for_message_for_rassilka)
@require_role("старший-администратор")
async def process_broadcast_message(message: Message, state: FSMContext, bot: Bot):
    """Обработка сообщения для рассылки"""
    broadcast_text = message.text.strip()
    
    try:
        await message.reply("🔄 Начинаю рассылку...")
        
        # Получаем всех пользователей
        users = db_operation("SELECT id FROM all_users", fetch=True)
        
        if not users:
            await message.reply("📭 Нет пользователей для рассылки.")
            await state.clear()
            return
        
        total_users = len(users)
        success_count = 0
        fail_count = 0
        
        for user_tuple in users:
            user_id = user_tuple[0]
            try:
                await bot.send_message(
                    user_id,
                    f"📢 <b>Рассылка от администрации:\n\n{broadcast_text}</b>",
                    parse_mode="HTML"
                )
                success_count += 1
                await asyncio.sleep(0.05)  # Задержка чтобы не получить flood control
            except Exception as e:
                fail_count += 1
                logger.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
        
        await message.reply(
            f"✅ <b>Рассылка завершена!</b>\n\n"
            f"📊 Статистика:\n"
            f"✅ Успешно: {success_count}\n"
            f"❌ Ошибок: {fail_count}\n"
            f"📈 Всего: {total_users}",
            parse_mode="HTML"
        )
        
        logger.info(f"📢 АДМИН: {message.from_user.id} сделал рассылку. Охват: {success_count}/{total_users}")
        
    except Exception as e:
        logger.error(f"Ошибка при рассылке: {e}")
        await message.reply(f"❌ Ошибка при рассылке: {str(e)[:100]}")
    finally:
        await state.clear()

@router_admins.message(Command("test_broadcast"))
@require_role("старший-администратор")
@log_command
async def test_broadcast_command(message: Message, bot: Bot):
    """Тестовая рассылка"""
    await message.reply("🔄 Запускаю тестовую рассылку...")
    # Реализация тестовой рассылки
    await message.reply("✅ Тестовая рассылка завершена.")

@router_admins.message(Command("scheduler_status"))
@require_role("младший-администратор")
@log_command
async def scheduler_status_command(message: Message):
    """Статус планировщика"""
    # Реализация проверки статуса планировщика
    await message.reply("📅 <b>Статус планировщика:</b>\n\n", parse_mode="HTML")


@router_admins.message(Command("getcard"))
@require_role("младший-администратор")
@log_admin_action("Получение карточки по нику")
async def getcard_command(message: Message):
    """Получить карточку игрока по никнейму (только для админов)"""
    
    # Проверяем права администратора

    
    # Получаем аргументы команды
    command_text = message.text.strip()
    args = command_text.split(maxsplit=1)  # Разделяем команду и аргументы
    
    if len(args) < 2:
        await message.reply(
            "📝 <b>Использование команды:</b>\n\n"
            "<code>/getcard никнейм_игрока</code>\n\n"
            "<b>Примеры:</b>\n"
            "• <code>/getcard DonbazZ</code>\n"
            "• <code>/getcard Bellingham</code>\n"
            "• <code>/getcard etiqinha</code>\n\n"
            "<i>Команда доступна только администраторам</i>",
            parse_mode="html"
        )
        return
    
    nickname = args[1].strip()
    
    try:
        # Ищем карточку в базе данных
        card = get_card_by_nickname_db(nickname)
        
        if not card:
            # Пробуем найти похожие карточки
            similar_cards = search_similar_cards(nickname)
            
            if similar_cards:
                # Формируем список похожих карточек
                cards_list = []
                for i, similar_card in enumerate(similar_cards[:5], 1):
                    cards_list.append(
                        f"{i}. <code>{similar_card['nickname']}</code> "
                        f"({similar_card['club']}) - {similar_card['rarity']}"
                    )
                
                await message.reply(
                    f"🔍 <b>Точное совпадение не найдено</b>\n\n"
                    f"<b>Возможно, вы искали:</b>\n" + "\n".join(cards_list) + "\n\n"
                    f"<i>Используйте точный никнейм из списка</i>",
                    parse_mode="html"
                )
            else:
                await message.reply(
                    f"❌ Карточка с никнеймом <code>{nickname}</code> не найдена.\n\n"
                    f"<i>Проверьте правильность написания</i>",
                    parse_mode="html"
                )
            return
        
        # Форматируем информацию о карточке
        rarity_display = 'Эпический' if card['rarity'] == 'эпическая' else card['rarity']
        rarity_icons = {
            'Редкий': '🟢',
            'Эпический': '🟣',
            'Легендарный': '🟡',
            'Суперлегендарный': '🔴'
        }
        
        icon = rarity_icons.get(rarity_display, '⭐')
        
        # Формируем сообщение
        card_message = (
            f"{icon} <b>КАРТОЧКА ИГРОКА</b> {icon}\n\n"
            f"<b>👤 Никнейм:</b> <code>{card['nickname']}</code>\n"
            f"<b>🏟️ Клуб:</b> {card['club']}\n"
            f"<b>🎯 Позиция:</b> {card['position']}\n"
            f"<b>💎 Редкость:</b> {rarity_display}\n"
            f"<b>🆔 ID в БД:</b> <code>{card['id']}</code>\n\n"
        )
        
        # Добавляем статистику по карточке
        owners_count = get_card_owners_count(card['id'])
        if owners_count is not None:
            card_message += f"<b>👥 Владельцев карточки:</b> {owners_count}\n\n"
        
        card_message += (
            f"<i>Команда: /getcard {card['nickname']}</i>"
        )
        
        # Пытаемся найти и отправить картинку
        try:
            # Получаем конкретную карточку
            png_file_path = get_specific_card_image(card['nickname'], rarity_display)
            
            if png_file_path and os.path.exists(png_file_path):
                # Создаем FSInputFile для отправки
                from aiogram.types import FSInputFile
                photo = FSInputFile(png_file_path)
                
                # Отправляем картинку с описанием
                await message.reply_photo(
                    photo=photo,
                    caption=card_message,
                    parse_mode="html"
                )
                logger.info(f"👑 Админ {message.from_user.id} запросил карточку: {card['nickname']}")
                
            else:
                # Если не нашли картинку, отправляем только текст
                await message.reply(
                    card_message + "\n\n⚠️ <i>Картинка для этой карточки не найдена</i>",
                    parse_mode="html"
                )
                logger.warning(f"⚠️ Не удалось найти PNG карточку для '{card['nickname']}'")
                
        except Exception as photo_error:
            # Если ошибка при отправке фото, отправляем только текст
            logger.error(f"❌ Ошибка при отправке PNG карточки: {photo_error}")
            await message.reply(
                card_message + "\n\n❌ <i>Ошибка при загрузке картинки</i>",
                parse_mode="html"
            )
        
    except Exception as e:
        logger.error(f"❌ Ошибка в команде /getcard: {e}")
        await message.reply(
            f"❌ Произошла ошибка при поиске карточки: {str(e)[:100]}",
            parse_mode="html"
        )
def get_all_promocodes():
    """Получает список всех промокодов"""
    try:
        result = db_operation(
            """SELECT code, coins, max_uses, used_count, created_at, is_active,
                      CASE 
                          WHEN max_uses = 0 THEN '∞'
                          ELSE CAST(max_uses AS TEXT)
                      END as max_uses_display,
                      CASE 
                          WHEN max_uses = 0 THEN 'безлимит'
                          WHEN used_count >= max_uses THEN 'исчерпан'
                          ELSE CAST((max_uses - used_count) AS TEXT)
                      END as uses_left
               FROM promocodes 
               ORDER BY created_at DESC""",
            fetch=True
        )
        
        if not result:
            return []
        
        promocodes = []
        for row in result:
            (code, coins, max_uses, used_count, created_at, is_active, 
             max_uses_display, uses_left) = row
            
            promocodes.append({
                'code': code,
                'coins': coins,
                'max_uses': max_uses,
                'used_count': used_count,
                'created_at': created_at[:16],  # Обрезаем до даты и времени
                'is_active': bool(is_active),
                'max_uses_display': max_uses_display,
                'uses_left': uses_left,
                'status': "✅" if is_active else "❌"
            })
        
        return promocodes
        
    except Exception as e:
        logger.error(f"Ошибка при получении списка промокодов: {e}")
        return []
@router_admins.message(Command("allpromocodes"))
@require_role("старший-администратор")
@log_admin_action("Просмотр всех промокодов")
async def allpromocodes_command(message: Message):
    """Показать все промокоды"""
    try:
        promocodes = get_all_promocodes()
        
        if not promocodes:
            await message.reply(
                "📭 <b>Промокоды не найдены</b>\n\n"
                "<i>Используйте /addpromo чтобы создать первый промокод</i>",
                parse_mode="html"
            )
            return
        
        message_text = "🧾 <b>ВСЕ ПРОМОКОДЫ</b>\n\n"
        
        total_coins = 0
        total_uses = 0
        active_count = 0
        
        for i, promo in enumerate(promocodes, 1):
            # Статистика
            total_coins += promo['coins'] * promo['used_count']
            total_uses += promo['used_count']
            if promo['is_active']:
                active_count += 1
            
            # Форматируем информацию о промокоде
            message_text += (
                f"<b>{i}. {promo['status']} {promo['code']}</b>\n"
                f"💰 <b>Коины:</b> {promo['coins']}\n"
                f"📊 <b>Использован:</b> {promo['used_count']} раз\n"
                f"🎯 <b>Лимит:</b> {promo['max_uses_display']}\n"
                f"📅 <b>Создан:</b> {promo['created_at']}\n"
            )
            
            if promo['uses_left'] != 'безлимит':
                message_text += f"📈 <b>Осталось:</b> {promo['uses_left']}\n"
            
            message_text += "─" * 25 + "\n\n"
        
        # Добавляем статистику
        message_text += (
            f"📊 <b>СТАТИСТИКА:</b>\n"
            f"• Всего промокодов: {len(promocodes)}\n"
            f"• Активных: {active_count}\n"
            f"• Всего использований: {total_uses}\n"
            f"• Начислено коинов: {total_coins}\n\n"
            f"<i>Для создания: /addpromo\n"
            f"Для удаления: /deletepromo</i>"
        )
        
        await message.reply(message_text, parse_mode="html")
        
    except Exception as e:
        logger.error(f"Ошибка в команде /allpromocodes: {e}")
        await message.reply(f"❌ Ошибка: {str(e)[:100]}")


def search_similar_cards(nickname: str, limit: int = 5):
    """Ищет похожие карточки по никнейму"""
    try:
        result = db_operation(
            """SELECT id, nickname, club, position, rarity 
               FROM players_catalog 
               WHERE LOWER(nickname) LIKE LOWER(?)
               ORDER BY nickname
               LIMIT ?""",
            (f"%{nickname}%", limit),
            fetch=True
        )
        
        if not result:
            return []
        
        cards = []
        for row in result:
            card_id, nickname, club, position, rarity = row
            cards.append({
                'id': card_id,
                'nickname': nickname,
                'club': club,
                'position': position,
                'rarity': rarity
            })
        
        return cards
        
    except Exception as e:
        logger.error(f"Ошибка при поиске похожих карточек для '{nickname}': {e}")
        return []

def get_card_owners_count(card_id: int):
    """Получает количество пользователей, у которых есть эта карточка"""
    try:
        result = db_operation(
            "SELECT COUNT(*) FROM user_cards WHERE card_id = ?",
            (card_id,),
            fetch=True
        )
        
        if result:
            return result[0][0]
        return 0
        
    except Exception as e:
        logger.error(f"Ошибка при получении количества владельцев карточки {card_id}: {e}")
        return None
    
def get_specific_card_image(card_nickname: str, rarity: str) -> str:
    """
    Получает конкретный PNG файл для карточки по никнейму игрока.
    Для редкости EEA ищет файлы, начинающиеся с 'fk.EEA'.
    Если не найден - возвращает случайный по редкости.
    
    Args:
        card_nickname: никнейм игрока (например "DonbazZ")
        rarity: редкость карточки (например "Эпический" или "EEA")
    
    Returns:
        Путь к файлу PNG или None если не найден
    """
    try:
        # Папка с карточками
        cards_dir = os.path.join(BASE_DIR, "mamo_cards_files")
        
        if not os.path.exists(cards_dir):
            logger.error(f"Папка с карточками не найдена: {cards_dir}")
            return get_random_card_image(rarity)
        
        # --- НОВАЯ ЛОГИКА ДЛЯ EEA ---
        if rarity.upper() == 'EEA':
            logger.info(f"🔍 Поиск EEA карточки для игрока '{card_nickname}'")
            
            possible_extensions = ['.png', '.jpg', '.jpeg']
            
            # Проходим по всем файлам в директории
            for filename in os.listdir(cards_dir):
                # Проверяем, начинается ли имя файла с 'fk.EEA' (регистронезависимо)
                if filename.lower().startswith('fk.eea_'):
                    # Проверяем, содержит ли файл имя игрока (опционально, для точного соответствия)
                    file_path = os.path.join(cards_dir, filename)
                    
                    # Вариант 1: Ищем файл, содержащий имя игрока после префикса
                    # Например: fk.EEA_Molan.png, fk.EEA_DonbazZ.jpg
                    if card_nickname.lower() in filename.lower():
                        logger.info(f"✅ Найдена EEA карточка для игрока {card_nickname}: {filename}")
                        return file_path
                    
                    # Вариант 2: Если хотим просто первый попавшийся fk.EEA файл
                    # (раскомментируй, если нужен этот вариант)
                    # logger.info(f"✅ Найден EEA файл (первый попавшийся): {filename}")
                    # return file_path
            
            # Если не нашли файл с именем игрока, ищем любой EEA файл как запасной вариант
            logger.warning(f"⚠️ Не найдена EEA карточка специально для '{card_nickname}', ищу любой EEA файл...")
            for filename in os.listdir(cards_dir):
                if filename.lower().startswith('fk.eea'):
                    file_path = os.path.join(cards_dir, filename)
                    logger.info(f"✅ Найден запасной EEA файл: {filename}")
                    return file_path
            
            # Если не нашли ни одного EEA файла
            logger.warning(f"⚠️ Не найден ни один файл, начинающийся с 'fk.EEA'")
            return get_random_card_image(rarity)
        
        # --- СТАНДАРТНАЯ ЛОГИКА ДЛЯ ОСТАЛЬНЫХ РЕДКОСТЕЙ ---
        else:
            # 1. Попробовать найти по точному имени файла (с учетом разных расширений)
            possible_extensions = ['.png', '.jpg', '.jpeg']
            
            for ext in possible_extensions:
                # Вариант 1: Точное совпадение никнейма
                exact_filename = f"{card_nickname}{ext}"
                exact_path = os.path.join(cards_dir, exact_filename)
                
                if os.path.exists(exact_path):
                    logger.info(f"✅ Найдена конкретная карточка: {exact_filename}")
                    return exact_path
                
                # Вариант 2: Никнейм в нижнем регистре
                lower_filename = f"{card_nickname.lower()}{ext}"
                lower_path = os.path.join(cards_dir, lower_filename)
                
                if os.path.exists(lower_path):
                    logger.info(f"✅ Найдена карточка (нижний регистр): {lower_filename}")
                    return lower_path
                
                # Вариант 3: Без пробелов и специальных символов
                clean_nickname = card_nickname.replace(' ', '_').replace('(', '').replace(')', '')
                clean_filename = f"{clean_nickname}{ext}"
                clean_path = os.path.join(cards_dir, clean_filename)
                
                if os.path.exists(clean_path):
                    logger.info(f"✅ Найдена карточка (очищенный ник): {clean_filename}")
                    return clean_path
                
                # Вариант 4: Только латинские буквы (для кириллицы)
                if any(ord(c) > 127 for c in card_nickname):  # Есть не-латинские символы
                    latin_nickname = card_nickname.replace('е', 'e').replace('а', 'a').replace('о', 'o')
                    latin_filename = f"{latin_nickname}{ext}"
                    latin_path = os.path.join(cards_dir, latin_filename)
                    
                    if os.path.exists(latin_path):
                        logger.info(f"✅ Найдена карточка (латиница): {latin_filename}")
                        return latin_path
            
            # 2. Если не нашли конкретную карточку - поискать по клубным карточкам
            # Получаем клуб игрока из базы данных
            result = db_operation(
                "SELECT club FROM players_catalog WHERE nickname = ?",
                (card_nickname,),
                fetch=True
            )
            
            if result:
                club = result[0][0]
                # Ищем карточку клуба
                club_filenames = [
                    f"{club}{ext}" for ext in possible_extensions
                ]
                
                for club_file in club_filenames:
                    club_path = os.path.join(cards_dir, club_file)
                    if os.path.exists(club_path):
                        logger.info(f"✅ Найдена клубная карточка: {club_file}")
                        return club_path
            
            # 3. Если все еще не нашли - используем старую логику (по редкости)
            logger.warning(f"⚠️ Не найдена конкретная карточка для '{card_nickname}', ищу по редкости '{rarity}'")
            return get_random_card_image(rarity)
        
    except Exception as e:
        logger.error(f"❌ Ошибка при поиске карточки для '{card_nickname}': {e}")
        return get_random_card_image(rarity)
    
def get_random_card_image(rarity: str) -> str:
    """
    Возвращает путь к случайному PNG файлу карточки в зависимости от редкости.
    """
    try:
        # Папка с карточками
        cards_dir = os.path.join(BASE_DIR, "mamo_cards_files")
        
        if not os.path.exists(cards_dir):
            logger.error(f"Папка с карточками не найдена: {cards_dir}")
            return None
        
        # Префиксы файлов в зависимости от редкости
        prefix_map = {
            # Основные варианты (с учетом разных написаний)
            'Редкий': ['fk.GREEN.', 'green.', 'зеленый.', 'редкий.'],
            'Эпический': ['fk.PURPLE.', 'purple.', 'фиолетовый.', 'эпический.', 'эпическая.'],
            'Легендарный': ['fk.YELLOW.', 'yellow.', 'желтый.', 'легендарный.'],
            'Суперлегендарный': ['fk.RED.', 'red.', 'красный.', 'суперлегендарный.', 'супер.'],
        }
        
        # Приводим редкость к нижнему регистру для поиска
        rarity_lower = rarity.lower()
        
        # Определяем префикс на основе редкости
        selected_prefixes = None
        
        # Поиск подходящей редкости
        for key_prefixes in prefix_map.values():
            for prefix_variant in key_prefixes:
                # Проверяем содержит ли редкость ключевые слова
                if any(keyword in rarity_lower for keyword in ['супер', 'красный', 'red']):
                    selected_prefixes = prefix_map['Суперлегендарный']
                    break
                elif any(keyword in rarity_lower for keyword in ['легенд', 'желт', 'yellow']):
                    selected_prefixes = prefix_map['Легендарный']
                    break
                elif any(keyword in rarity_lower for keyword in ['эпич', 'фиолет', 'purple']):
                    selected_prefixes = prefix_map['Эпический']
                    break
                elif any(keyword in rarity_lower for keyword in ['редк', 'зелен', 'green']):
                    selected_prefixes = prefix_map['Редкий']
                    break
        
        # Если не определили, используем эпический как дефолт
        if not selected_prefixes:
            selected_prefixes = prefix_map['Эпический']
            logger.warning(f"Не удалось определить редкость '{rarity}', использую 'Эпический'")
        
        # Ищем файлы со всеми возможными префиксами для этой редкости
        matching_files = []
        for prefix in selected_prefixes:
            for file in os.listdir(cards_dir):
                file_lower = file.lower()
                if (file_lower.endswith('.png') or file_lower.endswith('.jpg') or file_lower.endswith('.jpeg')) and file_lower.startswith(prefix.lower()):
                    matching_files.append(file)
        
        if not matching_files:
            logger.error(f"❌ Не найдены файлы для редкости '{rarity}' с префиксами: {selected_prefixes}")
            logger.error(f"   В папке есть файлы: {os.listdir(cards_dir)[:10]}...")
            
            # Попробуем найти любую картинку в папке
            all_images = [f for f in os.listdir(cards_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            if all_images:
                logger.warning(f"⚠️ Использую случайную картинку из {len(all_images)} доступных")
                random_file = random.choice(all_images)
                file_path = os.path.abspath(os.path.join(cards_dir, random_file))
                return file_path
            else:
                logger.error("❌ В папке нет картинок!")
                return None
        
        # Выбираем случайный файл
        random_file = random.choice(matching_files)
        file_path = os.path.abspath(os.path.join(cards_dir, random_file))
        
        logger.info(f"✅ Выбран файл: {random_file} для редкости '{rarity}'")
        return file_path
        
    except Exception as e:
        logger.error(f"❌ Ошибка при поиске карточки для редкости '{rarity}': {e}")
        return None 
    


@public_router_admins.message(Command("reset"))
@require_role("старший-администратор")
@log_admin_action("Сброс кулдауна")
async def reset_cooldown_command(message: Message, state: FSMContext):
    """Сброс кулдауна для пользователя (админская команда)"""
    user_id = message.from_user.id
    
    # Проверяем, является ли пользователь администратором
    
    # Получаем текст команды и аргументы
    command_text = message.text.strip()
    args = command_text.split()[1:]  # Получаем все аргументы после /reset
    
    # Проверяем, указан ли ID пользователя
    if len(args) >= 1:
        try:
            # Пытаемся получить ID из первого аргумента
            target_user_id = int(args[0])
            
            # Получаем информацию о пользователе из базы данных
            user_info = None
            try:
                result = db_operation(
                    "SELECT username, first_name FROM all_users WHERE id = ?",
                    (target_user_id,),
                    fetch=True
                )
                if result:
                    username, first_name = result[0]
                    user_info = f"@{username}" if username else (first_name or f"ID: {target_user_id}")
            except Exception as e:
                logger.error(f"Ошибка при получении информации о пользователе {target_user_id}: {e}")
            
            target_user_name = user_info or f"ID: {target_user_id}"
            
            # Сбрасываем кулдаун
            if reset_fammo_cooldown(target_user_id):
                # Получаем статистику коллекции пользователя
                stats = get_user_card_stats(target_user_id)
                stats_text = ""
                if stats:
                    stats_text = f"\n📊 <b>Коллекция:</b> {stats['user_cards']}/{stats['total_cards']} карточек ({stats['completion_percentage']}%)"
                
                await message.reply(
                    f"✅ <b>Кулдаун сброшен!</b>\n\n"
                    f"👤 <b>Пользователь:</b> {target_user_name}\n"
                    f"🆔 <b>ID:</b> <code>{target_user_id}</code>"
                    f"{stats_text}\n\n"
                    f"Теперь пользователь может получить карточку <code>фмамо</code> немедленно.",
                    parse_mode="html"
                )
                logger.warning(f"👑 Админ {user_id} сбросил кулдаун пользователю {target_user_id} ({target_user_name})")
            else:
                await message.reply(
                    f"❌ Не удалось сбросить кулдаун для пользователя {target_user_name} (ID: {target_user_id}).\n"
                    f"Возможно, пользователь еще не получал карточки или не существует в базе.",
                    parse_mode="html"
                )
            
        except ValueError:
            await message.reply(
                "❌ <b>Неверный формат ID!</b>\n\n"
                "ID пользователя должен быть числом.\n"
                "Пример: <code>/reset 123456789</code>",
                parse_mode="html"
            )
        except Exception as e:
            logger.error(f"Ошибка при сбросе кулдауна: {e}")
            await message.reply(
                f"❌ Произошла ошибка при сбросе кулдауна: {str(e)[:100]}",
                parse_mode="html"
            )
    
    # Если нет аргументов, показываем справку
    else:
        await message.reply(
            "📝 <b>Использование команды:</b>\n\n"
            "<b>Формат:</b>\n"
            "<code>/reset &lt;user_id&gt;</code>\n\n"
            "<b>Примеры:</b>\n"
            "• <code>/reset 123456789</code> - сбросить кулдаун для пользователя с ID 123456789\n"
            "• <code>/reset 1088006569</code> - сбросить кулдаун для указанного ID\n\n"
            "<i>⚠️ Команда доступна только администраторам</i>",
            parse_mode="html"
        )

def get_all_cards_from_db():
    """Получает все карточки из базы данных"""
    try:
        result = db_operation(
            """SELECT id, nickname, club, position, rarity 
               FROM players_catalog 
               ORDER BY 
                 CASE rarity 
                   WHEN 'EEA' THEN 1  -- EEA на первом месте
                   WHEN 'Суперлегендарный' THEN 2
                   WHEN 'Легендарный' THEN 3
                   WHEN 'Эпический' THEN 4
                   WHEN 'Редкий' THEN 5
                   ELSE 6
                 END,
                 nickname""",
            fetch=True
        )
        
        if not result:
            return []
        
        cards = []
        for row in result:
            card_id, nickname, club, position, rarity = row
            cards.append({
                'id': card_id,
                'nickname': nickname,
                'club': club,
                'position': position,
                'rarity': rarity
            })
        
        return cards
        
    except Exception as e:
        logger.error(f"Ошибка при получении всех карточек: {e}")
        return []
async def show_cards_page(message_or_callback, all_cards: list, page: int = 0, total_pages: int = 1):
    """Показывает страницу с карточками"""
    try:
        cards_per_page = 10
        total_cards = len(all_cards)
        
        # Проверяем корректность страницы
        if page < 0:
            page = 0
        elif page >= total_pages:
            page = total_pages - 1
        
        page_number = page + 1
        
        # Вычисляем индексы для текущей страницы
        start_idx = page * cards_per_page
        end_idx = min(start_idx + cards_per_page, total_cards)
        
        # Получаем карточки для текущей страницы
        page_cards = all_cards[start_idx:end_idx]
        
        # Формируем заголовок
        header = (
            f"📚 <b>ВСЕ КАРТОЧКИ</b>\n\n"
            f"📊 <b>Всего карточек:</b> {total_cards}\n"
            f"📄 <b>Страница:</b> {page_number}/{total_pages}\n"
            f"👁️ <b>Показывается:</b> {start_idx + 1}-{end_idx}\n\n"
        )
        
        # Формируем список карточек
        cards_text = ""
        
        for idx, card in enumerate(page_cards, start_idx + 1):
            rarity_display = 'Эпический' if card['rarity'] == 'эпическая' else card['rarity']
            
            # Проверяем, есть ли картинка для этой карточки
            has_image = False
            try:
                image_path = get_specific_card_image(card['nickname'], rarity_display)
                if image_path and os.path.exists(image_path):
                    has_image = True
            except:
                pass
            
            image_icon = "🖼️" if has_image else "📝"
            
            cards_text += (
                f"{image_icon} <b>{idx}. {card['nickname']}</b>\n"
                f"   🆔 <code>{card['id']}</code> | 🏟️ {card['club']} | 🎯 {card['position']} | 💎 {rarity_display}\n"
                f"   📋 <code>/getcard {card['nickname']}</code>\n\n"
            )
        
        message_text = header + cards_text
        
        # Создаем inline-клавиатуру
        builder = InlineKeyboardBuilder()
        
        # Кнопки навигации
        nav_buttons = []
        
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data=f"allcards_page_{page - 1}"
                )
            )
        
        nav_buttons.append(
            InlineKeyboardButton(
                text=f"📄 {page_number}/{total_pages}",
                callback_data="noop"
            )
        )
        
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="Вперед ➡️",
                    callback_data=f"allcards_page_{page + 1}"
                )
            )
        
        if nav_buttons:
            builder.row(*nav_buttons)
        
        # Дополнительные кнопки
        action_buttons = []
        
        action_buttons.append(
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data=f"allcards_refresh_{page}"
            )
        )
        
        builder.row(*action_buttons)
        
        # Если это callback - редактируем сообщение
        if hasattr(message_or_callback, 'message'):
            await message_or_callback.message.edit_text(
                message_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
            await message_or_callback.answer(f"Страница {page_number}")
        # Если это команда - отправляем новое сообщение
        else:
            await message_or_callback.reply(
                message_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
        
    except Exception as e:
        logger.error(f"Ошибка в show_cards_page: {e}")
        if hasattr(message_or_callback, 'answer'):
            await message_or_callback.answer("❌ Ошибка при загрузке страницы", show_alert=True)

    
def reset_fammo_cooldown(user_id: int):
    """Сбрасывает кулдаун для пользователя"""
    try:
        db_operation(
            "DELETE FROM user_card_cooldowns WHERE user_id = ?",
            (user_id,)
        )
        logger.info(f"Кулдаун сброшен для пользователя {user_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при сбросе кулдауна для пользователя {user_id}: {e}")
        return False

def get_fammo_cooldown_status(user_id: int):
    """Получает информацию о кулдауне пользователя с учетом московского времени"""
    try:
        # Проверяем бан
        if is_user_banned(user_id):
            ban_info = get_ban_info(user_id)
            ban_reason = ban_info['ban_reason'] if ban_info else "Пользователь забанен"
            
            return {
                'has_cooldown': False,
                'last_fammo': None,
                'next_fammo': None,
                'remaining': None,
                'can_get_now': False,
                'is_banned': True,
                'ban_reason': ban_reason,
                'ban_info': ban_info
            }
        
        # Остальная существующая логика
        result = db_operation(
            """SELECT last_fammo_at, next_fammo_at 
               FROM user_card_cooldowns 
               WHERE user_id = ?""",
            (user_id,),
            fetch=True
        )
        
        if not result:
            return {
                'has_cooldown': False,
                'last_fammo': None,
                'next_fammo': None,
                'remaining': None,
                'can_get_now': True,
                'is_banned': False
            }
        
        last_fammo_at_str, next_fammo_at_str = result[0]
        
        if not last_fammo_at_str or not next_fammo_at_str:
            return {
                'has_cooldown': False,
                'last_fammo': None,
                'next_fammo': None,
                'remaining': None,
                'can_get_now': True,
                'is_banned': False
            }
        
        from datetime import datetime
        
        def parse_time(time_str):
            try:
                dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                return pytz.UTC.localize(dt)
            except:
                try:
                    dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S.%f')
                    return pytz.UTC.localize(dt)
                except:
                    return None
        
        last_fammo_utc = parse_time(last_fammo_at_str)
        next_fammo_utc = parse_time(next_fammo_at_str)
        
        if not last_fammo_utc or not next_fammo_utc:
            return {
                'has_cooldown': False,
                'last_fammo': None,
                'next_fammo': None,
                'remaining': None,
                'can_get_now': True,
                'is_banned': False
            }
        
        # Конвертируем в московское время
        moscow_tz = pytz.timezone('Europe/Moscow')
        last_fammo = last_fammo_utc.astimezone(moscow_tz)
        next_fammo = next_fammo_utc.astimezone(moscow_tz)
        now = datetime.now(pytz.UTC).astimezone(moscow_tz)
        
        remaining = next_fammo - now if next_fammo > now else None
        can_get_now = now >= next_fammo
        
        return {
            'has_cooldown': True,
            'last_fammo': last_fammo,
            'next_fammo': next_fammo,
            'remaining': remaining,
            'can_get_now': can_get_now,
            'is_banned': False
        }
    except Exception as e:
        logger.error(f"Ошибка при получении статуса кулдауна для пользователя {user_id}: {e}")
        return {
            'has_cooldown': False,
            'last_fammo': None,
            'next_fammo': None,
            'remaining': None,
            'can_get_now': True,
            'is_banned': False
        }
    
def get_user_card_stats(user_id: int) -> dict:
    """
    Получает статистику карточек пользователя.
    Возвращает словарь с ключами:
    - user_cards: количество карточек у пользователя
    - total_cards: всего карточек в каталоге
    - completion_percentage: процент заполнения коллекции
    - rarity_stats: статистика по редкостям (всегда словарь)
    """
    try:
        # Получаем количество карточек у пользователя
        result = db_operation(
            "SELECT COUNT(*) FROM user_cards WHERE user_id = ?",
            (user_id,),
            fetch=True
        )
        user_cards = result[0][0] if result else 0
        
        # Получаем общее количество карточек в каталоге
        result = db_operation(
            "SELECT COUNT(*) FROM players_catalog",
            fetch=True
        )
        total_cards = result[0][0] if result else 0
        
        # Рассчитываем процент заполнения
        completion_percentage = round((user_cards / total_cards * 100), 1) if total_cards > 0 else 0
        
        # Получаем статистику по редкостям
        rarity_stats = {}
        try:
            result = db_operation(
                """SELECT 
                    CASE 
                        WHEN pc.rarity = 'эпическая' THEN 'Эпический'
                        ELSE pc.rarity 
                    END as rarity,
                    COUNT(*) as count
                   FROM user_cards uc
                   JOIN players_catalog pc ON uc.card_id = pc.id
                   WHERE uc.user_id = ?
                   GROUP BY 
                    CASE 
                        WHEN pc.rarity = 'эпическая' THEN 'Эпический'
                        ELSE pc.rarity 
                    END""",
                (user_id,),
                fetch=True
            )
            
            if result:
                for rarity, count in result:
                    # Нормализуем названия редкостей
                    rarity_display = rarity
                    if rarity == 'эпическая':
                        rarity_display = 'Эпический'
                    
                    rarity_stats[rarity_display] = count
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики редкостей для пользователя {user_id}: {e}")
        
        # Всегда возвращаем словарь с rarity_stats
        return {
            'user_cards': user_cards,
            'total_cards': total_cards,
            'completion_percentage': completion_percentage,
            'rarity_stats': rarity_stats  # Теперь это всегда будет словарем
        }
        
    except Exception as e:
        logger.error(f"Ошибка при получении статистики карточек пользователя {user_id}: {e}")
        # Возвращаем структуру по умолчанию даже при ошибке
        return {
            'user_cards': 0,
            'total_cards': 0,
            'completion_percentage': 0,
            'rarity_stats': {}
        }
