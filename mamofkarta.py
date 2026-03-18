from aiogram import Bot, Dispatcher, F, Router
import re
from aiogram.enums.chat_member_status import ChatMemberStatus
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import message

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
from mamodatabases import init_databases, logger, BASE_DIR, db_operation,log_command, log_admin_action, log_mute_action,log_profile_action, format_moscow_time,get_card_by_id,get_players_from_source,get_user_filter,save_user_filter,validate_input,seed_players_catalog, get_user_cards
from mamoadmins import is_user_banned, get_ban_info, get_mute_info, get_admin_role, get_all_muted_users, require_role, SupportStates, get_random_card_image, is_muted, unmute_user, get_card_by_nickname_db, getcard_command, get_specific_card_image,get_card_owners_count, get_all_cards_from_db,get_fammo_cooldown_status,get_user_card_stats, group_of_admins, add_user_coins, get_user_coins, get_purchase_history, subtract_user_coins, get_user_info, update_user_coins
import mamokeyboardsAmvera as kb


router_fkarta = Router()
router_fkarta.message.filter(F.chat.type == "private")
router_fkarta.callback_query.filter(F.message.chat.type == "private")


public_router_fkarta = Router()




@router_fkarta.message(Command("addpromo"))
@require_role("младший-администратор")
@log_admin_action("Создание промокода")
async def addpromo_command(message: Message):
    """Создание нового промокода"""
    command_text = message.text.strip()
    args = command_text.split()
    
    if len(args) < 3:
        await message.reply(
            "📝 <b>Использование команды:</b>\n\n"
            "<code>/addpromo [название] [коины] [использований]</code>\n\n"
            "<b>Примеры:</b>\n"
            "• <code>/addpromo WELCOME 50 100</code> - на 50 коинов, 100 использований\n"
            "• <code>/addpromo BONUS100 100 0</code> - на 100 коинов, безлимит\n"
            "• <code>/addpromo NEWYEAR 200 50</code> - на 200 коинов, 50 использований\n\n"
            "<b>Примечания:</b>\n"
            "• [использований] = 0 означает безлимитное использование\n"
            "• Название должно быть уникальным\n"
            "• Коины должны быть больше 0\n\n"
            "<i>Команда доступна только старшим администраторам</i>",
            parse_mode="html"
        )
        return
    
    try:
        code = args[1].strip()
        coins = int(args[2])
        
        # Проверяем количество использований (если указано)
        max_uses = 0
        if len(args) >= 4:
            max_uses = int(args[3])
        
        if coins <= 0:
            await message.reply("❌ Количество коинов должно быть больше 0")
            return
        
        if max_uses < 0:
            await message.reply("❌ Количество использований не может быть отрицательным")
            return
        
        # Добавляем промокод
        success, result_msg = add_promocode(code, coins, max_uses, message.from_user.id)
        
        if success:
            # Формируем детальную информацию о промокоде
            uses_info = "безлимит" if max_uses == 0 else f"{max_uses} использований"
            
            await message.reply(
                f"✅ <b>Промокод создан!</b>\n\n"
                f"<b>🧾 Название:</b> <code>{code}</code>\n"
                f"<b>💰 Коины:</b> {coins}\n"
                f"<b>🎯 Использований:</b> {uses_info}\n"
                f"<b>👨‍💼 Создатель:</b> @{message.from_user.username or message.from_user.first_name}\n\n"
                f"<i>Для использования: /promokode {code}</i>",
                parse_mode="html"
            )
            
            logger.warning(f"👑 Админ {message.from_user.id} создал промокод: {code} на {coins} коинов")
        else:
            await message.reply(f"❌ {result_msg}")
            
    except ValueError:
        await message.reply(
            "❌ <b>Неверный формат!</b>\n\n"
            "Коины и количество использований должны быть числами.\n"
            "Пример: <code>/addpromo WELCOME 50 100</code>",
            parse_mode="html"
        )
    except Exception as e:
        logger.error(f"Ошибка в команде /addpromo: {e}")
        await message.reply(f"❌ Ошибка: {str(e)[:100]}")

@router_fkarta.message(Command("deletepromo"))
@require_role("младший-администратор")
@log_admin_action("Удаление промокода")
async def deletepromo_command(message: Message):
    """Удаление промокода"""
    command_text = message.text.strip()
    args = command_text.split()
    
    if len(args) < 2:
        await message.reply(
            "📝 <b>Использование команды:</b>\n\n"
            "<code>/deletepromo [название]</code>\n\n"
            "<b>Примеры:</b>\n"
            "• <code>/deletepromo WELCOME</code>\n"
            "• <code>/deletepromo BONUS100</code>\n\n"
            "<b>Примечания:</b>\n"
            "• Промокод будет полностью удален из системы\n"
            "• Все записи об использовании также будут удалены\n"
            "• Действие необратимо!\n\n"
            "<i>Команда доступна только старшим администраторам</i>",
            parse_mode="html"
        )
        return
    
    try:
        code = args[1].strip()
        
        # Сначала получаем информацию о промокоде
        promocode_info = get_promocode_info(code)
        if not promocode_info:
            await message.reply(f"❌ Промокод '{code}' не найден")
            return
        
        # Создаем клавиатуру для подтверждения
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="✅ Да, удалить",
                callback_data=f"confirm_delete_promo_{code}"
            ),
            InlineKeyboardButton(
                text="❌ Нет, отменить",
                callback_data="cancel_delete_promo"
            )
        )
        
        await message.reply(
            f"⚠️ <b>ВНИМАНИЕ!</b>\n\n"
            f"Вы собираетесь удалить промокод:\n\n"
            f"<b>🧾 Название:</b> <code>{code}</code>\n"
            f"<b>💰 Коины:</b> {promocode_info['coins']}\n"
            f"<b>📊 Использован:</b> {promocode_info['used_count']} раз\n"
            f"<b>👨‍💼 Создатель:</b> {promocode_info['creator']}\n\n"
            f"<b>Это действие необратимо!</b>\n\n"
            f"Вы уверены, что хотите удалить этот промокод?",
            parse_mode="html",
            reply_markup=builder.as_markup()
        )
        
    except Exception as e:
        logger.error(f"Ошибка в команде /deletepromo: {e}")
        await message.reply(f"❌ Ошибка: {str(e)[:100]}")
@router_fkarta.callback_query(F.data.startswith("confirm_delete_promo_"))
async def confirm_delete_promo_callback(callback: CallbackQuery):
    """Подтверждение удаления промокода"""
    try:
        code = callback.data.split("_", 3)[3]
        
        # Удаляем промокод
        success, result_msg = delete_promocode(code)
        
        if success:
            await callback.message.edit_text(
                f"✅ <b>Промокод удален!</b>\n\n"
                f"{result_msg}",
                parse_mode="html"
            )
            
            logger.warning(f"👑 Админ {callback.from_user.id} удалил промокод: {code}")
        else:
            await callback.message.edit_text(
                f"❌ <b>Ошибка удаления!</b>\n\n"
                f"{result_msg}",
                parse_mode="html"
            )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в confirm_delete_promo_callback: {e}")
        await callback.answer("❌ Ошибка при удалении", show_alert=True)

@router_fkarta.callback_query(F.data == "cancel_delete_promo")
async def cancel_delete_promo_callback(callback: CallbackQuery):
    """Отмена удаления промокода"""
    try:
        await callback.message.edit_text(
            "❌ <b>Удаление отменено</b>\n\n"
            "<i>Промокод не был удален</i>",
            parse_mode="html"
        )
        await callback.answer("Удаление отменено")
        
    except Exception as e:
        logger.error(f"Ошибка в cancel_delete_promo_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)
#============================
#СИСТЕМА ПРОМОКОДОВ

def add_promocode(code: str, coins: int, max_uses: int = 0, created_by: int = None):
    """Добавляет новый промокод в базу данных"""
    try:
        # Проверяем, существует ли уже такой промокод
        existing = db_operation(
            "SELECT id FROM promocodes WHERE LOWER(code) = LOWER(?)",
            (code,),
            fetch=True
        )
        
        if existing:
            return False, "Промокод с таким названием уже существует"
        
        # Проверяем валидность данных
        if coins <= 0:
            return False, "Количество коинов должно быть больше 0"
        
        if max_uses < 0:
            return False, "Количество использований не может быть отрицательным"
        
        # Добавляем промокод в базу
        db_operation(
            """INSERT INTO promocodes 
               (code, coins, max_uses, used_count, created_by, is_active) 
               VALUES (?, ?, ?, 0, ?, 1)""",
            (code, coins, max_uses, created_by)
        )
        
        logger.info(f"✅ Добавлен промокод: '{code}' на {coins} коинов (макс. использований: {max_uses if max_uses > 0 else 'безлимит'})")
        return True, f"Промокод '{code}' успешно создан на {coins} коинов"
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении промокода '{code}': {e}")
        return False, f"Ошибка: {str(e)[:100]}"
    
def delete_promocode(code: str):
    """Удаляет промокод из базы данных"""
    try:
        # Находим промокод
        result = db_operation(
            "SELECT id, code, coins, used_count FROM promocodes WHERE LOWER(code) = LOWER(?)",
            (code,),
            fetch=True
        )
        
        if not result:
            return False, "Промокод не найден"
        
        promocode_id, code_name, coins, used_count = result[0]
        
        # Удаляем промокод
        db_operation(
            "DELETE FROM promocodes WHERE id = ?",
            (promocode_id,)
        )
        
        # Также удаляем записи об использовании (каскадное удаление)
        db_operation(
            "DELETE FROM promocode_usage WHERE promocode_id = ?",
            (promocode_id,)
        )
        
        logger.info(f"🗑️ Удален промокод: '{code_name}' (использован {used_count} раз, начислено {coins} коинов)")
        return True, f"Промокод '{code_name}' удален (был использован {used_count} раз)"
        
    except Exception as e:
        logger.error(f"Ошибка при удалении промокода '{code}': {e}")
        return False, f"Ошибка: {str(e)[:100]}"

def use_promocode(code: str, user_id: int):
    """Активирует промокод для пользователя и начисляет коины"""
    try:
        # Находим активный промокод
        result = db_operation(
            """SELECT id, code, coins, max_uses, used_count 
               FROM promocodes 
               WHERE LOWER(code) = LOWER(?) AND is_active = 1""",
            (code,),
            fetch=True
        )
        
        if not result:
            return False, "Промокод не найден или неактивен"
        
        promocode_id, code_name, coins, max_uses, used_count = result[0]
        
        # Проверяем, использовал ли уже этот пользователь этот промокод
        usage_check = db_operation(
            "SELECT id FROM promocode_usage WHERE promocode_id = ? AND user_id = ?",
            (promocode_id, user_id),
            fetch=True
        )
        
        if usage_check:
            return False, "Вы уже использовали этот промокод"
        
        # Проверяем лимит использований (если max_uses > 0)
        if max_uses > 0 and used_count >= max_uses:
            return False, "Лимит использований промокода исчерпан"
        
        # Начисляем коины пользователю
        success = add_user_coins(user_id, coins)
        if not success:
            return False, "Ошибка при начислении коинов"
        
        # Обновляем счетчик использований промокода
        db_operation(
            "UPDATE promocodes SET used_count = used_count + 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (promocode_id,)
        )
        
        # Записываем факт использования
        db_operation(
            "INSERT INTO promocode_usage (promocode_id, user_id) VALUES (?, ?)",
            (promocode_id, user_id)
        )
        
        logger.info(f"🎁 Пользователь {user_id} использовал промокод '{code_name}' (+{coins} коинов)")
        
        # Получаем обновленный баланс пользователя
        user_coins = get_user_coins(user_id)
        
        return True, {
            'success': True,
            'message': f"✅ Промокод активирован!\nВы получили {coins} мамокоинов\n\n💰 Ваш баланс: {user_coins} мамокоинов",
            'code': code_name,
            'coins': coins,
            'user_id': user_id,
            'new_balance': user_coins
        }
        
    except Exception as e:
        logger.error(f"Ошибка при использовании промокода '{code}' пользователем {user_id}: {e}")
        return False, f"Ошибка активации промокода"
async def send_promocode_notification_to_admin(bot: Bot, user_id: int, user_name: str, 
                                              promocode: str, coins: int, promocode_info: dict = None):
    """Отправляет уведомление администратору об использовании промокода"""
    try:
        # Формируем сообщение для администратора
        admin_message = (
            f"🎁 <b>ПРОМОКОД ИСПОЛЬЗОВАН!</b>\n\n"
            f"<b>👤 Пользователь:</b> @{user_name}\n"
            f"<b>🆔 ID пользователя:</b> <code>{user_id}</code>\n\n"
            f"<b>🧾 Промокод:</b> <code>{promocode}</code>\n"
            f"<b>💰 Получено коинов:</b> {coins}\n\n"
        )
        
        # Добавляем дополнительную информацию о промокоде, если есть
        if promocode_info:
            admin_message += (
                f"<b>📊 Статистика промокода:</b>\n"
                f"• Всего использований: {promocode_info.get('used_count', 0)}\n"
                f"• Макс. использований: {promocode_info.get('max_uses_display', 'безлимит')}\n"
                f"• Осталось использований: {promocode_info.get('uses_left', 'безлимит')}\n\n"
            )
        
        admin_message += (
            f"<b>⏰ Время активации:</b> {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}\n\n"
            f"<i>Для проверки пользователя: /checkuser {user_id}</i>"
        )
        
        # Отправляем сообщение администратору
        await bot.send_message(
            chat_id=1088006569,
            text=admin_message,
            parse_mode="html"
        )
        
        logger.info(f"📨 Отправлено уведомление администратору об использовании промокода '{promocode}' пользователем {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке уведомления администратору: {e}")
def get_promocode_info(code: str):
    """Получает детальную информацию о промокоде"""
    try:
        result = db_operation(
            """SELECT id, code, coins, max_uses, used_count, 
                      created_at, is_active,
                      CASE 
                          WHEN max_uses = 0 THEN '∞'
                          ELSE CAST(max_uses AS TEXT)
                      END as max_uses_display,
                      CASE 
                          WHEN max_uses = 0 THEN 'безлимит'
                          WHEN used_count >= max_uses THEN 'исчерпан'
                          ELSE CONCAT(CAST((max_uses - used_count) AS TEXT), ' из ', CAST(max_uses AS TEXT))
                      END as uses_left
               FROM promocodes 
               WHERE LOWER(code) = LOWER(?)""",
            (code,),
            fetch=True
        )
        
        if not result:
            return None
        
        (promocode_id, code_name, coins, max_uses, used_count, 
         created_at, is_active, max_uses_display, uses_left) = result[0]
        
        # Получаем информацию о создателе
        creator_info = db_operation(
            "SELECT username FROM all_users WHERE id = (SELECT created_by FROM promocodes WHERE id = ?)",
            (promocode_id,),
            fetch=True
        )
        
        creator = creator_info[0][0] if creator_info and creator_info[0][0] else "Неизвестно"
        
        return {
            'id': promocode_id,
            'code': code_name,
            'coins': coins,
            'max_uses': max_uses,
            'used_count': used_count,
            'created_at': created_at,
            'is_active': bool(is_active),
            'creator': creator,
            'max_uses_display': max_uses_display,
            'uses_left': uses_left,
            'status': "✅ Активен" if is_active else "❌ Неактивен"
        }
        
    except Exception as e:
        logger.error(f"Ошибка при получении информации о промокоде '{code}': {e}")
        return None



def can_get_fammo_card(user_id: int) -> tuple:
    """
    Проверяет, может ли пользователь получить карточку фмамо.
    Возвращает (может_ли, время_доступности, причина_отказа)
    """
    try:
        # Проверяем, не забанен ли пользователь
        if is_user_banned(user_id):
            return False, None, "пользователь забанен"
        
        # Остальная существующая логика проверки кулдауна
        result = db_operation(
            """SELECT last_fammo_at, next_fammo_at 
               FROM user_card_cooldowns 
               WHERE user_id = ?""",
            (user_id,),
            fetch=True
        )
        
        if not result:
            return True, None, None
        
        last_fammo_at_str, next_fammo_at_str = result[0]
        
        if not last_fammo_at_str or not next_fammo_at_str:
            return True, None, None
        
        # Преобразуем строки времени в datetime объекты
        def parse_sqlite_time(time_str):
            try:
                return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
            except:
                return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S.%f')
        
        next_fammo_at = parse_sqlite_time(next_fammo_at_str)
        now = datetime.now()
        
        if now >= next_fammo_at:
            return True, None, None
        else:
            # Вычисляем оставшееся время
            remaining = next_fammo_at - now
            return False, remaining, "кулдаун не истек"
            
    except Exception as e:
        logger.error(f"Ошибка при проверке кулдауна для пользователя {user_id}: {e}")
        return False, None, "ошибка проверки"

def update_fammo_cooldown(user_id: int, cooldown_hours: int = 4):
    """Обновляет время кулдауна для пользователя (теперь 4 часа)"""
    try:
        from datetime import datetime, timedelta
        
        # Получаем текущее время в UTC
        now_utc = datetime.now(pytz.UTC)
        next_fammo_utc = now_utc + timedelta(hours=cooldown_hours)
        
        # Форматируем для SQLite (храним в UTC)
        now_str = now_utc.strftime('%Y-%m-%d %H:%M:%S')
        next_str = next_fammo_utc.strftime('%Y-%m-%d %H:%M:%S')
        
        db_operation(
            """INSERT OR REPLACE INTO user_card_cooldowns 
               (user_id, last_fammo_at, next_fammo_at) 
               VALUES (?, ?, ?)""",
            (user_id, now_str, next_str)
        )
        logger.info(f"Кулдаун обновлен для пользователя {user_id}: следующая карточка через {cooldown_hours}ч")
        return True
    except Exception as e:
        logger.error(f"Ошибка при обновлении кулдауна для пользователя {user_id}: {e}")
        return False



def format_cooldown_time(seconds: float) -> str:
    """Форматирует время в читаемый вид"""
    if seconds is None or seconds <= 0:
        return "сейчас"
    
    try:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        
        parts = []
        if hours > 0:
            parts.append(f"{hours}ч")
        if minutes > 0:
            parts.append(f"{minutes}м")
        
        if seconds < 60:
            secs = int(seconds)
            parts.append(f"{secs}с")
        
        return " ".join(parts) if parts else "менее 1 секунды"
    except:
        return "неизвестное время"
    



def add_card_to_user(user_id: int, card_id: int):
    """Добавляет карточку пользователю"""
    try:
        db_operation(
            """INSERT OR IGNORE INTO user_cards (user_id, card_id) 
               VALUES (?, ?)""",
            (user_id, card_id)
        )
        logger.info(f"Карточка {card_id} добавлена пользователю {user_id}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при добавлении карточки {card_id} пользователю {user_id}: {e}")
        return False

def get_user_missing_cards(user_id: int):
    """Получает карточки, которых нет у пользователя"""
    try:
        result = db_operation(
            """SELECT pc.id, pc.nickname, pc.club, pc.position, pc.rarity
               FROM players_catalog pc
               WHERE pc.id NOT IN (
                   SELECT card_id FROM user_cards WHERE user_id = ?
               )
               ORDER BY 
                 CASE pc.rarity 
                   WHEN 'Суперлегендарный' THEN 1
                   WHEN 'Легендарный' THEN 2
                   WHEN 'Эпический' THEN 3
                   WHEN 'Редкий' THEN 4
                   ELSE 5
                 END,
                 pc.nickname""",
            (user_id,),
            fetch=True
        )
        return result if result else []
    except Exception as e:
        logger.error(f"Ошибка при получении недостающих карточек пользователя {user_id}: {e}")
        return []

def get_random_card_by_rarity():
    """Возвращает случайную карточку с учетом шансов по редкости"""
    try:
        # Получаем все карточки сгруппированные по редкости
        rarity_groups = {
            'Редкий': [],
            'Эпический': [],
            'Легендарный': [],
            'Суперлегендарный': []
        }
        
        result = db_operation(
            "SELECT id, nickname, club, position, rarity FROM players_catalog",
            fetch=True
        )
        
        if not result:
            return None
        
        # Группируем карточки по редкости
        for card in result:
            card_id, nickname, club, position, rarity = card
            if rarity in rarity_groups:
                rarity_groups[rarity].append({
                    'id': card_id,
                    'nickname': nickname,
                    'club': club,
                    'position': position,
                    'rarity': rarity
                })
            else:
                # Если редкость не из списка, считаем её Редкой
                rarity_groups['Редкий'].append({
                    'id': card_id,
                    'nickname': nickname,
                    'club': club,
                    'position': position,
                    'rarity': 'Редкий'
                })
        
        # Проверяем, есть ли карточки в группах
        total_cards = sum(len(cards) for cards in rarity_groups.values())
        if total_cards == 0:
            return None
        
        # Шансы для каждой редкости
        rarity_chances = {
        'Редкий': 49,   # Было 50, уменьшим для EEA
        'Эпический': 30,
        'Легендарный': 15,
        'Суперлегендарный': 5,
        'EEA': 1         # <--- ДОБАВЛЯЕМ НОВУЮ РЕДКОСТЬ С ШАНСОМ 1%
    }
        
        # Выбираем редкость с учетом шансов
        rand = random.randint(1, 100)
        selected_rarity = None
        
        if rand <= 5:  # 5% для суперлегендарных
            selected_rarity = 'Суперлегендарный'
        elif rand <= 20:  # 15% для легендарных (5+15=20)
            selected_rarity = 'Легендарный'
        elif rand <= 50:  # 30% для эпических (20+30=50)
            # Выбираем между двумя вариантами эпических
            selected_rarity = random.choice(['Эпический'])
        else:  # 50% для редких (оставшиеся 50%)
            selected_rarity = 'Редкий'
        
        # Проверяем, есть ли карточки выбранной редкости
        available_cards = rarity_groups.get(selected_rarity, [])
        
        # Если нет карточек выбранной редкости, ищем любую доступную
        if not available_cards:
            for rarity in ['Редкий', 'Эпический', 'Легендарный', 'Суперлегендарный']:
                if rarity_groups.get(rarity):
                    available_cards = rarity_groups[rarity]
                    selected_rarity = rarity
                    break
        
        if not available_cards:
            return None
        
        # Выбираем случайную карточку из доступных
        card = random.choice(available_cards)
        return card
        
    except Exception as e:
        logger.error(f"Ошибка при выборе случайной карточки: {e}")
        return None

def get_new_card_for_user(user_id: int):
    """Возвращает новую карточку для пользователя, которой у него ещё нет"""
    try:
        # Получаем все карточки пользователя
        user_cards = get_user_cards(user_id)
        user_card_ids = [card[0] for card in user_cards]  # nicknames
        
        # Получаем все карточки из каталога
        all_cards = db_operation(
            "SELECT id, nickname, club, position, rarity FROM players_catalog",
            fetch=True
        )
        
        if not all_cards:
            return None
        
        # Вычисляем шансы на основе редкости
        rarity_weights = {
        'Редкий': 49,   # Было 50
        'Эпический': 30,
        'Легендарный': 15,
        'Суперлегендарный': 5,
        'EEA': 1         # <--- ДОБАВЛЯЕМ
    }
        
        # Создаем список карточек с весами, исключая те, что уже есть у пользователя
        weighted_cards = []
        total_weight = 0
        
        for card in all_cards:
            card_id, nickname, club, position, rarity = card
            
            # Пропускаем карточки, которые уже есть у пользователя
            if nickname in user_card_ids:
                continue
            
            weight = rarity_weights.get(rarity, 50)  # по умолчанию 50 для неизвестных редкостей
            weighted_cards.append({
                'id': card_id,
                'nickname': nickname,
                'club': club,
                'position': position,
                'rarity': rarity,
                'weight': weight
            })
            total_weight += weight
        
        # Если у пользователя уже есть все карточки
        if not weighted_cards:
            return None
        
        # Выбираем карточку с учетом весов
        rand = random.uniform(0, total_weight)
        cumulative = 0
        
        for card in weighted_cards:
            cumulative += card['weight']
            if rand <= cumulative:
                return card
        
        # На всякий случай возвращаем последнюю карточку
        return weighted_cards[-1]
        
    except Exception as e:
        logger.error(f"Ошибка при выборе новой карточки для пользователя {user_id}: {e}")
        return None


@public_router_fkarta.message(F.text.lower() == "фмамо" or F.text.lower() == "fmamo")
async def fammo_command(message: Message, bot: Bot):
    """Обработчик команды фмамо - выдача случайной карточки раз в 4 часа (для ВСЕХ чатов)"""
    # Проверяем текст сообщения на команду фмамо
    text = message.text.strip().lower()
    
    # Проверяем различные варианты написания команды
    if text not in ["фмамо", "fmamo"]:
        # Дополнительные варианты, если нужно
        import re
        if not re.match(r'^(фмамо|fmamo)[!?.,:;]?$', text):
            return  # Это не команда фмамо
    
    # Логируем для отладки
    print(f"🎮 Получена команда фмамо от {message.from_user.id} (@{message.from_user.username}) в чате {message.chat.id} (тип: {message.chat.type})")
    user_id = message.from_user.id
    user_name = message.from_user.username or message.from_user.first_name or str(user_id)
    
    try:
        # ПЕРВОЕ: Проверяем, не забанен ли пользователь
        if is_user_banned(user_id):
            ban_info = get_ban_info(user_id)
            if ban_info:
                ban_reason = ban_info['ban_reason']
                banned_at = format_moscow_time(ban_info['banned_at']) if ban_info['banned_at'] else "Не указана"
                
                await message.reply(
                    f"🚫 <b>Вы забанены в боте MamoTinder!</b>\n\n"
                    f"📅 <b>Дата бана:</b> {banned_at}\n"
                    f"📝 <b>Причина:</b> {ban_reason}\n\n"
                    f"Для обжалования обратитесь: @kirik1231zzap",
                    parse_mode="html"
                )
            else:
                await message.reply(
                    "🚫 <b>Вы забанены в боте MamoTinder!</b>\n\n"
                    "Для обжалования обратитесь: @kirik1231zzap",
                    parse_mode="html"
                )
            return
        
        # ВТОРОЕ: Проверяем кулдаун
        cooldown_status = get_fammo_cooldown_status(user_id)
        
        # Проверяем, забанен ли пользователь (дополнительная проверка)
        if cooldown_status.get('is_banned', False):
            ban_reason = cooldown_status.get('ban_reason', 'Не указана')
            await message.reply(
                f"🚫 <b>Вы забанены в боте MamoTinder!</b>\n\n"
                f"📝 <b>Причина:</b> {ban_reason}\n\n"
                f"<i>Бан распространяется на все функции бота, включая получение фмамокарт.</i>\n\n"
                f"Для обжалования обратитесь: @kirik1231zzap",
                parse_mode="html"
            )
            return
        
        if not cooldown_status['can_get_now']:
            remaining = cooldown_status['remaining']
            if remaining:
                remaining_str = format_cooldown_time(remaining.total_seconds())
                
                await message.reply(
                    f"⏳ <b>Карточку можно получить раз в 4 часа</b>\n\n"
                    f"Вы уже получали карточку:\n"
                    f"<i>{cooldown_status['last_fammo'].strftime('%d.%m.%Y в %H:%M')} (по МСК)</i>\n\n"
                    f"⏰ <b>Следующая карточка будет доступна через:</b>\n"
                    f"<code>{remaining_str}</code>\n\n"
                    f"<i>Вернитесь позже!</i> 👀",
                    parse_mode="html"
                )
                return
        
        # Получаем новую карточку для пользователя
        new_card = get_new_card_for_user(user_id)
        
        if not new_card:
            # У пользователя уже есть все карточки
            stats = get_user_card_stats(user_id)
            
            # Все равно обновляем кулдаун
            update_fammo_cooldown(user_id)
            
            if stats and stats['user_cards'] > 0:
                await message.reply(
                    f"🎉 <b>Поздравляем!</b>\n\n"
                    f"Вы уже собрали <b>все {stats['total_cards']} карточек</b> из коллекции!\n\n"
                    f"📊 Ваша коллекция:\n"
                    f"• Полностью завершена (100%)\n\n"
                    f"⏰ <b>Следующая попытка:</b> через 4 часа\n\n"
                    f"<i>Вы настоящий коллекционер! 🏆</i>",
                    parse_mode="html"
                )
            else:
                await message.reply(
                    "❌ В базе данных нет карточек игроков.\n"
                    "Попробуйте позже или обратитесь к администратору.",
                    parse_mode="html"
                )
            return
        
        # Добавляем карточку пользователю
        add_card_to_user(user_id, new_card['id'])
        
        # Обновляем кулдаун (4 часа)
        update_fammo_cooldown(user_id, 4)
        
        # Получаем статистику пользователя
        stats = get_user_card_stats(user_id)
        cooldown_status = get_fammo_cooldown_status(user_id)
        
        # Форматируем редкость для отображения
        rarity_display = 'Эпический' if new_card['rarity'] == 'эпическая' else new_card['rarity']
        rarity_icons = {
            'Редкий': '🟢',
            'Эпический': '🟣',
            'Легендарный': '🟡',
            'Суперлегендарный': '🔴'
        }
        
        # Получаем иконку для конкретной редкости
        icon = rarity_icons.get(rarity_display, '⭐')
        
        # Формируем время следующей доступности
        next_available = cooldown_status['next_fammo']
        next_time_str = next_available.strftime('%d.%m.%Y в %H:%M') + " (по МСК)" if next_available else "неизвестно"
        
        # Формируем сообщение
        card_message = (
            f"{icon} <b>НОВАЯ КАРТОЧКА!</b> {icon}\n\n"
            f"<b>👤 Игрок:</b> {new_card['nickname']}\n"
            f"<b>🏟️ Клуб:</b> {new_card['club']}\n"
            f"<b>🎯 Позиция:</b> {new_card['position']}\n"
            f"<b>💎 Редкость:</b> {rarity_display}\n\n"
        )
        group_id = -1003615487276 
        # Отправляем уведомление админу
        try:
            await bot.send_message(
                group_id, 
                f"Пользователю @{message.from_user.username} с ID {message.from_user.id} выпала карточка!\n\n\n{card_message}", 
                parse_mode="html"
            )
        except:
            pass
        
        # Добавляем статистику
        if stats:
            card_message += (
                f"📊 <b>Ваша коллекция:</b>\n"
                f"• Карточек: {stats['user_cards']}/{stats['total_cards']}\n"
                f"• Завершено: {stats['completion_percentage']}%\n\n"
            )
        
        card_message += (
            f"⏰ <b>Следующая карточка:</b>\n"
            f"<i>{next_time_str}</i>\n\n"
            f"<i>Используйте /mycards чтобы посмотреть свою коллекцию</i>\n\n"
            f"<b>@mamoballtinder_bot</b>"
        )
        
        # 🔧 ИСПРАВЛЕНИЕ: Используем новую функцию для поиска конкретной картинки
        # с возвратом к случайной картинке по редкости если конкретная не найдена
        try:
            # Получаем конкретную карточку (по никнейму игрока)
            png_file_path = get_specific_card_image(new_card['nickname'], rarity_display)
            
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
                logger.info(f"✅ PNG карточка отправлена пользователю {user_id}: {new_card['nickname']} -> {os.path.basename(png_file_path)}")
            else:
                # 🔧 ИСПРАВЛЕНИЕ: Если не нашли конкретную картинку, берем случайную по редкости
                png_file_path = get_random_card_image(rarity_display)
                
                if png_file_path and os.path.exists(png_file_path):
                    # Создаем FSInputFile для отправки
                    from aiogram.types import FSInputFile
                    photo = FSInputFile(png_file_path)
                    
                    # Отправляем картинку с описанием
                    await message.reply_photo(
                        photo=photo,
                        caption=card_message + f"\n\n⚠️ <i>Специальной карточки для игрока не найдено, отправлена случайная карточка ({rarity_display})</i>",
                        parse_mode="html"
                    )
                    logger.warning(f"⚠️ Для игрока '{new_card['nickname']}' не найдена конкретная карточка, отправлена случайная: {os.path.basename(png_file_path)}")
                else:
                    # Если даже случайную не нашли, отправляем только текст
                    await message.reply(card_message + f"\n\n⚠️ <i>Картинка для карточки не найдена</i>", parse_mode="html")
                    logger.error(f"❌ Не удалось найти даже случайную карточку для редкости '{rarity_display}'")
                    
        except Exception as photo_error:
            # Если ошибка при отправке фото, отправляем только текст
            logger.error(f"❌ Ошибка при отправке PNG карточки: {photo_error}")
            await message.reply(card_message, parse_mode="html")
        
        # Логируем выдачу карточки
        logger.info(f"📨 Пользователь {user_name} ({user_id}) получил карточку: {new_card['nickname']} ({rarity_display})")
        
    except Exception as e:
        logger.error(f"Ошибка в команде фмамо для пользователя {user_id}: {str(e)}")
        
        try:
            await message.reply(
                "❌ Произошла ошибка при выдаче карточки.\n"
                "Попробуйте позже.",
                parse_mode="html"
            )
        except:
            try:
                await message.reply("❌ Ошибка. Попробуйте позже.")
            except:
                pass

#================
@router_fkarta.message(Command("reload_cards"))
@require_role("старший-администратор")
@log_admin_action("Сброс кулдаунов")
async def reload_cards_command(message: Message):
    """Сбрасывает все кулдауны для карточек (админская команда)"""
    user_id = message.from_user.id
    
    # Проверяем, является ли пользователь администратором

    
    try:
        # Удаляем все записи о кулдаунах
        db_operation("DELETE FROM user_card_cooldowns")
        
        await message.reply(
            "✅ <b>Кулдауны успешно сброшены!</b>\n\n"
            "Теперь все пользователи могут получать карточки немедленно.",
            parse_mode="html"
        )
        
        logger.warning(f"👑 Админ {user_id} сбросил все кулдауны карточек")
        
    except Exception as e:
        logger.error(f"Ошибка при сбросе кулдаунов: {e}")
        await message.reply(
            f"❌ Ошибка при сбросе кулдаунов: {str(e)[:100]}",
            parse_mode="html"
        )
@public_router_fkarta.callback_query(F.data == "check_fammo_status")
async def check_fammo_status_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик проверки статуса фмамо"""
    user_id = callback.from_user.id
    user_name = callback.from_user.username or callback.from_user.first_name or str(user_id)
    
    try:
        # Получаем статус кулдауна
        cooldown_status = get_fammo_cooldown_status(user_id)
        stats = get_user_card_stats(user_id)
        
        if not cooldown_status['has_cooldown'] or not cooldown_status['last_fammo']:
            # Пользователь еще не получал карточку
            await callback.message.edit_text(
                f"🎯 <b>Статус получения карточек</b>\n\n"
                f"👤 <b>Пользователь:</b> {user_name}\n\n"
                f"✅ <b>Можете получить карточку прямо сейчас!</b>\n\n"
                f"📊 <b>Статистика коллекции:</b>\n"
                f"• Карточек: {stats['user_cards']}/{stats['total_cards']}\n"
                f"• Завершено: {stats['completion_percentage']}%\n\n"
                f"<i>Напишите <code>фмамо</code> чтобы получить карточку!</i>",
                parse_mode="html"
            )
            await callback.answer()
            return
        
        # Форматируем время
        last_time = cooldown_status['last_fammo'].strftime('%d.%m.%Y в %H:%M') + " (по МСК)"
        
        if cooldown_status['can_get_now']:
            status_text = "✅ <b>Можете получить карточку сейчас!</b>"
            remaining_text = "доступно немедленно"
        else:
            remaining = cooldown_status['remaining']
            remaining_str = format_cooldown_time(remaining.total_seconds())
            next_time = cooldown_status['next_fammo'].strftime('%d.%m.%Y в %H:%M')
            status_text = f"⏳ <b>Ожидайте:</b> {remaining_str}"
            remaining_text = f"доступно {next_time}"
        
        # Формируем сообщение
        message_text = (
            f"🎯 <b>Статус получения карточек</b>\n\n"
            f"👤 <b>Пользователь:</b> {user_name}\n\n"
            f"📅 <b>Последняя карточка:</b>\n"
            f"<i>{last_time}</i>\n\n"
            f"{status_text}\n"
            f"<i>{remaining_text}</i>\n\n"
            f"📊 <b>Статистика коллекции:</b>\n"
            f"• Карточек: {stats['user_cards']}/{stats['total_cards']}\n"
            f"• Завершено: {stats['completion_percentage']}%\n\n"
            f"🔄 <b>Карточки можно получать раз в 4 часа</b>"
        )
        
        # Создаем кнопки
        builder = InlineKeyboardBuilder()
        
    
        
        builder.add(
            InlineKeyboardButton(
                text="📚 Моя коллекция",
                callback_data="view_my_cards"
            ),
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data="check_fammo_status"
            )
        )
        
        if cooldown_status['can_get_now']:
            builder.adjust(1, 2)
        else:
            builder.adjust(2)
        
        # Редактируем сообщение
        await callback.message.edit_text(
            message_text,
            parse_mode="html",
            reply_markup=builder.as_markup()
        )
        
        await callback.answer("Статус обновлен")
        
    except Exception as e:
        logger.error(f"Ошибка в check_fammo_status для пользователя {user_id}: {str(e)}")
        await callback.answer("❌ Вы не дождались конца 4-часового колдауна", show_alert=True)












@public_router_fkarta.message(Command("mycards"))
async def mycards_command(message: Message, state: FSMContext):
    """Показывает коллекцию карточек пользователя с постраничной навигацией"""
    user_id = message.from_user.id
    user_name = message.from_user.username or message.from_user.first_name or f"ID: {user_id}"
    
    try:
        # ПЕРВОЕ: Проверяем, не забанен ли пользователь
        if is_user_banned(user_id):
            ban_info = get_ban_info(user_id)
            if ban_info:
                ban_reason = ban_info['ban_reason']
                banned_at = format_moscow_time(ban_info['banned_at']) if ban_info['banned_at'] else "Не указана"
                
                await message.reply(
                    f"🚫 <b>Вы забанены в боте MamoTinder!</b>\n\n"
                    f"📅 <b>Дата бана:</b> {banned_at}\n"
                    f"📝 <b>Причина:</b> {ban_reason}\n\n"
                    f"<i>Бан распространяется на все функции бота, включая просмотр фмамокарт.</i>\n\n"
                    f"Для обжалования обратитесь: @kirik1231zzap",
                    parse_mode="html"
                )
            return
        
        # Получаем карточки пользователя
        user_cards = get_user_cards(user_id)
        
        # Получаем статистику с показом завершенных редкостей
        stats = get_user_card_stats(user_id)  # Изменили функцию!
        cooldown_status = get_fammo_cooldown_status(user_id)
        
        if not user_cards:
            # Формируем сообщение для пустой коллекции
            if cooldown_status['can_get_now']:
                cooldown_info = "✅ **Можете получить карточку сейчас!**"
            else:
                remaining = cooldown_status['remaining']
                remaining_str = format_cooldown_time(remaining.total_seconds()) if remaining else "неизвестно"
                cooldown_info = f"⏳ **Следующая карточка через:** {remaining_str}"
            
            # Показываем статистику даже для пустой коллекции
            stats_text = ""
            if stats and 'total_by_rarity' in stats:
                rarity_icons = {
                    'Редкий': '🟢',
                    'Эпический': '🟣',
                    'Легендарный': '🟡',
                    'Суперлегендарный': '🔴'
                }
                
                stats_text = "\n<b>Доступные редкости:</b>\n"
                for rarity in ['Суперлегендарный', 'Легендарный', 'Эпический', 'Редкий']:
                    if rarity in stats['total_by_rarity']:
                        total_count = stats['total_by_rarity'][rarity]
                        icon = rarity_icons.get(rarity, '⚪')
                        stats_text += f"{icon} <b>{rarity}:</b> {total_count} карточек\n"
            
            message_text = (
                f"📭 <b>Ваша коллекция пуста</b>\n\n"
                f"👤 <b>Пользователь:</b> {user_name}\n\n"
                f"{cooldown_info}\n\n"
                f"🎯 <b>Шансы на получение:</b>\n"
                f"🟢 Редкий - 50%\n"
                f"🟣 Эпический - 30%\n"
                f"🟡 Легендарный - 15%\n"
                f"🔴 Суперлегендарный - 5%\n"
                f"{stats_text}\n\n"
                f"<i>Используйте команду <code>фмамо</code> чтобы получить свою первую карточку!</i>"
            )
            
            # Создаем инлайн-клавиатуру только со статусом
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(
                    text="⏰ Проверить статус",
                    callback_data="check_fammo_status"
                )
            )
            
            await message.reply(
                message_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
            return
        
        # Отображаем первую страницу
        await show_mycards_page(message, user_id, user_name, user_cards, stats, cooldown_status, page=0)
        
    except Exception as e:
        logger.error(f"Ошибка в команде mycards для пользователя {user_id}: {str(e)}")
        await message.reply(
            "❌ Произошла ошибка при загрузке коллекции.\n"
            "Попробуйте позже.",
            parse_mode="html"
        )


async def show_mycards_page(message: Message, user_id: int, user_name: str, user_cards: list, 
                           stats: dict, cooldown_status: dict, page: int = 0, callback: CallbackQuery = None):
    """Показывает указанную страницу коллекции с inline-клавиатурой - ОБНОВЛЕННАЯ ВЕРСИЯ"""
    try:
        # Настройки отображения
        cards_per_page = 15
        total_cards = len(user_cards)
        total_pages = (total_cards + cards_per_page - 1) // cards_per_page
        
        # Проверяем корректность страницы
        if page < 0:
            page = 0
        elif page >= total_pages:
            page = total_pages - 1
        
        page_number = page + 1
        
        # Формируем заголовок сообщения с новой статистикой
        header = (
            f"📚 <b>Коллекция карточек</b>\n\n"
            f"👤 <b>Пользователь:</b> {user_name}\n"
            f"📊 <b>Статистика:</b>\n"
        )
        
        # Новая статистика по редкостям
        if stats and 'total_by_rarity' in stats and 'user_by_rarity' in stats:
            rarity_icons = {
                'Редкий': '🟢',
                'Эпический': '🟣',
                'Легендарный': '🟡',
                'Суперлегендарный': '🔴'
            }
            
            # Порядок отображения редкостей
            rarity_order = ['EEA', 'Суперлегендарный', 'Легендарный', 'Эпический', 'Редкий']
            
            for rarity in rarity_order:
                if rarity in stats['total_by_rarity']:
                    total_count = stats['total_by_rarity'][rarity]
                    user_count = stats['user_by_rarity'].get(rarity, 0)
                    icon = rarity_icons.get(rarity, '⚪')
                    
                    # Проверяем, собрана ли вся редкость
                    if total_count > 0 and user_count >= total_count:
                        header += f"{icon} <b>{rarity}:</b> ✅ <i>Полная коллекция!</i> ({user_count}/{total_count})\n"
                    else:
                        header += f"{icon} <b>{rarity}:</b> {user_count}/{total_count} "
                        if total_count > 0:
                            percentage = (user_count / total_count * 100)
                            header += f"({percentage:.1f}%)\n"
                        else:
                            header += "\n"
            
            header += f"\n🃏 <b>Всего карточек:</b> {stats['user_cards']}/{stats['total_cards']}\n"
            
            # Показываем собранные редкости
            if stats.get('completed_rarities'):
                header += f"\n🎉 <b>Полностью собраны:</b>\n"
                for rarity in stats['completed_rarities']:
                    icon = rarity_icons.get(rarity, '⭐')
                    header += f"{icon} {rarity}\n"
                header += "\n"
        else:
            header += f"• Всего карточек: {stats['user_cards']}/{stats['total_cards']}\n\n"
        
        # Формируем список карточек текущей страницы
        cards_text = f"<b>📄 Страница {page_number} из {total_pages}</b>\n\n"
        
        start_idx = page * cards_per_page
        end_idx = min(start_idx + cards_per_page, total_cards)
        
        # Группируем карточки по редкости
        cards_by_rarity = {}
        for i in range(start_idx, end_idx):
            # Получаем все 5 значений
            nickname, club, position, rarity, received_at = user_cards[i]
            
            # Нормализуем редкость "эпическая" в "Эпический"
            if rarity == 'эпическая':
                rarity = 'Эпический'
            
            if rarity not in cards_by_rarity:
                cards_by_rarity[rarity] = []
            
            cards_by_rarity[rarity].append((nickname, club, position, rarity))
        
        # Форматируем карточки по группам редкости
        rarity_order = ['EEA', 'Суперлегендарный', 'Легендарный', 'Эпический', 'Редкий']
        rarity_icons = {
            'Редкий': '🟢',
            'Эпический': '🟣',
            'Легендарный': '🟡',
            'Суперлегендарный': '🔴'
        }
        
        for rarity in rarity_order:
            if rarity in cards_by_rarity and cards_by_rarity[rarity]:
                icon = rarity_icons.get(rarity, '⚪')
                cards_text += f"{icon} <b>{rarity}</b> ({len(cards_by_rarity[rarity])}):\n"
                
                for idx, (nickname, club, position, rarity) in enumerate(cards_by_rarity[rarity], 1):
                    # Получаем ID карточки
                    card_info = get_card_by_nickname_db(nickname)
                    card_id = card_info['id'] if card_info else '?'
                    
                    cards_text += f"  {idx}. <b>{nickname}</b> - ID: <code>{card_id}</code> - {position} ({club})\n"
        
        # Добавляем информацию о кулдауне
        if cooldown_status['can_get_now']:
            cooldown_info = "✅ **Можете получить новую карточку!**"
        else:
            remaining = cooldown_status['remaining']
            remaining_str = format_cooldown_time(remaining.total_seconds()) if remaining else "неизвестно"
            cooldown_info = f"⏳ **Следующая карточка через:** {remaining_str}"
        
        footer = (
            f"\n{cooldown_info}\n\n"
            f"<i>Карточки показываются: {start_idx + 1}-{end_idx} из {total_cards}</i>"
        )
        
        # Объединяем все части
        message_text = header + cards_text + footer
        
        # Создаем инлайн-клавиатуру
        builder = InlineKeyboardBuilder()
        
        # Кнопки навигации по страницам
        if total_pages > 1:
            nav_buttons = []
            
            if page > 0:
                nav_buttons.append(
                    InlineKeyboardButton(
                        text="⬅️ Назад",
                        callback_data=f"mycards_page_{page - 1}"
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
                        callback_data=f"mycards_page_{page + 1}"
                    )
                )
            
            if nav_buttons:
                builder.row(*nav_buttons)
        
        # Основные кнопки действий
        action_buttons = []
        
        action_buttons.append(
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data="mycards_refresh"
            )
        )
        
        builder.row(*action_buttons)
        
        # Если это callback (листание страниц)
        if callback:
            await callback.message.edit_text(
                message_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
            await callback.answer(f"Страница {page_number}")
        # Если это новое сообщение (команда /mycards)
        elif isinstance(message, Message):
            await message.reply(
                message_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
        # Если это обновление существующего сообщения (для mycards_refresh)
        elif hasattr(message, 'edit_text'):
            await message.edit_text(
                message_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
        
    except Exception as e:
        logger.error(f"Ошибка в show_mycards_page для пользователя {user_id}: {str(e)}")
        if callback:
            await callback.answer("❌ Ошибка при загрузке страницы", show_alert=True)
        raise

@public_router_fkarta.callback_query(F.data.startswith("mycards_page_"))
async def mycards_page_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик переключения страниц коллекции"""
    user_id = callback.from_user.id
    user_name = callback.from_user.username or callback.from_user.first_name or f"ID: {user_id}"
    
    try:
        # Получаем номер страницы из callback_data
        page = int(callback.data.split("_")[2])
        
        # Получаем карточки пользователя
        user_cards = get_user_cards(user_id)
        stats = get_user_card_stats(user_id)
        cooldown_status = get_fammo_cooldown_status(user_id)
        
        if not user_cards:
            await callback.answer("Ваша коллекция пуста", show_alert=True)
            return
        
        # Показываем запрошенную страницу, изменяя исходное сообщение
        await show_mycards_page(None, user_id, user_name, user_cards, stats, cooldown_status, page, callback)
        
    except Exception as e:
        logger.error(f"Ошибка в mycards_page_callback для пользователя {user_id}: {str(e)}")
        await callback.answer("❌ Ошибка при загрузке страницы", show_alert=True)

@public_router_fkarta.callback_query(F.data == "mycards_refresh")
async def mycards_refresh_callback(callback: CallbackQuery, state: FSMContext):
    """Обновляет страницу коллекции"""
    user_id = callback.from_user.id
    user_name = callback.from_user.username or callback.from_user.first_name or f"ID: {user_id}"
    
    try:
        # Получаем текущую страницу из текста сообщения
        message_text = callback.message.text
        page_match = re.search(r'Страница (\d+) из (\d+)', message_text)
        
        current_page = 0
        if page_match:
            current_page = int(page_match.group(1)) - 1
        
        # Получаем обновленные данные
        user_cards = get_user_cards(user_id)
        stats = get_user_card_stats(user_id)
        cooldown_status = get_fammo_cooldown_status(user_id)
        
        if not user_cards:
            await callback.answer("Ваша коллекция пуста", show_alert=True)
            return
        
        # Показываем обновленную страницу, изменяя исходное сообщение
        await show_mycards_page(None, user_id, user_name, user_cards, stats, cooldown_status, current_page, callback)
        await callback.answer("🔄 Коллекция обновлена")
        
    except Exception as e:
        logger.error(f"Ошибка в mycards_refresh_callback для пользователя {user_id}: {str(e)}")
        await callback.answer("❌ Ошибка при обновлении", show_alert=True)

# ===================
# КОМАНДА /SHOWCARD ID
# ===================

@public_router_fkarta.message(Command("showcard"))
async def showcard_command(message: Message):
    """Просмотр конкретной карточки по ID"""
    user_id = message.from_user.id
    
    try:
        # ПЕРВОЕ: Проверяем, не забанен ли пользователь
        if is_user_banned(user_id):
            ban_info = get_ban_info(user_id)
            if ban_info:
                ban_reason = ban_info['ban_reason']
                banned_at = format_moscow_time(ban_info['banned_at']) if ban_info['banned_at'] else "Не указана"
                
                await message.reply(
                    f"🚫 <b>Вы забанены в боте MamoTinder!</b>\n\n"
                    f"📅 <b>Дата бана:</b> {banned_at}\n"
                    f"📝 <b>Причина:</b> {ban_reason}\n\n"
                    f"<i>Бан распространяется на все функции бота, включая просмотр карточек.</i>\n\n"
                    f"Для обжалования обратитесь: @kirik1231zzap",
                    parse_mode="html"
                )
            return
        
        # Получаем аргументы команды
        command_text = message.text.strip()
        args = command_text.split()
        
        if len(args) < 2:
            await message.reply(
                "📝 <b>Использование команды:</b>\n\n"
                "<code>/showcard [id_карточки]</code>\n\n"
                "<b>Примеры:</b>\n"
                "• <code>/showcard 1</code> - показать карточку с ID 1\n"
                "• <code>/showcard 25</code> - показать карточку с ID 25\n\n"
                "<b>Как узнать ID карточки?</b>\n"
                "В вашей коллекции (<code>/mycards</code>) у каждой карточки указан ID\n"
                "<i>ID карточки - это числовой идентификатор из каталога игроков</i>",
                parse_mode="html"
            )
            return
        
        # Пытаемся получить ID карточки
        try:
            card_id = int(args[1].strip())
        except ValueError:
            await message.reply(
                "❌ <b>Неверный формат ID!</b>\n\n"
                "ID карточки должен быть числом.\n"
                "Пример: <code>/showcard 1</code>",
                parse_mode="html"
            )
            return
        
        # Получаем информацию о карточке
        card_info = get_card_by_id(card_id)
        
        if not card_info:
            await message.reply(
                f"❌ <b>Карточка с ID {card_id} не найдена!</b>\n\n"
                f"<b>Возможные причины:</b>\n"
                f"• Неверный ID карточки\n"
                f"• Карточка была удалена из каталога\n"
                f"• ID карточки изменился\n\n"
                f"<i>Проверьте правильность ID с помощью команды /allcards</i>",
                parse_mode="html"
            )
            return
        
        # Форматируем информацию о карточке
        rarity_display = 'Эпический' if card_info['rarity'] == 'эпическая' else card_info['rarity']
        rarity_icons = {
            'Редкий': '🟢',
            'Эпический': '🟣',
            'Легендарный': '🟡',
            'Суперлегендарный': '🔴'
        }
        
        icon = rarity_icons.get(rarity_display, '⭐')
        
        # Проверяем, есть ли эта карточка у пользователя
        user_has = user_has_card(user_id, card_id)
        ownership_status = "✅ У вас есть эта карточка" if user_has else "❌ У вас нет этой карточки"
        
        # Получаем количество владельцев этой карточки
        owners_count = get_card_owners_count(card_id)
        
        # Формируем основное сообщение
        card_message = (
            f"{icon} <b>ИНФОРМАЦИЯ О КАРТОЧКЕ</b> {icon}\n\n"
            f"<b>🆔 ID:</b> <code>{card_id}</code>\n"
            f"<b>👤 Игрок:</b> {card_info['nickname']}\n"
            f"<b>🏟️ Клуб:</b> {card_info['club']}\n"
            f"<b>🎯 Позиция:</b> {card_info['position']}\n"
            f"<b>💎 Редкость:</b> {rarity_display}\n\n"
            f"<b>📊 Статистика:</b>\n"
            f"• Владельцев: {owners_count}\n"
            f"• Статус: {ownership_status}\n\n"
        )
        
        # Добавляем информацию о продаже, если карточка продается
        if is_card_in_sale(card_id):
            # Получаем информацию о продаже
            sale_info = get_card_sale_info_db(card_id)
            if sale_info:
                sale_type = sale_info.get('type', 'unknown')
                if sale_type == 'admin':
                    seller = "Администратор"
                elif sale_type == 'user':
                    seller = sale_info.get('seller_display', 'Игрок')
                else:
                    seller = "Неизвестно"
                
                card_message += (
                    f"<b>🛒 Продается:</b>\n"
                    f"• Цена: {sale_info.get('price', 0)} коинов\n"
                    f"• Продавец: {seller}\n"
                    f"• ID продажи: <code>{sale_info.get('sell_id', '?')}</code>\n\n"
                    f"<i>Для покупки используйте ID продажи выше</i>\n\n"
                )
        
        # Пробуем найти и отправить картинку карточки
        try:
            png_file_path = get_specific_card_image(card_info['nickname'], rarity_display)
            
            if png_file_path and os.path.exists(png_file_path):
                from aiogram.types import FSInputFile
                photo = FSInputFile(png_file_path)
                
                # Отправляем картинку с описанием
                await message.reply_photo(
                    photo=photo,
                    caption=card_message,
                    parse_mode="html"
                )
                logger.info(f"✅ PNG карточка {card_id} отправлена пользователю {user_id}")
            else:
                # Если не нашли конкретную картинку, берем случайную по редкости
                png_file_path = get_random_card_image(rarity_display)
                
                if png_file_path and os.path.exists(png_file_path):
                    from aiogram.types import FSInputFile
                    photo = FSInputFile(png_file_path)
                    
                    # Отправляем картинку с описанием
                    await message.reply_photo(
                        photo=photo,
                        caption=card_message + f"\n\n⚠️ <i>Специальной карточки для игрока не найдено, отправлена случайная карточка ({rarity_display})</i>",
                        parse_mode="html"
                    )
                    logger.warning(f"⚠️ Для игрока '{card_info['nickname']}' не найдена конкретная карточка, отправлена случайная")
                else:
                    # Если даже случайную не нашли, отправляем только текст
                    await message.reply(card_message + f"\n\n⚠️ <i>Картинка для карточки не найдена</i>", parse_mode="html")
                    logger.error(f"❌ Не удалось найти картинку для карточки {card_id}")
                    
        except Exception as photo_error:
            # Если ошибка при отправке фото, отправляем только текст
            logger.error(f"❌ Ошибка при отправке PNG карточки: {photo_error}")
            await message.reply(card_message, parse_mode="html")
        
        # Логируем просмотр карточки
        logger.info(f"👁️ Пользователь {user_id} просмотрел карточку {card_id} ({card_info['nickname']})")
        
    except Exception as e:
        logger.error(f"Ошибка в команде /showcard для пользователя {user_id}: {str(e)}")
        await message.reply(
            "❌ Произошла ошибка при загрузке информации о карточке.\n"
            "Попробуйте позже или проверьте правильность ID.",
            parse_mode="html"
        )


# Вспомогательная функция для получения информации о продаже карточки
def get_card_sale_info_db(card_id: int):
    """Получает информацию о продаже карточки по ID карточки"""
    try:
        # Проверяем админские продажи
        admin_result = db_operation(
            """SELECT sc.id, sc.price, sc.is_available
               FROM sell_cards sc
               WHERE sc.card_id = ? AND sc.is_available = 1""",
            (card_id,),
            fetch=True
        )
        
        if admin_result:
            sell_id, price, is_available = admin_result[0]
            return {
                'sell_id': sell_id,
                'price': price,
                'type': 'admin',
                'seller_display': 'Администратор'
            }
        
        # Проверяем пользовательские продажи
        user_result = db_operation(
            """SELECT ust.id, ust.price, ust.seller_id, au.username
               FROM user_sell_transactions ust
               JOIN all_users au ON ust.seller_id = au.id
               WHERE ust.card_id = ? AND ust.status = 'active'""",
            (card_id,),
            fetch=True
        )
        
        if user_result:
            sell_id, price, seller_id, username = user_result[0]
            seller_display = f"@{username}" if username else f"Игрок (ID: {seller_id})"
            return {
                'sell_id': sell_id,
                'price': price,
                'type': 'user',
                'seller_display': seller_display,
                'seller_id': seller_id
            }
        
        return None
        
    except Exception as e:
        logger.error(f"Ошибка при получении информации о продаже карточки {card_id}: {e}")
        return None





@public_router_fkarta.callback_query(F.data == "view_my_cards")
async def view_my_cards_callback(callback: CallbackQuery, state: FSMContext):
    """Показывает коллекцию карточек при нажатии на кнопку "Моя коллекция" - ОБНОВЛЕННАЯ"""
    user_id = callback.from_user.id
    user_name = callback.from_user.username or callback.from_user.first_name or f"ID: {user_id}"
    
    try:
        # Получаем карточки пользователя
        user_cards = get_user_cards(user_id)
        
        # Получаем новую статистику с завершенными редкостями
        stats = get_user_card_stats(user_id)  # Изменили!
        cooldown_status = get_fammo_cooldown_status(user_id)
        
        if not user_cards:
            # Формируем сообщение для пустой коллекции
            if cooldown_status['can_get_now']:
                cooldown_info = "✅ **Можете получить карточку сейчас!**"
            else:
                remaining = cooldown_status['remaining']
                remaining_str = format_cooldown_time(remaining.total_seconds()) if remaining else "неизвестно"
                cooldown_info = f"⏳ **Следующая карточка через:** {remaining_str}"
            
            message_text = (
                f"📭 <b>Ваша коллекция пуста</b>\n\n"
                f"👤 <b>Пользователь:</b> {user_name}\n\n"
                f"{cooldown_info}\n\n"
                f"🎯 <b>Шансы на получение:</b>\n"
                f"🟢 Редкий - 50%\n"
                f"🟣 Эпический - 30%\n"
                f"🟡 Легендарный - 15%\n"
                f"🔴 Суперлегендарный - 5%\n\n"
                f"<i>Напишите <code>фмамо</code> чтобы получить свою первую карточку!</i>"
            )
            
            # Создаем инлайн-клавиатуру
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(
                    text="⏰ Проверить статус",
                    callback_data="check_fammo_status"
                )
            )
            
            # Редактируем сообщение
            await callback.message.edit_text(
                message_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
            
            await callback.answer()
            return
        
        # Получаем настройки отображения
        current_page = 0
        
        # Показываем первую страницу
        await show_mycards_page(None, user_id, user_name, user_cards, stats, cooldown_status, current_page, callback)
        
        await callback.answer("📚 Ваша коллекция")
        
    except Exception as e:
        logger.error(f"Ошибка в view_my_cards_callback для пользователя {user_id}: {str(e)}")
        await callback.answer("❌ Ошибка при загрузке коллекции", show_alert=True)

@router_fkarta.callback_query(F.data.startswith("view_cards_page_"))
async def view_cards_page_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик переключения страниц коллекции из view_my_cards"""
    user_id = callback.from_user.id
    user_name = callback.from_user.username or callback.from_user.first_name or f"ID: {user_id}"
    
    try:
        # Получаем номер страницы из callback_data
        page = int(callback.data.split("_")[3])
        
        # Получаем карточки пользователя
        user_cards = get_user_cards(user_id)
        stats = get_user_card_stats(user_id)
        cooldown_status = get_fammo_cooldown_status(user_id)
        
        if not user_cards:
            await callback.answer("Ваша коллекция пуста", show_alert=True)
            return
        
        # Настройки отображения
        cards_per_page = 15
        total_cards = len(user_cards)
        total_pages = (total_cards + cards_per_page - 1) // cards_per_page
        
        # Проверяем корректность страницы
        if page < 0:
            page = 0
        elif page >= total_pages:
            page = total_pages - 1
        
        # Формируем заголовок сообщения
        header = (
            f"📚 <b>Коллекция карточек</b>\n\n"
            f"👤 <b>Пользователь:</b> {user_name}\n"
            f"📊 <b>Статистика:</b>\n"
            f"• Всего карточек: {stats['user_cards']}/{stats['total_cards']}\n"
            f"• Завершено: {stats['completion_percentage']}%\n\n"
        )
        
        # Добавляем статистику по редкостям
        if stats['rarity_stats']:
            rarity_icons = {
                'Редкий': '🟢',
                'Эпический': '🟣',
                'Легендарный': '🟡',
                'Суперлегендарный': '🔴'
            }
            
            header += "<b>По редкостям:</b>\n"
            for rarity, count in stats['rarity_stats'].items():
                # Нормализуем редкость "эпическая" в "Эпический"
                display_rarity = 'Эпический' if rarity == 'эпическая' else rarity
                icon = rarity_icons.get(display_rarity, '⚪')
                percentage = (count / stats['total_cards'] * 100) if stats['total_cards'] > 0 else 0
                header += f"{icon} {display_rarity}: {count} ({percentage:.1f}%)\n"
            header += "\n"
        
        # Формируем список карточек текущей страницы
        cards_text = f"<b>📄 Страница {page + 1} из {total_pages}</b>\n\n"
        
        start_idx = page * cards_per_page
        end_idx = min(start_idx + cards_per_page, total_cards)
        
        # Группируем карточки по редкости
        cards_by_rarity = {}
        for i in range(start_idx, end_idx):
            nickname, club, position, rarity, received_at = user_cards[i]
            
            # Нормализуем редкость "эпическая" в "Эпический"
            if rarity == 'эпическая':
                rarity = 'Эпический'
            
            if rarity not in cards_by_rarity:
                cards_by_rarity[rarity] = []
            
            cards_by_rarity[rarity].append((nickname, club, position))
        
        # Форматируем карточки по группам редкости
        rarity_order = ['EEA', 'Суперлегендарный', 'Легендарный', 'Эпический', 'Редкий']
        rarity_icons = {
            'Редкий': '🟢',
            'Эпический': '🟣',
            'Легендарный': '🟡',
            'Суперлегендарный': '🔴'
        }
        
        for rarity in rarity_order:
            if rarity in cards_by_rarity and cards_by_rarity[rarity]:
                icon = rarity_icons.get(rarity, '⚪')
                cards_text += f"{icon} <b>{rarity}</b> ({len(cards_by_rarity[rarity])}):\n"
                
                for idx, (nickname, club, position) in enumerate(cards_by_rarity[rarity], 1):
                    cards_text += f"  {idx}. <b>{nickname}</b> - {position} ({club})\n"
                
                cards_text += "\n"
        
        # Добавляем информацию о кулдауне
        if cooldown_status['can_get_now']:
            cooldown_info = "✅ **Можете получить новую карточку!**"
        else:
            remaining = cooldown_status['remaining']
            remaining_str = format_cooldown_time(remaining.total_seconds()) if remaining else "неизвестно"
            cooldown_info = f"⏳ **Следующая карточка через:** {remaining_str}"
        
        footer = (
            f"\n{cooldown_info}\n\n"
            f"<i>Карточки показываются: {start_idx + 1}-{end_idx} из {total_cards}</i>"
        )
        
        # Объединяем все части
        message_text = header + cards_text + footer
        
        # Создаем инлайн-клавиатуру
        builder = InlineKeyboardBuilder()
        
        # Кнопки навигации
        nav_buttons = []
        
        if total_pages > 1:
            if page > 0:
                nav_buttons.append(
                    InlineKeyboardButton(
                        text="⬅️ Назад",
                        callback_data=f"view_cards_page_{page - 1}"
                    )
                )
            
            nav_buttons.append(
                InlineKeyboardButton(
                    text=f"📄 {page + 1}/{total_pages}",
                    callback_data="noop"
                )
            )
            
            if page < total_pages - 1:
                nav_buttons.append(
                    InlineKeyboardButton(
                        text="Вперед ➡️",
                        callback_data=f"view_cards_page_{page + 1}"
                    )
                )
            
            if nav_buttons:
                builder.row(*nav_buttons)
        
        # Основные кнопки действий
        action_buttons = []
        

        action_buttons.append(
                InlineKeyboardButton(
                    text="⏰ Статус",
                    callback_data="check_fammo_status"
                )
            )
        
        action_buttons.append(
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data="view_my_cards"
            )
        )
        
        builder.row(*action_buttons)
        
        # Обновляем сообщение (изменяем исходное)
        await callback.message.edit_text(
            message_text,
            parse_mode="html",
            reply_markup=builder.as_markup()
        )
        
        await callback.answer(f"Страница {page + 1}")
        
    except Exception as e:
        logger.error(f"Ошибка в view_cards_page_callback для пользователя {user_id}: {str(e)}")
        await callback.answer("❌ Ошибка при загрузке страницы", show_alert=True)

# ДОБАВЛЯЕМ В НАЧАЛО ФАЙЛА (после других импортов)
import random

# 1. ФУНКЦИЯ ДЛЯ ПОИСКА КАРТОЧКИ ПО НИКНЕЙМУ
def find_card_by_nickname(nickname: str):
    """Находит карточку по никнейму (точный или частичный поиск)"""
    try:
        # Сначала точный поиск (регистронезависимо)
        result = db_operation(
            """SELECT id, nickname, club, position, rarity 
               FROM players_catalog 
               WHERE LOWER(nickname) = LOWER(?)""",
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
        
        # Если точный поиск не дал результатов, ищем частичное совпадение
        result = db_operation(
            """SELECT id, nickname, club, position, rarity 
               FROM players_catalog 
               WHERE LOWER(nickname) LIKE LOWER(?) 
               ORDER BY nickname""",
            (f"%{nickname}%",),
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

# 2. ФУНКЦИЯ ДЛЯ ПОЛУЧЕНИЯ ВСЕХ КАРТОЧЕК ИЗ КАТАЛОГА
def get_all_cards_from_catalog():
    """Получает список всех карточек из каталога"""
    try:
        result = db_operation(
            """SELECT id, nickname, club, position, rarity 
               FROM players_catalog 
               ORDER BY nickname""",
            fetch=True
        )
        
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
        logger.error(f"Ошибка при получении карточек из каталога: {e}")
        return []

# 3. ФУНКЦИЯ ДЛЯ ПОИСКА КАРТОЧКИ ПО НИКНЕЙМУ ДЛЯ /ADDCARD И /DELETECARD
def find_card_by_nickname(nickname: str):
    """Находит карточку по никнейму (точный или частичный поиск)"""
    try:
        # Сначала точный поиск (регистронезависимо)
        result = db_operation(
            """SELECT id, nickname, club, position, rarity 
               FROM players_catalog 
               WHERE LOWER(nickname) = LOWER(?)""",
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
        
        # Если точный поиск не дал результатов, ищем частичное совпадение
        result = db_operation(
            """SELECT id, nickname, club, position, rarity 
               FROM players_catalog 
               WHERE LOWER(nickname) LIKE LOWER(?) 
               ORDER BY nickname""",
            (f"%{nickname}%",),
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

# 4. ФУНКЦИЯ ДЛЯ ПОЛУЧЕНИЯ ИНФОРМАЦИИ О ПОЛЬЗОВАТЕЛЕ


# 5. ФУНКЦИЯ ДЛЯ ПРОВЕРКИ, ЕСТЬ ЛИ У ПОЛЬЗОВАТЕЛЯ КАРТОЧКА
def user_has_card(user_id: int, card_id: int):
    """Проверяет, есть ли у пользователя указанная карточка"""
    try:
        result = db_operation(
            "SELECT 1 FROM user_cards WHERE user_id = ? AND card_id = ?",
            (user_id, card_id),
            fetch=True
        )
        return bool(result)
        
    except Exception as e:
        logger.error(f"Ошибка при проверке карточки {card_id} у пользователя {user_id}: {e}")
        return False

# 6. КОМАНДА /ADDCARD - ДОБАВЛЕНИЕ КАРТОЧКИ ПОЛЬЗОВАТЕЛЮ
@router_fkarta.message(Command("addcard"))
@require_role("старший-администратор")
@log_admin_action("Добавление карточки пользователю")
async def addcard_command(message: Message):
    """Добавить карточку пользователю"""
    
    command_text = message.text.strip()
    args = command_text.split()
    
    # Проверяем аргументы
    if len(args) < 3:
        await message.reply(
            "📝 <b>Использование команды:</b>\n\n"
            "<code>/addcard [ник_игрока] [id_пользователя]</code>\n\n"
            "<b>Примеры:</b>\n"
            "• <code>/addcard DonbazZ 123456789</code>\n"
            "• <code>/addcard Bellingham 987654321</code>\n\n"
            "<b>Примечания:</b>\n"
            "1. Ник игрока можно указывать частично\n"
            "2. ID пользователя должен быть числом\n"
            "3. Если карточка уже есть у пользователя, она не будет добавлена повторно\n\n"
            "<i>Команда доступна только администраторам</i>",
            parse_mode="html"
        )
        return
    
    nickname = args[1].strip()
    target_user_id_str = args[2].strip()
    
    # Проверяем ID пользователя
    try:
        target_user_id = int(target_user_id_str)
    except ValueError:
        await message.reply(
            f"❌ <b>Неверный ID пользователя!</b>\n\n"
            f"ID должен быть числом.\n"
            f"Вы указали: <code>{target_user_id_str}</code>",
            parse_mode="html"
        )
        return
    
    try:
        # Проверяем существование пользователя
        user_info = get_user_info(target_user_id)
        if not user_info:
            await message.reply(
                f"❌ <b>Пользователь с ID {target_user_id} не найден!</b>\n\n"
                f"Проверьте правильность ID пользователя.",
                parse_mode="html"
            )
            return
        
        # Ищем карточку
        card = find_card_by_nickname(nickname)
        if not card:
            # Показываем список похожих карточек
            similar_cards = search_similar_cards(nickname, limit=10)
            
            if similar_cards:
                cards_list = []
                for i, similar_card in enumerate(similar_cards[:5], 1):
                    cards_list.append(
                        f"{i}. <code>{similar_card['nickname']}</code> "
                        f"({similar_card['club']}) - {similar_card['rarity']}"
                    )
                
                await message.reply(
                    f"🔍 <b>Карточка не найдена!</b>\n\n"
                    f"По запросу <code>{nickname}</code> не найдено карточек.\n\n"
                    f"<b>Ближайшие совпадения:</b>\n" + "\n".join(cards_list) + "\n\n"
                    f"<i>Используйте точный никнейм из списка выше</i>",
                    parse_mode="html"
                )
            else:
                await message.reply(
                    f"❌ Карточка с никнеймом <code>{nickname}</code> не найдена.\n\n"
                    f"<i>Проверьте правильность написания никнейма</i>",
                    parse_mode="html"
                )
            return
        
        # Проверяем, есть ли уже эта карточка у пользователя
        if user_has_card(target_user_id, card['id']):
            user_display = f"@{user_info['username']}" if user_info['username'] else user_info['first_name']
            
            await message.reply(
                f"ℹ️ <b>Карточка уже есть у пользователя!</b>\n\n"
                f"<b>Пользователь:</b> {user_display}\n"
                f"<b>ID:</b> <code>{target_user_id}</code>\n\n"
                f"<b>Карточка:</b> <code>{card['nickname']}</code>\n"
                f"<b>Редкость:</b> {card['rarity']}\n\n"
                f"<i>Карточка не была добавлена повторно</i>",
                parse_mode="html"
            )
            return
        
        # Добавляем карточку
        success = add_card_to_user(target_user_id, card['id'])
        
        if success:
            # Обновляем статистику
            stats = get_user_card_stats(target_user_id)
            user_display = f"@{user_info['username']}" if user_info['username'] else user_info['first_name']
            
            rarity_display = 'Эпический' if card['rarity'] == 'эпическая' else card['rarity']
            
            message_text = (
                f"✅ <b>Карточка успешно добавлена!</b>\n\n"
                f"<b>Пользователь:</b> {user_display}\n"
                f"<b>ID:</b> <code>{target_user_id}</code>\n\n"
                f"<b>Добавленная карточка:</b>\n"
                f"• <b>Игрок:</b> {card['nickname']}\n"
                f"• <b>Клуб:</b> {card['club']}\n"
                f"• <b>Позиция:</b> {card['position']}\n"
                f"• <b>Редкость:</b> {rarity_display}\n\n"
            )
            
            if stats:
                message_text += (
                    f"📊 <b>Новая статистика коллекции:</b>\n"
                    f"• Карточек: {stats['user_cards']}/{stats['total_cards']}\n"
                    f"• Завершено: {stats['completion_percentage']}%\n\n"
                )
            
            await message.reply(
                message_text,
                parse_mode="html"
            )
            
            logger.warning(f"👑 Админ {message.from_user.id} добавил карточку {card['nickname']} ({card['id']}) пользователю {target_user_id}")
            
        else:
            await message.reply(
                f"❌ <b>Ошибка при добавлении карточки!</b>\n\n"
                f"Не удалось добавить карточку пользователю.\n"
                f"Проверьте логи для подробностей.",
                parse_mode="html"
            )
            
    except Exception as e:
        logger.error(f"❌ Ошибка в команде /addcard: {e}")
        await message.reply(
            f"❌ Произошла ошибка: {str(e)[:100]}",
            parse_mode="html"
        )

# 7. КОМАНДА /DELETECARD - УДАЛЕНИЕ КАРТОЧКИ У ПОЛЬЗОВАТЕЛЯ
@router_fkarta.message(Command("deletecard"))
@require_role("старший-администратор")
@log_admin_action("Удаление карточки у пользователя")
async def deletecard_command(message: Message):
    """Удалить карточку у пользователя"""
    
    command_text = message.text.strip()
    args = command_text.split()
    
    # Проверяем аргументы
    if len(args) < 3:
        await message.reply(
            "📝 <b>Использование команды:</b>\n\n"
            "<code>/deletecard [ник_игрока] [id_пользователя]</code>\n\n"
            "<b>Примеры:</b>\n"
            "• <code>/deletecard DonbazZ 123456789</code>\n"
            "• <code>/deletecard Bellingham 987654321</code>\n\n"
            "<b>Примечания:</b>\n"
            "1. Ник игрока можно указывать частично\n"
            "2. ID пользователя должен быть числом\n"
            "3. Если карточки нет у пользователя, команда ничего не делает\n\n"
            "<i>Команда доступна только администраторам</i>",
            parse_mode="html"
        )
        return
    
    nickname = args[1].strip()
    target_user_id_str = args[2].strip()
    
    # Проверяем ID пользователя
    try:
        target_user_id = int(target_user_id_str)
    except ValueError:
        await message.reply(
            f"❌ <b>Неверный ID пользователя!</b>\n\n"
            f"ID должен быть числом.\n"
            f"Вы указали: <code>{target_user_id_str}</code>",
            parse_mode="html"
        )
        return
    
    try:
        # Проверяем существование пользователя
        user_info = get_user_info(target_user_id)
        if not user_info:
            await message.reply(
                f"❌ <b>Пользователь с ID {target_user_id} не найден!</b>\n\n"
                f"Проверьте правильность ID пользователя.",
                parse_mode="html"
            )
            return
        
        # Ищем карточку
        card = find_card_by_nickname(nickname)
        if not card:
            # Показываем список похожих карточек
            similar_cards = search_similar_cards(nickname, limit=10)
            
            if similar_cards:
                cards_list = []
                for i, similar_card in enumerate(similar_cards[:5], 1):
                    cards_list.append(
                        f"{i}. <code>{similar_card['nickname']}</code> "
                        f"({similar_card['club']}) - {similar_card['rarity']}"
                    )
                
                await message.reply(
                    f"🔍 <b>Карточка не найдена!</b>\n\n"
                    f"По запросу <code>{nickname}</code> не найдено карточек.\n\n"
                    f"<b>Ближайшие совпадения:</b>\n" + "\n".join(cards_list) + "\n\n"
                    f"<i>Используйте точный никнейм из списка выше</i>",
                    parse_mode="html"
                )
            else:
                await message.reply(
                    f"❌ Карточка с никнеймом <code>{nickname}</code> не найдена.\n\n"
                    f"<i>Проверьте правильность написания никнейма</i>",
                    parse_mode="html"
                )
            return
        
        # Проверяем, есть ли карточка у пользователя
        if not user_has_card(target_user_id, card['id']):
            user_display = f"@{user_info['username']}" if user_info['username'] else user_info['first_name']
            
            await message.reply(
                f"ℹ️ <b>Карточки нет у пользователя!</b>\n\n"
                f"<b>Пользователь:</b> {user_display}\n"
                f"<b>ID:</b> <code>{target_user_id}</code>\n\n"
                f"<b>Карточка:</b> <code>{card['nickname']}</code>\n"
                f"<b>Редкость:</b> {card['rarity']}\n\n"
                f"<i>У пользователя нет этой карточки для удаления</i>",
                parse_mode="html"
            )
            return
        
        # Удаляем карточку
        try:
            db_operation(
                "DELETE FROM user_cards WHERE user_id = ? AND card_id = ?",
                (target_user_id, card['id'])
            )
            
            # Обновляем статистику
            stats = get_user_card_stats(target_user_id)
            user_display = f"@{user_info['username']}" if user_info['username'] else user_info['first_name']
            
            rarity_display = 'Эпический' if card['rarity'] == 'эпическая' else card['rarity']
            
            message_text = (
                f"✅ <b>Карточка успешно удалена!</b>\n\n"
                f"<b>Пользователь:</b> {user_display}\n"
                f"<b>ID:</b> <code>{target_user_id}</code>\n\n"
                f"<b>Удаленная карточка:</b>\n"
                f"• <b>Игрок:</b> {card['nickname']}\n"
                f"• <b>Клуб:</b> {card['club']}\n"
                f"• <b>Позиция:</b> {card['position']}\n"
                f"• <b>Редкость:</b> {rarity_display}\n\n"
            )
            
            if stats:
                message_text += (
                    f"📊 <b>Новая статистика коллекции:</b>\n"
                    f"• Карточек: {stats['user_cards']}/{stats['total_cards']}\n"
                    f"• Завершено: {stats['completion_percentage']}%\n\n"
                )
            
            await message.reply(
                message_text,
                parse_mode="html"
            )
            
            logger.warning(f"👑 Админ {message.from_user.id} удалил карточку {card['nickname']} ({card['id']}) у пользователя {target_user_id}")
            
        except Exception as e:
            logger.error(f"Ошибка при удалении карточки {card['id']} у пользователя {target_user_id}: {e}")
            await message.reply(
                f"❌ <b>Ошибка при удалении карточки!</b>\n\n"
                f"Не удалось удалить карточку.\n"
                f"Ошибка: {str(e)[:100]}",
                parse_mode="html"
            )
            
    except Exception as e:
        logger.error(f"❌ Ошибка в команде /deletecard: {e}")
        await message.reply(
            f"❌ Произошла ошибка: {str(e)[:100]}",
            parse_mode="html"
        )

# 8. КОМАНДА /GIVEALLCARDS - ВЫДАЧА ВСЕХ КАРТОЧЕК ПОЛЬЗОВАТЕЛЮ
@router_fkarta.message(Command("giveallcards"))
@require_role("старший-администратор")
@log_admin_action("Выдача всех карточек пользователю")
async def giveallcards_command(message: Message):
    """Выдать все карточки пользователю"""
    
    command_text = message.text.strip()
    args = command_text.split()
    
    # Проверяем аргументы
    if len(args) < 2:
        await message.reply(
            "📝 <b>Использование команды:</b>\n\n"
            "<code>/giveallcards [id_пользователя]</code>\n\n"
            "<b>Примеры:</b>\n"
            "• <code>/giveallcards 123456789</code>\n"
            "• <code>/giveallcards 987654321</code>\n\n"
            "<b>Примечания:</b>\n"
            "1. ID пользователя должен быть числом\n"
            "2. Команда добавит ВСЕ карточки из каталога пользователю\n"
            "3. Если какие-то карточки уже есть у пользователя, они не будут добавлены повторно\n\n"
            "<i>Команда доступна только старшим администраторам</i>",
            parse_mode="html"
        )
        return
    
    target_user_id_str = args[1].strip()
    
    # Проверяем ID пользователя
    try:
        target_user_id = int(target_user_id_str)
    except ValueError:
        await message.reply(
            f"❌ <b>Неверный ID пользователя!</b>\n\n"
            f"ID должен быть числом.\n"
            f"Вы указали: <code>{target_user_id_str}</code>",
            parse_mode="html"
        )
        return
    
    try:
        # Проверяем существование пользователя
        user_info = get_user_info(target_user_id)
        if not user_info:
            await message.reply(
                f"❌ <b>Пользователь с ID {target_user_id} не найден!</b>\n\n"
                f"Проверьте правильность ID пользователя.",
                parse_mode="html"
            )
            return
        
        user_display = f"@{user_info['username']}" if user_info['username'] else user_info['first_name']
        
        # Получаем текущие карточки пользователя
        current_cards = get_user_cards(target_user_id)
        current_card_nicknames = {card[0] for card in current_cards}
        
        # Получаем все карточки из каталога
        all_cards = get_all_cards_from_catalog()
        
        if not all_cards:
            await message.reply(
                f"❌ <b>В каталоге нет карточек!</b>\n\n"
                f"Не могу добавить карточки - каталог пуст.",
                parse_mode="html"
            )
            return
        
        # Считаем, сколько карточек нужно добавить
        cards_to_add = []
        for card in all_cards:
            if card['nickname'] not in current_card_nicknames:
                cards_to_add.append(card)
        
        if not cards_to_add:
            await message.reply(
                f"ℹ️ <b>У пользователя уже есть все карточки!</b>\n\n"
                f"<b>Пользователь:</b> {user_display}\n"
                f"<b>ID:</b> <code>{target_user_id}</code>\n\n"
                f"<b>Всего карточек в каталоге:</b> {len(all_cards)}\n"
                f"<b>Карточек у пользователя:</b> {len(current_cards)}\n\n"
                f"<i>Ничего не добавлено</i>",
                parse_mode="html"
            )
            return
        
        # Добавляем карточки
        added_count = 0
        errors = []
        
        for card in cards_to_add:
            try:
                db_operation(
                    """INSERT OR IGNORE INTO user_cards (user_id, card_id) 
                       VALUES (?, ?)""",
                    (target_user_id, card['id'])
                )
                added_count += 1
            except Exception as e:
                errors.append(f"{card['nickname']}: {str(e)[:50]}")
        
        # Получаем обновленную статистику
        stats = get_user_card_stats(target_user_id)
        
        # Формируем отчет
        message_text = (
            f"✅ <b>Карточки успешно добавлены!</b>\n\n"
            f"<b>Пользователь:</b> {user_display}\n"
            f"<b>ID:</b> <code>{target_user_id}</code>\n\n"
            f"📊 <b>Результаты операции:</b>\n"
            f"• Всего карточек в каталоге: {len(all_cards)}\n"
            f"• Было карточек у пользователя: {len(current_cards)}\n"
            f"• Добавлено новых карточек: {added_count}\n"
        )
        
        if stats:
            message_text += (
                f"• Теперь карточек у пользователя: {stats['user_cards']}\n"
                f"• Завершено: {stats['completion_percentage']}%\n\n"
            )
        else:
            message_text += "\n"
        
        if errors:
            message_text += (
                f"⚠️ <b>Ошибки при добавлении:</b>\n"
                f"<code>" + "\n".join(errors[:5]) + "</code>\n\n"
                f"<i>Показано первых {min(5, len(errors))} ошибок из {len(errors)}</i>\n\n"
            )
        
        message_text += (
            f"<i>Используйте /mycards чтобы посмотреть коллекцию пользователя</i>"
        )
        
        await message.reply(
            message_text,
            parse_mode="html"
        )
        
        logger.warning(f"👑 Старший админ {message.from_user.id} выдал все карточки пользователю {target_user_id} ({user_display})")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в команде /giveallcards: {e}")
        await message.reply(
            f"❌ Произошла ошибка: {str(e)[:100]}",
            parse_mode="html"
        )

# 9. КОМАНДА /DELETEALLCARDS - УДАЛЕНИЕ ВСЕХ КАРТОЧЕК У ПОЛЬЗОВАТЕЛЯ
@router_fkarta.message(Command("deleteallcards"))
@require_role("старший-администратор")
@log_admin_action("Удаление всех карточек у пользователя")
async def deleteallcards_command(message: Message):
    """Удалить все карточки у пользователя"""
    
    command_text = message.text.strip()
    args = command_text.split()
    
    # Проверяем аргументы
    if len(args) < 2:
        await message.reply(
            "📝 <b>Использование команды:</b>\n\n"
            "<code>/deleteallcards [id_пользователя]</code>\n\n"
            "<b>Примеры:</b>\n"
            "• <code>/deleteallcards 123456789</code>\n"
            "• <code>/deleteallcards 987654321</code>\n\n"
            "<b>Примечания:</b>\n"
            "1. ID пользователя должен быть числом\n"
            "2. Команда удалит ВСЕ карточки у пользователя\n"
            "3. Действие необратимо!\n\n"
            "<i>Команда доступна только старшим администраторам</i>",
            parse_mode="html"
        )
        return
    
    target_user_id_str = args[1].strip()
    
    # Проверяем ID пользователя
    try:
        target_user_id = int(target_user_id_str)
    except ValueError:
        await message.reply(
            f"❌ <b>Неверный ID пользователя!</b>\n\n"
            f"ID должен быть числом.\n"
            f"Вы указали: <code>{target_user_id_str}</code>",
            parse_mode="html"
        )
        return
    
    try:
        # Проверяем существование пользователя
        user_info = get_user_info(target_user_id)
        if not user_info:
            await message.reply(
                f"❌ <b>Пользователь с ID {target_user_id} не найден!</b>\n\n"
                f"Проверьте правильность ID пользователя.",
                parse_mode="html"
            )
            return
        
        user_display = f"@{user_info['username']}" if user_info['username'] else user_info['first_name']
        
        # Получаем текущие карточки пользователя
        current_cards = get_user_cards(target_user_id)
        
        if not current_cards:
            await message.reply(
                f"ℹ️ <b>У пользователя нет карточек!</b>\n\n"
                f"<b>Пользователь:</b> {user_display}\n"
                f"<b>ID:</b> <code>{target_user_id}</code>\n\n"
                f"<i>Нечего удалять</i>",
                parse_mode="html"
            )
            return
        
        # Создаем клавиатуру для подтверждения
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="✅ Да, удалить все",
                callback_data=f"confirm_delete_all_{target_user_id}"
            ),
            InlineKeyboardButton(
                text="❌ Нет, отменить",
                callback_data="cancel_delete_all"
            )
        )
        
        await message.reply(
            f"⚠️ <b>ВНИМАНИЕ!</b>\n\n"
            f"Вы собираетесь удалить <b>ВСЕ карточки</b> у пользователя:\n\n"
            f"<b>Пользователь:</b> {user_display}\n"
            f"<b>ID:</b> <code>{target_user_id}</code>\n\n"
            f"<b>Количество карточек для удаления:</b> {len(current_cards)}\n\n"
            f"<b>Будут удалены следующие типы карточек:</b>\n"
            f"• Редкие: {sum(1 for c in current_cards if c[3].lower() in ['редкий', 'редкая'])}\n"
            f"• Эпические: {sum(1 for c in current_cards if c[3].lower() in ['эпический', 'эпическая', 'эпик'])}\n"
            f"• Легендарные: {sum(1 for c in current_cards if c[3].lower() in ['легендарный', 'легендарная'])}\n"
            f"• Суперлегендарные: {sum(1 for c in current_cards if c[3].lower() in ['суперлегендарный', 'супер'])}\n\n"
            f"<b>Это действие необратимо!</b>\n\n"
            f"Вы уверены, что хотите продолжить?",
            parse_mode="html",
            reply_markup=builder.as_markup()
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка в команде /deleteallcards: {e}")
        await message.reply(
            f"❌ Произошла ошибка: {str(e)[:100]}",
            parse_mode="html"
        )

# 10. КОЛБЭК ДЛЯ ПОДТВЕРЖДЕНИЯ УДАЛЕНИЯ ВСЕХ КАРТОЧЕК
@router_fkarta.callback_query(F.data.startswith("confirm_delete_all_"))
async def confirm_delete_all_callback(callback: CallbackQuery):
    """Подтверждение удаления всех карточек"""
    try:
        target_user_id = int(callback.data.split("_")[3])
        
        # Удаляем все карточки пользователя
        db_operation(
            "DELETE FROM user_cards WHERE user_id = ?",
            (target_user_id,)
        )
        
        # Получаем информацию о пользователе
        user_info = get_user_info(target_user_id)
        user_display = f"@{user_info['username']}" if user_info and user_info['username'] else f"ID: {target_user_id}"
        
        await callback.message.edit_text(
            f"✅ <b>Все карточки удалены!</b>\n\n"
            f"<b>Пользователь:</b> {user_display}\n"
            f"<b>ID:</b> <code>{target_user_id}</code>\n\n"
            f"<i>Коллекция пользователя полностью очищена</i>",
            parse_mode="html"
        )
        
        logger.warning(f"👑 Старший админ {callback.from_user.id} удалил все карточки у пользователя {target_user_id} ({user_display})")
        
        await callback.answer("Карточки удалены")
        
    except Exception as e:
        logger.error(f"Ошибка в confirm_delete_all_callback: {e}")
        await callback.answer("❌ Ошибка при удалении", show_alert=True)

# 11. КОЛБЭК ДЛЯ ОТМЕНЫ УДАЛЕНИЯ ВСЕХ КАРТОЧЕК
@router_fkarta.callback_query(F.data == "cancel_delete_all")
async def cancel_delete_all_callback(callback: CallbackQuery):
    """Отмена удаления всех карточек"""
    try:
        await callback.message.edit_text(
            "❌ <b>Удаление отменено</b>\n\n"
            "<i>Карточки пользователя не были удалены</i>",
            parse_mode="html"
        )
        await callback.answer("Удаление отменено")
        
    except Exception as e:
        logger.error(f"Ошибка в cancel_delete_all_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

# 12. ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ПОИСКА ПОХОЖИХ КАРТОЧЕК
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
#==========================
#обработчик сообщений из ТГК



#==========================
#обработчик TRADE
class TradeStates(StatesGroup):
    waiting_for_card_id = State()
    viewing_sell_cards = State() 
    waiting_for_sell_card_number = State()
    waiting_for_sell_price = State()
    waiting_for_remove_sale_id = State()



import random








def get_last_insert_id():
    """Получает ID последней вставленной записи"""
    try:
        result = db_operation("SELECT last_insert_rowid()", fetch=True)
        if result and result[0][0]:
            return result[0][0]
        # Альтернативный способ
        result = db_operation("SELECT seq FROM sqlite_sequence WHERE name='sell_cards'", fetch=True)
        if result:
            return result[0][0]
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении последнего ID: {e}")
        return None

def add_card_to_sell(card_id: int, price: int, comment: str, added_by_id: int):
    """Добавляет карточку в продажу (админская продажа)"""
    try:
        # Проверяем, существует ли карточка
        card_check = db_operation(
            "SELECT id, nickname FROM players_catalog WHERE id = ?",
            (card_id,),
            fetch=True
        )
        
        if not card_check:
            return False, f"Карточка с ID {card_id} не найдена"
        
        card_db_id, card_nickname = card_check[0]
        
        # Проверяем цену
        if price <= 0:
            return False, "Цена должна быть больше 0"
        if price > 10000:
            return False, "Цена не может превышать 10000 коинов"
        
        # Проверяем, не продается ли уже
        existing = db_operation(
            "SELECT 1 FROM sell_cards WHERE card_id = ? AND is_available = 1",
            (card_id,),
            fetch=True
        )
        
        if existing:
            return False, f"Карточка '{card_nickname}' уже есть в продаже"
        
        # Проверяем комментарий
        if not comment or comment.strip() == "":
            comment = "Без комментария"
        elif len(comment) > 100:
            comment = comment[:97] + "..."
        
        # Добавляем в продажу (используем card_id как primary key)
        db_operation(
            """INSERT OR REPLACE INTO sell_cards (card_id, price, comment, added_by_id, is_available) 
               VALUES (?, ?, ?, ?, 1)""",
            (card_id, price, comment, added_by_id)
        )
        
        logger.info(f"✅ Карточка '{card_nickname}' (ID: {card_id}) добавлена в продажу")
        return True, f"Карточка '{card_nickname}' добавлена в продажу (ID: {card_id})"
        
    except Exception as e:
        logger.error(f"❌ Ошибка при добавлении карточки в продажу: {e}")
        return False, f"Ошибка: {str(e)[:100]}"






# ===================
# УНИВЕРСАЛЬНАЯ СИСТЕМА ПОКУПКИ
# ===================

def get_all_cards_for_sale():
    """Получает ВСЕ карточки, доступные для покупки"""
    try:
        cards = []
        
        # Админские карточки
        admin_cards = get_all_sell_cards()
        for card in admin_cards:
            cards.append({
                'sell_id': card['sell_id'],
                'nickname': card['nickname'],
                'club': card['club'],
                'position': card['position'],
                'rarity': card['rarity'],
                'price': card['price'],
                'type': 'admin',
                'seller': 'Администратор'
            })
        
        # Пользовательские карточки
        user_cards = db_operation(
            """SELECT 
                   ust.id as sell_id,
                   pc.nickname,
                   pc.club,
                   pc.position,
                   pc.rarity,
                   ust.price,
                   au.username,
                   au.first_name
               FROM user_sell_transactions ust
               JOIN players_catalog pc ON ust.card_id = pc.id
               JOIN all_users au ON ust.seller_id = au.id
               WHERE ust.status = 'active'""",
            fetch=True
        )
        
        if user_cards:
            for row in user_cards:
                sell_id, nickname, club, position, rarity, price, username, first_name = row
                
                seller_name = f"@{username}" if username else first_name
                
                cards.append({
                    'sell_id': sell_id,
                    'nickname': nickname,
                    'club': club,
                    'position': position,
                    'rarity': rarity,
                    'price': price,
                    'type': 'user',
                    'seller': seller_name
                })
        
        return cards
        
    except Exception as e:
        logger.error(f"Ошибка в get_all_cards_for_sale: {e}")
        return []

def buy_card_universal(user_id: int, sell_id: int):
    """Универсальная функция покупки карточки по ID продажи"""
    try:
        # Определяем тип продажи
        sale_info = get_sell_card_info(sell_id)
        if not sale_info:
            return False, "Продажа не найдена"
        
        card_id = sale_info.get('card_id')
        price = sale_info.get('price')
        nickname = sale_info.get('nickname')
        sale_type = sale_info.get('type')
        
        # Проверяем коины
        user_coins = get_user_coins(user_id)
        if user_coins < price:
            return False, f"Недостаточно коинов. Нужно: {price}, у вас: {user_coins}"
        
        # Проверяем, есть ли уже карточка
        if user_has_card(user_id, card_id):
            return False, f"У вас уже есть карточка '{nickname}'"
        
        # В зависимости от типа продажи
        if sale_type == 'user':
            # Пользовательская продажа
            seller_id = sale_info.get('seller_id')
            
            # Проверяем, что покупатель не является продавцом
            if user_id == seller_id:
                return False, "Вы не можете купить свою же карточку"
            
            # Начинаем транзакцию
            # 1. Списываем коины у покупателя
            success, message = subtract_user_coins(user_id, price)
            if not success:
                return False, f"Ошибка списания коинов: {message}"
            
            # 2. Добавляем коины продавцу
            add_user_coins(seller_id, price)
            
            # 3. Удаляем карточку у продавца
            db_operation(
                "DELETE FROM user_cards WHERE user_id = ? AND card_id = ?",
                (seller_id, card_id)
            )
            
            # 4. Добавляем карточку покупателю
            add_card_to_user(user_id, card_id)
            
            # 5. Обновляем статус продажи
            db_operation(
                """UPDATE user_sell_transactions 
                   SET buyer_id = ?, status = 'sold', sold_at = CURRENT_TIMESTAMP 
                   WHERE id = ?""",
                (user_id, sell_id)
            )
            
            # 6. Добавляем в историю покупок
            db_operation(
                """INSERT INTO purchase_history (user_id, sell_id, card_id, price, transaction_type) 
                   VALUES (?, ?, ?, ?, 'user_sell')""",
                (user_id, sell_id, card_id, price)
            )
            
        else:
            # Админская продажа
            # 1. Списываем коины у покупателя
            success, message = subtract_user_coins(user_id, price)
            if not success:
                return False, f"Ошибка списания коинов: {message}"
            
            # 2. Добавляем карточку покупателю
            add_card_to_user(user_id, card_id)
            
            # 3. Помечаем как проданную
            db_operation(
                "UPDATE sell_cards SET is_available = 0 WHERE id = ?",
                (sell_id,)
            )
            
            # 4. Добавляем в историю покупок
            db_operation(
                """INSERT INTO purchase_history (user_id, sell_id, card_id, price, transaction_type) 
                   VALUES (?, ?, ?, ?, 'admin_sell')""",
                (user_id, sell_id, card_id, price)
            )
        
        return True, {
            'success': True,
            'message': f"Карточка '{nickname}' успешно куплена!",
            'price': price,
            'card_id': card_id,
            'nickname': nickname
        }
        
    except Exception as e:
        logger.error(f"Ошибка при покупке карточки: {e}")
        return False, f"Ошибка: {str(e)[:100]}"









def remove_card_from_sell(card_id: int):
    """Удаляет карточку из продажи"""
    try:
        # Получаем информацию о карточке
        card_check = db_operation(
            """SELECT pc.nickname 
               FROM players_catalog pc
               WHERE pc.id = ?""",
            (card_id,),
            fetch=True
        )
        
        if not card_check:
            return False, "Карточка не найдена"
        
        nickname = card_check[0][0] or f"ID: {card_id}"
        
        # Удаляем из продажи
        db_operation(
            "DELETE FROM sell_cards WHERE card_id = ?",
            (card_id,)
        )
        
        logger.info(f"✅ Карточка '{nickname}' (ID: {card_id}) удалена из продажи")
        return True, f"Карточка '{nickname}' удалена из продажи"
        
    except Exception as e:
        logger.error(f"❌ Ошибка при удалении карточки из продажи: {e}")
        return False, f"Ошибка: {str(e)[:100]}"

# Временно добавьте отладочную информацию
def get_sell_card_info(sell_id: int):
    """Получает информацию о карточке в продаже по ID продажи - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    try:
        # Сначала проверяем админские продажи
        admin_result = db_operation(
            """SELECT 
                   sc.id,
                   sc.card_id,
                   sc.price,
                   COALESCE(sc.comment, '') as comment,
                   sc.added_at,
                   sc.is_available,
                   pc.nickname,
                   pc.club,
                   pc.position,
                   pc.rarity,
                   sc.added_by_id,
                   au.username as added_by_username
             FROM sell_cards sc
             JOIN players_catalog pc ON sc.card_id = pc.id
             LEFT JOIN all_users au ON sc.added_by_id = au.id
             WHERE sc.id = ?""",
            (sell_id,),
            fetch=True
        )
        
        if admin_result:
            row = admin_result[0]
            seller_name = None
            if row[11]:  # added_by_username
                seller_name = f"@{row[11]}"
            else:
                seller_name = "Администратор"
            
            return {
                'sell_id': row[0],
                'card_id': row[1],
                'price': row[2],
                'comment': row[3],  # Теперь всегда будет строка
                'added_at': row[4],
                'is_available': row[5],
                'nickname': row[6],
                'club': row[7],
                'position': row[8],
                'rarity': row[9],
                'seller': seller_name,
                'seller_id': row[10],
                'status_text': "✅ Доступна" if row[5] == 1 else "❌ Продана",
                'type': 'admin'
            }
        
        # Если не нашли в админских, проверяем пользовательские
        user_result = db_operation(
            """SELECT 
                   ust.id,
                   ust.seller_id,
                   ust.card_id,
                   ust.price,
                   ust.status,
                   pc.nickname,
                   pc.club,
                   pc.position,
                   pc.rarity,
                   COALESCE(au.username, '') as seller_username,
                   COALESCE(au.first_name, '') as seller_first_name
             FROM user_sell_transactions ust
             JOIN players_catalog pc ON ust.card_id = pc.id
             JOIN all_users au ON ust.seller_id = au.id
             WHERE ust.id = ?""",
            (sell_id,),
            fetch=True
        )
        
        if user_result:
            row = user_result[0]
            
            seller_name = None
            if row[9]:  # seller_username
                seller_name = f"@{row[9]}"
            elif row[10]:  # seller_first_name
                seller_name = row[10]
            else:
                seller_name = f"Игрок (ID: {row[1]})"
            
            return {
                'sell_id': row[0],
                'seller_id': row[1],
                'card_id': row[2],
                'price': row[3],
                'status': row[4],
                'nickname': row[5],
                'club': row[6],
                'position': row[7],
                'rarity': row[8],
                'seller': seller_name,
                'seller_username': row[9],
                'comment': '',  # Для пользовательских продаж комментария нет
                'status_text': "✅ Доступна" if row[4] == 'active' else "❌ Продана",
                'type': 'user'
            }
        
        return None
        
    except Exception as e:
        logger.error(f"❌ Ошибка при получении информации о продаже {sell_id}: {e}")
        return None


@router_fkarta.message(Command("check_ids"))
@require_role("старший-администратор")
async def check_ids_command(message: Message):
    """Проверка всех ID в системе"""
    try:
        result = db_operation("SELECT id FROM players_catalog", fetch=True)
        used_ids = {row[0] for row in result} if result else set()
        total_ids = len(used_ids)
        
        if total_ids == 0:
            await message.reply("🆔 В системе нет ID")
            return
        
        # Проверяем дубликаты
        admin_ids = db_operation("SELECT id FROM sell_cards", fetch=True) or []
        user_ids = db_operation("SELECT id FROM user_sell_transactions", fetch=True) or []
        
        admin_id_list = [row[0] for row in admin_ids]
        user_id_list = [row[0] for row in user_ids]
        
        # Ищем пересечения
        duplicates = set(admin_id_list).intersection(set(user_id_list))
        
        message_text = (
            f"🆔 <b>ПРОВЕРКА ID СИСТЕМЫ</b>\n\n"
            f"📊 <b>Статистика:</b>\n"
            f"• Всего уникальных ID: {total_ids}\n"
            f"• Админских продаж: {len(admin_id_list)}\n"
            f"• Пользовательских продаж: {len(user_id_list)}\n\n"
        )
        
        if duplicates:
            message_text += (
                f"⚠️ <b>НАЙДЕНЫ ДУБЛИКАТЫ ID!</b>\n"
                f"Дублирующиеся ID: {sorted(list(duplicates))}\n\n"
                f"<i>Необходимо исправить через команду /fix_duplicate_ids</i>\n\n"
            )
        else:
            message_text += "✅ <b>Все ID уникальны!</b>\n\n"
        
        # Показываем диапазон ID
        if used_ids:
            min_id = min(used_ids)
            max_id = max(used_ids)
            message_text += (
                f"📈 <b>Диапазон ID:</b>\n"
                f"• Минимальный: {min_id}\n"
                f"• Максимальный: {max_id}\n"
                f"• Трехзначные: {sum(1 for id in used_ids if 100 <= id <= 999)} шт.\n"
                f"• Четырехзначные: {sum(1 for id in used_ids if id >= 1000)} шт.\n\n"
            )
        
        # Показываем несколько ID для примера
        sample_ids = sorted(list(used_ids))[:10]
        message_text += f"<b>Пример ID:</b>\n" + ", ".join([str(id) for id in sample_ids])
        
        await message.reply(message_text, parse_mode="html")
        
    except Exception as e:
        logger.error(f"Ошибка в check_ids_command: {e}")
        await message.reply(f"❌ Ошибка: {str(e)}")




@router_fkarta.message(Command("fix_sell_status"))
@require_role("старший-администратор")
async def fix_sell_status_command(message: Message):
    """Исправляет статусы карточек в продаже"""
    try:
        # Устанавливаем всем карточкам is_available = 1
        db_operation(
            "UPDATE sell_cards SET is_available = 1 WHERE is_available = 0 OR is_available IS NULL"
        )
        
        # Проверяем результат
        result = db_operation(
            "SELECT COUNT(*) FROM sell_cards WHERE is_available = 1",
            fetch=True
        )
        
        count = result[0][0] if result else 0
        
        await message.reply(
            f"✅ <b>Статусы исправлены!</b>\n\n"
            f"Теперь доступно для продажи: <b>{count}</b> карточек\n\n"
            f"<i>Проверьте через /viewsellcards</i>",
            parse_mode="html"
        )
        
    except Exception as e:
        await message.reply(f"❌ Ошибка: {str(e)}")

def get_all_sell_cards():
    """Получает все карточки в продаже (от админов) - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    try:
        result = db_operation(
            """SELECT 
                   sc.id, 
                   COALESCE(pc.nickname, 'УДАЛЕНА') as nickname,
                   COALESCE(pc.club, 'Неизвестно') as club,
                   COALESCE(pc.position, 'Неизвестно') as position,
                   COALESCE(pc.rarity, 'Неизвестно') as rarity,
                   sc.price, 
                   sc.comment, 
                   sc.added_at,
                   sc.is_available,
                   sc.added_by_id
               FROM sell_cards sc
               LEFT JOIN players_catalog pc ON sc.card_id = pc.id
               WHERE sc.is_available = 1
               ORDER BY sc.price, pc.rarity, pc.nickname""",
            fetch=True
        )
        
        cards = []
        for row in result:
            cards.append({
                'sell_id': row[0],
                'nickname': row[1],
                'club': row[2],
                'position': row[3],
                'rarity': row[4],
                'price': row[5],
                'comment': row[6] or '',
                'added_at': row[7],
                'is_available': row[8],
                'added_by_id': row[9],
                'type': 'admin',
                'seller_display': 'Администратор'
            })
        
        return cards
        
    except Exception as e:
        logger.error(f"❌ Ошибка при получении карточек в продаже: {e}")
        return []
@router_fkarta.message(Command("sell_monitor"))
@require_role("помощник-администратора")
async def sell_monitor_command(message: Message):
    """Мониторинг целостности продаж (все типы)"""
    try:
        # 1. Статистика по админским продажам
        admin_stats = db_operation(
            """SELECT 
                   COUNT(*) as total,
                   SUM(CASE WHEN is_available = 1 THEN 1 ELSE 0 END) as available,
                   SUM(CASE WHEN is_available = 0 THEN 1 ELSE 0 END) as sold,
                   SUM(CASE WHEN is_available IS NULL THEN 1 ELSE 0 END) as null_status,
                   SUM(price) as total_value
               FROM sell_cards""",
            fetch=True
        )
        
        # 2. Статистика по пользовательским продажам
        user_stats = db_operation(
            """SELECT 
                   COUNT(*) as total,
                   SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active,
                   SUM(CASE WHEN status = 'sold' THEN 1 ELSE 0 END) as sold,
                   SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled,
                   SUM(price) as total_value
               FROM user_sell_transactions""",
            fetch=True
        )
        
        # 3. Некорректные записи в админских продажах
        admin_incorrect = db_operation(
            """SELECT COUNT(*)
               FROM sell_cards sc
               WHERE sc.is_available = 0
                 AND sc.id NOT IN (
                     SELECT sell_id 
                     FROM purchase_history 
                     WHERE sell_id IS NOT NULL
                 )""",
            fetch=True
        )
        
        # 4. Карточки без связи с каталогом (админские)
        admin_orphaned = db_operation(
            """SELECT COUNT(*)
               FROM sell_cards sc
               LEFT JOIN players_catalog pc ON sc.card_id = pc.id
               WHERE pc.id IS NULL""",
            fetch=True
        )
        
        # 5. Карточки без связи с каталогом (пользовательские)
        user_orphaned = db_operation(
            """SELECT COUNT(*)
               FROM user_sell_transactions ust
               LEFT JOIN players_catalog pc ON ust.card_id = pc.id
               WHERE pc.id IS NULL""",
            fetch=True
        )
        
        # 6. Пользовательские продажи без карточек у продавца
        user_no_card = db_operation(
            """SELECT COUNT(*)
               FROM user_sell_transactions ust
               WHERE ust.status = 'active'
                 AND ust.card_id NOT IN (
                     SELECT card_id 
                     FROM user_cards 
                     WHERE user_id = ust.seller_id
                 )""",
            fetch=True
        )
        
        # Получаем данные
        admin_total, admin_available, admin_sold, admin_null, admin_value = admin_stats[0] if admin_stats else (0, 0, 0, 0, 0)
        user_total, user_active, user_sold, user_cancelled, user_value = user_stats[0] if user_stats else (0, 0, 0, 0, 0)
        admin_incorrect_count = admin_incorrect[0][0] if admin_incorrect else 0
        admin_orphaned_count = admin_orphaned[0][0] if admin_orphaned else 0
        user_orphaned_count = user_orphaned[0][0] if user_orphaned else 0
        user_no_card_count = user_no_card[0][0] if user_no_card else 0
        
        # Общая статистика
        total_cards = admin_total + user_total
        total_available = admin_available + user_active
        total_sold = admin_sold + user_sold
        total_value = (admin_value or 0) + (user_value or 0)
        
        message_text = (
            f"📊 <b>МОНИТОРИНГ ВСЕХ ПРОДАЖ</b>\n\n"
            
            f"<b>ОБЩАЯ СТАТИСТИКА:</b>\n"
            f"• Всего карточек: {total_cards}\n"
            f"• Доступно для продажи: {total_available}\n"
            f"• Продано: {total_sold}\n"
            f"• Отменено: {user_cancelled}\n"
            f"• Общая стоимость: {total_value} коинов\n\n"
            
            f"<b>⚡ АДМИНСКИЕ ПРОДАЖИ:</b>\n"
            f"• Всего: {admin_total}\n"
            f"• Доступно: {admin_available}\n"
            f"• Продано: {admin_sold}\n"
            f"• Без статуса: {admin_null}\n"
            f"• Стоимость: {admin_value or 0} коинов\n\n"
            
            f"<b>👤 ПОЛЬЗОВАТЕЛЬСКИЕ ПРОДАЖИ:</b>\n"
            f"• Всего: {user_total}\n"
            f"• Активных: {user_active}\n"
            f"• Продано: {user_sold}\n"
            f"• Отменено: {user_cancelled}\n"
            f"• Стоимость: {user_value or 0} коинов\n\n"
            
            f"<b>🔍 ПРОБЛЕМНЫЕ ЗАПИСИ:</b>\n"
            f"• Некорректные статусы админских: {admin_incorrect_count}\n"
            f"• Админские без карточек в каталоге: {admin_orphaned_count}\n"
            f"• Пользовательские без карточек в каталоге: {user_orphaned_count}\n"
            f"• Пользовательские продажи без карточек у продавца: {user_no_card_count}\n\n"
        )
        
        # Проверяем на проблемы
        problems = []
        if admin_incorrect_count > 0:
            problems.append("🔸 Некорректные статусы админских продаж")
        if admin_orphaned_count > 0:
            problems.append("🔸 Админские продажи без карточек в каталоге")
        if user_orphaned_count > 0:
            problems.append("🔸 Пользовательские продажи без карточек в каталоге")
        if user_no_card_count > 0:
            problems.append("🔸 Пользовательские продажи без карточек у продавца")
        
        if problems:
            message_text += f"⚠️ <b>ОБНАРУЖЕНЫ ПРОБЛЕМЫ!</b>\n"
            for problem in problems:
                message_text += f"{problem}\n"
            
            message_text += f"\n<b>Команды для исправления:</b>\n"
            message_text += f"• <code>/fix_sell_status</code> - исправить статусы админских продаж\n"
            message_text += f"• <code>/clean_orphaned_sales</code> - очистить некорректные записи\n"
            message_text += f"• <code>/check_combined_sales</code> - проверить видимость всех карточек\n"
        else:
            message_text += "✅ <b>Все продажи в норме!</b>\n\n"
        
        # Добавляем информацию о видимости
        combined_cards = get_all_sell_cards_combined()
        visible_count = len(combined_cards) if combined_cards else 0
        
        message_text += (
            f"\n<b>👁️ ВИДИМОСТЬ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ:</b>\n"
            f"• Показывается карточек: {visible_count}\n"
            f"• Должно показываться: {total_available}\n"
        )
        
        if visible_count != total_available:
            message_text += f"⚠️ <b>РАСХОЖДЕНИЕ!</b> Разница: {abs(visible_count - total_available)}\n"
            message_text += f"Используйте <code>/debug_sales</code> для диагностики\n"
        else:
            message_text += "✅ <b>Все доступные карточки видны пользователям!</b>\n"
        
        await message.reply(message_text, parse_mode="html")
        
    except Exception as e:
        logger.error(f"Ошибка в sell_monitor_command: {e}")
        await message.reply(f"❌ Ошибка: {str(e)}")


@router_fkarta.message(Command("clean_orphaned_sales"))
@require_role("старший-администратор")
async def clean_orphaned_sales_command(message: Message):
    """Очищает некорректные записи о продажах"""
    try:
        removed_count = 0
        
        # 1. Удаляем админские продажи без карточек в каталоге
        admin_orphaned = db_operation(
            """SELECT sc.id, sc.card_id 
               FROM sell_cards sc
               LEFT JOIN players_catalog pc ON sc.card_id = pc.id
               WHERE pc.id IS NULL""",
            fetch=True
        )
        
        if admin_orphaned:
            for row in admin_orphaned:
                sell_id, card_id = row
                db_operation(
                    "DELETE FROM sell_cards WHERE id = ?",
                    (sell_id,)
                )
                removed_count += 1
                logger.warning(f"🗑️ Удалена админская продажа {sell_id} (карточка {card_id} не найдена в каталоге)")
        
        # 2. Удаляем пользовательские продажи без карточек в каталоге
        user_orphaned = db_operation(
            """SELECT ust.id, ust.card_id, ust.seller_id
               FROM user_sell_transactions ust
               LEFT JOIN players_catalog pc ON ust.card_id = pc.id
               WHERE pc.id IS NULL""",
            fetch=True
        )
        
        if user_orphaned:
            for row in user_orphaned:
                sell_id, card_id, seller_id = row
                db_operation(
                    "DELETE FROM user_sell_transactions WHERE id = ?",
                    (sell_id,)
                )
                removed_count += 1
                logger.warning(f"🗑️ Удалена пользовательская продажа {sell_id} (карточка {card_id} не найдена в каталоге)")
        
        # 3. Отменяем пользовательские продажи, где у продавца нет карточки
        user_no_card = db_operation(
            """SELECT ust.id, ust.card_id, ust.seller_id, pc.nickname
               FROM user_sell_transactions ust
               JOIN players_catalog pc ON ust.card_id = pc.id
               WHERE ust.status = 'active'
                 AND ust.card_id NOT IN (
                     SELECT card_id 
                     FROM user_cards 
                     WHERE user_id = ust.seller_id
                 )""",
            fetch=True
        )
        
        if user_no_card:
            for row in user_no_card:
                sell_id, card_id, seller_id, nickname = row
                db_operation(
                    """UPDATE user_sell_transactions 
                       SET status = 'cancelled' 
                       WHERE id = ?""",
                    (sell_id,)
                )
                removed_count += 1
                logger.warning(f"🚫 Отменена продажа {sell_id} (у продавца {seller_id} нет карточки {nickname})")
        
        await message.reply(
            f"✅ <b>ОЧИСТКА ЗАВЕРШЕНА!</b>\n\n"
            f"<b>Обработано записей:</b> {removed_count}\n"
            f"<b>Типы очистки:</b>\n"
            f"• Удалены орфанные записи\n"
            f"• Отменены некорректные продажи\n\n"
            f"<i>Используйте /sell_monitor для проверки</i>",
            parse_mode="html"
        )
        
    except Exception as e:
        logger.error(f"Ошибка в clean_orphaned_sales_command: {e}")
        await message.reply(f"❌ Ошибка: {str(e)}")
def purchase_card(user_id: int, sell_id: int):
    """Покупка карточки по ID продажи"""
    try:
        logger.info(f"🔍 Начало покупки: sell_id={sell_id}, user_id={user_id}")
        
        # Получаем информацию о продаже
        sale_info = get_sell_card_info(sell_id)
        if not sale_info:
            return False, "Продажа не найдена"
        
        card_id = sale_info.get('card_id')
        price = sale_info.get('price', 0)
        nickname = sale_info.get('nickname', 'Неизвестно')
        sale_type = sale_info.get('type')
        
        if not card_id:
            return False, "Ошибка: не найден ID карточки"
        
        # Проверяем коины покупателя
        buyer_coins = get_user_coins(user_id)
        if buyer_coins < price:
            return False, f"Недостаточно коинов. Нужно: {price}, у вас: {buyer_coins}"
        
        # Проверяем, есть ли уже карточка у покупателя
        if user_has_card(user_id, card_id):
            return False, f"У вас уже есть карточка '{nickname}'"
        
        # В зависимости от типа продажи обрабатываем по-разному
        if sale_type == 'user':
            # Пользовательская продажа
            seller_id = sale_info.get('seller_id')
            
            if not seller_id:
                return False, "Ошибка: не найден продавец"
            
            # Проверяем, что покупатель не является продавцом
            if user_id == seller_id:
                return False, "Вы не можете купить свою же карточку"
            
            # Проверяем, что продажа все еще активна
            status_check = db_operation(
                "SELECT status FROM user_sell_transactions WHERE id = ?",
                (sell_id,),
                fetch=True
            )
            
            if not status_check or status_check[0][0] != 'active':
                return False, "Карточка уже продана или отменена"
            
            # НАЧИНАЕМ ТРАНЗАКЦИЮ
            
            # 1. Списываем коины у покупателя
            success, message = subtract_user_coins(user_id, price)
            if not success:
                return False, f"Ошибка списания коинов: {message}"
            
            # 2. Добавляем коины продавцу
            add_user_coins(seller_id, price)
            
            # 3. Удаляем карточку у продавца
            db_operation(
                "DELETE FROM user_cards WHERE user_id = ? AND card_id = ?",
                (seller_id, card_id)
            )
            
            # 4. Добавляем карточку покупателю
            add_card_to_user(user_id, card_id)
            
            # 5. Обновляем статус продажи
            db_operation(
                """UPDATE user_sell_transactions 
                   SET buyer_id = ?, status = 'sold', sold_at = CURRENT_TIMESTAMP 
                   WHERE id = ?""",
                (user_id, sell_id)
            )
            
            # 6. Добавляем запись в историю покупок (ИСПРАВЛЕНО)
            db_operation(
    """INSERT INTO purchase_history (user_id, card_id, price, transaction_type, sell_id) 
       VALUES (?, ?, ?, ?, ?)""",
    (user_id, card_id, price, 'user_sell', sell_id)
)
            
            logger.warning(f"💰 ПОЛЬЗОВАТЕЛЬСКАЯ СДЕЛКА: Продавец {seller_id} → Покупатель {user_id} | Карточка: {nickname} за {price} коинов")
            
        else:
            # Админская продажа
            # Проверяем, что продажа все еще доступна
            status_check = db_operation(
                "SELECT is_available FROM sell_cards WHERE id = ?",
                (sell_id,),
                fetch=True
            )
            
            if not status_check or status_check[0][0] != 1:
                return False, "Карточка уже продана"
            
            # 1. Списываем коины у покупателя
            success, message = subtract_user_coins(user_id, price)
            if not success:
                return False, f"Ошибка списания коинов: {message}"
            
            # 2. Добавляем карточку покупателю
            add_card_to_user(user_id, card_id)
            
            # 3. Помечаем карточку как проданную
            db_operation(
                "UPDATE sell_cards SET is_available = 0 WHERE id = ?",
                (sell_id,)
            )
            
            # 4. Добавляем запись в историю покупок (ИСПРАВЛЕНО)
            db_operation(
                """INSERT INTO purchase_history (user_id, card_id, price, transaction_type, sell_id) 
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, card_id, price, 'admin_sell', sell_id)
            )
            
            logger.warning(f"💰 АДМИНСКАЯ ПОКУПКА: {user_id} купил {nickname} за {price} коинов")
        
        return True, {
            'success': True,
            'message': f"Карточка '{nickname}' успешно куплена!",
            'price': price,
            'card_id': card_id,
            'sell_id': sell_id,
            'nickname': nickname
        }
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при покупке: {e}")
        import traceback
        logger.error(f"Трейсбэк: {traceback.format_exc()}")
        return False, f"Внутренняя ошибка сервера: {str(e)[:100]}"



        


def get_total_purchases_stats():
    """Получает статистику по покупкам"""
    try:
        # Общее количество покупок
        total_result = db_operation(
            "SELECT COUNT(*), SUM(price) FROM purchase_history",
            fetch=True
        )
        
        total_count = total_result[0][0] if total_result else 0
        total_coins = total_result[0][1] if total_result and total_result[0][1] else 0
        
        # Покупки за последние 7 дней
        week_result = db_operation(
            """SELECT COUNT(*), SUM(price) 
               FROM purchase_history 
               WHERE purchased_at >= datetime('now', '-7 days')""",
            fetch=True
        )
        
        week_count = week_result[0][0] if week_result else 0
        week_coins = week_result[0][1] if week_result and week_result[0][1] else 0
        
        return {
            'total_count': total_count,
            'total_coins': total_coins,
            'week_count': week_count,
            'week_coins': week_coins
        }
    except Exception as e:
        logger.error(f"Ошибка при получении статистики покупок: {e}")
        return None

def is_card_in_sale(card_id: int):
    """Проверяет, продается ли карточка"""
    try:
        # Проверяем админские продажи
        admin_check = db_operation(
            "SELECT 1 FROM sell_cards WHERE card_id = ? AND is_available = 1",
            (card_id,),
            fetch=True
        )
        
        # Проверяем пользовательские продажи
        user_check = db_operation(
            "SELECT 1 FROM user_sell_transactions WHERE card_id = ? AND status = 'active'",
            (card_id,),
            fetch=True
        )
        
        return admin_check or user_check
        
    except Exception as e:
        logger.error(f"Ошибка при проверке продажи карточки {card_id}: {e}")
        return False

def get_total_purchases_stats():
    """Получает статистику по покупкам"""
    try:
        # Общее количество покупок
        total_result = db_operation(
            "SELECT COUNT(*), SUM(price) FROM purchase_history",
            fetch=True
        )
        
        total_count = total_result[0][0] if total_result else 0
        total_coins = total_result[0][1] if total_result and total_result[0][1] else 0
        
        # Покупки за последние 7 дней
        week_result = db_operation(
            """SELECT COUNT(*), SUM(price) 
               FROM purchase_history 
               WHERE purchased_at >= datetime('now', '-7 days')""",
            fetch=True
        )
        
        week_count = week_result[0][0] if week_result else 0
        week_coins = week_result[0][1] if week_result and week_result[0][1] else 0
        
        return {
            'total_count': total_count,
            'total_coins': total_coins,
            'week_count': week_count,
            'week_coins': week_coins
        }
    except Exception as e:
        logger.error(f"Ошибка при получении статистики покупок: {e}")
        return None
@router_fkarta.message(Command("addsellcard"))
@require_role("старший-администратор")
async def addsellcard_command(message: Message):
    """Добавить карточку в продажу"""
    command_text = message.text.strip()
    args = command_text.split(maxsplit=3)
    
    if len(args) < 4:
        await message.reply(
            "📝 <b>Использование команды:</b>\n\n"
            "<code>/addsellcard [id_карточки] [цена] [комментарий]</code>\n\n"
            "<b>Примеры:</b>\n"
            "• <code>/addsellcard 1 10 Редкая карточка</code>\n"
            "<i>ID карточки можно узнать через /allcards</i>",
            parse_mode="html"
        )
        return
    
    try:
        card_id = int(args[1])
        price = int(args[2])
        comment = args[3] if len(args) > 3 else ""
        
        # Получаем информацию о карточке
        card_info = db_operation(
            "SELECT nickname FROM players_catalog WHERE id = ?",
            (card_id,),
            fetch=True
        )
        
        if not card_info:
            await message.reply(f"❌ Карточка с ID {card_id} не найдена")
            return
        
        nickname = card_info[0][0]
        
        # Добавляем в продажу
        success, msg = add_card_to_sell(card_id, price, comment, message.from_user.id)
        
        if success:
            await message.reply(
                f"✅ <b>КАРТОЧКА ДОБАВЛЕНА В ПРОДАЖУ!</b>\n\n"
                f"<b>Игрок:</b> {nickname}\n"
                f"<b>ID карточки:</b> <code>{card_id}</code>\n"
                f"<b>Цена:</b> {price} коинов\n"
                f"<b>Комментарий:</b> {comment if comment else 'Нет'}",
                parse_mode="html"
            )
        else:
            await message.reply(f"❌ {msg}")
            
    except ValueError:
        await message.reply("❌ Неверный формат! ID и цена должны быть числами.")
    except Exception as e:
        logger.error(f"Ошибка в команде /addsellcard: {e}")
        await message.reply(f"❌ Ошибка: {str(e)[:100]}")

@router_fkarta.message(Command("dellsellcard"))
@require_role("старший-администратор")
async def dellsellcard_command(message: Message):
    """Удалить карточку из продажи (админскую или пользовательскую)"""
    command_text = message.text.strip()
    args = command_text.split()
    
    if len(args) < 2:
        await message.reply(
            "📝 <b>Использование команды:</b>\n\n"
            "<code>/dellsellcard [id_продажи]</code>\n\n"
            "<b>Примеры:</b>\n"
            "• <code>/dellsellcard 1</code> - удалить продажу с ID 1\n"
            "• <code>/dellsellcard 123</code> - удалить продажу с ID 123\n\n"
            "<b>Примечания:</b>\n"
            "• ID продажи можно узнать через /viewsellcards\n"
            "• Команда работает для АДМИНСКИХ и ПОЛЬЗОВАТЕЛЬСКИХ продаж\n"
            "• Действие необратимо!\n\n"
            "<i>Команда доступна только администраторам</i>",
            parse_mode="html"
        )
        return
    
    try:
        sell_id = int(args[1])
        
        # 1. Сначала проверяем, админская ли это продажа
        admin_check = db_operation(
            "SELECT id, card_id FROM sell_cards WHERE id = ?",
            (sell_id,),
            fetch=True
        )
        
        if admin_check:
            # Это админская продажа
            admin_id, card_id = admin_check[0]
            
            # Получаем информацию о карточке
            card_info = db_operation(
                "SELECT nickname FROM players_catalog WHERE id = ?",
                (card_id,),
                fetch=True
            )
            
            if card_info:
                card_name = card_info[0][0]
            else:
                card_name = f"ID: {card_id}"
            
            # Удаляем админскую продажу
            db_operation(
                "DELETE FROM sell_cards WHERE id = ?",
                (sell_id,)
            )
            
            await message.reply(
                f"✅ <b>АДМИНСКАЯ ПРОДАЖА УДАЛЕНА!</b>\n\n"
                f"<b>ID продажи:</b> <code>{sell_id}</code>\n"
                f"<b>Карточка:</b> {card_name}\n"
                f"<b>Тип:</b> Административная продажа\n\n"
                f"<i>Карточка убрана с продажи</i>",
                parse_mode="html"
            )
            
            logger.warning(f"👑 Админ {message.from_user.id} удалил админскую продажу {sell_id}")
            return
        
        # 2. Проверяем, пользовательская ли это продажа
        user_check = db_operation(
            """SELECT ust.id, ust.card_id, ust.seller_id, ust.price, 
                      pc.nickname, au.username
               FROM user_sell_transactions ust
               JOIN players_catalog pc ON ust.card_id = pc.id
               LEFT JOIN all_users au ON ust.seller_id = au.id
               WHERE ust.id = ? AND ust.status = 'active'""",
            (sell_id,),
            fetch=True
        )
        
        if user_check:
            # Это пользовательская продажа
            sell_id, card_id, seller_id, price, nickname, username = user_check[0]
            seller_name = f"@{username}" if username else f"ID: {seller_id}"
            
            # Удаляем пользовательскую продажу
            db_operation(
                "DELETE FROM user_sell_transactions WHERE id = ?",
                (sell_id,)
            )
            
            # Возвращаем карточку пользователю (если она еще у него есть)
            # Сначала проверяем, есть ли карточка у пользователя
            has_card = db_operation(
                "SELECT 1 FROM user_cards WHERE user_id = ? AND card_id = ?",
                (seller_id, card_id),
                fetch=True
            )
            
            if not has_card:
                # Возвращаем карточку пользователю
                db_operation(
                    "INSERT OR IGNORE INTO user_cards (user_id, card_id) VALUES (?, ?)",
                    (seller_id, card_id)
                )
                card_returned = "✅ Карточка возвращена продавцу"
            else:
                card_returned = "ℹ️ Карточка уже была у продавца"
            
            await message.reply(
                f"✅ <b>ПОЛЬЗОВАТЕЛЬСКАЯ ПРОДАЖА УДАЛЕНА!</b>\n\n"
                f"<b>ID продажи:</b> <code>{sell_id}</code>\n"
                f"<b>Карточка:</b> {nickname}\n"
                f"<b>Продавец:</b> {seller_name}\n"
                f"<b>Цена:</b> {price} коинов\n"
                f"<b>Тип:</b> Пользовательская продажа\n\n"
                f"{card_returned}\n\n"
                f"<i>Продажа отменена, карточка снята с продажи</i>",
                parse_mode="html"
            )
            
            logger.warning(f"👑 Админ {message.from_user.id} удалил пользовательскую продажу {sell_id} от {seller_name}")
            return
        
        # 3. Если не нашли ни админскую, ни пользовательскую продажу
        await message.reply(
            f"❌ <b>Продажа не найдена!</b>\n\n"
            f"Продажа с ID <code>{sell_id}</code> не найдена.\n\n"
            f"<b>Возможные причины:</b>\n"
            f"• Продажа уже удалена\n"
            f"• Неверный ID продажи\n"
            f"• Продажа была уже продана\n\n"
            f"<i>Проверьте ID через /viewsellcards</i>",
            parse_mode="html"
        )
            
    except ValueError:
        await message.reply("❌ ID продажи должен быть числом.")
    except Exception as e:
        logger.error(f"Ошибка в команде /dellsellcard: {e}")
        await message.reply(f"❌ Ошибка: {str(e)[:100]}")

@router_fkarta.message(Command("viewsellcards"))
@require_role("помощник-администратора")
@log_admin_action("Просмотр карточек в продаже")
async def viewsellcards_command(message: Message, state: FSMContext):
    """Просмотр всех карточек в продаже (админских + пользовательских) с пагинацией"""
    try:
        # Получаем все карточки
        sell_cards = get_all_sell_cards_combined()
        
        if not sell_cards:
            await message.reply(
                "📭 <b>Нет карточек в продаже</b>\n\n"
                "<i>Используйте /addsellcard чтобы добавить карточки</i>",
                parse_mode="html"
            )
            return
        
        # Сохраняем карточки в состоянии для пагинации
        await state.update_data({
            "all_sell_cards": sell_cards,
            "current_view_page": 0,
            "view_mode": "viewsellcards"
        })
        
        # Показываем первую страницу
        await show_viewsellcards_page(message, state, 0)
        
    except Exception as e:
        logger.error(f"Ошибка в команде /viewsellcards: {str(e)}")
        await message.reply(f"❌ Ошибка: {str(e)[:100]}")

async def show_viewsellcards_page(message: Message, state: FSMContext, page: int = 0):
    """Показывает страницу карточек в продаже"""
    try:
        state_data = await state.get_data()
        sell_cards = state_data.get("all_sell_cards", [])
        
        if not sell_cards:
            await message.reply("Нет карточек в продаже")
            return
        
        # Настройки пагинации
        cards_per_page = 8  # Уменьшаем для большего количества информации
        total_cards = len(sell_cards)
        total_pages = (total_cards + cards_per_page - 1) // cards_per_page
        
        if page < 0:
            page = 0
        elif page >= total_pages:
            page = total_pages - 1
        
        # Получаем карточки для текущей страницы
        start_idx = page * cards_per_page
        end_idx = min(start_idx + cards_per_page, total_cards)
        page_cards = sell_cards[start_idx:end_idx]
        
        # Группируем карточки по типу для статистики
        admin_cards = [c for c in page_cards if c.get('type') == 'admin']
        user_cards = [c for c in page_cards if c.get('type') == 'user']
        
        # Формируем заголовок
        message_text = (
            f"🛒 <b>ВСЕ КАРТОЧКИ В ПРОДАЖЕ</b>\n\n"
            f"📊 <b>Общая статистика:</b>\n"
            f"• Всего карточек: {total_cards}\n"
            f"• Админских: {len([c for c in sell_cards if c.get('type') == 'admin'])}\n"
            f"• Пользовательских: {len([c for c in sell_cards if c.get('type') == 'user'])}\n"
            f"• Стоимость всех: {sum(c.get('price', 0) for c in sell_cards)} коинов\n\n"
            f"<b>📄 Страница {page + 1} из {total_pages}</b>\n"
            f"<i>Карточки {start_idx + 1}-{end_idx} из {total_cards}</i>\n\n"
        )
        
        # Показываем админские карточки
        if admin_cards:
            message_text += "⚡ <b>АДМИНСКИЕ КАРТОЧКИ</b>\n"
            message_text += "─" * 40 + "\n"
            
            for card in admin_cards:
                rarity_display = 'Эпический' if card['rarity'] == 'эпическая' else card['rarity']
                message_text += (
                    f"🆔 <b>ID продажи:</b> <code>{card['sell_id']}</code>\n"
                    f"👤 <b>Игрок:</b> {card['nickname']}\n"
                    f"🏟️ <b>Клуб:</b> {card['club']}\n"
                    f"🎯 <b>Позиция:</b> {card['position']}\n"
                    f"💎 <b>Редкость:</b> {rarity_display}\n"
                    f"💰 <b>Цена:</b> {card['price']} коинов\n"
                )
                
                if card['comment'] and card['comment'] not in ['', 'no_comment']:
                    message_text += f"📝 <b>Комментарий:</b> {card['comment']}\n"
                
                message_text += f"📅 <b>Добавлена:</b> {card['added_at'][:16] if card['added_at'] else 'Не указана'}\n"
                message_text += f"👤 <b>Продавец:</b> {card['seller_display']}\n"
                message_text += "─" * 40 + "\n"
            
            message_text += "\n"
        
        # Показываем пользовательские карточки
        if user_cards:
            message_text += "👤 <b>ПОЛЬЗОВАТЕЛЬСКИЕ КАРТОЧКИ</b>\n"
            message_text += "─" * 40 + "\n"
            
            for card in user_cards:
                rarity_display = 'Эпический' if card['rarity'] == 'эпическая' else card['rarity']
                message_text += (
                    f"🆔 <b>ID продажи:</b> <code>{card['sell_id']}</code>\n"
                    f"👤 <b>Игрок:</b> {card['nickname']}\n"
                    f"🏟️ <b>Клуб:</b> {card['club']}\n"
                    f"🎯 <b>Позиция:</b> {card['position']}\n"
                    f"💎 <b>Редкость:</b> {rarity_display}\n"
                    f"💰 <b>Цена:</b> {card['price']} коинов\n"
                )
                
                # Получаем информацию о продавце
                seller_id = card.get('seller_id')
                if seller_id:
                    seller_info = db_operation(
                        """SELECT username, first_name 
                           FROM all_users 
                           WHERE id = ?""",
                        (seller_id,),
                        fetch=True
                    )
                    
                    if seller_info:
                        username, first_name = seller_info[0]
                        seller_name = f"@{username}" if username else first_name or f"ID: {seller_id}"
                        message_text += f"👤 <b>Продавец:</b> {seller_name}\n"
                        message_text += f"🆔 <b>ID продавца:</b> <code>{seller_id}</code>\n"
                
                message_text += "─" * 40 + "\n"
            
            message_text += "\n"
        
        # Форматируем команды
        message_text += (
            f"<b>Команды для управления:</b>\n"
            f"• <code>/addsellcard ID цена комментарий</code> - добавить админскую\n"
            f"• <code>/dellsellcard ID</code> - удалить админскую\n"
            f"• <code>/remove_user_sale ID</code> - удалить пользовательскую\n"
        )
        
        # Создаем клавиатуру с навигацией
        builder = InlineKeyboardBuilder()
        
        # Навигация по страницам
        nav_buttons = []
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data=f"viewsell_page_{page - 1}"
                )
            )
        
        nav_buttons.append(
            InlineKeyboardButton(
                text=f"📄 {page + 1}/{total_pages}",
                callback_data="noop"
            )
        )
        
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="Вперед ➡️",
                    callback_data=f"viewsell_page_{page + 1}"
                )
            )
        
        if nav_buttons:
            builder.row(*nav_buttons)
        
        # Основные кнопки
        builder.row(
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data="viewsell_refresh"
            ),
            InlineKeyboardButton(
                text="📊 Статистика",
                callback_data="viewsell_stats"
            )
        )
        
        # Проверяем, это новое сообщение или редактирование
        if hasattr(message, 'reply'):
            await message.reply(
                message_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
        else:
            # Это для редактирования через callback
            await message.edit_text(
                message_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
        
    except Exception as e:
        logger.error(f"Ошибка в show_viewsellcards_page: {e}")
        if hasattr(message, 'reply'):
            await message.reply(f"❌ Ошибка: {str(e)[:100]}")
        else:
            await message.answer(f"❌ Ошибка: {str(e)[:100]}")


@router_fkarta.message(Command("remove_user_sale"))
@require_role("старший-администратор")
async def remove_user_sale_command(message: Message):
    """Удалить пользовательскую карточку из продажи"""
    command_text = message.text.strip()
    args = command_text.split()
    
    if len(args) < 2:
        await message.reply(
            "📝 <b>Использование команды:</b>\n\n"
            "<code>/remove_user_sale [id_карточки]</code>\n\n"
            "<i>ID карточки можно узнать через /viewsellcards</i>",
            parse_mode="html"
        )
        return
    
    try:
        card_id = int(args[1])  # Теперь используем card_id вместо sell_id
        
        # Получаем информацию о продаже
        sale_info = db_operation(
            """SELECT ust.seller_id, ust.price, pc.nickname, au.username
               FROM user_sell_transactions ust
               JOIN players_catalog pc ON ust.card_id = pc.id
               LEFT JOIN all_users au ON ust.seller_id = au.id
               WHERE ust.card_id = ?""",
            (card_id,),
            fetch=True
        )
        
        if not sale_info:
            await message.reply(f"❌ Продажа карточки с ID {card_id} не найдена.")
            return
        
        seller_id, price, nickname, username = sale_info[0]
        seller_name = f"@{username}" if username else f"ID: {seller_id}"
        
        # Удаляем продажу
        db_operation(
            "DELETE FROM user_sell_transactions WHERE card_id = ?",
            (card_id,)
        )
        
        # ... остальной код ...
        
    except ValueError:
        await message.reply("❌ ID карточки должен быть числом.")
    except Exception as e:
        logger.error(f"Ошибка в команде /remove_user_sale: {e}")
        await message.reply(f"❌ Ошибка: {str(e)[:100]}")


@router_fkarta.callback_query(F.data.startswith("viewsell_page_"))
async def viewsell_page_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик переключения страниц в /viewsellcards"""
    try:
        page = int(callback.data.split("_")[2])
        await show_viewsellcards_page(callback.message, state, page)
        await callback.answer(f"Страница {page + 1}")
    except Exception as e:
        logger.error(f"Ошибка в viewsell_page_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


def get_card_sale_info(card_data: dict):
    """Получает информацию о продаже из данных карточки (для обратной совместимости)"""
    # Если есть card_id, используем его
    if 'card_id' in card_data:
        return {
            'id': card_data['card_id'],
            'card_id': card_data['card_id'],
            'is_card_id': True
        }
    # Если есть sell_id, конвертируем (для старого кода)
    elif 'sell_id' in card_data:
        return {
            'id': card_data['sell_id'],
            'card_id': card_data.get('card_id', card_data['sell_id']),
            'is_card_id': False
        }
    else:
        return {
            'id': '?',
            'card_id': '?',
            'is_card_id': True
        }

@router_fkarta.callback_query(F.data == "viewsell_refresh")
async def viewsell_refresh_callback(callback: CallbackQuery, state: FSMContext):
    """Обновление списка карточек"""
    try:
        # Получаем текущую страницу
        state_data = await state.get_data()
        current_page = state_data.get("current_view_page", 0)
        
        # Получаем свежий список карточек
        sell_cards = get_all_sell_cards_combined()
        
        if not sell_cards:
            await callback.answer("Нет карточек в продаже", show_alert=True)
            return
        
        # Сохраняем обновленные данные
        await state.update_data({
            "all_sell_cards": sell_cards,
            "current_view_page": current_page
        })
        
        # Показываем ту же страницу
        await show_viewsellcards_page(callback.message, state, current_page)
        await callback.answer("🔄 Список обновлен")
        
    except Exception as e:
        logger.error(f"Ошибка в viewsell_refresh_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@router_fkarta.callback_query(F.data == "viewsell_stats")
async def viewsell_stats_callback(callback: CallbackQuery):
    """Показывает статистику продаж"""
    try:
        # Получаем статистику
        stats = get_sell_stats()
        
        if not stats:
            await callback.answer("Нет статистики", show_alert=True)
            return
        
        admin_info = stats['admin']
        user_info = stats['user']
        
        message_text = (
            f"📊 <b>СТАТИСТИКА ПРОДАЖ</b>\n\n"
            
            f"<b>ОБЩАЯ СТАТИСТИКА:</b>\n"
            f"• Всего карточек: {stats['total_cards']}\n"
            f"• Общая стоимость: {stats['total_value']} коинов\n\n"
            
            f"<b>⚡ АДМИНСКИЕ ПРОДАЖИ:</b>\n"
            f"• Всего: {admin_info['total']}\n"
            f"• Доступно: {admin_info['available']}\n"
            f"• Продано: {admin_info['sold']}\n"
            f"• Стоимость: {admin_info['total_value']} коинов\n\n"
            
            f"<b>👤 ПОЛЬЗОВАТЕЛЬСКИЕ ПРОДАЖИ:</b>\n"
            f"• Всего: {user_info['total']}\n"
            f"• Активные: {user_info['active']}\n"
            f"• Продано: {user_info['sold']}\n"
            f"• Отменено: {user_info.get('cancelled', 0)}\n"
            f"• Стоимость: {user_info['total_value']} коинов\n\n"
            
            f"<i>Обновлено: {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}</i>"
        )
        
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="⬅️ Назад к списку",
                callback_data="viewsell_back_to_list"
            ),
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data="viewsell_stats"
            )
        )
        
        await callback.message.edit_text(
            message_text,
            parse_mode="html",
            reply_markup=builder.as_markup()
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в viewsell_stats_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@router_fkarta.callback_query(F.data == "viewsell_back_to_list")
async def viewsell_back_to_list_callback(callback: CallbackQuery, state: FSMContext):
    """Возврат к списку карточек из статистики"""
    try:
        # Получаем текущую страницу из состояния
        state_data = await state.get_data()
        current_page = state_data.get("current_view_page", 0)
        
        # Показываем список карточек
        await show_viewsellcards_page(callback.message, state, current_page)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в viewsell_back_to_list_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)
@router_fkarta.message(Command("sellhistory"))
@require_role("помощник-администратора")
async def sellhistory_command(message: Message):
    """Показать историю покупок - УПРОЩЕННАЯ ВЕРСИЯ"""
    user_id = message.from_user.id
    user_name = message.from_user.username or message.from_user.first_name
    
    logger.info(f"🔍 Запрос истории покупок от {user_name} ({user_id})")
    
    try:
        # Сначала проверяем простым способом
        has_purchases = user_has_purchases(user_id)
        
        if not has_purchases:
            await message.reply(
                "📭 <b>У вас еще нет покупок</b>\n\n"
                "<i>Купите свою первую карточку в разделе 'Покупка карточек'</i>",
                parse_mode="html"
            )
            return
        
        # Если есть покупки, загружаем историю
        history = get_purchase_history(user_id, limit=20)
        
        if not history:
            await message.reply(
                "⚠️ <b>Ошибка загрузки истории</b>\n\n"
                "<i>У вас есть покупки, но произошла ошибка при их загрузке.\n",

                parse_mode="html"
            )
            return
        
        message_text = f"📜 <b>ВАША ИСТОРИЯ ПОКУПОК</b>\n\n"
        message_text += f"👤 <b>Пользователь:</b> {user_name}\n"
        
        total_spent = sum(purchase['price'] for purchase in history)
        message_text += f"💰 <b>Всего потрачено:</b> {total_spent} коинов\n"
        message_text += f"🃏 <b>Куплено карточек:</b> {len(history)}\n\n"
        message_text += "<b>Последние покупки:</b>\n\n"
        
        for i, purchase in enumerate(history, 1):
            rarity_display = 'Эпический' if purchase['rarity'] == 'эпическая' else purchase['rarity']
            message_text += (
                f"<b>{i}. {purchase['nickname']}</b>\n"
                f"   💰 Цена: {purchase['price']} коинов\n"
                f"   🏟️ Клуб: {purchase['club']}\n"
                f"   💎 Редкость: {rarity_display}\n"
                f"   📅 Дата: {purchase['purchased_at'][:16]}\n"
            )
            if i < len(history):
                message_text += "   " + "─" * 25 + "\n"
        
        await message.reply(message_text, parse_mode="html")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в команде /sellhistory: {e}")
        await message.reply(
            f"❌ Ошибка при загрузке истории: {str(e)[:100]}\n\n"
            f"<i>Используйте /debug_purchases для диагностики</i>",
            parse_mode="html"
        )
def user_has_purchases(user_id: int) -> bool:
    """Проверяет, есть ли у пользователя покупки - ПРОСТАЯ ВЕРСИЯ"""
    try:
        logger.info(f"🔍 Проверка покупок для user_id={user_id}")
        
        # ПРОСТОЙ ЗАПРОС
        result = db_operation(
            "SELECT 1 FROM purchase_history WHERE user_id = ? LIMIT 1",
            (user_id,),
            fetch=True
        )
        
        has_purchases = bool(result)
        logger.info(f"🔍 Пользователь {user_id} имеет покупки: {has_purchases}")
        
        return has_purchases
        
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке покупок пользователя {user_id}: {e}")
        return False

@router_fkarta.message(Command("debug_purchases"))
@require_role("старший-администратор")
async def debug_purchases_command(message: Message):
    """Отладочная команда для проверки покупок"""
    user_id = message.from_user.id
    
    try:
        # 1. Проверим, есть ли записи в purchase_history
        result1 = db_operation(
            "SELECT COUNT(*) FROM purchase_history WHERE user_id = ?",
            (user_id,),
            fetch=True
        )
        
        # 2. Проверим, есть ли записи в user_cards
        result2 = db_operation(
            "SELECT COUNT(*) FROM user_cards WHERE user_id = ?",
            (user_id,),
            fetch=True
        )
        
        # 3. Проверим структуру таблицы purchase_history
        result3 = db_operation("PRAGMA table_info(purchase_history)", fetch=True)
        
        # 4. Получим пример записи из purchase_history
        result4 = db_operation(
            "SELECT * FROM purchase_history WHERE user_id = ? LIMIT 1",
            (user_id,),
            fetch=True
        )
        
        await message.reply(
            f"<b>ДИАГНОСТИКА ПОКУПОК</b>\n\n"
            f"👤 ID пользователя: {user_id}\n\n"
            f"<b>1. Записи в purchase_history:</b> {result1[0][0] if result1 else 0}\n"
            f"<b>2. Записи в user_cards:</b> {result2[0][0] if result2 else 0}\n\n"
            f"<b>3. Структура purchase_history:</b>\n"
            f"{chr(10).join([f'• {col[1]} ({col[2]})' for col in result3]) if result3 else 'Нет данных'}\n\n"
            f"<b>4. Пример записи:</b>\n"
            f"{result4[0] if result4 else 'Нет записей'}",
            parse_mode="html"
        )
        
    except Exception as e:
        await message.reply(f"❌ Ошибка диагностики: {str(e)}")
@router_fkarta.message(Command("checkmypurchases"))
@require_role("старший-администратор")
async def checkmypurchases_command(message: Message):
    """Команда для отладки - проверка покупок пользователя"""
    user_id = message.from_user.id
    
    # Проверим, есть ли пользователь в базе покупок
    has_purchases = user_has_purchases(user_id)
    
    # Получим детальную информацию
    history = get_purchase_history(user_id)
    
    await message.reply(
        f"<b>Отладка покупок</b>\n\n"
        f"👤 ID пользователя: {user_id}\n"
        f"✅ Есть покупки: {has_purchases}\n"
        f"📊 Количество записей в истории: {len(history) if history else 0}\n\n"
        f"<b>Записи:</b>\n" + 
        ("\n".join([f"{i+1}. {p['nickname']} - {p['price']} коинов" for i, p in enumerate(history[:5])]) if history else "Нет записей"),
        parse_mode="html"
    )
@router_fkarta.callback_query(F.data == "trade_profile")
async def trade_profile_callback(callback: CallbackQuery):
    """Показывает профиль пользователя с коинами"""
    user_id = callback.from_user.id
    user_name = callback.from_user.username or callback.from_user.first_name
    
    try:
        coins = get_user_coins(user_id)
        
        # Получаем статистику покупок пользователя
        user_history = get_purchase_history(user_id)
        total_spent = sum(purchase['price'] for purchase in user_history)
        
        message_text = (
            f"👤 <b>ПРОФИЛЬ</b>\n\n"
            f"<b>Имя:</b> {user_name}\n"
            f"<b>ID:</b> <code>{user_id}</code>\n"
            f"💰 <b>МамоКоины:</b> {coins}\n\n"
        )
        
        if user_history:
            last_purchase = user_history[0]
            rarity_display = 'Эпический' if last_purchase['rarity'] == 'эпическая' else last_purchase['rarity']
            
            message_text += (
                f"📊 <b>Статистика покупок:</b>\n"
                f"• Всего куплено: {len(user_history)} карточек\n"
                f"• Потрачено коинов: {total_spent}\n\n"
                f"🛒 <b>Последняя покупка:</b>\n"
                f"• {last_purchase['nickname']}\n"
                f"• Цена: {last_purchase['price']} коинов\n"
                f"• Дата: {last_purchase['purchased_at'][:16]}\n\n"
            )
        else:
            message_text += (
                f"📭 <b>У вас еще нет покупок</b>\n\n"
                f"<i>Начните собирать коллекцию!</i>\n\n"
            )
        
        # Создаем inline-клавиатуру (УБРАЛИ кнопку "📊 Полная история")
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data="trade_profile"
            ),
            InlineKeyboardButton(
                text="📜 История покупок",  # Теперь это показывает полную историю с пагинацией
                callback_data="view_user_history"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="trade_nazad"
            )
        )
        
        await callback.message.edit_text(
            message_text,
            parse_mode="html",
            reply_markup=builder.as_markup()
        )
        
    except Exception as e:
        logger.error(f"Ошибка в trade_profile_callback для пользователя {user_id}: {e}")
        await callback.answer("❌ Ошибка при загрузке профиля", show_alert=True)
@router_fkarta.message(Command("trade"))
async def trade_message(message: Message):
    await message.reply(
        "💰 <b>ПАНЕЛЬ ТРЕЙДИНГА</b>\n"
        "═══════════════════\n"
        "🛒 Покупка карточек\n"
        "💰 Продажа карточек\n"
        "🎨 Крафт карточек\n"
        "📊 Ваш профиль\n"
        "═══════════════════\n",
        reply_markup=kb.trade_main, 
        parse_mode="html"
    )
@router_fkarta.callback_query(F.data == "trade_profile")
async def trade_profile_callback(callback: CallbackQuery):
    await callback.message.edit_text(f"{callback.message.from_user.first_name}:\n\nКоличество коинов:")
#=====================
#СИСТЕМА ПРОДАЖИ КАРТОЧЕК

# ===================
# КНОПКИ ТРЕЙДИНГА
# ===================

@router_fkarta.callback_query(F.data == "buy_cards")
async def trade_buy_cards_callback(callback: CallbackQuery, state: FSMContext):
    """Показывает карточки для покупки (админские и пользовательские)"""
    user_id = callback.from_user.id
    user_name = callback.from_user.username or callback.from_user.first_name
    
    try:
        # Получаем все карточки в продаже
        sell_cards = get_all_sell_cards_combined()
        
        if not sell_cards:
            await callback.message.edit_text(
                "📭 <b>Нет карточек в продаже</b>\n\n"
                "<i>Здесь будут появляться карточки, выставленные на продажу другими игроками и администраторами</i>",
                parse_mode="html",
                reply_markup=kb.trade_back_to_main
            )
            await callback.answer()
            return
        
        # Сохраняем карточки в состоянии для пагинации
        await state.update_data({
            "all_sell_cards": sell_cards,
            "current_trade_page": 0,
            "trade_mode": "buy"
        })
        
        # Показываем первую страницу
        await show_trade_buy_page(callback.message, state, 0, callback)
        
    except Exception as e:
        logger.error(f"Ошибка в trade_buy_cards_callback: {e}")
        await callback.answer("❌ Ошибка при загрузке карточек", show_alert=True)

async def show_trade_buy_page(message: Message, state: FSMContext, page: int = 0, callback: CallbackQuery = None):
    """Показывает страницу карточек для покупки"""
    try:
        state_data = await state.get_data()
        sell_cards = state_data.get("all_sell_cards", [])
        
        if not sell_cards:
            if callback:
                await callback.message.edit_text("Нет карточек в продаже", reply_markup=kb.trade_back_to_main)
            return
        
        # Настройки пагинации
        cards_per_page = 5
        total_cards = len(sell_cards)
        total_pages = (total_cards + cards_per_page - 1) // cards_per_page
        
        if page < 0:
            page = 0
        elif page >= total_pages:
            page = total_pages - 1
        
        # Получаем карточки для текущей страницы
        start_idx = page * cards_per_page
        end_idx = min(start_idx + cards_per_page, total_cards)
        page_cards = sell_cards[start_idx:end_idx]
        
        # Формируем сообщение
        message_text = (
            f"🛒 <b>ПОКУПКА КАРТОЧЕК</b>\n\n"
            f"📊 <b>Доступно карточек:</b> {total_cards}\n"
            f"📄 <b>Страница:</b> {page + 1}/{total_pages}\n\n"
        )
        
        # Показываем карточки текущей страницы
        for i, card in enumerate(page_cards, start_idx + 1):
            rarity_display = 'Эпический' if card['rarity'] == 'эпическая' else card['rarity']
            seller_type = "⚡ Админ" if card['type'] == 'admin' else "👤 Игрок"
            seller_info = "Администратор" if card['type'] == 'admin' else card.get('seller_display', 'Игрок')
            
            message_text += (
                f"<b>{i}. {card['nickname']}</b>\n"
                f"   🏟️ {card['club']} | 🎯 {card['position']}\n"
                f"   💎 {rarity_display} | 💰 {card['price']} коинов\n"
                f"   {seller_type} | 👤 {seller_info}\n"
                f"   🆔 <code>{card['sell_id']}</code>\n\n"
            )
        
        message_text += (
            f"<i>Используйте /buy [ID] чтобы купить карточку\n"
            f"Например: <code>/buy {page_cards[0]['sell_id'] if page_cards else '123'}</code></i>"
        )
        
        # Создаем клавиатуру с навигацией
        builder = InlineKeyboardBuilder()
        
        # Навигация по страницам
        nav_buttons = []
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data=f"trade_buy_page_{page - 1}"
                )
            )
        
        nav_buttons.append(
            InlineKeyboardButton(
                text=f"📄 {page + 1}/{total_pages}",
                callback_data="noop"
            )
        )
        
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="Вперед ➡️",
                    callback_data=f"trade_buy_page_{page + 1}"
                )
            )
        
        if nav_buttons:
            builder.row(*nav_buttons)
        
        builder.row(
            InlineKeyboardButton(text="🔄 Обновить", callback_data="trade_buy_refresh"),
            InlineKeyboardButton(text="⬅️ Назад", callback_data="trade_nazad")
        )
        
        # Обновляем сообщение
        if callback:
            await callback.message.edit_text(
                message_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
            await callback.answer()
        else:
            await message.reply(
                message_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
        
    except Exception as e:
        logger.error(f"Ошибка в show_trade_buy_page: {e}")
        if callback:
            await callback.answer("❌ Ошибка", show_alert=True)

@router_fkarta.callback_query(F.data.startswith("trade_buy_page_"))
async def trade_buy_page_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик переключения страниц в покупке"""
    try:
        page = int(callback.data.split("_")[3])
        await show_trade_buy_page(callback.message, state, page, callback)
    except Exception as e:
        logger.error(f"Ошибка в trade_buy_page_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@router_fkarta.callback_query(F.data == "trade_buy_refresh")
async def trade_buy_refresh_callback(callback: CallbackQuery, state: FSMContext):
    """Обновление списка карточек для покупки"""
    try:
        # Получаем свежий список карточек
        sell_cards = get_all_sell_cards_combined()
        
        if not sell_cards:
            await callback.answer("Нет карточек в продаже", show_alert=True)
            return
        
        # Сохраняем обновленные данные
        await state.update_data({
            "all_sell_cards": sell_cards,
            "current_trade_page": 0
        })
        
        # Показываем первую страницу
        await show_trade_buy_page(callback.message, state, 0, callback)
        await callback.answer("🔄 Список обновлен")
        
    except Exception as e:
        logger.error(f"Ошибка в trade_buy_refresh_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

# ===================
# КНОПКА "ПРОДАТЬ КАРТОЧКИ"
# ===================

@router_fkarta.callback_query(F.data == "sell_cards")
async def trade_sell_cards_callback(callback: CallbackQuery, state: FSMContext):
    """Показывает карточки пользователя для продажи"""
    user_id = callback.from_user.id
    user_name = callback.from_user.username or callback.from_user.first_name
    
    try:
        # Получаем карточки пользователя
        user_cards = get_user_cards(user_id)
        
        if not user_cards:
            await callback.message.edit_text(
                "📭 <b>У вас нет карточек для продажи</b>\n\n"
                "<i>Получите карточки с помощью команды 'фмамо' или купите их в разделе покупки</i>",
                parse_mode="html",
                reply_markup=kb.trade_back_to_main
            )
            await callback.answer()
            return
        
        # Получаем карточки пользователя, которые уже выставлены на продажу
        user_sell_cards = get_user_sell_cards(user_id)
        user_sell_ids = {card['sell_id'] for card in user_sell_cards}
        
        # Фильтруем карточки, которые еще не выставлены на продажу
        available_for_sale = []
        for card in user_cards:
            nickname, club, position, rarity, received_at = card
            # Получаем ID карточки из каталога
            card_info = get_card_by_nickname_db(nickname)
            if card_info and card_info['id'] not in user_sell_ids:
                available_for_sale.append({
                    'id': card_info['id'],
                    'nickname': nickname,
                    'club': club,
                    'position': position,
                    'rarity': rarity,
                    'received_at': received_at
                })
        
        if not available_for_sale:
            await callback.message.edit_text(
                "📝 <b>Все ваши карточки уже выставлены на продажу</b>\n\n"
                "<i>Вы можете отменить продажу или дождаться покупки ваших карточек</i>",
                parse_mode="html",
                reply_markup=kb.trade_back_to_main
            )
            await callback.answer()
            return
        
        # Сохраняем карточки в состоянии
        await state.update_data({
            "available_for_sale": available_for_sale,
            "current_sell_page": 0
        })
        
        # Показываем первую страницу
        await show_trade_sell_page(callback.message, state, 0, callback)
        
    except Exception as e:
        logger.error(f"Ошибка в trade_sell_cards_callback: {e}")
        await callback.answer("❌ Ошибка при загрузке карточек", show_alert=True)

async def show_trade_sell_page(message: Message, state: FSMContext, page: int = 0, callback: CallbackQuery = None):
    """Показывает страницу карточек пользователя для продажи с inline-кнопками"""
    try:
        user_id = callback.from_user.id if callback else message.from_user.id
        user_name = callback.from_user.username or callback.from_user.first_name if callback else message.from_user.username or message.from_user.first_name
        
        # Получаем данные из состояния
        state_data = await state.get_data()
        available_cards = state_data.get("available_for_sale", [])
        
        # Если нет в состоянии, получаем заново
        if not available_cards:
            user_cards = get_user_cards(user_id)
            user_sell_cards = get_user_sell_cards(user_id)
            user_sell_ids = {card['sell_id'] for card in user_sell_cards}
            
            # Фильтруем карточки
            available_cards = []
            for card in user_cards:
                nickname, club, position, rarity, received_at = card
                card_info = get_card_by_nickname_db(nickname)
                if card_info and card_info['id'] not in user_sell_ids:
                    available_cards.append({
                        'id': card_info['id'],
                        'nickname': nickname,
                        'club': club,
                        'position': position,
                        'rarity': rarity,
                        'received_at': received_at
                    })
            
            await state.update_data({"available_for_sale": available_cards})
        
        if not available_cards:
            message_text = (
                f"📭 <b>У вас нет карточек для продажи</b>\n\n"
                f"👤 <b>Пользователь:</b> {user_name}\n\n"
                f"<i>Получите карточки с помощью команды 'фмамо' или купите их в разделе покупки</i>"
            )
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🛒 Купить карточки", callback_data="bay_cards")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="trade_nazad")]
                ]
            )
            
            if callback:
                await callback.message.edit_text(
                    message_text,
                    parse_mode="html",
                    reply_markup=keyboard
                )
                await callback.answer()
            else:
                await message.reply(
                    message_text,
                    parse_mode="html",
                    reply_markup=keyboard
                )
            return
        
        # Настройки пагинации
        cards_per_page = 5
        total_cards = len(available_cards)
        total_pages = (total_cards + cards_per_page - 1) // cards_per_page
        
        if page < 0:
            page = 0
        elif page >= total_pages:
            page = total_pages - 1
        
        await state.update_data({"current_sell_page": page})
        
        # Получаем карточки для текущей страницы
        start_idx = page * cards_per_page
        end_idx = min(start_idx + cards_per_page, total_cards)
        page_cards = available_cards[start_idx:end_idx]
        
        # Получаем информацию о пользователе
        user_coins = get_user_coins(user_id)
        
        # Формируем сообщение
        message_text = (
            f"💰 <b>ПРОДАЖА ВАШИХ КАРТОЧЕК</b>\n\n"
            f"👤 <b>Пользователь:</b> {user_name}\n"
            f"💼 <b>Ваши коины:</b> {user_coins}\n"
            f"🃏 <b>Карточек для продажи:</b> {total_cards}\n"
            f"📄 <b>Страница:</b> {page + 1}/{total_pages}\n\n"
            f"<i>Нажмите на кнопку под карточкой, чтобы выставить её на продажу</i>\n\n"
        )
        
        # Показываем карточки текущей страницы
        for i, card in enumerate(page_cards, start_idx + 1):
            rarity_display = 'Эпический' if card['rarity'] == 'эпическая' else card['rarity']
            
            message_text += (
                f"<b>{i}. {card['nickname']}</b>\n"
                f"   🏟️ {card['club']} | 🎯 {card['position']}\n"
                f"   💎 {rarity_display} | 🆔 <code>{card['id']}</code>\n\n"
            )
        
        # Создаем клавиатуру с inline-кнопками
        builder = InlineKeyboardBuilder()
        
        # Кнопки для каждой карточки на странице
        for card in page_cards:
            builder.row(
                InlineKeyboardButton(
                    text=f"💰 Продать: {card['nickname']}",
                    callback_data=f"sell_card_{card['id']}"
                )
            )
        
        # Навигация по страницам
        if total_pages > 1:
            nav_buttons = []
            
            if page > 0:
                nav_buttons.append(
                    InlineKeyboardButton(
                        text="⬅️ Назад",
                        callback_data=f"trade_sell_page_{page - 1}"
                    )
                )
            
            nav_buttons.append(
                InlineKeyboardButton(
                    text=f"📄 {page + 1}/{total_pages}",
                    callback_data="noop"
                )
            )
            
            if page < total_pages - 1:
                nav_buttons.append(
                    InlineKeyboardButton(
                        text="Вперед ➡️",
                        callback_data=f"trade_sell_page_{page + 1}"
                    )
                )
            
            if nav_buttons:
                builder.row(*nav_buttons)
        
        # Основные кнопки
        builder.row(
            InlineKeyboardButton(text="🔄 Обновить", callback_data="trade_sell_refresh"),
            InlineKeyboardButton(text="📋 Мои продажи", callback_data="my_active_sales")
        )
        builder.row(
            InlineKeyboardButton(text="⬅️ Назад", callback_data="trade_nazad")
        )
        
        # Обновляем сообщение
        if callback:
            await callback.message.edit_text(
                message_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
            await callback.answer()
        else:
            await message.reply(
                message_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
        
    except Exception as e:
        logger.error(f"Ошибка в show_trade_sell_page: {e}")
        if callback:
            await callback.answer("❌ Ошибка", show_alert=True)

@router_fkarta.callback_query(F.data.startswith("trade_sell_page_"))
async def trade_sell_page_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик переключения страниц в продаже"""
    try:
        page = int(callback.data.split("_")[3])
        
        # Получаем данные из состояния
        state_data = await state.get_data()
        user_coins = get_user_coins(callback.from_user.id)
        
        # Показываем запрошенную страницу
        await show_sell_cards_page(callback, state, page, user_coins)
        await callback.answer(f"Страница {page + 1}")
        
    except Exception as e:
        logger.error(f"Ошибка в trade_sell_page_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@router_fkarta.callback_query(F.data == "trade_sell_refresh")
async def trade_sell_refresh_callback(callback: CallbackQuery, state: FSMContext):
    """Обновление списка карточек для продажи"""
    try:
        user_id = callback.from_user.id
        
        # Получаем обновленный список карточек
        user_cards = get_user_cards(user_id)
        user_sell_cards = get_user_sell_cards(user_id)
        user_sell_ids = {card['sell_id'] for card in user_sell_cards}
        
        # Фильтруем карточки
        available_for_sale = []
        for card in user_cards:
            nickname, club, position, rarity, received_at = card
            card_info = get_card_by_nickname_db(nickname)
            if card_info and card_info['id'] not in user_sell_ids:
                available_for_sale.append({
                    'id': card_info['id'],
                    'nickname': nickname,
                    'club': club,
                    'position': position,
                    'rarity': rarity,
                    'received_at': received_at
                })
        
        # Сохраняем обновленные данные
        await state.update_data({
            "available_for_sale": available_for_sale,
            "current_sell_page": 0
        })
        
        # Показываем первую страницу
        await show_trade_sell_page(callback.message, state, 0, callback)
        await callback.answer("🔄 Список обновлен")
        
    except Exception as e:
        logger.error(f"Ошибка в trade_sell_refresh_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@router_fkarta.callback_query(F.data == "trade_my_sales")
async def trade_my_sales_callback(callback: CallbackQuery, state: FSMContext):
    """Показывает карточки пользователя, выставленные на продажу"""
    user_id = callback.from_user.id
    user_name = callback.from_user.username or callback.from_user.first_name
    
    try:
        # Получаем карточки пользователя в продаже
        user_sell_cards = get_user_sell_cards(user_id)
        
        if not user_sell_cards:
            await callback.message.edit_text(
                "📭 <b>У вас нет активных продаж</b>\n\n"
                "<i>Выставьте карточки на продажу в разделе 'Продать карточки'</i>",
                parse_mode="html",
                reply_markup=kb.trade_back_to_sell
            )
            await callback.answer()
            return
        
        # Сохраняем в состоянии для пагинации
        await state.update_data({
            "my_sell_cards": user_sell_cards,
            "current_my_sales_page": 0
        })
        
        # Показываем первую страницу
        await show_my_sales_page(callback.message, state, 0, callback)
        
    except Exception as e:
        logger.error(f"Ошибка в trade_my_sales_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

async def show_my_sales_page(message: Message, state: FSMContext, page: int = 0, callback: CallbackQuery = None):
    """Показывает страницу активных продаж пользователя"""
    try:
        state_data = await state.get_data()
        sell_cards = state_data.get("my_sell_cards", [])
        
        if not sell_cards:
            if callback:
                await callback.message.edit_text("Нет активных продаж", reply_markup=kb.trade_back_to_sell)
            return
        
        # Настройки пагинации
        cards_per_page = 6
        total_cards = len(sell_cards)
        total_pages = (total_cards + cards_per_page - 1) // cards_per_page
        
        if page < 0:
            page = 0
        elif page >= total_pages:
            page = total_pages - 1
        
        # Получаем карточки для текущей страницы
        start_idx = page * cards_per_page
        end_idx = min(start_idx + cards_per_page, total_cards)
        page_cards = sell_cards[start_idx:end_idx]
        
        # Формируем сообщение
        message_text = (
            f"📋 <b>МОИ АКТИВНЫЕ ПРОДАЖИ</b>\n\n"
            f"📊 <b>Всего продаж:</b> {total_cards}\n"
            f"📄 <b>Страница:</b> {page + 1}/{total_pages}\n\n"
        )
        
        # Показываем карточки текущей страницы
        for i, card in enumerate(page_cards, start_idx + 1):
            rarity_display = 'Эпический' if card['rarity'] == 'эпическая' else card['rarity']
            
            message_text += (
                f"<b>{i}. {card['nickname']}</b>\n"
                f"   🏟️ {card['club']} | 🎯 {card['position']}\n"
                f"   💎 {rarity_display} | 💰 {card['price']} коинов\n"
                f"   🆔 ID продажи: <code>{card['sell_id']}</code>\n"
                f"   🆔 ID карточки: <code>{card['card_id']}</code>\n\n"
            )
        
        message_text += (
            f"<i>Чтобы отменить продажу, используйте:\n"
            f"<code>/cancel_sale [ID_продажи]</code>\n"
            f"Пример: <code>/cancel_sale {page_cards[0]['sell_id'] if page_cards else '123'}</code></i>"
        )
        
        # Создаем клавиатуру
        builder = InlineKeyboardBuilder()
        
        # Навигация по страницам
        nav_buttons = []
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data=f"my_sales_page_{page - 1}"
                )
            )
        
        nav_buttons.append(
            InlineKeyboardButton(
                text=f"📄 {page + 1}/{total_pages}",
                callback_data="noop"
            )
        )
        
        if page < total_pages - 1:
            nav_buttons.append(
                InlineKeyboardButton(
                    text="Вперед ➡️",
                    callback_data=f"my_sales_page_{page + 1}"
                )
            )
        
        if nav_buttons:
            builder.row(*nav_buttons)
        
        builder.row(
            InlineKeyboardButton(text="🔄 Обновить", callback_data="my_sales_refresh"),
            InlineKeyboardButton(text="⬅️ Назад к продаже", callback_data="trade_sell_cards")
        )
        
        # Обновляем сообщение
        if callback:
            await callback.message.edit_text(
                message_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
            await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в show_my_sales_page: {e}")
        if callback:
            await callback.answer("❌ Ошибка", show_alert=True) 


def purchase_admin_card(user_id: int, sell_id: int):
    """Покупка карточки, выставленной администратором (работает с sell_id)"""
    try:
        logger.info(f"🔍 Начало покупки админской карточки: sell_id={sell_id}, user_id={user_id}")
        
        # ПРОВЕРКА 1: Карточка существует и доступна
        card_check = db_operation(
            """SELECT sc.id, sc.card_id, sc.price, sc.is_available,
                      sc.card_id as player_card_id,  -- Здесь будет ID карточки игрока (3-значный)
                      pc.nickname, pc.club, pc.position, pc.rarity
               FROM sell_cards sc
               JOIN players_catalog pc ON sc.card_id = pc.id  -- card_id в sell_cards это 3-значный ID из players_catalog
               WHERE sc.id = ?""",
            (sell_id,),
            fetch=True
        )
        
        if not card_check:
            logger.warning(f"❌ Карточка продажи {sell_id} не найдена")
            return False, "Карточка не найдена в продаже"
        
        (sell_db_id, card_id_from_sell, price, is_available, 
         player_card_id, nickname, club, position, rarity) = card_check[0]
        
        logger.info(f"🔍 Найдена карточка: {nickname} (sell_id: {sell_id}, card_id: {player_card_id})")
        
        # ПРОВЕРКА 2: Статус доступности
        if is_available != 1:
            # Проверяем, есть ли запись о покупке
            purchase_check = db_operation(
                "SELECT id FROM purchase_history WHERE sell_id = ?",  # ИСПРАВЛЕНО: было sell_id
                (sell_id,),
                fetch=True
            )
            
            if purchase_check:
                logger.warning(f"❌ Карточка {sell_id} уже продана")
                return False, "Карточка уже продана"
            else:
                # Некорректный статус - исправляем
                logger.warning(f"⚠️ Некорректный статус карточки {sell_id}, исправляю...")
                db_operation(
                    "UPDATE sell_cards SET is_available = 1 WHERE id = ?",
                    (sell_id,)
                )
                return False, "Статус карточки был исправлен. Попробуйте покупку снова."
        
        # ПРОВЕРКА 3: У пользователя достаточно коинов
        user_coins = get_user_coins(user_id)
        if user_coins < price:
            logger.warning(f"❌ Недостаточно коинов у пользователя {user_id}: нужно {price}, есть {user_coins}")
            return False, f"Недостаточно коинов. Нужно: {price}, у вас: {user_coins}"
        
        # ПРОВЕРКА 4: У пользователя еще нет этой карточки
        if user_has_card(user_id, player_card_id):  # Используем player_card_id
            logger.warning(f"❌ У пользователя {user_id} уже есть карточка {nickname}")
            return False, f"У вас уже есть карточка '{nickname}'"
        
        # ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ - НАЧИНАЕМ ТРАНЗАКЦИЮ
        
        # Шаг 1: Списываем коины
        success, message = subtract_user_coins(user_id, price)
        if not success:
            logger.error(f"❌ Ошибка списания коинов для пользователя {user_id}: {message}")
            return False, f"Ошибка списания коинов: {message}"
        
        # Шаг 2: Добавляем карточку пользователю (используем player_card_id - 3-значный ID)
        card_added = add_card_to_user(user_id, player_card_id)  # Используем player_card_id
        if not card_added:
            # Откатываем списание коинов
            logger.error(f"❌ Ошибка добавления карточки {player_card_id} пользователю {user_id}")
            add_user_coins(user_id, price)
            return False, "Ошибка при добавлении карточки"
        
        # Шаг 3: Помечаем карточку как проданную
        db_operation(
            "UPDATE sell_cards SET is_available = 0 WHERE id = ?",
            (sell_id,)
        )
        
        # Шаг 4: Добавляем запись в историю покупок (ИСПРАВЛЕНО)
        db_operation(
            """INSERT INTO purchase_history (user_id, card_id, price, transaction_type, sell_id) 
               VALUES (?, ?, ?, ?, ?)""",  # ИСПРАВЛЕНО: было sell_id
            (user_id, player_card_id, price, 'admin_sell', sell_id)  # Используем player_card_id
        )
        
        # Шаг 5: Логируем успешную покупку
        logger.warning(
            f"💰 АДМИНСКАЯ ПОКУПКА: Пользователь {user_id} купил карточку "
            f"'{nickname}' (ID карточки: {player_card_id}, ID продажи: {sell_id}) за {price} коинов"
        )
        
        # Получаем обновленную информацию для возврата
        user_coins_after = get_user_coins(user_id)
        
        return True, {
            'success': True,
            'message': f"Карточка '{nickname}' успешно куплена за {price} коинов!",
            'card_info': {
                'id': player_card_id,  # 3-значный ID карточки
                'nickname': nickname,
                'club': club,
                'position': position,
                'rarity': rarity,
                'price': price
            },
            'user_coins_before': user_coins,
            'user_coins_after': user_coins_after,
            'sell_id': sell_id,
            'card_id': player_card_id  # 3-значный ID
        }
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при покупке админской карточки {sell_id}: {e}")
        import traceback
        logger.error(f"Трейсбэк: {traceback.format_exc()}")
        return False, f"Внутренняя ошибка сервера: {str(e)[:100]}"
def add_user_sell_card(user_id: int, card_id: int, price: int):
    """Добавляет карточку пользователя на продажу - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    try:
        # Проверяем, есть ли карточка у пользователя
        if not user_has_card(user_id, card_id):
            return False, "У вас нет этой карточки"
        
        # Проверяем, не продается ли уже эта карточка
        existing = db_operation(
            """SELECT id FROM user_sell_transactions 
               WHERE card_id = ? AND status = 'active'""",
            (card_id,),
            fetch=True
        )
        
        if existing:
            existing_id = existing[0][0]
            return False, f"Эта карточка уже выставлена на продажу (ID продажи: {existing_id})"
        
        # Проверяем цену
        if price < 1:
            return False, "Минимальная цена: 1 коин"
        if price > 10000:
            return False, "Максимальная цена: 10000 коинов"
        
        # Получаем информацию о карточке
        card_info = db_operation(
            """SELECT nickname FROM players_catalog WHERE id = ?""",
            (card_id,),
            fetch=True
        )
        
        card_name = card_info[0][0] if card_info else f"Карточка ID: {card_id}"
        
        # Добавляем в продажу
        result = db_operation(
            """INSERT INTO user_sell_transactions 
               (card_id, seller_id, price, status) 
               VALUES (?, ?, ?, 'active')""",
            (card_id, user_id, price)
        )
        
        # Получаем ID продажи
        sell_id = get_last_insert_id()
        
        logger.info(f"✅ Карточка '{card_name}' добавлена в пользовательскую продажу с ID: {sell_id}")
        
        return True, f"Карточка '{card_name}' выставлена на продажу (ID продажи: {sell_id}) за {price} коинов"
        
    except Exception as e:
        logger.error(f"❌ Ошибка при добавлении карточки в продажу: {e}")
        return False, f"Ошибка: {str(e)[:100]}"

def remove_user_sell_card(sell_id: int, user_id: int):
    """Удаляет карточку пользователя из продажи по ID продажи"""
    try:
        # Проверяем, принадлежит ли продажа пользователю
        check = db_operation(
            """SELECT id, status, card_id 
               FROM user_sell_transactions 
               WHERE id = ? AND seller_id = ?""",
            (sell_id, user_id),
            fetch=True
        )
        
        if not check:
            return False, "Продажа не найдена или вы не являетесь продавцом"
        
        sell_db_id, status, card_id = check[0]
        
        if status != 'active':
            return False, "Нельзя удалить проданную или отмененную карточку"
        
        # Удаляем продажу
        db_operation(
            "DELETE FROM user_sell_transactions WHERE id = ?",
            (sell_id,)
        )
        
        # Получаем информацию о карточке
        card_info = db_operation(
            "SELECT nickname FROM players_catalog WHERE id = ?",
            (card_id,),
            fetch=True
        )
        
        card_name = card_info[0][0] if card_info else "Карточка"
        
        return True, f"Продажа карточки '{card_name}' отменена (ID продажи: {sell_id})"
        
    except Exception as e:
        logger.error(f"Ошибка при удалении карточки из продажи: {e}")
        return False, f"Ошибка: {str(e)[:100]}"


@router_fkarta.message(Command("debug_user_sales"))
async def debug_user_sales_command(message: Message):
    """Детальная отладка пользовательских продаж"""
    try:
        # 1. Проверяем прямые запросы к БД
        result = db_operation(
            """SELECT ust.id, pc.nickname, ust.price, au.username, ust.status
               FROM user_sell_transactions ust
               JOIN players_catalog pc ON ust.card_id = pc.id
               JOIN all_users au ON ust.seller_id = au.id
               WHERE ust.status = 'active'
               ORDER BY ust.id""",
            fetch=True
        )
        
        message_text = "<b>🔍 ДЕТАЛЬНАЯ ОТЛАДКА ПОЛЬЗОВАТЕЛЬСКИХ ПРОДАЖ</b>\n\n"
        
        if not result:
            message_text += "❌ Нет активных пользовательских продаж в БД\n"
        else:
            message_text += f"<b>Найдено в БД:</b> {len(result)} продаж\n\n"
            for sale_id, nickname, price, username, status in result:
                message_text += f"• ID: <code>{sale_id}</code> - {nickname} - {price} коинов - @{username} - Статус: {status}\n"
        
        # 2. Проверяем функцию get_user_sell_cards()
        user_cards = get_user_sell_cards()
        message_text += f"\n<b>Функция get_user_sell_cards() вернула:</b> {len(user_cards) if user_cards else 0} карточек\n"
        
        # 3. Проверяем структуру возвращаемых данных
        if user_cards:
            message_text += "\n<b>Первая карточка:</b>\n"
            first_card = user_cards[0]
            for key, value in first_card.items():
                message_text += f"{key}: {value}\n"
        
        await message.reply(message_text, parse_mode="html")
        
    except Exception as e:
        logger.error(f"Ошибка в debug_user_sales_command: {e}")
        await message.reply(f"❌ Ошибка: {str(e)}")
def get_user_sell_cards(user_id: int):
    """Получает карточки пользователя, выставленные на продажу - ОБНОВЛЕННАЯ ВЕРСИЯ"""
    try:
        logger.info(f"🔍 Запрос пользовательских продаж для user_id={user_id}")
        
        # Запрос с JOIN для получения полной информации
        result = db_operation(
            """SELECT
                ust.id as sell_id,
                ust.seller_id,
                ust.card_id,
                ust.price,
                ust.status,
                pc.nickname,
                pc.club,
                pc.position,
                pc.rarity,
                au.username as seller_username,
                ust.created_at
            FROM user_sell_transactions ust
            JOIN players_catalog pc ON ust.card_id = pc.id
            JOIN all_users au ON ust.seller_id = au.id
            WHERE ust.seller_id = ? 
            ORDER BY ust.status, ust.created_at DESC""",
            (user_id,),
            fetch=True
        )
        
        logger.info(f"🔍 Результат из БД: {len(result) if result else 0} записей")
        
        if not result:
            logger.warning(f"⚠️ У пользователя {user_id} нет записей в user_sell_transactions")
            
            # Проверим, есть ли записи в таблице вообще (для отладки)
            debug_result = db_operation(
                "SELECT COUNT(*) as total FROM user_sell_transactions",
                fetch=True
            )
            if debug_result:
                logger.info(f"📊 Всего записей в user_sell_transactions: {debug_result[0][0]}")
            
            return []
        
        # Преобразуем результат
        cards = []
        for row in result:
            (sell_id, seller_id, card_id, price, status, 
             nickname, club, position, rarity, username, created_at) = row
            
            logger.info(f"🔍 Найдена продажа: ID={sell_id}, Карточка='{nickname}', Статус='{status}'")
            
            cards.append({
                'sell_id': sell_id,
                'seller_id': seller_id,
                'card_id': card_id,
                'price': price,
                'status': status,
                'nickname': nickname,
                'club': club,
                'position': position,
                'rarity': rarity,
                'seller_username': username,
                'created_at': created_at,
                'seller_display': f"@{username}" if username else f"Игрок (ID: {seller_id})"
            })
        
        # Фильтруем только активные продажи
        active_cards = [card for card in cards if card['status'] == 'active']
        logger.info(f"🔍 Активных продаж у пользователя {user_id}: {len(active_cards)}")
        
        return active_cards
        
    except Exception as e:
        logger.error(f"❌ Ошибка в get_user_sell_cards для пользователя {user_id}: {e}")
        logger.error(f"Трейсбэк: {traceback.format_exc()}")
        return []

def purchase_user_sell_card(buyer_id: int, sell_id: int):
    """Покупка карточки, выставленной пользователем (работает с sell_id)"""
    try:
        logger.info(f"🔍 Начало покупки пользовательской карточки: sell_id={sell_id}, buyer_id={buyer_id}")
        
        # Получаем информацию о продаже
        result = db_operation(
            """SELECT ust.id, ust.seller_id, ust.card_id, ust.price, 
                      ust.status, pc.nickname, pc.id as player_card_id
               FROM user_sell_transactions ust
               JOIN players_catalog pc ON ust.card_id = pc.id  -- card_id это 3-значный ID из players_catalog
               WHERE ust.id = ? AND ust.status = 'active'""",
            (sell_id,),
            fetch=True
        )
        
        if not result:
            logger.warning(f"❌ Продажа {sell_id} не найдена или не активна")
            return False, "Карточка не найдена или уже продана"
        
        sell_db_id, seller_id, card_id_in_ust, price, status, nickname, player_card_id = result[0]
        
        logger.info(f"🔍 Найдена продажа: {nickname} (sell_id: {sell_id}, card_id: {player_card_id})")
        
        # Проверяем, что покупатель не является продавцом
        if buyer_id == seller_id:
            logger.warning(f"❌ Покупатель {buyer_id} пытается купить свою же карточку")
            return False, "Вы не можете купить свою же карточку"
        
        # Проверяем, есть ли карточка у продавца (по 3-значному ID)
        if not user_has_card(seller_id, player_card_id):
            # Карточка больше не у продавца - отменяем продажу
            logger.warning(f"❌ У продавца {seller_id} нет карточки {player_card_id}")
            db_operation(
                """UPDATE user_sell_transactions 
                   SET status = 'cancelled' 
                   WHERE id = ?""",
                (sell_id,)
            )
            return False, "У продавца больше нет этой карточки"
        
        # Проверяем коины покупателя
        buyer_coins = get_user_coins(buyer_id)
        if buyer_coins < price:
            logger.warning(f"❌ Недостаточно коинов у покупателя {buyer_id}: нужно {price}, есть {buyer_coins}")
            return False, f"Недостаточно коинов. Нужно: {price}, у вас: {buyer_coins}"
        
        # Проверяем, есть ли уже карточка у покупателя (по 3-значному ID)
        if user_has_card(buyer_id, player_card_id):
            logger.warning(f"❌ У покупателя {buyer_id} уже есть карточка {nickname}")
            return False, f"У вас уже есть карточка '{nickname}'"
        
        # НАЧИНАЕМ ТРАНЗАКЦИЮ
        
        # 1. Списываем коины у покупателя
        success, message = subtract_user_coins(buyer_id, price)
        if not success:
            logger.error(f"❌ Ошибка списания коинов у покупателя {buyer_id}: {message}")
            return False, f"Ошибка списания коинов: {message}"
        
        # 2. Добавляем коины продавцу
        seller_coins_before = get_user_coins(seller_id)
        add_user_coins(seller_id, price)
        seller_coins_after = get_user_coins(seller_id)
        logger.info(f"💰 Переведено {price} коинов от {buyer_id} к {seller_id}")
        
        # 3. Удаляем карточку у продавца (по 3-значному ID)
        db_operation(
            "DELETE FROM user_cards WHERE user_id = ? AND card_id = ?",
            (seller_id, player_card_id)
        )
        
        # 4. Добавляем карточку покупателю (по 3-значному ID)
        add_card_to_user(buyer_id, player_card_id)
        
        # 5. Обновляем статус продажи
        db_operation(
            """UPDATE user_sell_transactions 
               SET buyer_id = ?, status = 'sold', sold_at = CURRENT_TIMESTAMP 
               WHERE id = ?""",
            (buyer_id, sell_id)
        )
        
        # 6. Добавляем запись в историю покупок
        db_operation(
    """INSERT INTO purchase_history (user_id, sell_id, price, transaction_type) 
       VALUES (?, ?, ?, 'user_sell')""",
    (buyer_id, sell_id, price)
)
        
        # 7. Получаем полную информацию о карточке для возврата
        card_info = get_card_by_id(player_card_id)
        
        logger.warning(
            f"💰 ПОЛЬЗОВАТЕЛЬСКАЯ СДЕЛКА: Продавец {seller_id} → Покупатель {buyer_id} | "
            f"Карточка: {nickname} (ID: {player_card_id}) | Цена: {price} коинов | ID продажи: {sell_id}"
        )
        
        return True, {
            'success': True,
            'message': f"Карточка '{nickname}' успешно куплена!",
            'price': price,
            'seller_id': seller_id,
            'buyer_id': buyer_id,
            'card_id': player_card_id,  # 3-значный ID карточки
            'nickname': nickname,
            'card_info': card_info if card_info else {
                'id': player_card_id,
                'nickname': nickname
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при покупке пользовательской карточки: {e}")
        import traceback
        logger.error(f"Трейсбэк: {traceback.format_exc()}")
        return False, f"Внутренняя ошибка: {str(e)[:100]}"


def get_all_sell_cards_combined():
    """Получает ВСЕ карточки в продаже - ОБНОВЛЕННАЯ ВЕРСИЯ"""
    try:
        cards = []
        
        # 1. Админские карточки
        admin_result = db_operation(
            """SELECT 
                   sc.id as sell_id,
                   sc.card_id,
                   pc.nickname,
                   pc.club,
                   pc.position,
                   pc.rarity,
                   sc.price,
                   sc.comment,
                   sc.added_at,
                   sc.is_available,
                   sc.added_by_id,
                   au.username as added_by_username
               FROM sell_cards sc
               JOIN players_catalog pc ON sc.card_id = pc.id
               LEFT JOIN all_users au ON sc.added_by_id = au.id
               WHERE sc.is_available = 1
               ORDER BY sc.price""",
            fetch=True
        )
        
        if admin_result:
            for row in admin_result:
                cards.append({
                    'sell_id': row[0],
                    'card_id': row[1],
                    'nickname': row[2],
                    'club': row[3],
                    'position': row[4],
                    'rarity': row[5],
                    'price': row[6],
                    'comment': row[7] or '',
                    'added_at': row[8] or '',
                    'is_available': row[9],
                    'added_by_id': row[10],
                    'seller_username': row[11],
                    'type': 'admin',
                    'seller_display': 'Администратор' if not row[11] else f"@{row[11]}"
                })
        
        # 2. Пользовательские карточки
        user_result = db_operation(
            """SELECT 
                   ust.id as sell_id,
                   ust.card_id,
                   ust.seller_id,
                   ust.price,
                   pc.nickname,
                   pc.club,
                   pc.position,
                   pc.rarity,
                   au.username as seller_username,
                   au.first_name as seller_first_name
               FROM user_sell_transactions ust
               JOIN players_catalog pc ON ust.card_id = pc.id
               JOIN all_users au ON ust.seller_id = au.id
               WHERE ust.status = 'active'
               ORDER BY ust.price""",
            fetch=True
        )
        
        if user_result:
            for row in user_result:
                sell_id, card_id, seller_id, price, nickname, club, position, rarity, seller_username, seller_first_name = row
                
                seller_display = None
                if seller_username:
                    seller_display = f"@{seller_username}"
                elif seller_first_name:
                    seller_display = seller_first_name
                else:
                    seller_display = f"Игрок (ID: {seller_id})"
                
                cards.append({
                    'sell_id': sell_id,
                    'card_id': card_id,
                    'seller_id': seller_id,
                    'price': price,
                    'nickname': nickname,
                    'club': club,
                    'position': position,
                    'rarity': rarity,
                    'seller_username': seller_username,
                    'seller_display': seller_display,
                    'type': 'user',
                    'comment': '',
                    'added_at': '',
                    'is_available': 1
                })
        
        # Сортируем по цене
        cards.sort(key=lambda x: x.get('price', 0))
        
        logger.info(f"✅ get_all_sell_cards_combined: найдено {len(cards)} карточек")
        return cards
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в get_all_sell_cards_combined: {e}")
        return []

@router_fkarta.message(Command("check_combined_sales"))
async def check_combined_sales_command(message: Message):
    """Проверяет, что все карточки видны в общей бирже"""
    try:
        cards = get_all_sell_cards_combined()
        
        if not cards:
            await message.reply(
                "📭 <b>Нет карточек в продаже</b>\n\n"
                "<i>Используйте /add_test_admin_cards чтобы добавить админские карточки</i>",
                parse_mode="html"
            )
            return
        
        message_text = f"🛒 <b>ВСЕ КАРТОЧКИ В ПРОДАЖЕ</b>\n\n"
        message_text += f"<b>Всего:</b> {len(cards)} карточек\n\n"
        
        admin_count = sum(1 for c in cards if c['type'] == 'admin')
        user_count = sum(1 for c in cards if c['type'] == 'user')
        
        message_text += f"⚡ <b>Админских:</b> {admin_count}\n"
        message_text += f"👤 <b>Пользовательских:</b> {user_count}\n\n"
        
        # Показываем первые 10 карточек
        message_text += "<b>Первые 10 карточек:</b>\n"
        for i, card in enumerate(cards[:10], 1):
            seller = "Администратор" if card['type'] == 'admin' else card.get('seller_display', 'Игрок')
            message_text += (
                f"{i}. <b>{card['nickname']}</b> - {card['price']} коинов\n"
                f"   Тип: {'⚡' if card['type'] == 'admin' else '👤'} | Продает: {seller}\n\n"
            )
        
        await message.reply(message_text, parse_mode="html")
        
    except Exception as e:
        logger.error(f"Ошибка в check_combined_sales_command: {e}")
        await message.reply(f"❌ Ошибка: {str(e)}")
@router_fkarta.message(Command("test_display"))
@require_role("старший-администратор")
async def test_display_command(message: Message):
    """Тест отображения карточек"""
    try:
        # Получаем все карточки
        all_cards = get_all_sell_cards_combined()
        
        if not all_cards:
            await message.reply("❌ Нет карточек в продаже")
            return
        
        message_text = f"<b>ТЕСТ ОТОБРАЖЕНИЯ</b>\n\n"
        message_text += f"<b>Всего карточек:</b> {len(all_cards)}\n\n"
        
        # Группируем по типу
        admin_cards = [c for c in all_cards if c.get('type') == 'admin']
        user_cards = [c for c in all_cards if c.get('type') == 'user']
        
        message_text += f"<b>Админских:</b> {len(admin_cards)}\n"
        message_text += f"<b>Пользовательских:</b> {len(user_cards)}\n\n"
        
        # Показываем пользовательские карточки
        if user_cards:
            message_text += "<b>ПОЛЬЗОВАТЕЛЬСКИЕ КАРТОЧКИ:</b>\n"
            for i, card in enumerate(user_cards, 1):
                message_text += (
                    f"{i}. <b>{card.get('nickname')}</b>\n"
                    f"   💰 {card.get('price')} коинов\n"
                    f"   👤 @{card.get('seller_username', 'игрок')}\n"
                    f"   🆔 ID: <code>{card.get('sell_id')}</code>\n\n"
                )
        
        # Показываем админские карточки
        if admin_cards:
            message_text += "<b>АДМИНСКИЕ КАРТОЧКИ:</b>\n"
            for i, card in enumerate(admin_cards, 1):
                message_text += (
                    f"{i}. <b>{card.get('nickname')}</b>\n"
                    f"   💰 {card.get('price')} коинов\n"
                    f"   👤 Администратор\n"
                    f"   🆔 ID: <code>{card.get('sell_id')}</code>\n\n"
                )
        
        await message.reply(message_text, parse_mode="html")
        
    except Exception as e:
        logger.error(f"Ошибка в test_display_command: {e}")
        await message.reply(f"❌ Ошибка: {str(e)}")
@router_fkarta.message(Command("check_combined"))
async def check_combined_command(message: Message):
    """Проверка объединенной функции"""
    try:
        cards = get_all_sell_cards_combined()
        
        await message.reply(
            f"<b>Результат get_all_sell_cards_combined():</b>\n\n"
            f"• Всего карточек: {len(cards)}\n"
            f"• Типы: {[c.get('type') for c in cards]}\n"
            f"• ID карточек: {[c.get('sell_id') for c in cards]}\n"
            f"• Никнеймы: {[c.get('nickname') for c in cards]}",
            parse_mode="html"
        )
        
    except Exception as e:
        await message.reply(f"Ошибка: {str(e)}")


@router_fkarta.message(Command("debug_sales"))
@require_role("старший-администратор")
async def debug_sales_command(message: Message):
    """Отладка системы продаж"""
    try:
        # Проверяем пользовательские продажи
        user_sales = db_operation(
            """SELECT COUNT(*) as total, 
                      SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active,
                      SUM(CASE WHEN status = 'sold' THEN 1 ELSE 0 END) as sold
               FROM user_sell_transactions""",
            fetch=True
        )
        
        # Проверяем админские продажи
        admin_sales = db_operation(
            """SELECT COUNT(*) as total, 
                      SUM(CASE WHEN is_available = 1 THEN 1 ELSE 0 END) as available,
                      SUM(CASE WHEN is_available = 0 THEN 1 ELSE 0 END) as sold
               FROM sell_cards""",
            fetch=True
        )
        
        # Получаем несколько активных пользовательских продаж
        active_user_sales = db_operation(
            """SELECT ust.id, pc.nickname, ust.price, au.username as seller
               FROM user_sell_transactions ust
               JOIN players_catalog pc ON ust.card_id = pc.id
               JOIN all_users au ON ust.seller_id = au.id
               WHERE ust.status = 'active'
               LIMIT 10""",
            fetch=True
        )
        
        total_user, active_user, sold_user = user_sales[0] if user_sales else (0, 0, 0)
        total_admin, available_admin, sold_admin = admin_sales[0] if admin_sales else (0, 0, 0)
        
        message_text = (
            f"🔍 <b>ДЕБАГ СИСТЕМЫ ПРОДАЖ</b>\n\n"
            f"<b>Пользовательские продажи:</b>\n"
            f"• Всего: {total_user}\n"
            f"• Активных: {active_user}\n"
            f"• Проданных: {sold_user}\n\n"
            
            f"<b>Админские продажи:</b>\n"
            f"• Всего: {total_admin}\n"
            f"• Доступно: {available_admin}\n"
            f"• Проданных: {sold_admin}\n\n"
        )
        
        if active_user_sales:
            message_text += "<b>Активные пользовательские продажи:</b>\n"
            for sale_id, nickname, price, seller in active_user_sales:
                message_text += f"• ID: {sale_id} - {nickname} - {price} коинов - @{seller}\n"
        
        # Проверяем, видны ли карточки через функцию get_all_sell_cards_combined
        combined_cards = get_all_sell_cards_combined()
        message_text += f"\n<b>В функции get_all_sell_cards_combined:</b> {len(combined_cards)} карточек\n"
        
        await message.reply(message_text, parse_mode="html")
        
    except Exception as e:
        logger.error(f"Ошибка в debug_sales_command: {e}")
        await message.reply(f"❌ Ошибка: {str(e)}")
@router_fkarta.message(Command("check_table_structure"))
@require_role("старший-администратор")
async def check_table_structure_command(message: Message):
    """Проверяет структуру таблиц"""
    try:
        # Проверяем структуру user_sell_transactions
        result = db_operation("PRAGMA table_info(user_sell_transactions)", fetch=True)
        
        message_text = "<b>Структура user_sell_transactions:</b>\n"
        for column in result:
            col_id, col_name, col_type, not_null, default_value, pk = column
            message_text += f"• {col_name} ({col_type})\n"
        
        await message.reply(message_text, parse_mode="html")
        
    except Exception as e:
        logger.error(f"Ошибка в check_table_structure_command: {e}")
        await message.reply(f"❌ Ошибка: {str(e)}")
@router_fkarta.message(Command("test_add_sale"))
@require_role("старший-администратор")
async def test_add_sale_command(message: Message):
    """Тестовая команда для добавления карточки в продажу"""
    try:
        user_id = message.from_user.id
        
        # Получаем первую карточку пользователя
        user_cards = get_user_cards(user_id)
        if not user_cards:
            await message.reply("У вас нет карточек")
            return
        
        nickname, club, position, rarity, _ = user_cards[0]
        
        # Получаем ID карточки
        result = db_operation(
            "SELECT id FROM players_catalog WHERE nickname = ?",
            (nickname,),
            fetch=True
        )
        
        if not result:
            await message.reply(f"Карточка {nickname} не найдена в каталоге")
            return
        
        card_id = result[0][0]
        
        # Добавляем в продажу
        success, msg = add_user_sell_card(user_id, card_id, 100)
        
        await message.reply(f"Результат: {success} - {msg}")
        
    except Exception as e:
        logger.error(f"Ошибка в test_add_sale_command: {e}")
        await message.reply(f"❌ Ошибка: {str(e)}")

def get_user_cards_for_sale(user_id: int):
    """Получает карточки пользователя для продажи"""
    try:
        # Получаем карточки пользователя
        user_cards = get_user_cards(user_id)
        
        cards_for_sale = []
        for card in user_cards:
            nickname, club, position, rarity, received_at = card
            
            # Получаем ID карточки из каталога
            card_info = get_card_by_nickname_db(nickname)
            if card_info:
                cards_for_sale.append({
                    'id': card_info['id'],
                    'nickname': nickname,
                    'club': club,
                    'position': position,
                    'rarity': rarity,
                    'received_at': received_at
                })
        
        return cards_for_sale
        
    except Exception as e:
        logger.error(f"Ошибка в get_user_cards_for_sale для пользователя {user_id}: {e}")
        return []
@router_fkarta.callback_query(F.data == "sell_my_card")
async def sell_my_card_callback(callback: CallbackQuery, state: FSMContext):
    """Показывает карточки пользователя для продажи"""
    try:
        user_id = callback.from_user.id
        user_coins = get_user_coins(user_id)
        
        # Получаем карточки пользователя
        user_cards = get_user_cards_for_sale(user_id)  # Теперь из mamodatabases
        
        if not user_cards:
            await callback.message.edit_text(
                f"📭 <b>Нет карточек для продажи</b>\n\n"
                f"💰 <b>Ваши коины:</b> {user_coins}\n\n"
                f"<i>У вас нет карточек, которые можно продать.</i>\n\n"
                f"<b>Как получить карточки:</b>\n"
                f"• Используйте команду 'фмамо'\n"
                f"• Купите карточки у других игроков\n"
                f"• Выполните крафт карточек",
                parse_mode="html",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="🛒 Купить карточки", callback_data="bay_cards")],
                        [InlineKeyboardButton(text="⬅️ Назад", callback_data="trade_nazad")]
                    ]
                )
            )
            return
        
        # Сохраняем карточки в состоянии для пагинации
        await state.update_data({
            "sell_user_cards": user_cards,
            "current_sell_page": 0
        })
        
        # Показываем первую страницу
        await show_sell_cards_page(callback, state, 0, user_coins)
        
    except Exception as e:
        logger.error(f"Ошибка в sell_my_card_callback: {e}")
        await callback.answer("❌ Ошибка при загрузке карточек", show_alert=True)


async def show_user_cards_for_sale(callback: CallbackQuery, state: FSMContext, page: int = 0):
    """Показывает карточки пользователя для продажи"""
    try:
        state_data = await state.get_data()
        user_cards = state_data.get("user_cards_for_sale", [])
        sell_message_id = state_data.get("sell_message_id", callback.message.message_id)
        
        if not user_cards:
            await callback.answer("Нет карточек", show_alert=True)
            return
        
        # Пагинация
        cards_per_page = 10
        total_cards = len(user_cards)
        total_pages = (total_cards + cards_per_page - 1) // cards_per_page
        
        if page < 0:
            page = 0
        elif page >= total_pages:
            page = total_pages - 1
        
        await state.update_data({"current_sell_page": page})
        
        # Получаем карточки текущей страницы
        start_idx = page * cards_per_page
        end_idx = min(start_idx + cards_per_page, total_cards)
        page_cards = user_cards[start_idx:end_idx]
        
        # Формируем сообщение
        message_text = (
            f"💰 <b>ПРОДАЖА ВАШИХ КАРТОЧЕК</b>\n\n"
            f"<b>Страница {page + 1} из {total_pages}</b>\n"
            f"<i>Карточки {start_idx + 1}-{end_idx} из {total_cards}</i>\n\n"
        )
        
        for i, card in enumerate(page_cards, start_idx + 1):
            nickname, club, position, rarity, _ = card
            rarity_display = 'Эпический' if rarity == 'эпическая' else rarity
            
            message_text += (
                f"<b>{i}. {nickname}</b>\n"
                f"   🏟️ {club} | 🎯 {position} | 💎 {rarity_display}\n"
                f"   🆔 <code>{i}</code>\n\n"
            )
        
        message_text += (
            "<b>Как продать:</b>\n"
            "1. Запомните номер карточки (🆔 ...)\n"
            "2. Нажмите '💰 Выставить на продажу'\n"
            "3. Введите номер карточки\n"
            "4. Укажите цену\n\n"
            "<i>Минимальная цена: 1 коин</i>"
        )
        
        # Создаем клавиатуру
        builder = InlineKeyboardBuilder()
        
        # Навигация
        if total_pages > 1:
            nav_buttons = []
            if page > 0:
                nav_buttons.append(
                    InlineKeyboardButton(
                        text="⬅️ Назад",
                        callback_data=f"sell_page_{page - 1}"
                    )
                )
            
            nav_buttons.append(
                InlineKeyboardButton(
                    text=f"📄 {page + 1}/{total_pages}",
                    callback_data="noop"
                )
            )
            
            if page < total_pages - 1:
                nav_buttons.append(
                    InlineKeyboardButton(
                        text="Вперед ➡️",
                        callback_data=f"sell_page_{page + 1}"
                    )
                )
            
            builder.row(*nav_buttons)
        
        # Основные кнопки
        builder.row(
            InlineKeyboardButton(
                text="💰 Выставить на продажу",
                callback_data="start_sell_process"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="📋 Мои продажи",
                callback_data="my_active_sales"
            ),
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data="sell_my_card"
            )
        )
        builder.row(
            InlineKeyboardButton(text="⬅️ Назад", callback_data="trade_nazad")
        )
        
        await callback.bot.edit_message_text(
                chat_id=callback.message.chat.id,
                message_id=sell_message_id,  # Используем сохраненный ID
                text=message_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
            
    except Exception as e:
        logger.error(f"Ошибка в show_user_cards_for_sale: {e}")


@router_fkarta.callback_query(F.data.startswith("sell_page_"))
async def sell_page_callback(callback: CallbackQuery, state: FSMContext):
    """Переключение страниц при продаже"""
    try:
        page = int(callback.data.split("_")[2])
        await show_user_cards_for_sale(callback, state, page)
        await callback.answer(f"Страница {page + 1}")
    except Exception as e:
        logger.error(f"Ошибка в sell_page_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router_fkarta.callback_query(F.data == "start_sell_process")
async def start_sell_process_callback(callback: CallbackQuery, state: FSMContext):
    """Начинает процесс продажи - все в одном сообщении"""
    try:
        # Получаем карточки пользователя из состояния
        state_data = await state.get_data()
        user_cards = state_data.get("user_cards_for_sale", [])
        
        if not user_cards:
            # РЕДАКТИРУЕМ текущее сообщение
            await callback.message.edit_text(
                "📭 <b>У вас нет карточек для продажи</b>\n\n"
                "<i>Сначала получите карточки через команду 'фмамо'</i>",
                parse_mode="html",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="⬅️ Назад", callback_data="sell_my_card")
                ]])
            )
            await callback.answer()
            return
        
        # Устанавливаем состояние
        await state.set_state(TradeStates.waiting_for_sell_card_number)
        
        # РЕДАКТИРУЕМ текущее сообщение (не отправляем новое)
        await callback.message.edit_text(
            "💰 <b>ВЫСТАВЛЕНИЕ КАРТОЧКИ НА ПРОДАЖУ</b>\n\n"
            "📝 <b>Введите номер карточки:</b>\n\n"
            "<i>Номер указан в списке ваших карточек (🆔 ...)</i>\n\n"
            "<b>Пример:</b> <code>1</code>\n\n"
            "<i>Для отмены нажмите кнопку ниже</i>",
            parse_mode="html",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_sell_process")
            ]])
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в start_sell_process_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router_fkarta.callback_query(F.data == "cancel_sell_process")
async def cancel_sell_process_callback(callback: CallbackQuery, state: FSMContext):
    """Отмена процесса продажи"""
    try:
        await state.clear()
        await sell_my_card_callback(callback, state)
        await callback.answer("Отменено")
    except Exception as e:
        logger.error(f"Ошибка в cancel_sell_process_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router_fkarta.message(F.text, TradeStates.waiting_for_sell_card_number)
async def process_sell_card_number(message: Message, state: FSMContext, bot: Bot):
    """Обрабатывает номер карточки - все в одном сообщении"""
    try:
        # Сначала удаляем сообщение пользователя (чтобы не было лишнего)
        try:
            await bot.delete_message(message.chat.id, message.message_id)
        except:
            pass
        
        # Получаем карточки пользователя из состояния
        state_data = await state.get_data()
        user_cards = state_data.get("user_cards_for_sale", [])
        
        if not user_cards:
            # РЕДАКТИРУЕМ сообщение бота
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=state_data.get("sell_message_id"),
                text="❌ <b>Ошибка: список карточек устарел</b>\n\n"
                     "<i>Пожалуйста, начните процесс продажи заново</i>",
                parse_mode="html",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="⬅️ Назад", callback_data="sell_my_card")
                ]])
            )
            await state.clear()
            return
        
        # Проверяем ввод
        try:
            card_number = int(message.text.strip())
        except ValueError:
            # РЕДАКТИРУЕМ сообщение бота
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=state_data.get("sell_message_id"),
                text="❌ <b>Неверный формат!</b>\n\n"
                     "Пожалуйста, введите число (номер карточки).\n"
                     "Пример: <code>1</code>\n\n"
                     "<i>Попробуйте еще раз или нажмите 'Отмена'</i>",
                parse_mode="html",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_sell_process")
                ]])
            )
            return
        
        # Проверяем диапазон
        if card_number < 1 or card_number > len(user_cards):
            # РЕДАКТИРУЕМ сообщение бота
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=state_data.get("sell_message_id"),
                text=f"❌ <b>Неверный номер!</b>\n\n"
                     f"Доступные номера: от 1 до {len(user_cards)}\n\n"
                     f"<i>Попробуйте еще раз или нажмите 'Отмена'</i>",
                parse_mode="html",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_sell_process")
                ]])
            )
            return
        
        # Получаем выбранную карточку
        selected_card = user_cards[card_number - 1]
        nickname, club, position, rarity, _ = selected_card
        
        # Получаем ID карточки из базы
        result = db_operation(
            "SELECT id FROM players_catalog WHERE nickname = ?",
            (nickname,),
            fetch=True
        )
        
        if not result:
            # РЕДАКТИРУЕМ сообщение бота
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=state_data.get("sell_message_id"),
                text=f"❌ Карточка '{nickname}' не найдена в базе",
                parse_mode="html",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="⬅️ Назад", callback_data="sell_my_card")
                ]])
            )
            await state.clear()
            return
        
        card_id = result[0][0]
        
        # Проверяем, не продается ли уже эта карточка
        existing_sale = db_operation(
            """SELECT id FROM user_sell_transactions 
               WHERE seller_id = ? AND card_id = ? AND status = 'active'""",
            (message.from_user.id, card_id),
            fetch=True
        )
        existing_sale = db_operation(
    """SELECT 
           CASE 
               WHEN ust.id IS NOT NULL THEN 'user_' || ust.id
               WHEN sc.id IS NOT NULL THEN 'admin_' || sc.id
           END as sale_info
    FROM players_catalog pc
    LEFT JOIN user_sell_transactions ust ON pc.id = ust.card_id AND ust.status = 'active'
    LEFT JOIN sell_cards sc ON pc.id = sc.card_id AND sc.is_available = 1
    WHERE pc.id = ?
      AND (ust.id IS NOT NULL OR sc.id IS NOT NULL)
    LIMIT 1""",
    (card_id,),
    fetch=True
)

        if existing_sale:
            sale_info = existing_sale[0][0]
            if sale_info.startswith('user_'):
                sale_id = sale_info.split('_')[1]
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=state_data.get("sell_message_id"),
                    text=f"❌ Карточка '{nickname}' уже выставлена на продажу другим пользователем",
                    parse_mode="html",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="📋 Все продажи", callback_data="bay_cards"),
                        InlineKeyboardButton(text="⬅️ Назад", callback_data="sell_my_card")
                    ]])
                )
            else:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=state_data.get("sell_message_id"),
                    text=f"❌ Карточка '{nickname}' уже есть в продаже от администратора",
                    parse_mode="html",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="🛒 К покупкам", callback_data="bay_cards"),
                        InlineKeyboardButton(text="⬅️ Назад", callback_data="sell_my_card")
                    ]])
                )
            await state.clear()
            return
        if existing_sale:
            # РЕДАКТИРУЕМ сообщение бота
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=state_data.get("sell_message_id"),
                text=f"❌ Карточка '{nickname}' уже выставлена на продажу",
                parse_mode="html",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="📋 Мои продажи", callback_data="my_active_sales"),
                    InlineKeyboardButton(text="⬅️ Назад", callback_data="sell_my_card")
                ]])
            )
            await state.clear()
            return
        
        # Сохраняем данные и переходим к запросу цены
        await state.update_data({
            "selected_card_id": card_id,
            "selected_card_nickname": nickname,
            "selected_card_number": card_number,
            "selected_card_club": club,
            "selected_card_position": position,
            "selected_card_rarity": rarity
        })
        
        await state.set_state(TradeStates.waiting_for_sell_price)
        
        # РЕДАКТИРУЕМ существующее сообщение (не отправляем новое)
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=state_data.get("sell_message_id"),
            text=(
                f"💰 <b>УКАЗАНИЕ ЦЕНЫ</b>\n\n"
                f"<b>Выбранная карточка:</b> {nickname}\n"
                f"<b>Клуб:</b> {club}\n"
                f"<b>Позиция:</b> {position}\n"
                f"<b>Редкость:</b> {rarity}\n\n"
                f"📝 <b>Введите цену продажи:</b>\n\n"
                f"<i>Минимальная цена: 1 коин\n"
                f"Максимальная цена: 10000 коинов</i>\n\n"
                f"<b>Пример:</b> <code>50</code>\n\n"
                f"<i>Для отмены нажмите кнопку ниже</i>"
            ),
            parse_mode="html",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_sell_process")
            ]])
        )
        
    except Exception as e:
        logger.error(f"Ошибка в process_sell_card_number: {e}")
        # Пытаемся редактировать сообщение при ошибке
        try:
            state_data = await state.get_data()
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=state_data.get("sell_message_id"),
                text="❌ Произошла ошибка",
                parse_mode="html",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="⬅️ Назад", callback_data="sell_my_card")
                ]])
            )
        except:
            pass
        await state.clear()


@router_fkarta.message(F.text, TradeStates.waiting_for_sell_price)
async def process_sell_price(message: Message, state: FSMContext, bot: Bot):
    """Обрабатывает цену продажи - все в одном сообщении"""
    try:
        # Удаляем сообщение пользователя
        try:
            await bot.delete_message(message.chat.id, message.message_id)
        except:
            pass
        
        # Получаем данные из состояния
        state_data = await state.get_data()
        sell_message_id = state_data.get("sell_message_id")
        
        if not sell_message_id:
            await state.clear()
            return
        
        # Проверяем цену
        try:
            price = int(message.text.strip())
        except ValueError:
            # РЕДАКТИРУЕМ существующее сообщение
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=sell_message_id,
                text=(
                    "❌ <b>Неверный формат!</b>\n\n"
                    "Цена должна быть числом.\n"
                    "Пример: <code>50</code>\n\n"
                    "<i>Попробуйте еще раз или нажмите 'Отмена'</i>"
                ),
                parse_mode="html",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_sell_process")
                ]])
            )
            return
        
        # Проверяем диапазон
        if price < 1:
            # РЕДАКТИРУЕМ существующее сообщение
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=sell_message_id,
                text=(
                    "❌ <b>Слишком низкая цена!</b>\n\n"
                    "Минимальная цена: 1 коин\n\n"
                    "<i>Попробуйте еще раз или нажмите 'Отмена'</i>"
                ),
                parse_mode="html",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_sell_process")
                ]])
            )
            return
        
        if price > 10000:
            # РЕДАКТИРУЕМ существующее сообщение
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=sell_message_id,
                text=(
                    "❌ <b>Слишком высокая цена!</b>\n\n"
                    "Максимальная цена: 10000 коинов\n\n"
                    "<i>Попробуйте еще раз или нажмите 'Отмена'</i>"
                ),
                parse_mode="html",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_sell_process")
                ]])
            )
            return
        
        # Получаем данные о карточке
        card_id = state_data.get("selected_card_id")
        card_nickname = state_data.get("selected_card_nickname")
        club = state_data.get("selected_card_club")
        position = state_data.get("selected_card_position")
        rarity = state_data.get("selected_card_rarity")
        
        # Добавляем карточку в продажу
        success, result_msg = add_user_sell_card(message.from_user.id, card_id, price)
        
        if success:
            # РЕДАКТИРУЕМ существующее сообщение с результатом
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=sell_message_id,
                text=(
                    f"✅ <b>КАРТОЧКА ВЫСТАВЛЕНА НА ПРОДАЖУ!</b>\n\n"
                    f"<b>Карточка:</b> {card_nickname}\n"
                    f"<b>Клуб:</b> {club}\n"
                    f"<b>Позиция:</b> {position}\n"
                    f"<b>Редкость:</b> {rarity}\n"
                    f"<b>Цена:</b> {price} коинов\n\n"
                    f"<i>Теперь другие пользователи могут купить вашу карточку</i>"
                ),
                parse_mode="html",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="📋 Мои продажи", callback_data="my_active_sales"),
                        InlineKeyboardButton(text="🛒 К покупкам", callback_data="bay_cards")
                    ],
                    [
                        InlineKeyboardButton(text="⬅️ В трейдинг", callback_data="trade_nazad")
                    ]
                ])
            )
        else:
            # РЕДАКТИРУЕМ существующее сообщение с ошибкой
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=sell_message_id,
                text=f"❌ <b>ОШИБКА!</b>\n\n{result_msg}",
                parse_mode="html",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="⬅️ Назад", callback_data="sell_my_card")
                ]])
            )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка в process_sell_price: {e}")
        await state.clear()


@router_fkarta.callback_query(F.data == "my_active_sales")
async def my_active_sales_callback(callback: CallbackQuery):
    """Показывает активные продажи пользователя"""
    user_id = callback.from_user.id
    user_name = callback.from_user.username or callback.from_user.first_name
    
    try:
        # Получаем активные продажи
        sales = get_user_sell_cards(user_id)
        
        if not sales:
            await callback.message.edit_text(
                f"📭 <b>АКТИВНЫЕ ПРОДАЖИ</b>\n\n"
                f"👤 <b>Продавец:</b> {user_name}\n\n"
                f"<i>У вас нет активных продаж</i>\n\n"
                f"<b>Чтобы выставить карточку на продажу:</b>\n"
                f"1. Нажмите '💰 Продажа карточек'\n"
                f"2. Выберите карточку\n"
                f"3. Укажите цену",
                parse_mode="html",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="💰 Продать карточку", callback_data="sell_my_card"),
                    InlineKeyboardButton(text="⬅️ Назад", callback_data="trade_nazad")
                ]])
            )
            return
        
        # Формируем сообщение
        message_text = f"💰 <b>ВАШИ АКТИВНЫЕ ПРОДАЖИ</b>\n\n"
        message_text += f"👤 <b>Продавец:</b> {user_name}\n"
        message_text += f"📊 <b>Количество:</b> {len(sales)}\n\n"
        
        total_value = sum(sale['price'] for sale in sales)
        message_text += f"💰 <b>Общая стоимость:</b> {total_value} коинов\n\n"
        
        for i, sale in enumerate(sales, 1):
            rarity_display = 'Эпический' if sale['rarity'] == 'эпическая' else sale['rarity']
            message_text += (
                f"<b>{i}. {sale['nickname']}</b>\n"
                f"   🏟️ {sale['club']} | 🎯 {sale['position']}\n"
                f"   💎 {rarity_display} | 💰 {sale['price']} коинов\n"
                f"   🆔 ID продажи: <code>{sale['sell_id']}</code>\n\n"
            )
        
        message_text += (
            "<b>Как удалить продажу:</b>\n"
            "1. Запомните ID продажи\n"
            "2. Нажмите '❌ Удалить продажу'\n"
            "3. Введите ID продажи\n\n"
            "<i>После удаления карточка вернется в вашу коллекцию</i>"
        )
        
        # Создаем клавиатуру
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="❌ Удалить продажу",
                callback_data="start_remove_sale"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="💰 Продать еще",
                callback_data="sell_my_card"
            ),
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data="my_active_sales"
            )
        )
        builder.row(
            InlineKeyboardButton(text="⬅️ Назад", callback_data="trade_nazad")
        )
        
        await callback.message.edit_text(
            message_text,
            parse_mode="html",
            reply_markup=builder.as_markup()
        )
        
    except Exception as e:
        logger.error(f"Ошибка в my_active_sales_callback: {e}")
        await callback.answer("❌ Ошибка при загрузке продаж", show_alert=True)


@router_fkarta.callback_query(F.data == "start_remove_sale")
async def start_remove_sale_callback(callback: CallbackQuery, state: FSMContext):
    """Начинает процесс удаления продажи"""
    await state.set_state(TradeStates.waiting_for_remove_sale_id)
    
    await callback.message.edit_text(
        "🗑️ <b>УДАЛЕНИЕ ПРОДАЖИ</b>\n\n"
        "📝 <b>Введите ID продажи:</b>\n\n"
        "<i>ID указан в списке ваших продаж</i>\n\n"
        "<b>Пример:</b> <code>1</code>\n\n"
        "<i>Для отмены нажмите кнопку ниже</i>",
        parse_mode="html",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_remove_sale")
        ]])
    )
    
    await callback.answer()


@router_fkarta.callback_query(F.data == "cancel_remove_sale")
async def cancel_remove_sale_callback(callback: CallbackQuery, state: FSMContext):
    """Отмена удаления продажи"""
    try:
        await state.clear()
        await my_active_sales_callback(callback)
        await callback.answer("Отменено")
    except Exception as e:
        logger.error(f"Ошибка в cancel_remove_sale_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@router_fkarta.message(F.text, TradeStates.waiting_for_remove_sale_id)
async def process_remove_sale(message: Message, state: FSMContext):
    """Обрабатывает удаление продажи"""
    try:
        # Проверяем ввод
        try:
            sell_id = int(message.text.strip())
        except ValueError:
            await message.reply(
                "❌ <b>Неверный формат!</b>\n\n"
                "ID должен быть числом.\n"
                "Пример: <code>1</code>",
                parse_mode="html"
            )
            return
        
        # Удаляем продажу
        success, result_msg = remove_user_sell_card(sell_id, message.from_user.id)
        
        if success:
            await message.reply(
                f"✅ <b>ПРОДАЖА УДАЛЕНА!</b>\n\n{result_msg}",
                parse_mode="html",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="📋 Мои продажи", callback_data="my_active_sales"),
                    InlineKeyboardButton(text="⬅️ В трейдинг", callback_data="trade_nazad")
                ]])
            )
        else:
            await message.reply(
                f"❌ <b>ОШИБКА!</b>\n\n{result_msg}",
                parse_mode="html"
            )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка в process_remove_sale: {e}")
        await message.reply("❌ Произошла ошибка")
        await state.clear()


async def send_user_sell_notification(bot: Bot, seller_id: int, buyer_id: int, 
                                      sell_id: int, card_info: dict, price: int):
    """Отправляет уведомление о продаже карточки пользователем - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    try:
        # Получаем полную информацию о карточке
        full_card_info = get_sell_card_info(sell_id)
        
        if not full_card_info:
            logger.error(f"❌ Не удалось получить информацию о карточке {sell_id}")
            # Пробуем получить базовую информацию из другого источника
            full_card_info = {
                'nickname': card_info.get('nickname', 'Неизвестно'),
                'club': 'Неизвестно',
                'position': 'Неизвестно',
                'rarity': 'Неизвестно',
                'price': price
            }
        else:
            logger.info(f"✅ Получена полная информация о карточке {sell_id}: {full_card_info}")
        
        # Получаем информацию о продавце и покупателе
        seller_info = db_operation(
            "SELECT username, first_name FROM all_users WHERE id = ?",
            (seller_id,),
            fetch=True
        )
        
        buyer_info = db_operation(
            "SELECT username, first_name FROM all_users WHERE id = ?",
            (buyer_id,),
            fetch=True
        )
        
        if seller_info:
            seller_username = seller_info[0][0]
            seller_first_name = seller_info[0][1]
            seller_display = f"@{seller_username}" if seller_username else seller_first_name or f"ID: {seller_id}"
        else:
            seller_display = f"ID: {seller_id}"
        
        if buyer_info:
            buyer_username = buyer_info[0][0]
            buyer_first_name = buyer_info[0][1]
            buyer_display = f"@{buyer_username}" if buyer_username else buyer_first_name or f"ID: {buyer_id}"
        else:
            buyer_display = f"ID: {buyer_id}"
        
        # Формируем сообщение для админов с ПОЛНОЙ информацией
        admin_message = (
            f"💰 <b>СДЕЛКА МЕЖДУ ПОЛЬЗОВАТЕЛЯМИ!</b>\n\n"
            f"<b>👨‍💼 Продавец:</b> {seller_display}\n"
            f"<b>🆔 ID продавца:</b> <code>{seller_id}</code>\n\n"
            f"<b>👨‍💼 Покупатель:</b> {buyer_display}\n"
            f"<b>🆔 ID покупателя:</b> <code>{buyer_id}</code>\n\n"
            f"<b>🃏 Карточка:</b>\n"
            f"• <b>Игрок:</b> {full_card_info.get('nickname', 'Неизвестно')}\n"
            f"• <b>Клуб:</b> {full_card_info.get('club', 'Неизвестно')}\n"
            f"• <b>Позиция:</b> {full_card_info.get('position', 'Неизвестно')}\n"
            f"• <b>Редкость:</b> {full_card_info.get('rarity', 'Неизвестно')}\n"
            f"• <b>Цена:</b> {price} коинов\n"
            f"• <b>ID продажи:</b> <code>{sell_id}</code>\n\n"
            f"<b>⏰ Время сделки:</b> {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}\n\n"
            f"<i>Сделка совершена автоматически через платформу трейдинга</i>"
        )
        
        # Отправляем в группу админов
        group_id = -1003615487276  # ID группы админов
        
        try:
            await bot.send_message(
                group_id,
                admin_message,
                parse_mode="html"
            )
            logger.info(f"✅ Уведомление о продаже отправлено в группу {group_id}")
        except Exception as group_error:
            logger.error(f"Ошибка при отправке в группу: {group_error}")
        
        # Отправляем уведомление продавцу
        try:
            seller_message = (
                f"💰 <b>ВАША КАРТОЧКА ПРОДАНА!</b>\n\n"
                f"<b>Карточка:</b> {full_card_info.get('nickname', 'Неизвестно')}\n"
                f"<b>Клуб:</b> {full_card_info.get('club', 'Неизвестно')}\n"
                f"<b>Позиция:</b> {full_card_info.get('position', 'Неизвестно')}\n"
                f"<b>Редкость:</b> {full_card_info.get('rarity', 'Неизвестно')}\n"
                f"<b>Цена:</b> {price} коинов\n"
                f"<b>Покупатель:</b> {buyer_display}\n\n"
                f"<b>Ваш баланс увеличен на {price} коинов!</b>"
            )
            
            await bot.send_message(
                seller_id,
                seller_message,
                parse_mode="html"
            )
            logger.info(f"✅ Уведомление отправлено продавцу {seller_id}")
        except Exception as seller_error:
            logger.error(f"Ошибка при отправке продавцу: {seller_error}")
        
        # Отправляем уведомление покупателю
        try:
            buyer_message = (
                f"💰 <b>ВЫ КУПИЛИ КАРТОЧКУ!</b>\n\n"
                f"<b>Карточка:</b> {full_card_info.get('nickname', 'Неизвестно')}\n"
                f"<b>Клуб:</b> {full_card_info.get('club', 'Неизвестно')}\n"
                f"<b>Позиция:</b> {full_card_info.get('position', 'Неизвестно')}\n"
                f"<b>Редкость:</b> {full_card_info.get('rarity', 'Неизвестно')}\n"
                f"<b>Цена:</b> {price} коинов\n"
                f"<b>Продавец:</b> {seller_display}\n\n"
                f"<b>Карточка добавлена в вашу коллекцию!</b>"
            )
            
            await bot.send_message(
                buyer_id,
                buyer_message,
                parse_mode="html"
            )
            logger.info(f"✅ Уведомление отправлено покупателю {buyer_id}")
        except Exception as buyer_error:
            logger.error(f"Ошибка при отправке покупателю: {buyer_error}")
        
        # Логируем сделку
        logger.warning(
            f"💰 ПОЛЬЗОВАТЕЛЬСКАЯ СДЕЛКА: Продавец {seller_display} ({seller_id}) → "
            f"Покупатель {buyer_display} ({buyer_id}) | "
            f"Карточка: {full_card_info.get('nickname')} ({full_card_info.get('club')}) | "
            f"Цена: {price} коинов | ID продажи: {sell_id}"
        )
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при отправке уведомлений о продаже: {e}")
        import traceback
        logger.error(f"Трейсбэк: {traceback.format_exc()}")
#=====================
@router_fkarta.callback_query(F.data == "bay_cards_refresh")
async def bay_cards_refresh_callback(callback: CallbackQuery, state: FSMContext):
    """Обновляет список карточек в продаже - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    try:
        # Получаем свежий список карточек
        all_cards = get_all_sell_cards_combined()
        
        if not all_cards:
            await callback.answer("Нет карточек в продаже", show_alert=True)
            return
        
        # Получаем текущую страницу из состояния или начинаем с 0
        state_data = await state.get_data()
        current_page = state_data.get("current_page", 0)
        
        # Сохраняем обновленные данные
        await state.update_data({
            "sell_cards": all_cards,
            "current_page": current_page
        })
        
        # Показываем ту же страницу с обновленными данными
        await show_sell_cards_page(callback, state, current_page)
        await callback.answer("🔄 Список обновлен")
        
    except Exception as e:
        logger.error(f"Ошибка в bay_cards_refresh_callback: {e}")
        await callback.answer("❌ Ошибка обновления", show_alert=True)
@router_fkarta.callback_query(F.data == "bay_cards")
async def bay_cards_callback(callback: CallbackQuery):
    """Показывает список карточек в продаже"""
    try:
        user_id = callback.from_user.id
        user_coins = get_user_coins(user_id)
        
        # Получаем все карточки в продаже
        all_cards = get_all_cards_for_sale()
        
        if not all_cards:
            await callback.message.edit_text(
                f"📭 <b>Нет карточек в продаже</b>\n\n"
                f"💰 <b>Ваши коины:</b> {user_coins}\n\n"
                f"<i>В настоящее время нет доступных карточек для покупки.</i>",
                parse_mode="html",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="🔄 Обновить", callback_data="bay_cards")],
                        [InlineKeyboardButton(text="💰 Продать карточку", callback_data="sell_my_card")],
                        [InlineKeyboardButton(text="⬅️ Назад", callback_data="trade_nazad")]
                    ]
                )
            )
            return
        
        # Показываем первую страницу
        await show_buy_cards_page(callback, 0, user_coins)
        
    except Exception as e:
        logger.error(f"Ошибка в bay_cards_callback: {e}")
        await callback.answer("❌ Ошибка при загрузке карточек", show_alert=True)



async def show_buy_cards_page(callback: CallbackQuery, page: int, user_coins: int = 0):
    """Показывает страницу карточек в продаже"""
    try:
        # Получаем карточки
        all_cards = get_all_cards_for_sale()
        total_cards = len(all_cards)
        
        # Пагинация
        cards_per_page = 5
        total_pages = (total_cards + cards_per_page - 1) // cards_per_page
        
        if page < 0:
            page = 0
        elif page >= total_pages:
            page = total_pages - 1
        
        # Получаем карточки для страницы
        start_idx = page * cards_per_page
        end_idx = min(start_idx + cards_per_page, total_cards)
        page_cards = all_cards[start_idx:end_idx]
        
        # Формируем сообщение
        message_text = (
            f"🛒 <b>ПОКУПКА КАРТОЧЕК</b>\n\n"
            f"💰 <b>Ваши коины:</b> {user_coins}\n"
            f"📊 <b>Доступно карточек:</b> {total_cards}\n"
            f"📄 <b>Страница:</b> {page + 1}/{total_pages}\n\n"
        )
        
        for i, card in enumerate(page_cards, start_idx + 1):
            rarity = card.get('rarity', 'Редкий')
            rarity_display = 'Эпический' if rarity == 'эпическая' else rarity
            
            seller_type = "⚡" if card.get('type') == 'admin' else "👤"
            seller_name = card.get('seller', 'Неизвестно')
            
            can_afford = user_coins >= card.get('price', 0)
            can_afford_icon = "✅" if can_afford else "❌"
            
            message_text += (
                f"<b>{can_afford_icon} {i}. {card.get('nickname', 'Неизвестно')}</b>\n"
                f"   🏟️ {card.get('club', 'Неизвестно')} | 🎯 {card.get('position', 'Неизвестно')}\n"
                f"   💎 {rarity_display} | 💰 {card.get('price', 0)} коинов\n"
                f"   {seller_type} Продает: {seller_name}\n"
                f"   🆔 ID: <code>{card.get('sell_id', '?')}</code>\n\n"
            )
        
        message_text += "<i>Нажмите на кнопку '🛒 Купить' под карточкой для покупки</i>"
        
        # Создаем клавиатуру
        keyboard = kb.get_buy_cards_keyboard(page, total_pages, page_cards)
        
        await callback.message.edit_text(
            message_text,
            parse_mode="html",
            reply_markup=keyboard
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в show_buy_cards_page: {e}")
        await callback.answer("❌ Ошибка при загрузке страницы", show_alert=True)


@router_fkarta.callback_query(F.data.startswith("buy_page_"))
async def buy_page_callback(callback: CallbackQuery):
    """Обработчик переключения страниц при покупке"""
    try:
        page = int(callback.data.split("_")[2])
        user_coins = get_user_coins(callback.from_user.id)
        await show_buy_cards_page(callback, page, user_coins)
        await callback.answer(f"Страница {page + 1}")
    except Exception as e:
        logger.error(f"Ошибка в buy_page_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@router_fkarta.callback_query(F.data.startswith("buy_card_"))
async def buy_card_callback(callback: CallbackQuery):
    """Обработчик нажатия на кнопку покупки карточки"""
    try:
        user_id = callback.from_user.id
        sell_id = int(callback.data.split("_")[2])
        
        # Получаем информацию о карточке
        card_info = get_sell_card_info(sell_id)
        if not card_info:
            await callback.answer("❌ Карточка не найдена", show_alert=True)
            return
        
        # Проверяем, есть ли уже карточка у пользователя
        if user_has_card(user_id, card_info.get('card_id', 0)):
            await callback.message.edit_text(
                f"❌ <b>У вас уже есть эта карточка!</b>\n\n"
                f"<b>{card_info.get('nickname', 'Неизвестно')}</b> уже есть в вашей коллекции.\n\n"
                f"<i>Выберите другую карточку для покупки.</i>",
                parse_mode="html",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[
                        InlineKeyboardButton(text="⬅️ К списку карточек", callback_data="bay_cards")
                    ]]
                )
            )
            return
        
        # Получаем коины пользователя
        user_coins = get_user_coins(user_id)
        price = card_info.get('price', 0)
        
        if user_coins < price:
            await callback.message.edit_text(
                f"❌ <b>Недостаточно коинов!</b>\n\n"
                f"<b>Цена:</b> {price} коинов\n"
                f"<b>Ваш баланс:</b> {user_coins} коинов\n\n"
                f"<i>Вам нужно еще {price - user_coins} коинов</i>",
                parse_mode="html",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[
                        InlineKeyboardButton(text="⬅️ К списку карточек", callback_data="bay_cards")
                    ]]
                )
            )
            return
        
        # Формируем сообщение с подтверждением
        rarity = card_info.get('rarity', 'Редкий')
        rarity_display = 'Эпический' if rarity == 'эпическая' else rarity
        
        message_text = (
            f"✅ <b>ПОДТВЕРЖДЕНИЕ ПОКУПКИ</b>\n\n"
            f"<b>Карточка:</b> {card_info.get('nickname', 'Неизвестно')}\n"
            f"<b>Клуб:</b> {card_info.get('club', 'Неизвестно')}\n"
            f"<b>Позиция:</b> {card_info.get('position', 'Неизвестно')}\n"
            f"<b>Редкость:</b> {rarity_display}\n"
            f"<b>Цена:</b> {price} коинов\n"
            f"<b>Продавец:</b> {card_info.get('seller', 'Неизвестно')}\n\n"
            f"<b>Ваш баланс:</b> {user_coins} коинов\n"
            f"<b>После покупки:</b> {user_coins - price} коинов\n\n"
            f"<i>Вы уверены, что хотите купить эту карточку?</i>"
        )
        
        # Создаем клавиатуру подтверждения
        keyboard = kb.get_purchase_confirmation_keyboard(sell_id)
        
        await callback.message.edit_text(
            message_text,
            parse_mode="html",
            reply_markup=keyboard
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в buy_card_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)










@router_fkarta.callback_query(F.data.startswith("confirm_buy_"))
async def confirm_buy_callback(callback: CallbackQuery):
    """Подтверждение покупки карточки"""
    try:
        user_id = callback.from_user.id
        sell_id = int(callback.data.split("_")[2])
        
        # Выполняем покупку
        success, result = buy_card_universal(user_id, sell_id)
        
        if success:
            # Получаем новую информацию о карточке
            card_info = get_sell_card_info(sell_id)
            
            # Получаем обновленный баланс
            user_coins = get_user_coins(user_id)
            
            message_text = (
                f"🎉 <b>ПОКУПКА УСПЕШНА!</b>\n\n"
                f"<b>Карточка добавлена в вашу коллекцию:</b>\n"
                f"• {card_info.get('nickname', 'Неизвестно')}\n"
                f"• {card_info.get('club', 'Неизвестно')}\n"
                f"• {card_info.get('position', 'Неизвестно')}\n"
                f"• Цена: {card_info.get('price', 0)} коинов\n\n"
                f"💰 <b>Ваш новый баланс:</b> {user_coins} коинов\n\n"
                f"<i>Поздравляем с покупкой! 🎉</i>"
            )
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🛒 Купить еще", callback_data="bay_cards")],
                    [InlineKeyboardButton(text="📚 Моя коллекция", callback_data="view_my_cards")],
                    [InlineKeyboardButton(text="⬅️ В меню трейдинга", callback_data="trade_nazad")]
                ]
            )
        else:
            message_text = f"❌ <b>ОШИБКА ПОКУПКИ</b>\n\n{result}"
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="bay_cards")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="bay_cards")]
                ]
            )
        
        await callback.message.edit_text(
            message_text,
            parse_mode="html",
            reply_markup=keyboard
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в confirm_buy_callback: {e}")
        await callback.answer("❌ Ошибка при покупке", show_alert=True)

@router_fkarta.callback_query(F.data == "cancel_buy")
async def cancel_buy_callback(callback: CallbackQuery):
    """Отмена покупки"""
    await callback.message.edit_text(
        "❌ <b>Покупка отменена</b>\n\n"
        "<i>Вы можете выбрать другую карточку</i>",
        parse_mode="html",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="🛒 К покупкам", callback_data="bay_cards"),
                InlineKeyboardButton(text="⬅️ Назад", callback_data="trade_nazad")
            ]]
        )
    )
    await callback.answer("Покупка отменена")


@router_fkarta.callback_query(F.data == "check_combined_callback")
async def check_combined_callback_handler(callback: CallbackQuery):
    """Проверка через callback"""
    try:
        cards = get_all_sell_cards_combined()
        await callback.answer(
            f"Найдено {len(cards)} карточек: {[c.get('type') for c in cards]}",
            show_alert=True
        )
    except Exception as e:
        await callback.answer(f"Ошибка: {str(e)}", show_alert=True)
async def show_sell_cards_page(callback: CallbackQuery, state: FSMContext, page: int = 0, user_coins: int = 0):
    """Показывает страницу карточек пользователя для продажи"""
    try:
        # Получаем данные из состояния
        state_data = await state.get_data()
        user_cards = state_data.get("sell_user_cards", [])
        
        if not user_cards:
            await callback.answer("Нет карточек для продажи", show_alert=True)
            return
        
        # Настройки пагинации
        cards_per_page = 5
        total_cards = len(user_cards)
        total_pages = (total_cards + cards_per_page - 1) // cards_per_page
        
        if page < 0:
            page = 0
        elif page >= total_pages:
            page = total_pages - 1
        
        # Обновляем текущую страницу в состоянии
        await state.update_data({"current_sell_page": page})
        
        # Получаем карточки для текущей страницы
        start_idx = page * cards_per_page
        end_idx = min(start_idx + cards_per_page, total_cards)
        page_cards = user_cards[start_idx:end_idx]
        
        # Формируем сообщение
        message_text = (
            f"💰 <b>ПРОДАЖА КАРТОЧЕК</b>\n\n"
            f"💰 <b>Ваши коины:</b> {user_coins}\n"
            f"📊 <b>Карточек для продажи:</b> {total_cards}\n"
            f"📄 <b>Страница:</b> {page + 1}/{total_pages}\n\n"
        )
        
        for i, card in enumerate(page_cards, start_idx + 1):
            rarity = card.get('rarity', 'Редкий')
            rarity_display = 'Эпический' if rarity == 'эпическая' else rarity
            
            message_text += (
                f"<b>{i}. {card.get('nickname', 'Неизвестно')}</b>\n"
                f"   🏟️ {card.get('club', 'Неизвестно')} | 🎯 {card.get('position', 'Неизвестно')}\n"
                f"   💎 {rarity_display} | 🆔 ID: <code>{card.get('id', '?')}</code>\n\n"
            )
        
        message_text += "<i>Нажмите на кнопку '💰 Продать' под карточкой для выставления на продажу</i>"
        
        # Создаем клавиатуру
        builder = InlineKeyboardBuilder()
        
        # Кнопки для каждой карточки на странице
        for card in page_cards:
            builder.row(
                InlineKeyboardButton(
                    text=f"💰 Продать: {card.get('nickname', 'Карточка')}",
                    callback_data=f"sell_card_{card.get('id', 0)}"
                )
            )
        
        # Навигация по страницам
        if total_pages > 1:
            nav_buttons = []
            
            if page > 0:
                nav_buttons.append(
                    InlineKeyboardButton(
                        text="⬅️ Назад",
                        callback_data=f"trade_sell_page_{page - 1}"
                    )
                )
            
            nav_buttons.append(
                InlineKeyboardButton(
                    text=f"📄 {page + 1}/{total_pages}",
                    callback_data="noop"
                )
            )
            
            if page < total_pages - 1:
                nav_buttons.append(
                    InlineKeyboardButton(
                        text="Вперед ➡️",
                        callback_data=f"trade_sell_page_{page + 1}"
                    )
                )
            
            if nav_buttons:
                builder.row(*nav_buttons)
        
        # Основные кнопки
        builder.row(
            InlineKeyboardButton(text="🔄 Обновить", callback_data="sell_my_card"),
            InlineKeyboardButton(text="📋 Мои продажи", callback_data="my_active_sales")
        )
        builder.row(
            InlineKeyboardButton(text="⬅️ Назад", callback_data="trade_nazad")
        )
        
        # Обновляем сообщение
        await callback.message.edit_text(
            message_text,
            parse_mode="html",
            reply_markup=builder.as_markup()
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в show_sell_cards_page: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@router_fkarta.callback_query(F.data.startswith("sell_page_"))
async def sell_page_callback(callback: CallbackQuery):
    """Обработчик переключения страниц при продаже"""
    try:
        page = int(callback.data.split("_")[2])
        user_coins = get_user_coins(callback.from_user.id)
        await show_sell_cards_page(callback, page, user_coins)
        await callback.answer(f"Страница {page + 1}")
    except Exception as e:
        logger.error(f"Ошибка в sell_page_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@router_fkarta.callback_query(F.data.startswith("sell_card_"))
async def sell_card_callback(callback: CallbackQuery):
    """Обработчик нажатия на кнопку продажи карточки"""
    try:
        card_id = int(callback.data.split("_")[2])
        
        # Получаем информацию о карточке
        card_info = get_card_by_id(card_id)
        if not card_info:
            await callback.answer("❌ Карточка не найдена", show_alert=True)
            return
        
        # Проверяем, не продается ли уже карточка
        if is_card_in_sale(card_id):
            await callback.message.edit_text(
                f"❌ <b>Карточка уже выставлена на продажу!</b>\n\n"
                f"<b>{card_info.get('nickname', 'Неизвестно')}</b> уже есть в продаже.\n\n"
                f"<i>Выберите другую карточку для продажи.</i>",
                parse_mode="html",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[
                        InlineKeyboardButton(text="⬅️ К моим карточкам", callback_data="sell_my_card")
                    ]]
                )
            )
            return
        
        # Формируем сообщение с выбором цены
        rarity = card_info.get('rarity', 'Редкий')
        rarity_display = 'Эпический' if rarity == 'эпическая' else rarity
        
        message_text = (
            f"💰 <b>УКАЗАНИЕ ЦЕНЫ</b>\n\n"
            f"<b>Карточка для продажи:</b>\n"
            f"• {card_info.get('nickname', 'Неизвестно')}\n"
            f"• {card_info.get('club', 'Неизвестно')}\n"
            f"• {card_info.get('position', 'Неизвестно')}\n"
            f"• {rarity_display}\n\n"
            f"<b>Выберите цену продажи:</b>\n\n"
            f"<i>Или введите свою цену (от 1 до 10000 коинов)</i>"
        )
        
        # Создаем клавиатуру с выбором цены
        keyboard = kb.get_sell_price_keyboard(card_id)
        
        # Сохраняем ID карточки в данных сообщения
        await callback.message.edit_text(
            message_text,
            parse_mode="html",
            reply_markup=keyboard
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в sell_card_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@router_fkarta.callback_query(F.data.startswith("set_price_"))
async def set_price_callback(callback: CallbackQuery):
    """Обработчик выбора цены для продажи"""
    try:
        parts = callback.data.split("_")
        card_id = int(parts[2])
        price = int(parts[3])
        
        # Получаем информацию о карточке
        card_info = get_card_by_id(card_id)
        if not card_info:
            await callback.answer("❌ Карточка не найдена", show_alert=True)
            return
        
        # Проверяем цену
        if price < 1 or price > 10000:
            await callback.message.edit_text(
                f"❌ <b>Неверная цена!</b>\n\n"
                f"Цена должна быть от 1 до 10000 коинов.\n\n"
                f"<i>Выберите другую цену.</i>",
                parse_mode="html",
                reply_markup=kb.get_sell_price_keyboard(card_id)
            )
            return
        
        # Формируем сообщение с подтверждением
        rarity = card_info.get('rarity', 'Редкий')
        rarity_display = 'Эпический' if rarity == 'эпическая' else rarity
        
        message_text = (
            f"✅ <b>ПОДТВЕРЖДЕНИЕ ПРОДАЖИ</b>\n\n"
            f"<b>Карточка для продажи:</b>\n"
            f"• {card_info.get('nickname', 'Неизвестно')}\n"
            f"• {card_info.get('club', 'Неизвестно')}\n"
            f"• {card_info.get('position', 'Неизвестно')}\n"
            f"• {rarity_display}\n\n"
            f"<b>Цена продажи:</b> {price} коинов\n\n"
            f"<i>После выставления на продажу карточка будет доступна другим игрокам для покупки.</i>\n\n"
            f"<b>Вы уверены, что хотите выставить эту карточку на продажу?</b>"
        )
        
        # Создаем клавиатуру подтверждения
        keyboard = kb.get_sell_confirmation_keyboard(card_id, price)
        
        await callback.message.edit_text(
            message_text,
            parse_mode="html",
            reply_markup=keyboard
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в set_price_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@router_fkarta.callback_query(F.data.startswith("confirm_sell_"))
async def confirm_sell_callback(callback: CallbackQuery):
    """Подтверждение продажи карточки"""
    try:
        parts = callback.data.split("_")
        card_id = int(parts[2])
        price = int(parts[3])
        user_id = callback.from_user.id
        
        # Выставляем карточку на продажу
        success, message = add_user_sell_card(user_id, card_id, price)
        
        if success:
            # Получаем информацию о карточке
            card_info = get_card_by_id(card_id)
            
            message_text = (
                f"✅ <b>КАРТОЧКА ВЫСТАВЛЕНА НА ПРОДАЖУ!</b>\n\n"
                f"<b>Карточка:</b> {card_info.get('nickname', 'Неизвестно')}\n"
                f"<b>Цена:</b> {price} коинов\n\n"
                f"<i>Теперь другие игроки могут купить вашу карточку.</i>"
            )
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="📋 Мои продажи", callback_data="my_active_sales")],
                    [InlineKeyboardButton(text="🛒 К покупкам", callback_data="bay_cards")],
                    [InlineKeyboardButton(text="⬅️ В меню трейдинга", callback_data="trade_nazad")]
                ]
            )
        else:
            message_text = f"❌ <b>ОШИБКА ПРОДАЖИ</b>\n\n{message}"
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="sell_my_card")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="sell_my_card")]
                ]
            )
        
        await callback.message.edit_text(
            message_text,
            parse_mode="html",
            reply_markup=keyboard
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в confirm_sell_callback: {e}")
        await callback.answer("❌ Ошибка при продаже", show_alert=True)
def remove_all_sell_cards():
    """Удаляет ВСЕ карточки с продажи (админские + пользовательские)"""
    try:
        logger.warning("🔄 Начинаю удаление ВСЕХ карточек с продажи...")
        
        # 1. Удаляем админские продажи
        admin_result = db_operation("SELECT COUNT(*) FROM sell_cards", fetch=True)
        admin_count = admin_result[0][0] if admin_result else 0
        
        if admin_count > 0:
            db_operation("DELETE FROM sell_cards")
            logger.warning(f"🗑️ Удалено админских продаж: {admin_count}")
        
        # 2. Удаляем пользовательские продажи (только активные)
        user_result = db_operation(
            "SELECT COUNT(*) FROM user_sell_transactions WHERE status = 'active'",
            fetch=True
        )
        user_count = user_result[0][0] if user_result else 0
        
        if user_count > 0:
            # Получаем информацию о карточках перед удалением для логирования
            user_sales = db_operation(
                """SELECT ust.id, pc.nickname, ust.price, au.username
                   FROM user_sell_transactions ust
                   JOIN players_catalog pc ON ust.card_id = pc.id
                   JOIN all_users au ON ust.seller_id = au.id
                   WHERE ust.status = 'active'""",
                fetch=True
            )
            
            # Удаляем пользовательские продажи
            db_operation(
                "DELETE FROM user_sell_transactions WHERE status = 'active'"
            )
            
            # Логируем удаленные продажи
            for sale_id, nickname, price, username in (user_sales or []):
                logger.warning(f"🗑️ Удалена пользовательская продажа: {nickname} (ID: {sale_id}) от @{username} за {price} коинов")
            
            logger.warning(f"🗑️ Удалено пользовательских продаж: {user_count}")
        
        total_removed = admin_count + user_count
        
        # 3. Сбрасываем автоинкремент для таблиц (опционально, для чистоты)
        try:
            db_operation("DELETE FROM sqlite_sequence WHERE name='sell_cards'")
            db_operation("DELETE FROM sqlite_sequence WHERE name='user_sell_transactions'")
            logger.info("🔄 Сброшен автоинкремент для таблиц")
        except:
            pass
        
        # 4. Логируем результат
        logger.warning(f"✅ УДАЛЕНО ВСЕГО: {total_removed} карточек с продажи")
        
        return {
            'success': True,
            'admin_removed': admin_count,
            'user_removed': user_count,
            'total_removed': total_removed,
            'message': f"Удалено {total_removed} карточек с продажи"
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка при удалении всех карточек с продажи: {e}")
        import traceback
        logger.error(f"Трейсбэк: {traceback.format_exc()}")
        return {
            'success': False,
            'message': f"Ошибка при удалении: {str(e)[:100]}"
        }

def get_sell_stats():
    """Получает статистику по продажам"""
    try:
        # Админские продажи
        admin_stats = db_operation(
            """SELECT 
                   COUNT(*) as total,
                   SUM(CASE WHEN is_available = 1 THEN 1 ELSE 0 END) as available,
                   SUM(price) as total_value
               FROM sell_cards""",
            fetch=True
        )
        
        # Пользовательские продажи
        user_stats = db_operation(
            """SELECT 
                   COUNT(*) as total,
                   SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active,
                   SUM(price) as total_value
               FROM user_sell_transactions""",
            fetch=True
        )
        
        admin_total, admin_available, admin_value = admin_stats[0] if admin_stats else (0, 0, 0)
        user_total, user_active, user_value = user_stats[0] if user_stats else (0, 0, 0)
        
        return {
            'admin': {
                'total': admin_total,
                'available': admin_available or 0,
                'sold': admin_total - (admin_available or 0),
                'total_value': admin_value or 0
            },
            'user': {
                'total': user_total,
                'active': user_active or 0,
                'sold': user_total - (user_active or 0),
                'total_value': user_value or 0
            },
            'total_cards': admin_total + user_total,
            'total_value': (admin_value or 0) + (user_value or 0)
        }
        
    except Exception as e:
        logger.error(f"Ошибка при получении статистики продаж: {e}")
        return None

@router_fkarta.message(Command("remove_all_sales"))
@require_role("старший-администратор")
@log_admin_action("Удаление всех карточек с продажи")
async def remove_all_sales_command(message: Message):
    """Удалить ВСЕ карточки с продажи (админские и пользовательские)"""
    
    try:
        # Получаем статистику перед удалением
        stats = get_sell_stats()
        
        if not stats or stats['total_cards'] == 0:
            await message.reply(
                "📭 <b>Нет карточек в продаже для удаления</b>\n\n"
                "<i>В продаже нет ни одной карточки</i>",
                parse_mode="html"
            )
            return
        
        # Формируем информацию о текущих продажах
        admin_info = stats['admin']
        user_info = stats['user']
        
        info_message = (
            f"⚠️ <b>ВНИМАНИЕ! УДАЛЕНИЕ ВСЕХ КАРТОЧЕК С ПРОДАЖИ</b>\n\n"
            
            f"<b>📊 Текущая статистика продаж:</b>\n"
            f"• Всего карточек в продаже: {stats['total_cards']}\n"
            f"• Общая стоимость: {stats['total_value']} коинов\n\n"
            
            f"<b>⚡ Админские продажи:</b>\n"
            f"• Всего: {admin_info['total']}\n"
            f"• Доступно: {admin_info['available']}\n"
            f"• Проданные: {admin_info['sold']}\n"
            f"• Стоимость: {admin_info['total_value']} коинов\n\n"
            
            f"<b>👤 Пользовательские продажи:</b>\n"
            f"• Всего: {user_info['total']}\n"
            f"• Активные: {user_info['active']}\n"
            f"• Проданные: {user_info['sold']}\n"
            f"• Стоимость: {user_info['total_value']} коинов\n\n"
            
            f"<b>⚠️ Это действие:</b>\n"
            f"• Удалит ВСЕ карточки с продажи\n"
            f"• Пользователи потеряют выставленные карточки (они вернутся в их коллекции)\n"
            f"• Админские продажи будут полностью удалены\n"
            f"• <b>Действие необратимо!</b>\n\n"
            
            f"<i>Для подтверждения нажмите кнопку ниже</i>"
        )
        
        # Создаем клавиатуру с подтверждением
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="✅ ДА, удалить ВСЕ карточки",
                callback_data="confirm_remove_all_sales"
            ),
            InlineKeyboardButton(
                text="❌ НЕТ, отменить",
                callback_data="cancel_remove_all_sales"
            )
        )
        
        await message.reply(
            info_message,
            parse_mode="html",
            reply_markup=builder.as_markup()
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка в команде remove_all_sales: {e}")
        await message.reply(
            f"❌ Ошибка при получении статистики: {str(e)[:100]}",
            parse_mode="html"
        )


@router_fkarta.callback_query(F.data == "confirm_remove_all_sales")
async def confirm_remove_all_sales_callback(callback: CallbackQuery):
    """Подтверждение удаления всех карточек с продажи"""
    try:
        user_id = callback.from_user.id
        user_name = callback.from_user.username or callback.from_user.first_name
        
        # Удаляем все карточки с продажи
        result = remove_all_sell_cards()
        
        if result['success']:
            # Формируем сообщение об успехе
            success_message = (
                f"✅ <b>ВСЕ КАРТОЧКИ УДАЛЕНЫ С ПРОДАЖИ!</b>\n\n"
                
                f"<b>📊 Результат операции:</b>\n"
                f"• Удалено админских карточек: {result['admin_removed']}\n"
                f"• Удалено пользовательских карточек: {result['user_removed']}\n"
                f"• Всего удалено: {result['total_removed']}\n\n"
                
                f"<b>⚠️ Последствия:</b>\n"
                f"• Все карточки убраны с продажи\n"
                f"• Пользовательские карточки вернулись в коллекции\n"
                f"• Продажи полностью очищены\n\n"
                
                f"<i>Система продаж теперь пуста</i>"
            )
            
            # Логируем действие
            logger.warning(f"👑 АДМИН {user_name} ({user_id}) удалил ВСЕ карточки с продажи: {result['total_removed']} шт.")
            
            # Уведомляем в админскую группу
            try:
                group_id = -1003615487276
                admin_notification = (
                    f"🚨 <b>ВСЕ КАРТОЧКИ УДАЛЕНЫ С ПРОДАЖИ!</b>\n\n"
                    f"<b>👨‍💼 Администратор:</b> @{user_name}\n"
                    f"<b>🆔 ID:</b> <code>{user_id}</code>\n\n"
                    f"<b>📊 Результат:</b>\n"
                    f"• Удалено админских: {result['admin_removed']}\n"
                    f"• Удалено пользовательских: {result['user_removed']}\n"
                    f"• Всего: {result['total_removed']}\n\n"
                    f"<b>⏰ Время:</b> {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}"
                )
                
                await callback.bot.send_message(
                    group_id,
                    admin_notification,
                    parse_mode="html"
                )
            except Exception as group_error:
                logger.error(f"Ошибка при отправке в группу: {group_error}")
            
            # Обновляем сообщение
            await callback.message.edit_text(
                success_message,
                parse_mode="html",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[
                        InlineKeyboardButton(
                            text="🔄 Проверить продажи",
                            callback_data="bay_cards"
                        ),
                        InlineKeyboardButton(
                            text="📊 Статистика",
                            callback_data="check_sell_stats"
                        )
                    ]]
                )
            )
            
        else:
            # Ошибка при удалении
            await callback.message.edit_text(
                f"❌ <b>ОШИБКА УДАЛЕНИЯ!</b>\n\n{result['message']}",
                parse_mode="html",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[
                        InlineKeyboardButton(
                            text="🔄 Попробовать снова",
                            callback_data="confirm_remove_all_sales"
                        ),
                        InlineKeyboardButton(
                            text="⬅️ Назад",
                            callback_data="cancel_remove_all_sales"
                        )
                    ]]
                )
            )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"❌ Ошибка в confirm_remove_all_sales_callback: {e}")
        await callback.answer("❌ Ошибка при удалении", show_alert=True)

@router_fkarta.callback_query(F.data == "cancel_remove_all_sales")
async def cancel_remove_all_sales_callback(callback: CallbackQuery):
    """Отмена удаления всех карточек"""
    try:
        await callback.message.edit_text(
            "❌ <b>Удаление отменено</b>\n\n"
            "<i>Карточки остались в продаже</i>",
            parse_mode="html",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[
                    InlineKeyboardButton(
                        text="🛒 К продажам",
                        callback_data="bay_cards"
                    ),
                    InlineKeyboardButton(
                        text="📊 Статистика",
                        callback_data="check_sell_stats"
                    )
                ]]
            )
        )
        await callback.answer("Удаление отменено")
        
    except Exception as e:
        logger.error(f"Ошибка в cancel_remove_all_sales_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

# Удалите старый обработчик или закомментируйте его:
# @router_fkarta.callback_query(F.data.startswith("page_sell_"))

# Добавьте новый обработчик с уникальным именем:
@router_fkarta.callback_query(F.data.startswith("trade_sell_page_"))
async def trade_sell_page_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик переключения страниц в трейдинге - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    try:
        # Получаем номер страницы из callback_data
        page = int(callback.data.split("_")[3])  # Изменено с [2] на [3]
        
        # Получаем сохраненные карточки из состояния
        state_data = await state.get_data()
        sell_cards = state_data.get("sell_cards", [])
        
        if not sell_cards:
            # Если нет в состоянии, получаем заново
            sell_cards = get_all_sell_cards_combined()
            await state.update_data({"sell_cards": sell_cards})
        
        if not sell_cards:
            await callback.answer("Нет карточек в продаже", show_alert=True)
            return
        
        # Обновляем текущую страницу в состоянии
        await state.update_data({"current_page": page})
        
        # Показываем запрошенную страницу
        await show_sell_cards_page(callback, state, page)
        
    except Exception as e:
        logger.error(f"❌ Ошибка в trade_sell_page_callback: {e}")
        await callback.answer("❌ Ошибка при переключении страницы", show_alert=True)

@router_fkarta.callback_query(F.data == "start_buy_process")
async def start_buy_process_callback(callback: CallbackQuery, state: FSMContext):
    """Начинает процесс покупки - просит ввести ID карточки"""
    try:
        # Устанавливаем состояние ожидания ID карточки
        await state.set_state(TradeStates.waiting_for_card_id)
        
        # Сохраняем ID сообщения для возврата
        await state.update_data({
            "message_id": callback.message.message_id,
            "chat_id": callback.message.chat.id,
            "return_to_page": "bay_cards"  # Возвращать к списку с пагинацией
        })
        
        # Получаем коины пользователя
        user_coins = get_user_coins(callback.from_user.id)
        
        # Сохраняем текущие данные о странице
        state_data = await state.get_data()
        current_page = state_data.get("current_page", 0)
        await state.update_data({"return_page": current_page})
        
        await callback.message.edit_text(
            f"🛒 <b>ПОКУПКА КАРТОЧКИ</b>\n\n"
            f"💰 <b>Ваши МамоКоины:</b> {user_coins}\n\n"
            f"📝 <b>Введите ID карточки:</b>\n\n"
            f"<i>Например: <code>1</code></i>\n\n"
            f"<b>Как узнать ID?</b>\n"
            f"• ID указан в списке карточек (🆔 ...)\n"
            f"• Последние цифры ID на странице с карточками\n\n"
            f"<i>Чтобы отменить, нажмите кнопку 'Отмена'</i>",
            parse_mode="html",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[
                    InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_buy_process")
                ]]
            )
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в start_buy_process_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@router_fkarta.callback_query(F.data == "cancel_buy_process")
async def cancel_buy_process_callback(callback: CallbackQuery, state: FSMContext):
    """Отменяет процесс покупки и возвращает к списку карточек"""
    try:
        # Получаем сохраненную страницу
        state_data = await state.get_data()
        return_page = state_data.get("return_page", 0)
        
        # Возвращаем к списку карточек на нужной странице
        await show_sell_cards_page(callback, state, return_page)
        await callback.answer("Покупка отменена")
    except Exception as e:
        logger.error(f"Ошибка в cancel_buy_process_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@router_fkarta.message(F.text, TradeStates.waiting_for_card_id)
async def process_card_id(message: Message, state: FSMContext):
    """Обработка введенного ID карточки - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    user_id = message.from_user.id
    
    try:
        # Проверяем, что сообщение - число (ID продажи)
        try:
            sell_id = int(message.text.strip())
        except ValueError:
            await message.reply(
                "❌ <b>Неверный формат!</b>\n\n"
                "Пожалуйста, введите число (ID для покупки).\n"
                "Пример: <code>123</code>\n\n"
                "<i>Попробуйте еще раз или отмените операцию</i>",
                parse_mode="html",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[
                        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_buy_process")
                    ]]
                )
            )
            return
        
        # Получаем информацию о продаже
        card_info = get_sell_card_info(sell_id)
        if not card_info:
            await message.reply(
                f"❌ <b>Карточка с ID {sell_id} не найдена!</b>\n\n"
                f"<b>Возможные причины:</b>\n"
                f"• Карточка уже продана\n"
                f"• Неверный ID\n"
                f"• Карточка удалена из продажи\n\n"
                f"<i>Проверьте правильность ID в списке карточек</i>",
                parse_mode="html",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[
                        InlineKeyboardButton(text="🔄 К списку карточек", callback_data="bay_cards"),
                        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_buy_process")
                    ]]
                )
            )
            await state.clear()
            return
        
        # Проверяем, есть ли уже эта карточка у пользователя
        if user_has_card(user_id, card_info.get('card_id', 0)):
            await message.reply(
                f"❌ <b>У вас уже есть эта карточка!</b>\n\n"
                f"<b>{card_info.get('nickname', 'Неизвестно')}</b> уже есть в вашей коллекции.\n"
                f"<i>Используйте /mycards для просмотра коллекции</i>",
                parse_mode="html",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[
                        InlineKeyboardButton(text="⬅️ К списку карточек", callback_data="bay_cards"),
                        InlineKeyboardButton(text="📚 Моя коллекция", callback_data="view_my_cards")
                    ]]
                )
            )
            await state.clear()
            return
        
        # Получаем коины пользователя
        user_coins = get_user_coins(user_id)
        
        # Формируем сообщение с подтверждением
        rarity = card_info.get('rarity', 'Редкий')
        rarity_display = 'Эпический' if rarity == 'эпическая' else rarity
        
        confirmation_text = (
            f"✅ <b>ПОДТВЕРЖДЕНИЕ ПОКУПКИ</b>\n\n"
            f"<b>Выбранная карточка:</b>\n"
            f"👤 <b>Игрок:</b> {card_info.get('nickname', 'Неизвестно')}\n"
            f"🏟️ <b>Клуб:</b> {card_info.get('club', 'Неизвестно')}\n"
            f"🎯 <b>Позиция:</b> {card_info.get('position', 'Неизвестно')}\n"
            f"💎 <b>Редкость:</b> {rarity_display}\n"
            f"💰 <b>Цена:</b> {card_info.get('price', 0)} коинов\n\n"
        )
        
        # Добавляем комментарий только если он есть (безопасно)
        comment = card_info.get('comment', '')
        if comment and comment.strip() and comment.strip().lower() not in ['', 'no_comment']:
            confirmation_text += f"<b>📝 Комментарий:</b> {comment}\n\n"
        
        confirmation_text += (
            f"<b>Ваш баланс:</b> {user_coins} коинов\n"
            f"<b>После покупки:</b> {user_coins - card_info.get('price', 0)} коинов\n\n"
        )
        
        if user_coins < card_info.get('price', 0):
            confirmation_text += (
                f"❌ <b>Недостаточно коинов!</b>\n\n"
                f"<i>Вам нужно еще {card_info.get('price', 0) - user_coins} коинов</i>"
            )
            buttons = [
                [
                    InlineKeyboardButton(text="⬅️ К списку карточек", callback_data="bay_cards"),
                    InlineKeyboardButton(text="👤 Мой профиль", callback_data="trade_profile")
                ]
            ]
            
            await message.reply(
                confirmation_text,
                parse_mode="html",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
            )
            await state.clear()
            return
        
        confirmation_text += "<i>Вы уверены, что хотите купить эту карточку?</i>"
        
        # Сохраняем ID карточки в состоянии
        await state.update_data({
            "selected_sell_id": sell_id,
            "card_info": card_info
        })
        
        # Отправляем сообщение с подтверждением
        await message.reply(
            confirmation_text,
            parse_mode="html",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Купить", callback_data=f"confirm_buy_{sell_id}"),
                    InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_buy")
                ]
            ])
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка в process_card_id для пользователя {user_id}: {e}")
        await message.reply(
            "❌ Произошла ошибка при обработке запроса\n\n"
            "<i>Попробуйте еще раз или обратитесь к администратору</i>",
            parse_mode="html",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[
                    InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="start_buy_process"),
                    InlineKeyboardButton(text="⬅️ Назад", callback_data="bay_cards")
                ]]
            )
        )
        await state.clear()


async def send_purchase_notification_to_admin(bot: Bot, user_id: int, user_name: str, 
                                             sell_id: int, card_info: dict = None, price: int = 0):
    """Отправляет уведомление администратору о покупке карточки"""
    try:
        # Формируем сообщение для администратора
        if card_info and 'nickname' in card_info:
            rarity_display = 'Эпический' if card_info.get('rarity') == 'эпическая' else card_info.get('rarity', 'Неизвестно')
            admin_message = (
                f"🛒 <b>НОВАЯ ПОКУПКА КАРТОЧКИ!</b>\n\n"
                f"<b>👤 Покупатель:</b> @{user_name}\n"
                f"<b>🆔 ID покупателя:</b> <code>{user_id}</code>\n\n"
                f"<b>🃏 Купленная карточка:</b>\n"
                f"• <b>Игрок:</b> {card_info.get('nickname', 'Неизвестно')}\n"
                f"• <b>Клуб:</b> {card_info.get('club', 'Неизвестно')}\n"
                f"• <b>Позиция:</b> {card_info.get('position', 'Неизвестно')}\n"
                f"• <b>Редкость:</b> {rarity_display}\n"
                f"• <b>Цена:</b> {card_info.get('price', price)} коинов\n"
                f"• <b>ID продажи:</b> <code>{sell_id}</code>\n\n"
                f"<b>⏰ Время покупки:</b> {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}\n\n"
                f"<i>Для проверки пользователя: /checkuser {user_id}</i>"
            )
        else:
            admin_message = (
                f"🛒 <b>НОВАЯ ПОКУПКА!</b>\n\n"
                f"<b>👤 Покупатель:</b> @{user_name}\n"
                f"<b>🆔 ID покупателя:</b> <code>{user_id}</code>\n"
                f"<b>💰 Цена:</b> {price} коинов\n"
                f"<b>🆔 ID продажи:</b> <code>{sell_id}</code>\n\n"
                f"<b>⏰ Время покупки:</b> {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}\n\n"
                f"<i>Информация о карточке не найдена в базе</i>"
            )
        
        # ID администратора
        admin_ids = [1088006569]
        
        # Отправляем всем администраторам
        for admin_id in admin_ids:
            try:
                # Пытаемся отправить с картинкой если есть информация о карточке
                if card_info and 'nickname' in card_info:
                    png_file_path = get_specific_card_image(card_info['nickname'], card_info.get('rarity', 'Редкий'))
                    if png_file_path and os.path.exists(png_file_path):
                        from aiogram.types import FSInputFile
                        photo = FSInputFile(png_file_path)
                        
                        await bot.send_photo(
                            chat_id=admin_id,
                            photo=photo,
                            caption=admin_message,
                            parse_mode="html"
                        )
                    else:
                        await bot.send_message(
                            chat_id=admin_id,
                            text=admin_message,
                            parse_mode="html"
                        )
                else:
                    await bot.send_message(
                        chat_id=admin_id,
                        text=admin_message,
                        parse_mode="html"
                    )
                
                logger.info(f"✅ Уведомление о покупке отправлено администратору {admin_id}")
                await asyncio.sleep(0.5)
                
            except Exception as admin_error:
                logger.error(f"Ошибка при отправке уведомления администратору {admin_id}: {admin_error}")
        
        # Также логируем в файл
        logger.warning(
            f"💰 ПОКУПКА: Пользователь {user_name} (ID: {user_id}) купил карточку "
            f"{card_info['nickname'] if card_info and 'nickname' in card_info else 'ID:' + str(sell_id)} за {price} коинов"
        )
        
    except Exception as e:
        logger.error(f"Критическая ошибка при отправке уведомления администратору: {e}")


@router_fkarta.callback_query(F.data.startswith("trade_buy_page_"))
async def trade_buy_page_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик переключения страниц в покупке"""
    try:
        # Извлекаем номер страницы из callback_data
        # Формат: "trade_buy_page_0", "trade_buy_page_1" и т.д.
        page = int(callback.data.split("_")[3])  # Разделяем по "_" и берем 4-й элемент
        
        # Получаем данные из состояния
        state_data = await state.get_data()
        sell_cards = state_data.get("all_sell_cards", [])
        
        if not sell_cards:
            await callback.answer("Нет карточек", show_alert=True)
            return
        
        # Показываем запрошенную страницу
        await show_trade_buy_page(callback.message, state, page, callback)
        
    except Exception as e:
        logger.error(f"Ошибка в trade_buy_page_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)



@router_fkarta.callback_query(F.data.startswith("trade_sell_page_"))
async def trade_sell_page_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик переключения страниц в продаже"""
    try:
        # Формат: "trade_sell_page_0", "trade_sell_page_1" и т.д.
        page = int(callback.data.split("_")[3])
        
        # Получаем данные из состояния
        state_data = await state.get_data()
        available_cards = state_data.get("available_for_sale", [])
        
        if not available_cards:
            await callback.answer("Нет карточек", show_alert=True)
            return
        
        # Показываем запрошенную страницу
        await show_trade_sell_page(callback.message, state, page, callback)
        
    except Exception as e:
        logger.error(f"Ошибка в trade_sell_page_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)
@router_fkarta.callback_query(F.data.startswith("my_sales_page_"))
async def my_sales_page_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик переключения страниц в разделе "мои продажи" """
    try:
        # Формат: "my_sales_page_0", "my_sales_page_1" и т.д.
        page = int(callback.data.split("_")[3])
        
        # Получаем данные из состояния
        state_data = await state.get_data()
        sell_cards = state_data.get("my_sell_cards", [])
        
        if not sell_cards:
            await callback.answer("Нет продаж", show_alert=True)
            return
        
        # Показываем запрошенную страницу
        await show_my_sales_page(callback.message, state, page, callback)
        
    except Exception as e:
        logger.error(f"Ошибка в my_sales_page_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@router_fkarta.callback_query(F.data.startswith("confirm_buy_"))
async def confirm_buy_callback(callback: CallbackQuery, state: FSMContext):
    """Подтверждение покупки с уведомлением"""
    user_id = callback.from_user.id
    user_name = callback.from_user.username or callback.from_user.first_name
    
    try:
        # Получаем ID карточки
        sell_id = int(callback.data.split("_")[2])
        
        # Покупаем карточку
        success, message = purchase_card(user_id, sell_id)
        
        if success:
            # Определяем тип продажи
            admin_check = db_operation(
                "SELECT 1 FROM sell_cards WHERE id = ?",
                (sell_id,),
                fetch=True
            )
            
            if admin_check:
                # Админская продажа
                card_info = get_sell_card_info(sell_id)
                transaction_type = "admin"
                
                # Отправляем уведомление админу
                await send_purchase_notification_to_admin(
                    bot=callback.bot,
                    user_id=user_id,
                    user_name=user_name,
                    sell_id=sell_id,
                    card_info=card_info,
                    price=card_info['price'] if card_info else 0
                )
            else:
                # Пользовательская продажа
                result = db_operation(
                    """SELECT ust.seller_id, ust.card_id, ust.price, pc.nickname
                       FROM user_sell_transactions ust
                       JOIN players_catalog pc ON ust.card_id = pc.id
                       WHERE ust.id = ?""",
                    (sell_id,),
                    fetch=True
                )
                
                if result:
                    seller_id, card_id, price, nickname = result[0]
                    card_info = {'nickname': nickname, 'price': price}
                    transaction_type = "user"
                    
                    # Отправляем уведомление о сделке
                    await send_user_sell_notification(
                        bot=callback.bot,
                        seller_id=seller_id,
                        buyer_id=user_id,
                        sell_id=sell_id,
                        card_info=card_info,
                        price=price
                    )
            
            # Показываем успешное сообщение
            user_coins = get_user_coins(user_id)
            
            success_message = (
                f"🎉 <b>ПОКУПКА УСПЕШНА!</b>\n\n"
                f"<b>Тип сделки:</b> {'👤 Пользовательская' if transaction_type == 'user' else '⚡ Административная'}\n"
                f"<b>Осталось коинов:</b> {user_coins}\n\n"
                f"<i>Карточка добавлена в вашу коллекцию</i>"
            )
            
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text="📚 Моя коллекция", callback_data="view_my_cards"),
                InlineKeyboardButton(text="🛒 Еще покупки", callback_data="bay_cards")
            )
            
            await callback.message.edit_text(
                success_message,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
            
        else:
            # Ошибка при покупке
            await callback.message.edit_text(
                f"❌ <b>ОШИБКА ПОКУПКИ</b>\n\n{message}",
                parse_mode="html",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="start_buy_process"),
                    InlineKeyboardButton(text="⬅️ Назад", callback_data="bay_cards")
                ]])
            )
        
        await state.clear()
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в confirm_buy_callback: {e}")
        await callback.answer("❌ Ошибка при покупке", show_alert=True)
        await state.clear()

@router_fkarta.callback_query(F.data == "cancel_buy")
async def cancel_buy_callback(callback: CallbackQuery, state: FSMContext):
    """Отмена покупки"""
    try:
        await callback.message.edit_text(
            "❌ <b>Покупка отменена</b>\n\n"
            "<i>Вы можете выбрать другую карточку</i>",
            parse_mode="html",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[
                    InlineKeyboardButton(text="🛒 К покупкам", callback_data="bay_cards"),
                    InlineKeyboardButton(text="⬅️ Назад", callback_data="trade_nazad")
                ]]
            )
        )
        await state.clear()
        await callback.answer("Покупка отменена")
    except Exception as e:
        logger.error(f"Ошибка в cancel_buy_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@router_fkarta.callback_query(F.data == "view_user_history")
async def view_user_history_callback(callback: CallbackQuery):
    """Показывает полную историю покупок пользователя с пагинацией (первая страница)"""
    user_id = callback.from_user.id
    user_name = callback.from_user.username or callback.from_user.first_name
    
    try:
        # Получаем всю историю покупок
        all_history = get_purchase_history(user_id, limit=1000)  # Получаем все записи
        total_purchases = len(all_history)
        
        if total_purchases == 0:
            await callback.message.edit_text(
                f"📭 <b>ИСТОРИЯ ПОКУПОК</b>\n\n"
                f"👤 <b>Пользователь:</b> {user_name}\n\n"
                f"<i>У вас еще нет покупок</i>\n\n"
                f"<b>Начните собирать коллекцию!</b>",
                parse_mode="html",
                reply_markup=InlineKeyboardBuilder()
                .add(InlineKeyboardButton(text="🛒 К покупкам", callback_data="bay_cards"))
                .add(InlineKeyboardButton(text="⬅️ В профиль", callback_data="trade_profile"))
                .adjust(2)
                .as_markup()
            )
            return
        
        # Показываем первую страницу
        await show_purchase_history_page(callback, user_id, user_name, all_history, page=0)
        
    except Exception as e:
        logger.error(f"Ошибка в view_user_history_callback для пользователя {user_id}: {e}")
        await callback.answer("❌ Ошибка при загрузке истории", show_alert=True)


async def show_purchase_history_page(callback: CallbackQuery, user_id: int, user_name: str, 
                                    all_history: list, page: int = 0):
    """Показывает указанную страницу истории покупок"""
    try:
        # Настройки пагинации
        items_per_page = 5
        total_purchases = len(all_history)
        total_pages = (total_purchases + items_per_page - 1) // items_per_page
        
        # Проверяем корректность страницы
        if page < 0:
            page = 0
        elif page >= total_pages:
            page = total_pages - 1
        
        # Получаем покупки для текущей страницы
        start_idx = page * items_per_page
        end_idx = min(start_idx + items_per_page, total_purchases)
        page_purchases = all_history[start_idx:end_idx]
        
        # Формируем заголовок
        total_spent = sum(purchase['price'] for purchase in all_history)
        
        header = (
            f"📜 <b>ПОЛНАЯ ИСТОРИЯ ПОКУПОК</b>\n\n"
            f"👤 <b>Пользователь:</b> {user_name}\n"
            f"💰 <b>Всего потрачено:</b> {total_spent} коинов\n"
            f"🃏 <b>Куплено карточек:</b> {total_purchases}\n\n"
            f"<b>Страница {page + 1} из {total_pages}</b>\n"
            f"<i>Покупки {start_idx + 1}-{end_idx} из {total_purchases}</i>\n\n"
        )
        
        # Формируем список покупок
        purchases_text = ""
        for i, purchase in enumerate(page_purchases, start_idx + 1):
            rarity_display = 'Эпический' if purchase['rarity'] == 'эпическая' else purchase['rarity']
            purchases_text += (
                f"<b>{i}. {purchase['nickname']}</b>\n"
                f"   💰 <b>Цена:</b> {purchase['price']} коинов\n"
                f"   🏟️ <b>Клуб:</b> {purchase['club']}\n"
                f"   🎯 <b>Позиция:</b> {purchase['position'] or 'Не указана'}\n"
                f"   💎 <b>Редкость:</b> {rarity_display}\n"
                f"   📅 <b>Дата:</b> {purchase['purchased_at'][:16]}\n"
            )
            if i < end_idx:
                purchases_text += "   ─" * 15 + "\n\n"
        
        message_text = header + purchases_text
        
        # Создаем клавиатуру с навигацией
        builder = InlineKeyboardBuilder()
        
        # Кнопки навигации по страницам (если больше одной страницы)
        if total_pages > 1:
            nav_buttons = []
            
            if page > 0:
                nav_buttons.append(
                    InlineKeyboardButton(
                        text="⬅️ Назад",
                        callback_data=f"history_page_{page - 1}_{user_id}"
                    )
                )
            
            nav_buttons.append(
                InlineKeyboardButton(
                    text=f"📄 {page + 1}/{total_pages}",
                    callback_data="noop"
                )
            )
            
            if page < total_pages - 1:
                nav_buttons.append(
                    InlineKeyboardButton(
                        text="Вперед ➡️",
                        callback_data=f"history_page_{page + 1}_{user_id}"
                    )
                )
            
            if nav_buttons:
                builder.row(*nav_buttons)
        
        # Основные кнопки действий
        action_buttons = []
        action_buttons.append(
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data="view_user_history"
            )
        )
        action_buttons.append(
            InlineKeyboardButton(
                text="⬅️ В профиль",
                callback_data="trade_profile"
            )
        )
        
        builder.row(*action_buttons)
        
        # Обновляем сообщение
        await callback.message.edit_text(
            message_text,
            parse_mode="html",
            reply_markup=builder.as_markup()
        )
        
        await callback.answer(f"Страница {page + 1}")
        
    except Exception as e:
        logger.error(f"Ошибка в show_purchase_history_page для пользователя {user_id}: {e}")
        await callback.answer("❌ Ошибка при загрузке страницы", show_alert=True)
#=====================
#обработчик постов во всех тгк, в которых есть бот
import asyncio

DISCUSSION_GROUP_ID = -1003505055906
CHANNEL_ID = -1002904046490

@router_fkarta.channel_post()
async def handle_channel_post(channel_post: Message, bot: Bot):
    if channel_post.chat.id != CHANNEL_ID:
        return
    
    # Проверяем, есть ли у поста комментарии/тема
    has_comments = False
    
    try:
        # Получаем информацию о чате
        chat_info = await bot.get_chat(CHANNEL_ID)
        
        # Проверяем, есть ли у канала темы
        if hasattr(chat_info, 'is_forum') and chat_info.is_forum:
            has_comments = True

    except Exception as e:
        logger.error(f"Ошибка получения информации о чате: {e}")
    
    try:
        if has_comments:
            # Отправляем в комментарии канала
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text="🎮 Напиши 'Фмамо' и забери свою карточку!",
                message_thread_id=channel_post.message_id
            )
            logger.info(f"Отправил в комментарии к посту {channel_post.message_id}")
        else:
            # Отправляем в группу обсуждений
            await bot.send_message(
                chat_id=DISCUSSION_GROUP_ID,
                text="🎮 Напиши 'Фмамо' и забери свою карточку!"
            )
            logger.info(f"Отправил в группу обсуждений для поста {channel_post.message_id}")
            
    except Exception as e:
        logger.error(f"Ошибка при отправке: {e}")
#=====================
@router_fkarta.callback_query(F.data.startswith("history_page_"))
async def history_page_callback(callback: CallbackQuery):
    """Обработчик переключения страниц истории покупок"""
    try:
        # Получаем данные из callback_data: history_page_{page}_{user_id}
        parts = callback.data.split("_")
        page = int(parts[2])
        user_id = int(parts[3])
        
        # Проверяем, что текущий пользователь имеет доступ
        if callback.from_user.id != user_id:
            await callback.answer("❌ Это не ваша история покупок!", show_alert=True)
            return
        
        user_name = callback.from_user.username or callback.from_user.first_name
        
        # Получаем историю заново (простой подход)
        all_history = get_purchase_history(user_id, limit=1000)
        
        if not all_history:
            await callback.answer("История покупок пуста", show_alert=True)
            return
        
        # Показываем запрошенную страницу
        await show_purchase_history_page(callback, user_id, user_name, all_history, page)
        
    except Exception as e:
        logger.error(f"Ошибка в history_page_callback: {e}")
        await callback.answer("❌ Ошибка при переключении страницы", show_alert=True)

@router_fkarta.callback_query(F.data == "obmen_cards")
async def obmen_cards_callback(callback: CallbackQuery):
    await callback.message.edit_text("<b>🔄 Обмен карточек\n\nВыберите карточку, которую хотите обменять:</b>", reply_markup=kb.trade_obmen, parse_mode="html")

@router_fkarta.callback_query(F.data == "trade_nazad")
async def trade_nazad_callback(callback: CallbackQuery):
    await callback.message.edit_text(
        "💰 <b>ПАНЕЛЬ ТРЕЙДИНГА</b>\n"
        "═══════════════════\n"
        "🛒 Покупка карточек\n"
        "💰 Продажа карточек\n"
        "🎨 Крафт карточек\n"
        "📊 Ваш профиль\n"
        "═══════════════════\n",
        reply_markup=kb.trade_main, 
        parse_mode="html"
    )
    

@router_fkarta.message(Command("promo"))
async def promokode_command(message: Message):
    """Использование промокода пользователем"""
    user_id = message.from_user.id
    user_name = message.from_user.username or message.from_user.first_name
    
    command_text = message.text.strip()
    args = command_text.split()
    
    if len(args) < 2:
        await message.reply(
        "<b>Примеры:</b>\n"
        "• <code>/promo WELCOME</code>\n"
        "• <code>/promo BONUS100</code>\n\n"
        "==========================\n"
        "🎁 <b>ПРОМОКОДЫ</b>\n\n"
        "💰 <b>Что это?</b>\n"
        "Промокоды - это специальные коды, которые дают бесплатные МамоКоины!\n\n"
        "📝 <b>Как использовать?</b>\n"
        "1. Получите промокод из новостей или от администратора\n"
        "2. Используйте команду: <code>/promo КОД</code>\n"
        "3. Получите коины на свой счет!\n\n"
        "ℹ️ <b>Важная информация:</b>\n"
        "• Один промокод можно использовать только один раз\n"
        "• Некоторые промокоды имеют ограниченное количество использований\n"
        "• Следите за обновлениями в @mamoballtinder\n\n"
        "<i>Для активации: /promo [код]</i>",
            parse_mode="html"
        )
        return
    
    try:
        # Проверяем бан пользователя
        if is_user_banned(user_id):
            await message.reply(
                "🚫 <b>Вы забанены и не можете использовать промокоды!</b>\n\n"
                "Для обжалования обратитесь: @kirik1231zzap",
                parse_mode="html"
            )
            return
        
        code = args[1].strip()
        
        # Получаем информацию о промокоде для уведомления админу
        promocode_info = get_promocode_info(code)
        
        # Используем промокод
        success, result_msg = use_promocode(code, user_id)
        
        if success:
            # Уведомление об успехе
            if isinstance(result_msg, dict):
                await message.reply(
                    result_msg['message'],
                    parse_mode="html"
                )
                
                # Отправляем уведомление администратору
                await send_promocode_notification_to_admin(
                    bot=message.bot,
                    user_id=user_id,
                    user_name=user_name,
                    promocode=code,
                    coins=result_msg['coins'],
                    promocode_info=promocode_info
                )
            else:
                await message.reply(
                    f"✅ {result_msg}",
                    parse_mode="html"
                )
        else:
            await message.reply(
                f"❌ <b>Не удалось активировать промокод</b>\n\n"
                f"{result_msg}",
                parse_mode="html"
            )
            
    except Exception as e:
        logger.error(f"Ошибка в команде /promokode для пользователя {user_id}: {e}")
        await message.reply(
            f"❌ Произошла ошибка при активации промокода.\n"
            f"Попробуйте позже или обратитесь к администратору.",
            parse_mode="html"
        )



# ===================
# СИСТЕМА КРАФТА КАРТОЧЕК
# ===================

# ===================
# СИСТЕМА КРАФТА КАРТОЧЕК
# ===================

class CraftStates(StatesGroup):
    """Состояния для крафта карточек"""
    waiting_for_rarity = State()
    waiting_for_confirmation = State()
    waiting_for_craft_rarity = State()

# Функции для системы крафта
def get_user_cards_for_craft(user_id: int):
    """Получает карточки пользователя, которые можно использовать для крафта (с учетом "уник")"""
    try:
        # ВАЖНО: Эта функция используется для крафта, а не для составов.
        # Но для единообразия тоже добавим сюда "уник" карточки, если они должны крафтиться.
        # Обычно "уник" - это тоже редкость, как и другие.
        result = db_operation(
            """SELECT 
                   pc.id,
                   pc.nickname,
                   pc.club,
                   pc.position,
                   pc.rarity,
                   uc.card_id,
                   (SELECT COUNT(*) FROM user_cards uc2 WHERE uc2.card_id = uc.card_id AND uc2.user_id = ?) as count
               FROM user_cards uc
               JOIN players_catalog pc ON uc.card_id = pc.id
               WHERE uc.user_id = ?
               GROUP BY pc.id, pc.nickname, pc.club, pc.position, pc.rarity
               ORDER BY 
                 CASE pc.rarity 
                   WHEN 'EEA' THEN 1
                   WHEN 'Суперлегендарный' THEN 2
                   WHEN 'Легендарный' THEN 3
                   WHEN 'Эпический' THEN 4
                   WHEN 'Редкий' THEN 5
                   ELSE 6
                 END,
                 pc.nickname""",
            (user_id, user_id),
            fetch=True
        )

        cards = []
        if result:
            for row in result:
                card_id, nickname, club, position, rarity, db_card_id, count = row
                # Оставляем редкость как есть, "уник" тоже будет в списке
                cards.append({
                    'id': card_id,
                    'db_id': db_card_id,
                    'nickname': nickname,
                    'club': club,
                    'position': position,
                    'rarity': rarity,
                    'count': count
                })

        return cards
    except Exception as e:
        logger.error(f"Ошибка при получении карточек для крафта: {e}")
        return []

def get_craft_requirements(rarity: str):
    """Возвращает требования для крафта карточки определенной редкости"""
    requirements = {
        'Эпический': {
            'required_rarity': 'Редкий',
            'required_count': 8,
            'target_rarity': 'Эпический',
            'target_rarity_db': 'Эпический',
            'description': '8 Редких → 1 Эпический',
            'icon': '🟣'
        },
        'Легендарный': {
            'required_rarity': 'Эпический',
            'required_count': 6,
            'target_rarity': 'Легендарный',
            'target_rarity_db': 'Легендарный',
            'description': '6 Эпических → 1 Легендарный',
            'icon': '🟡'
        },
        'Суперлегендарный': {
            'required_rarity': 'Легендарный',
            'required_count': 5,
            'target_rarity': 'Суперлегендарный',
            'target_rarity_db': 'Суперлегендарный',
            'description': '5 Легендарных → 1 Суперлегендарный',
            'icon': '🔴'
        }
    }
    
    return requirements.get(rarity)

def get_random_craft_card(rarity: str):
    """Возвращает случайную карточку для крафта указанной редкости"""
    try:
        # Маппинг редкостей для базы данных
        rarity_mapping = {
            'Эпический': 'Эпический',
            'Легендарный': 'Легендарный',
            'Суперлегендарный': 'Суперлегендарный'
        }
        
        db_rarity = rarity_mapping.get(rarity)
        if not db_rarity:
            logger.error(f"❌ Неизвестная редкость для крафта: {rarity}")
            return None
        
        # Получаем все карточки указанной редкости
        result = db_operation(
            """SELECT id, nickname, club, position, rarity 
               FROM players_catalog 
               WHERE rarity = ?""",
            (db_rarity,),
            fetch=True
        )
        
        if not result:
            logger.error(f"❌ Нет карточек редкости '{db_rarity}' в базе данных")
            return None
        
        # Выбираем случайную карточку
        card_data = random.choice(result)
        card_id, nickname, club, position, card_rarity = card_data
        
        logger.info(f"✅ Для крафта выбрана карточка: {nickname} ({card_rarity})")
        
        return {
            'id': card_id,
            'nickname': nickname,
            'club': club,
            'position': position,
            'rarity': card_rarity,
            'db_rarity': card_rarity
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка при выборе карточки для крафта {rarity}: {e}")
        import traceback
        logger.error(f"Трейсбэк: {traceback.format_exc()}")
        return None

def perform_craft(user_id: int, rarity: str):
    """Выполняет крафт карточки указанной редкости с проверкой на дубликаты"""
    try:
        logger.info(f"🔧 Начало крафта для пользователя {user_id}, редкость: {rarity}")
        
        # Получаем требования
        requirements = get_craft_requirements(rarity)
        if not requirements:
            logger.error(f"❌ Не найдены требования для редкости: {rarity}")
            return False, "Неверная редкость для крафта"
        
        logger.info(f"🔧 Требования крафта: {requirements}")
        
        # Получаем карточки пользователя
        user_cards = get_user_cards_for_craft(user_id)
        logger.info(f"🔧 У пользователя {len(user_cards)} карточек для крафта")
        
        # Получаем ВСЕ карточки пользователя для проверки дубликатов
        all_user_cards = get_user_cards(user_id)
        user_card_nicknames = {card[0] for card in all_user_cards}  # Никнеймы всех карточек пользователя
        
        # Фильтруем карточки нужной редкости для крафта
        required_cards = [card for card in user_cards if card['rarity'] == requirements['required_rarity']]
        logger.info(f"🔧 Найдено {len(required_cards)} карточек редкости {requirements['required_rarity']}")
        
        # Проверяем, достаточно ли карточек
        total_required = requirements['required_count']
        if len(required_cards) < total_required:
            logger.warning(f"❌ Недостаточно карточек для крафта: нужно {total_required}, есть {len(required_cards)}")
            return False, f"Недостаточно карточек. Нужно {total_required} {requirements['required_rarity'].lower()}, у вас {len(required_cards)}"
        
        # Получаем ВСЕ карточки нужной редкости из каталога
        all_target_cards_result = db_operation(
            """SELECT id, nickname, club, position, rarity 
               FROM players_catalog 
               WHERE rarity = ?""",
            (requirements['target_rarity_db'],),
            fetch=True
        )
        
        if not all_target_cards_result:
            logger.error(f"❌ Нет карточек редкости {rarity} в каталоге")
            return False, "В каталоге нет карточек этой редкости"
        
        # Преобразуем результат
        all_target_cards = []
        for row in all_target_cards_result:
            card_id, nickname, club, position, card_rarity = row
            all_target_cards.append({
                'id': card_id,
                'nickname': nickname,
                'club': club,
                'position': position,
                'rarity': card_rarity
            })
        
        # Фильтруем карточки, которых НЕТ у пользователя
        available_cards = []
        for card in all_target_cards:
            if card['nickname'] not in user_card_nicknames:
                available_cards.append(card)
        
        logger.info(f"🔧 Всего карточек редкости {rarity}: {len(all_target_cards)}")
        logger.info(f"🔧 Карточек которых нет у пользователя: {len(available_cards)}")
        
        # Если у пользователя уже есть все карточки этой редкости
        if not available_cards:
            logger.warning(f"❌ У пользователя уже есть все карточки редкости {rarity}")
            return False, {
                'already_has_all': True,
                'message': f"У вас уже есть ВСЕ карточки редкости '{rarity}'!\n\n"
                          f"Вы не можете создать дубликат.\n\n"
                          f"<b>Что можно сделать:</b>\n"
                          f"• Продать или обменять дубликаты\n"
                          f"• Собрать карточки для другого типа крафта\n"
                          f"• Подождать добавления новых карточек",
                'rarity': rarity,
                'user_has_count': len([c for c in all_user_cards if c[3] == requirements['target_rarity_db'] or 
                                      (c[3] == 'эпическая' and requirements['target_rarity_db'] == 'Эпический')])
            }
        
        # Выбираем случайную карточку из доступных (которых нет у пользователя)
        new_card = random.choice(available_cards)
        logger.info(f"✅ Выбрана новая карточка для крафта: {new_card['nickname']} (ID: {new_card['id']})")
        
        # Выбираем случайные карточки для удаления
        cards_to_remove = random.sample(required_cards, min(total_required, len(required_cards)))
        logger.info(f"🔧 Будет удалено {len(cards_to_remove)} карточек")
        
        # СОЗДАЕМ СПИСОК КАРТОЧЕК ДЛЯ СООБЩЕНИЯ ПОЛЬЗОВАТЕЛЮ
        removed_cards_list = []
        removed_ids = []
        for card in cards_to_remove:
            logger.info(f"🔧 Удаление карточки: {card['nickname']} (ID: {card['db_id']})")
            # Удаляем одну копию карточки
            db_operation(
                """DELETE FROM user_cards 
                   WHERE rowid IN (
                       SELECT rowid FROM user_cards 
                       WHERE user_id = ? AND card_id = ? 
                       LIMIT 1
                   )""",
                (user_id, card['db_id'])
            )
            removed_ids.append(card['db_id'])
            # Добавляем в список для отображения пользователю
            removed_cards_list.append({
                'nickname': card['nickname'],
                'club': card['club'],
                'position': card['position'],
                'rarity': card['rarity']
            })
        
        logger.info(f"✅ Новая карточка: {new_card['nickname']} (ID: {new_card['id']})")
        
        # Добавляем новую карточку пользователю
        add_card_to_user(user_id, new_card['id'])
        
        # Логируем крафт
        logger.info(f"🎨 Крафт выполнен успешно: пользователь {user_id} получил {new_card['nickname']} ({rarity})")
        
        return True, {
            'success': True,
            'message': f"Крафт успешно выполнен! Вы получили:",
            'card': new_card,
            'removed_count': len(cards_to_remove),
            'removed_rarity': requirements['required_rarity'],
            'removed_cards': removed_cards_list,
            'requirements': requirements
        }
        
    except Exception as e:
        logger.error(f"❌ Ошибка при выполнении крафта: {e}")
        import traceback
        logger.error(f"Трейсбэк: {traceback.format_exc()}")
        return False, f"Ошибка при выполнении крафта: {str(e)[:100]}"

# Команда и обработчики для крафта
@router_fkarta.callback_query(F.data == "craft_cards")
async def craft_cards_callback(callback: CallbackQuery, state: FSMContext):
    """Показывает меню крафта карточек"""
    user_id = callback.from_user.id
    user_name = callback.from_user.username or callback.from_user.first_name
    
    try:
        # Получаем карточки пользователя для статистики
        user_cards = get_user_cards_for_craft(user_id)
        
        # Считаем карточки по редкостям
        rarity_counts = {}
        for card in user_cards:
            rarity = card['rarity']
            if rarity not in rarity_counts:
                rarity_counts[rarity] = 0
            rarity_counts[rarity] += card['count']
        
        # Формируем сообщение
        message_text = (
            f"🎨 <b>СИСТЕМА КРАФТА КАРТОЧЕК</b>\n\n"
            f"👤 <b>Пользователь:</b> {user_name}\n\n"
            f"📊 <b>Ваши карточки для крафта:</b>\n"
        )
        
        rarity_order = ['Редкий', 'Эпический', 'Легендарный', 'Суперлегендарный']
        for rarity in rarity_order:
            count = rarity_counts.get(rarity, 0)
            message_text += f"• {rarity}: {count} шт.\n"
        
        message_text += "\n🎯 <b>Доступный крафт:</b>\n"
        message_text += "1. 8 × Редких → 1 Эпический\n"
        message_text += "2. 6 × Эпических → 1 Легендарный\n"
        message_text += "3. 5 × Легендарных → 1 Суперлегендарный\n\n"
        message_text += "<i>Выберите редкость карточки, которую хотите получить:</i>"
        
        # Создаем клавиатуру с выбором редкости
        builder = InlineKeyboardBuilder()
        
        # Проверяем, достаточно ли карточек для каждого типа крафта
        if rarity_counts.get('Редкий', 0) >= 8:
            builder.button(text="🟣 Получить Эпический (8 редких)", callback_data="craft_epic")
        else:
            builder.button(text="❌ Эпический (нужно 8 редких)", callback_data="no_craft")
        
        if rarity_counts.get('Эпический', 0) >= 6:
            builder.button(text="🟡 Получить Легендарный (6 эпических)", callback_data="craft_legendary")
        else:
            builder.button(text="❌ Легендарный (нужно 6 эпических)", callback_data="no_craft")
        
        if rarity_counts.get('Легендарный', 0) >= 5:
            builder.button(text="🔴 Получить Суперлегендарный (5 легендарных)", callback_data="craft_super_legendary")
        else:
            builder.button(text="❌ Суперлегендарный (нужно 5 легендарных)", callback_data="no_craft")
        
        builder.button(text="⬅️ Назад", callback_data="trade_nazad")
        
        builder.adjust(1)
        
        await callback.message.edit_text(
            message_text,
            parse_mode="html",
            reply_markup=builder.as_markup()
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в craft_cards_callback: {e}")
        await callback.answer("❌ Ошибка при загрузке меню крафта", show_alert=True)

@router_fkarta.callback_query(F.data.startswith("craft_"))
async def craft_rarity_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора редкости для крафта"""
    user_id = callback.from_user.id
    user_name = callback.from_user.username or callback.from_user.first_name
    
    try:
        rarity_map = {
            'craft_epic': 'Эпический',
            'craft_legendary': 'Легендарный',
            'craft_super_legendary': 'Суперлегендарный'
        }
        
        rarity = rarity_map.get(callback.data)
        if not rarity:
            await callback.answer("❌ Неверный тип крафта")
            return
        
        # Получаем требования для крафта
        requirements = get_craft_requirements(rarity)
        if not requirements:
            await callback.answer("❌ Ошибка: не найдены требования для крафта")
            return
        
        # Получаем карточки пользователя
        user_cards = get_user_cards_for_craft(user_id)
        
        # Фильтруем карточки нужной редкости
        required_cards = [card for card in user_cards if card['rarity'] == requirements['required_rarity']]
        
        # Проверяем, достаточно ли карточек
        if len(required_cards) < requirements['required_count']:
            await callback.answer(
                f"❌ Недостаточно карточек! Нужно {requirements['required_count']} {requirements['required_rarity'].lower()}, у вас {len(required_cards)}",
                show_alert=True
            )
            return
        
        # Сохраняем выбранную редкость в состоянии
        await state.update_data({
            'craft_rarity': rarity,
            'craft_requirements': requirements
        })
        
        # Формируем сообщение с подтверждением
        message_text = (
            f"🎨 <b>ПОДТВЕРЖДЕНИЕ КРАФТА</b>\n\n"
            f"👤 <b>Пользователь:</b> {user_name}\n\n"
            f"🎯 <b>Вы хотите получить:</b> {rarity} карточку\n\n"
            f"📊 <b>Для этого потребуется:</b>\n"
            f"• Отдать {requirements['required_count']} {requirements['required_rarity'].lower()} карточек\n"
            f"• Вы получите случайную {rarity.lower()} карточку\n\n"
            f"📈 <b>Ваши доступные карточки:</b>\n"
            f"• {requirements['required_rarity']}: {len(required_cards)} шт.\n\n"
            f"<i>После крафта выбранные {requirements['required_rarity'].lower()} карточки будут удалены!</i>\n\n"
            f"<b>Вы уверены, что хотите выполнить крафт?</b>"
        )
        
        # Создаем клавиатуру подтверждения
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="✅ Да, выполнить крафт",
                callback_data="confirm_craft"
            ),
            InlineKeyboardButton(
                text="❌ Нет, отменить",
                callback_data="cancel_craft"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="⬅️ Назад к выбору",
                callback_data="craft_cards"
            )
        )
        
        await callback.message.edit_text(
            message_text,
            parse_mode="html",
            reply_markup=builder.as_markup()
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в craft_rarity_callback: {e}")
        await callback.answer("❌ Ошибка при выборе крафта", show_alert=True)

@router_fkarta.callback_query(F.data == "confirm_craft")
async def confirm_craft_callback(callback: CallbackQuery, state: FSMContext):
    """Подтверждение и выполнение крафта"""
    user_id = callback.from_user.id
    user_name = callback.from_user.username or callback.from_user.first_name
    
    try:
        # Получаем данные из состояния
        state_data = await state.get_data()
        rarity = state_data.get('craft_rarity')
        requirements = state_data.get('craft_requirements')
        
        if not rarity or not requirements:
            await callback.answer("❌ Ошибка: данные крафта не найдены", show_alert=True)
            return
        
        # Выполняем крафт
        success, result = perform_craft(user_id, rarity)
        
        if success:
            # Получаем информацию о новой карточке
            new_card = result['card']
            removed_cards = result.get('removed_cards', [])
            
            # Формируем сообщение об успехе
            message_text = (
                f"🎉 <b>КРАФТ ВЫПОЛНЕН УСПЕШНО!</b>\n\n"
                f"👤 <b>Пользователь:</b> {user_name}\n\n"
                f"📤 <b>Вы отдали:</b> {result['removed_count']} {result['removed_rarity'].lower()} карточек\n"
            )
            
            # Добавляем список удаленных карточек
            if removed_cards:
                message_text += f"\n📋 <b>Использованные карточки:</b>\n"
                for i, card in enumerate(removed_cards, 1):
                    message_text += (
                        f"<b>{i}. {card['nickname']}</b>\n"
                        f"   🏟️ {card['club']} | 🎯 {card['position']}\n"
                    )
                
                message_text += f"\n📥 <b>Вы получили НОВУЮ карточку:</b>\n"
            else:
                message_text += f"\n📥 <b>Вы получили НОВУЮ карточку:</b>\n"
            
            message_text += (
                f"<b>• Игрок:</b> {new_card['nickname']}\n"
                f"<b>• Клуб:</b> {new_card['club']}\n"
                f"<b>• Позиция:</b> {new_card['position']}\n"
                f"<b>• Редкость:</b> {new_card['rarity']}\n\n"
                f"✅ <b>Эта карточка была добавлена в вашу коллекцию!</b>\n\n"
                f"🎨 <b>Крафт:</b> {requirements['description']}\n\n"
                f"<i>Поздравляем с успешным крафтом! 🎉</i>"
            )
            
            # Создаем клавиатуру
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(
                    text="🔄 Еще раз",
                    callback_data="craft_cards"
                ),
                InlineKeyboardButton(
                    text="⬅️ В меню трейдинга",
                    callback_data="trade_nazad"
                )
            )
            
            await callback.message.edit_text(
                message_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
            
            # Отправляем уведомление администратору
            try:
                removed_names = ", ".join([card['nickname'] for card in removed_cards[:5]])
                if len(removed_cards) > 5:
                    removed_names += f" и еще {len(removed_cards) - 5}"
                
                await callback.bot.send_message(
                    group_of_admins,  # ID администратора
                    text=f"🎨 НОВЫЙ КРАФТ!\n\n"
                         f"Пользователь: @{callback.from_user.username or callback.from_user.first_name}\n"
                         f"ID: {user_id}\n"
                         f"Получил: {new_card['nickname']} ({rarity})\n"
                         f"Использовал: {removed_names}\n"
                         f"Крафт: {requirements['description']}",
                    parse_mode="html"
                )
            except:
                pass
            
        elif isinstance(result, dict) and result.get('already_has_all'):
            # У пользователя уже есть ВСЕ карточки этой редкости
            message_text = (
                f"❌ <b>НЕВОЗМОЖНО ВЫПОЛНИТЬ КРАФТ</b>\n\n"
                f"{result['message']}\n\n"
                f"<b>Статистика:</b>\n"
                f"• У вас уже есть {result.get('user_has_count', 0)} карточек редкости '{rarity}'\n"
                f"• Вы собрали ВСЕ карточки этой редкости!\n\n"
                f"<i>Система крафта не позволяет создавать дубликаты.</i>"
            )
            
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(
                    text="🔄 Попробовать другой крафт",
                    callback_data="craft_cards"
                ),
                InlineKeyboardButton(
                    text="📚 Моя коллекция",
                    callback_data="view_my_cards"
                )
            )
            builder.row(
                InlineKeyboardButton(
                    text="💰 Продать дубликаты",
                    callback_data="sell_my_card"
                ),
                InlineKeyboardButton(
                    text="⬅️ В меню трейдинга",
                    callback_data="trade_nazad"
                )
            )
            
            await callback.message.edit_text(
                message_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
            
        else:
            # Ошибка при крафте
            error_message = result if isinstance(result, str) else result.get('message', 'Неизвестная ошибка')
            message_text = (
                f"❌ <b>ОШИБКА КРАФТА</b>\n\n"
                f"{error_message}\n\n"
                f"<i>Попробуйте еще раз</i>"
            )
            
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(
                    text="🔄 Попробовать снова",
                    callback_data="craft_cards"
                ),
                InlineKeyboardButton(
                    text="⬅️ В меню трейдинга",
                    callback_data="trade_nazad"
                )
            )
            
            await callback.message.edit_text(
                message_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
        
        await callback.answer()
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка в confirm_craft_callback: {e}")
        await callback.answer("❌ Ошибка при выполнении крафта", show_alert=True)

# Добавляем новые обработчики для выбора при дубликате





@router_fkarta.callback_query(F.data == "cancel_craft")
async def cancel_craft_callback(callback: CallbackQuery, state: FSMContext):
    """Отмена крафта"""
    try:
        await state.clear()
        
        message_text = (
            f"❌ <b>КРАФТ ОТМЕНЕН</b>\n\n"
            f"<i>Вы отменили процесс крафта. Ваши карточки не были использованы.</i>"
        )
        
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="🔄 Начать заново",
                callback_data="craft_cards"
            ),
            InlineKeyboardButton(
                text="⬅️ В меню трейдинга",
                callback_data="trade_nazad"
            )
        )
        
        await callback.message.edit_text(
            message_text,
            parse_mode="html",
            reply_markup=builder.as_markup()
        )
        
        await callback.answer("Крафт отменен")
        
    except Exception as e:
        logger.error(f"Ошибка в cancel_craft_callback: {e}")
        await callback.answer("❌ Ошибка при отмене крафта", show_alert=True)

@router_fkarta.callback_query(F.data == "no_craft")
async def no_craft_callback(callback: CallbackQuery):
    """Обработка нажатия на недоступный крафт"""
    await callback.answer("❌ Недостаточно карточек для этого крафта", show_alert=True)

# Добавим отладочные команды для тестирования
@router_fkarta.message(Command("debug_craft_system"))
@require_role("старший-администратор")
async def debug_craft_system_command(message: Message):
    """Отладка всей системы крафта"""
    try:
        user_id = message.from_user.id
        
        message_text = "🔍 <b>ОТЛАДКА СИСТЕМЫ КРАФТА</b>\n\n"
        
        # 1. Проверим редкости в базе
        rarities_result = db_operation(
            "SELECT DISTINCT rarity, COUNT(*) FROM players_catalog GROUP BY rarity",
            fetch=True
        )
        
        message_text += "<b>Редкости в базе данных:</b>\n"
        if rarities_result:
            for rarity, count in rarities_result:
                message_text += f"• '{rarity}': {count} карточек\n"
        else:
            message_text += "• Нет данных\n"
        
        message_text += "\n<b>Функция get_random_craft_card:</b>\n"
        
        # 2. Протестируем каждую редкость
        for rarity in ['Эпический', 'Легендарный', 'Суперлегендарный']:
            card = get_random_craft_card(rarity)
            if card:
                message_text += f"• {rarity}: {card['nickname']} - OK\n"
            else:
                message_text += f"• {rarity}: ОШИБКА\n"
        
        # 3. Проверим карточки пользователя
        user_cards = get_user_cards_for_craft(user_id)
        message_text += f"\n<b>Карточки пользователя:</b> {len(user_cards)} шт.\n"
        
        # 4. Проверим требования крафта
        message_text += "\n<b>Требования крафта:</b>\n"
        for rarity in ['Эпический', 'Легендарный', 'Суперлегендарный']:
            req = get_craft_requirements(rarity)
            if req:
                message_text += f"• {rarity}: {req['description']}\n"
        
        await message.reply(message_text, parse_mode="html")
        
    except Exception as e:
        logger.error(f"Ошибка в debug_craft_system_command: {e}")
        await message.reply(f"❌ Ошибка: {str(e)}")

# Также нужно добавить кнопку крафта в файл mamokeyboardsAmvera.py:
# В клавиатуре trade_main добавьте строку:
# [InlineKeyboardButton(text="🎨 Крафт карточек", callback_data="craft_cards")

# ДОБАВИМ ЭТИ ФУНКЦИИ В КОНЕЦ ФАЙЛА mamofkarta.py (перед последней строкой)

# ===================
# СИСТЕМА ЛИДЕРОВ
# ===================

def get_leaders_by_coins(limit: int = 10):
    """Получает топ пользователей по количеству коинов"""
    try:
        result = db_operation(
            """SELECT 
                   uc.user_id, 
                   uc.coins,
                   COALESCE(au.username, au.first_name, 'Аноним') as user_name
               FROM user_coins uc
               LEFT JOIN all_users au ON uc.user_id = au.id
               WHERE uc.coins > 0
               ORDER BY uc.coins DESC
               LIMIT ?""",
            (limit,),
            fetch=True
        )
        
        leaders = []
        for row in result:
            user_id, coins, user_name = row
            leaders.append({
                'user_id': user_id,
                'coins': coins,
                'user_name': user_name
            })
        
        return leaders
        
    except Exception as e:
        logger.error(f"Ошибка при получении лидеров по коинам: {e}")
        return []

def get_leaders_by_cards(limit: int = 10):
    """Получает топ пользователей по количеству уникальных карточек"""
    try:
        result = db_operation(
            """SELECT 
                   uc.user_id,
                   COUNT(DISTINCT uc.card_id) as cards_count,
                   COALESCE(au.username, au.first_name, 'Аноним') as user_name
               FROM user_cards uc
               LEFT JOIN all_users au ON uc.user_id = au.id
               GROUP BY uc.user_id
               ORDER BY cards_count DESC
               LIMIT ?""",
            (limit,),
            fetch=True
        )
        
        leaders = []
        for row in result:
            user_id, cards_count, user_name = row
            leaders.append({
                'user_id': user_id,
                'cards_count': cards_count,
                'user_name': user_name
            })
        
        return leaders
        
    except Exception as e:
        logger.error(f"Ошибка при получении лидеров по карточкам: {e}")
        return []

def get_user_position_by_coins(user_id: int):
    """Получает позицию пользователя в рейтинге по коинам"""
    try:
        result = db_operation(
            """SELECT COUNT(*) + 1 as position
               FROM user_coins uc1
               WHERE uc1.coins > (
                   SELECT COALESCE(uc2.coins, 0)
                   FROM user_coins uc2
                   WHERE uc2.user_id = ?
               )""",
            (user_id,),
            fetch=True
        )
        
        if result and result[0]:
            return result[0][0]
        return None
        
    except Exception as e:
        logger.error(f"Ошибка при получении позиции пользователя по коинам: {e}")
        return None

def get_user_position_by_cards(user_id: int):
    """Получает позицию пользователя в рейтинге по карточкам"""
    try:
        result = db_operation(
            """SELECT COUNT(*) + 1 as position
               FROM (
                   SELECT uc.user_id, COUNT(DISTINCT uc.card_id) as cards_count
                   FROM user_cards uc
                   GROUP BY uc.user_id
               ) user_stats1
               WHERE user_stats1.cards_count > (
                   SELECT COALESCE(COUNT(DISTINCT uc2.card_id), 0)
                   FROM user_cards uc2
                   WHERE uc2.user_id = ?
               )""",
            (user_id,),
            fetch=True
        )
        
        if result and result[0]:
            return result[0][0]
        return None
        
    except Exception as e:
        logger.error(f"Ошибка при получении позиции пользователя по карточкам: {e}")
        return None

# ===================
# ОБРАБОТЧИКИ КНОПОК ЛИДЕРОВ
# ===================

@router_fkarta.callback_query(F.data == "trade_leaders")
async def trade_leaders_callback(callback: CallbackQuery):
    """Показывает панель лидеров"""
    try:
        user_id = callback.from_user.id
        user_coins = get_user_coins(user_id)
        user_cards_count = len(get_user_cards(user_id))
        
        # Получаем позиции пользователя
        coins_position = get_user_position_by_coins(user_id)
        cards_position = get_user_position_by_cards(user_id)
        
        message_text = (
            f"🏆 <b>ТАБЛИЦА ЛИДЕРОВ</b>\n\n"
            f"<b>Ваша статистика:</b>\n"
            f"💰 <b>МамоКоины:</b> {user_coins}\n"
            f"🃏 <b>Карточек в коллекции:</b> {user_cards_count}\n\n"
        )
        
        if coins_position:
            message_text += f"📈 <b>Позиция по коинам:</b> #{coins_position}\n"
        
        if cards_position:
            message_text += f"📊 <b>Позиция по карточкам:</b> #{cards_position}\n"
        
        message_text += (
            f"\n<b>Выберите тип рейтинга:</b>\n\n"
            f"<i>Отображаются топ-10 пользователей по каждому показателю</i>"
        )
        
        # Импортируем клавиатуру из mamokeyboardsAmvera
        from mamokeyboardsAmvera import leaders_main
        
        await callback.message.edit_text(
            message_text,
            parse_mode="html",
            reply_markup=leaders_main
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в trade_leaders_callback: {e}")
        await callback.answer("❌ Ошибка при загрузке лидеров", show_alert=True)

@router_fkarta.callback_query(F.data == "leaders_coins")
async def leaders_coins_callback(callback: CallbackQuery):
    """Показывает топ-10 по коинам"""
    try:
        user_id = callback.from_user.id
        leaders = get_leaders_by_coins(limit=10)
        
        if not leaders:
            message_text = (
                "💰 <b>ТОП-10 ПО КОИНАМ</b>\n\n"
                "❌ <i>Нет данных о пользователях</i>"
            )
        else:
            message_text = (
                "💰 <b>ТОП-10 ПО КОИНАМ</b>\n\n"
                "<i>Пользователи с наибольшим количеством мамокоинов</i>\n\n"
            )
            
            for i, leader in enumerate(leaders, 1):
                medal = ""
                if i == 1:
                    medal = "🥇 "
                elif i == 2:
                    medal = "🥈 "
                elif i == 3:
                    medal = "🥉 "
                else:
                    medal = f"<b>{i}.</b> "
                
                user_name = leader['user_name']
                if user_name.startswith("@"):
                    user_display = user_name
                else:
                    user_display = f"<b>{user_name}</b>"
                
                message_text += (
                    f"{medal}{user_display}\n"
                    f"   💰 <b>{leader['coins']}</b> мамокоинов\n\n"
                )
        
        # Добавляем информацию о текущем пользователе
        user_coins = get_user_coins(user_id)
        user_position = get_user_position_by_coins(user_id)
        
        if user_position:
            message_text += (
                f"\n─────────────────────\n"
                f"<b>Ваша позиция:</b> #{user_position}\n"
                f"<b>Ваши коины:</b> {user_coins}\n"
            )
        
        # Создаем клавиатуру для навигации
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="🃏 По карточкам",
                callback_data="leaders_cards"
            ),
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data="leaders_coins"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="trade_leaders"
            )
        )
        
        await callback.message.edit_text(
            message_text,
            parse_mode="html",
            reply_markup=builder.as_markup()
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в leaders_coins_callback: {e}")
        await callback.answer("❌ Ошибка при загрузке рейтинга", show_alert=True)

@router_fkarta.callback_query(F.data == "leaders_cards")
async def leaders_cards_callback(callback: CallbackQuery):
    """Показывает топ-10 по карточкам"""
    try:
        user_id = callback.from_user.id
        leaders = get_leaders_by_cards(limit=10)
        
        if not leaders:
            message_text = (
                "🃏 <b>ТОП-10 ПО КАРТОЧКАМ</b>\n\n"
                "❌ <i>Нет данных о пользователях</i>"
            )
        else:
            # Получаем общее количество карточек в каталоге для сравнения
            total_cards_result = db_operation(
                "SELECT COUNT(*) FROM players_catalog",
                fetch=True
            )
            total_cards = total_cards_result[0][0] if total_cards_result else 0
            
            message_text = (
                "🃏 <b>ТОП-10 ПО КАРТОЧКАМ</b>\n\n"
                f"<i>Пользователи с самой большой коллекцией (всего карточек: {total_cards})</i>\n\n"
            )
            
            for i, leader in enumerate(leaders, 1):
                medal = ""
                if i == 1:
                    medal = "🥇 "
                elif i == 2:
                    medal = "🥈 "
                elif i == 3:
                    medal = "🥉 "
                else:
                    medal = f"<b>{i}.</b> "
                
                user_name = leader['user_name']
                if user_name.startswith("@"):
                    user_display = user_name
                else:
                    user_display = f"<b>{user_name}</b>"
                
                percentage = (leader['cards_count'] / total_cards * 100) if total_cards > 0 else 0
                
                message_text += (
                    f"{medal}{user_display}\n"
                    f"   🃏 <b>{leader['cards_count']}</b> карточек ({percentage:.1f}%)\n\n"
                )
        
        # Добавляем информацию о текущем пользователе
        user_cards = get_user_cards(user_id)
        user_cards_count = len(user_cards) if user_cards else 0
        user_position = get_user_position_by_cards(user_id)
        
        if user_position:
            percentage = (user_cards_count / total_cards * 100) if total_cards > 0 else 0
            message_text += (
                f"\n─────────────────────\n"
                f"<b>Ваша позиция:</b> #{user_position}\n"
                f"<b>Ваши карточки:</b> {user_cards_count} ({percentage:.1f}%)\n"
            )
        
        # Создаем клавиатуру для навигации
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="💰 По коинам",
                callback_data="leaders_coins"
            ),
            InlineKeyboardButton(
                text="🔄 Обновить",
                callback_data="leaders_cards"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="trade_leaders"
            )
        )
        
        await callback.message.edit_text(
            message_text,
            parse_mode="html",
            reply_markup=builder.as_markup()
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в leaders_cards_callback: {e}")
        await callback.answer("❌ Ошибка при загрузке рейтинга", show_alert=True)

# ===================
# АДМИНСКИЕ КОМАНДЫ ДЛЯ УПРАВЛЕНИЯ РЕЙТИНГОМ
# ===================

@router_fkarta.message(Command("leaderboard_stats"))
@require_role("помощник-администратора")
async def leaderboard_stats_command(message: Message):
    """Показывает статистику рейтингов"""
    try:
        # Статистика по коинам
        coins_stats = db_operation(
            """SELECT 
                   COUNT(*) as total_users,
                   AVG(coins) as avg_coins,
                   MAX(coins) as max_coins,
                   MIN(coins) as min_coins
               FROM user_coins
               WHERE coins > 0""",
            fetch=True
        )
        
        # Статистика по карточкам
        cards_stats = db_operation(
            """SELECT 
                   COUNT(DISTINCT user_id) as total_collectors,
                   AVG(card_count) as avg_cards,
                   MAX(card_count) as max_cards
               FROM (
                   SELECT user_id, COUNT(DISTINCT card_id) as card_count
                   FROM user_cards
                   GROUP BY user_id
               )""",
            fetch=True
        )
        
        # Топ-3 по коинам
        top_coins = get_leaders_by_coins(limit=3)
        
        # Топ-3 по карточкам
        top_cards = get_leaders_by_cards(limit=3)
        
        message_text = (
            f"📊 <b>СТАТИСТИКА РЕЙТИНГОВ</b>\n\n"
            
            f"<b>💰 ПО КОИНАМ:</b>\n"
        )
        
        if coins_stats and coins_stats[0]:
            total_users, avg_coins, max_coins, min_coins = coins_stats[0]
            message_text += (
                f"• Всего пользователей: {total_users or 0}\n"
                f"• Среднее количество: {avg_coins or 0:.1f}\n"
                f"• Максимум: {max_coins or 0}\n"
                f"• Минимум: {min_coins or 0}\n\n"
            )
        
        if top_coins:
            message_text += "<b>Топ-3 по коинам:</b>\n"
            for i, leader in enumerate(top_coins, 1):
                message_text += f"{i}. {leader['user_name']} - {leader['coins']} коинов\n"
            message_text += "\n"
        
        message_text += f"<b>🃏 ПО КАРТОЧКАМ:</b>\n"
        
        if cards_stats and cards_stats[0]:
            total_collectors, avg_cards, max_cards = cards_stats[0]
            message_text += (
                f"• Всего коллекционеров: {total_collectors or 0}\n"
                f"• Среднее количество: {avg_cards or 0:.1f}\n"
                f"• Максимум: {max_cards or 0}\n\n"
            )
        
        if top_cards:
            message_text += "<b>Топ-3 по карточкам:</b>\n"
            for i, leader in enumerate(top_cards, 1):
                message_text += f"{i}. {leader['user_name']} - {leader['cards_count']} карточек\n"
        
        message_text += (
            f"\n─────────────────────\n"
            f"<i>Обновлено: {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}</i>"
        )
        
        await message.reply(message_text, parse_mode="html")
        
    except Exception as e:
        logger.error(f"Ошибка в leaderboard_stats_command: {e}")
        await message.reply(f"❌ Ошибка: {str(e)[:100]}")

@router_fkarta.message(Command("reset_leaderboard"))
@require_role("старший-администратор")
@log_admin_action("Сброс рейтингов")
async def reset_leaderboard_command(message: Message):
    """Сбрасывает рейтинги (только для тестирования)"""
    try:
        # Создаем клавиатуру подтверждения
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="✅ Да, сбросить",
                callback_data="confirm_reset_leaderboard"
            ),
            InlineKeyboardButton(
                text="❌ Нет, отменить",
                callback_data="cancel_reset_leaderboard"
            )
        )
        
        await message.reply(
            "⚠️ <b>ВНИМАНИЕ!</b>\n\n"
            "Вы собираетесь сбросить ВСЕ рейтинги:\n\n"
            "• Таблица лидеров по коинам\n"
            "• Таблица лидеров по карточкам\n"
            "• Все позиции пользователей\n\n"
            "<b>Это действие необратимо!</b>\n\n"
            "Вы уверены, что хотите продолжить?",
            parse_mode="html",
            reply_markup=builder.as_markup()
        )
        
    except Exception as e:
        logger.error(f"Ошибка в reset_leaderboard_command: {e}")
        await message.reply(f"❌ Ошибка: {str(e)[:100]}")

@router_fkarta.callback_query(F.data == "confirm_reset_leaderboard")
async def confirm_reset_leaderboard_callback(callback: CallbackQuery):
    """Подтверждение сброса рейтингов"""
    try:
        # На самом деле мы не будем удалять данные, только покажем сообщение
        # В реальной системе здесь была бы логика сброса
        await callback.message.edit_text(
            "✅ <b>Рейтинги сброшены!</b>\n\n"
            "<i>Все таблицы лидеров были обнулены.</i>\n\n"
            "<b>Примечание:</b> В демонстрационной версии данные не удаляются.\n"
            "В реальной системе здесь будет полный сброс статистики.",
            parse_mode="html"
        )
        
        logger.warning(f"👑 Админ {callback.from_user.id} сбросил таблицы лидеров")
        await callback.answer("Рейтинги сброшены")
        
    except Exception as e:
        logger.error(f"Ошибка в confirm_reset_leaderboard_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@router_fkarta.callback_query(F.data == "cancel_reset_leaderboard")
async def cancel_reset_leaderboard_callback(callback: CallbackQuery):
    """Отмена сброса рейтингов"""
    try:
        await callback.message.edit_text(
            "❌ <b>Сброс отменен</b>\n\n"
            "<i>Рейтинги не были сброшены</i>",
            parse_mode="html"
        )
        await callback.answer("Сброс отменен")
        
    except Exception as e:
        logger.error(f"Ошибка в cancel_reset_leaderboard_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)