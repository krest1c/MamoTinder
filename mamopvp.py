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
from mamodatabases import db_operation,logger, get_card_by_nickname_db,get_card_by_id, get_user_squad, get_card_details, get_user_cards_by_position, get_user_cards, save_user_squad, show_cards_for_next_position, SquadStates
public_router_pvp = Router() #публичный роутер pvp
from mamoadmins import require_role
pvp_queue = {}  # {user_id: {'message_id': int, 'chat_id': int, 'time_joined': datetime}}
active_pvp_matches = {}  # {match_id: {'player1': user_id, 'player2': user_id, ...}}

message_update_timestamps = {}
async def safe_edit_message_text(bot: Bot, chat_id: int, message_id: int, text: str, 
                                 parse_mode: str = "html", reply_markup=None, 
                                 min_update_interval: float = 0.5):
    """Безопасное редактирование сообщения с защитой от частых обновлений"""
    try:
        # Создаем уникальный ключ для сообщения
        message_key = f"{chat_id}_{message_id}"
        
        # Проверяем время последнего обновления
        current_time = time.time()
        last_update = message_update_timestamps.get(message_key, 0)
        
        # Если прошло слишком мало времени, пропускаем обновление
        if current_time - last_update < min_update_interval:
            return False
        
        # Обновляем сообщение
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )
        
        # Сохраняем время обновления
        message_update_timestamps[message_key] = current_time
        
        # Очищаем старые записи (старше 5 минут)
        cleanup_time = current_time - 300
        to_remove = [key for key, timestamp in message_update_timestamps.items() 
                    if timestamp < cleanup_time]
        for key in to_remove:
            del message_update_timestamps[key]
        
        return True
        
    except Exception as e:
        error_msg = str(e).lower()
        
        # Обрабатываем разные типы ошибок
        if "message to edit not found" in error_msg or "message not found" in error_msg:
            # Сообщение было удалено, это нормально в процессе поиска
            logger.info(f"Сообщение {chat_id}_{message_id} было удалено или не найдено")
            return False
        elif "message is not modified" in error_msg:
            # Сообщение уже содержит такой текст
            return True
        elif "too many requests" in error_msg:
            # Слишком много запросов, делаем паузу
            await asyncio.sleep(1)
            return False
        else:
            # Другие ошибки
            logger.warning(f"Ошибка при редактировании сообщения {chat_id}_{message_id}: {e}")
            return False
import functools
from aiogram.exceptions import TelegramBadRequest

def handle_old_callback(func):
    """Декоратор для обработки устаревших callback-запросов"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except TelegramBadRequest as e:
            if "query is too old" in str(e) or "query ID is invalid" in str(e):
                # Логируем, но не пробрасываем ошибку
                print(f"Ignored expired callback in {func.__name__}: {e}")
                # Пытаемся получить callback для ответа
                for arg in args:
                    if hasattr(arg, 'answer') and callable(arg.answer):
                        try:
                            await arg.answer()
                        except:
                            pass
                        break
                return
            raise
    return wrapper
# ДОБАВЬТЕ ЭТИ ДВЕ СТРОЧКИ:
pvp_active_matches = {}  # Текущие активные PvP матчи {match_id: {...}}
pvp_tactics = {} 
#основная клавиатура
main_play = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="⚽ Матч", callback_data="play_match")],
    [InlineKeyboardButton(text="👥 Состав", callback_data="sostav")],
    [InlineKeyboardButton(text="📊 Статистика", callback_data="statistics")],
    [InlineKeyboardButton(text="🏆 Топ игроков", callback_data="top_players")],  # НОВАЯ КНОПКА
])
pvp_confirmation_states = {}  
@public_router_pvp.message(Command("play"))
async def play_command(message: Message):
    await message.reply("<b>🎮 Игровое меню:</b>", reply_markup=main_play, parse_mode="html")

# Глобальный словарь для хранения сообщений поиска

search_messages_dict = {}  # {user_id: (chat_id, message_id)}
pvp_confirmation_states = {}  # Состояния подтверждения PvP
pvp_queue = {}  # {user_id: {'message_id': int, 'chat_id': int, 'time_joined': datetime}}
active_pvp_matches = {}  # {match_id: {'player1': user_id, 'player2': user_id, ...}}
pvp_active_matches = {}  # Текущие активные PvP матчи {match_id: {...}}
pvp_tactics = {} 
async def cleanup_search_messages(user_id: int, opponent_id: int, bot: Bot):
    """Очищает сообщения поиска у обоих игроков"""
    try:
        global search_messages_dict
        
        messages_to_delete = []
        
        # Удаляем сообщение поиска у пользователя
        if user_id in search_messages_dict:
            messages_to_delete.append((user_id, search_messages_dict[user_id]))
            logger.info(f"Найдено сообщение поиска для удаления у пользователя {user_id}")
        
        # Удаляем сообщение поиска у соперника
        if opponent_id in search_messages_dict:
            messages_to_delete.append((opponent_id, search_messages_dict[opponent_id]))
            logger.info(f"Найдено сообщение поиска для удаления у соперника {opponent_id}")
        
        # Удаляем все найденные сообщения
        for uid, (chat_id, message_id) in messages_to_delete:
            try:
                logger.info(f"Попытка удалить сообщение поиска у пользователя {uid}: chat_id={chat_id}, message_id={message_id}")
                await bot.delete_message(chat_id=chat_id, message_id=message_id)
                logger.info(f"✅ Удалено сообщение поиска у пользователя {uid}")
            except Exception as e:
                logger.error(f"❌ Ошибка при удалении сообщения поиска у пользователя {uid}: {e}")
            finally:
                # Удаляем из словаря в любом случае
                if uid in search_messages_dict:
                    del search_messages_dict[uid]
                    logger.info(f"Запись удалена из search_messages_dict для пользователя {uid}")
                
    except Exception as e:
        logger.error(f"Ошибка при очистке сообщений поиска: {e}")

cleanup_search_messages.search_messages = {}
@public_router_pvp.callback_query(F.data == "sostav")
@handle_old_callback
async def sostav_message(callback: CallbackQuery, state: FSMContext):
    """Показывает состав пользователя с возможностью изменения"""
    user_id = callback.from_user.id
    await state.clear()
    try:
        # Получаем текущий состав пользователя
        squad = get_user_squad(user_id)
        
        if squad:
            # Формируем текст состава с деталями карточек
            message_text = "<b>👥 ВАШ СОСТАВ</b>\n\n"
            
            # Получаем детали для каждой позиции
            positions = [
                ("ГК (Вратарь)", squad['gk_card_id']),
                ("ОП (Защитник)", squad['op_card_id']),
                ("НАП (Нападающий 1)", squad['nap1_card_id']),
                ("НАП (Нападающий 2)", squad['nap2_card_id'])
            ]
            
            for pos_name, card_id in positions:
                if card_id:
                    card_details = get_card_details(card_id)
                    if card_details:
                        rarity_display = 'Эпический' if card_details['rarity'] == 'эпическая' else card_details['rarity']
                        message_text += f"<b>{pos_name}:</b> {card_details['nickname']}\n"
                        message_text += f"  🏟️ {card_details['club']} | 💎 {rarity_display}\n"
                    else:
                        message_text += f"<b>{pos_name}:</b> ❌ Карточка не найдена\n"
                else:
                    message_text += f"<b>{pos_name}:</b> ❌ Не выбрано\n"
                
                message_text += "\n"
            
            message_text += f"<b>🏆 Название состава:</b> {squad.get('squad_name', 'Мой состав')}\n\n"
            message_text += "<i>Вы можете изменить любую позицию в составе</i>"
            
            # Создаем инлайн  клавиатуру для редактирования
            builder = InlineKeyboardBuilder()
            
            # Кнопки для изменения каждой позиции
            builder.row(
                InlineKeyboardButton(
                    text="⚽ Изменить ГК",
                    callback_data="edit_position_gk"
                ),
                InlineKeyboardButton(
                    text="🛡️ Изменить ОП",
                    callback_data="edit_position_op"
                )
            )
            builder.row(
                InlineKeyboardButton(
                    text="🎯 Изменить НАП 1",
                    callback_data="edit_position_nap1"
                ),
                InlineKeyboardButton(
                    text="🎯 Изменить НАП 2",
                    callback_data="edit_position_nap2"
                )
            )
            builder.row(
                InlineKeyboardButton(
                    text="🏆 Изменить название",
                    callback_data="edit_squad_name"
                )
            )
            builder.row(
                InlineKeyboardButton(
                    text="🔄 Обновить",
                    callback_data="sostav"
                ),
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="back_to_play_menu"
                )
            )
            
        else:
            # Состав еще не создан
            message_text = (
                "<b>👥 СОЗДАНИЕ СОСТАВА</b>\n\n"
                "У вас еще нет состава команды!\n\n"
                "<b>📋 Формат состава:</b>\n"
                "• 1 вратарь (ГК)\n"
                "• 1 защитник (ОП)\n"
                "• 2 нападающих (НАП)\n\n"
                "<b>🎯 Требования:</b>\n"
                "• Карточки должны быть из вашей коллекции\n"
                "• Нельзя использовать одну карточку в двух позициях\n"
                "• Можно выбрать только карточки подходящей позиции\n\n"
                "<i>Готовы создать свой состав?</i>"
            )
            
            # Кнопка для создания состава
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(
                    text="🏗️ Создать состав",
                    callback_data="create_squad"
                )
            )
            builder.row(
                InlineKeyboardButton(
                    text="📚 Моя коллекция",
                    callback_data="view_my_cards"
                ),
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="back_to_play_menu"
                )
            )
        await callback.message.edit_text("🚀")
        sleep(3)
        await callback.message.edit_text(
            message_text,
            parse_mode="html",
            reply_markup=builder.as_markup()
        )
        await state.clear()
        await callback.answer()
        from aiogram.exceptions import TelegramBadRequest
    except Exception as e:
        logger.error(f"Ошибка в sostav_message для пользователя {user_id}: {e}")
        await callback.answer("❌ Ошибка при загрузке состава", show_alert=True)
        try:
            await callback.answer(f"❌ Ошибка: {str(e)[:50]}...", show_alert=True)
        except TelegramBadRequest as telegram_error:
            if "query is too old" in str(telegram_error) or "query ID is invalid" in str(telegram_error):
                # Просто логируем, если callback устарел
                print(f"Ignored expired callback: {telegram_error}")
            else:
                # Пробрасываем другие ошибки Telegram
                raise telegram_error
            await state.clear()
@public_router_pvp.callback_query(F.data == "create_squad")
@handle_old_callback
async def create_squad_callback(callback: CallbackQuery, state: FSMContext):
    """Начинает процесс создания состава"""
    await callback.answer()
    user_id = callback.from_user.id
    
    try:
        # Проверяем, есть ли у пользователя карточки
        user_cards = get_user_cards(user_id)
        
        if not user_cards:
            await callback.message.edit_text(
                "<b>❌ НЕТ КАРТОЧЕК</b>\n\n"
                "У вас еще нет карточек для создания состава!\n\n"
                "<b>Как получить карточки:</b>\n"
                "• Используйте команду <code>фмамо</code>\n"
                "• Покупайте карточки в разделе трейдинга\n"
                "• Получайте карточки от других игроков\n\n"
                "<i>Соберите хотя бы 4 карточки для создания состава</i>",
                parse_mode="html",
                reply_markup=InlineKeyboardBuilder()
                .add(InlineKeyboardButton(text="🎮 Получить карточку", callback_data="get_fammo_card"))
                .add(InlineKeyboardButton(text="📚 Моя коллекция", callback_data="view_my_cards"))
                .adjust(2)
                .as_markup()
            )
            return
        
        # Проверяем, есть ли карточки для каждой позиции
        gk_cards = get_user_cards_by_position(user_id, "гк")
        op_cards = get_user_cards_by_position(user_id, "оп")
        nap_cards = get_user_cards_by_position(user_id, "нап")
        
        if not gk_cards:
            await callback.message.edit_text(
                "<b>❌ НЕТ ВРАТАРЕЙ</b>\n\n"
                "У вас нет карточек вратарей (ГК)!\n\n"
                "<b>Требуется:</b>\n"
                "• Минимум 1 вратарь\n\n"
                "<i>Пополните коллекцию карточками вратарей</i>",
                parse_mode="html"
            )
            return
        
        if not op_cards:
            await callback.message.edit_text(
                "<b>❌ НЕТ ЗАЩИТНИКОВ</b>\n\n"
                "У вас нет карточек защитников (ОП)!\n\n"
                "<b>Требуется:</b>\n"
                "• Минимум 1 защитник\n\n"
                "<i>Пополните коллекцию карточками защитников</i>",
                parse_mode="html"
            )
            return
        
        if len(nap_cards) < 2:
            await callback.message.edit_text(
                "<b>❌ МАЛО НАПАДАЮЩИХ</b>\n\n"
                f"У вас только {len(nap_cards)} нападающих!\n\n"
                "<b>Требуется:</b>\n"
                "• Минимум 2 нападающих\n\n"
                "<i>Пополните коллекцию карточками нападающих</i>",
                parse_mode="html"
            )
            return
        
        # Начинаем процесс создания состава
        await state.set_state(SquadStates.selecting_gk)
        await state.update_data({
            "creating_squad": True,
            "current_position": "gk",
            "selected_cards": {}
        })
        
        # Показываем выбор вратаря
        await show_cards_for_next_position(callback, state, "gk")
        
    except Exception as e:
        logger.error(f"Ошибка в create_squad_callback для пользователя {user_id}: {e}")
        await callback.answer("❌ Ошибка при создании состава", show_alert=True)

@public_router_pvp.callback_query(F.data.startswith("edit_position_"))
@handle_old_callback
async def edit_position_callback(callback: CallbackQuery, state: FSMContext):
    """Начинает изменение конкретной позиции в составе"""
    user_id = callback.from_user.id
    position = callback.data.split("_")[2]  # gk, op, nap1, nap2
    
    try:
        # Проверяем, есть ли карточки для этой позиции
        position_map = {
            "gk": "гк",
            "op": "оп",
            "nap1": "нап",
            "nap2": "нап"
        }
        
        position_name = position_map.get(position, "нап")
        available_cards = get_user_cards_by_position(user_id, position_name)
        
        if not available_cards:
            await callback.message.edit_text(
                f"<b>❌ НЕТ ДОСТУПНЫХ КАРТОЧЕК</b>\n\n"
                f"У вас нет карточки для позиции {position_name.upper()}!\n\n"
                "<i>Получите карточки для этой позиции</i>",
                parse_mode="html",
                reply_markup=InlineKeyboardBuilder()
                .add(InlineKeyboardButton(text="⬅️ Назад", callback_data="sostav"))
                .as_markup()
            )
            return
        
        # Получаем текущий состав для проверки уже выбранных карточек
        current_squad = get_user_squad(user_id)
        
        # Фильтруем карточки, исключая уже выбранные (кроме текущей позиции)
        filtered_cards = []
        for card in available_cards:
            card_id = card['id']
            # Проверяем, используется ли карточка в другой позиции
            is_used_in_other_position = False
            if current_squad:
                # Определяем, какая карточка сейчас на этой позиции
                current_card_on_position = current_squad.get(f'{position}_card_id')
                
                # Проверяем все позиции, кроме текущей
                for pos_key, pos_card_id in [
                    ('gk_card_id', current_squad.get('gk_card_id')),
                    ('op_card_id', current_squad.get('op_card_id')),
                    ('nap1_card_id', current_squad.get('nap1_card_id')),
                    ('nap2_card_id', current_squad.get('nap2_card_id'))
                ]:
                    # Если карточка используется в другой позиции
                    if pos_key != f'{position}_card_id' and pos_card_id == card_id:
                        is_used_in_other_position = True
                        break
            
            if not is_used_in_other_position:
                filtered_cards.append(card)
        
        if not filtered_cards:
            await callback.message.edit_text(
                f"<b>❌ НЕТ ДОСТУПНЫХ КАРТОЧЕК</b>\n\n"
                f"Все ваши карточки для позиции {position_name.upper()} "
                f"уже используются в других позициях!\n\n"
                "<i>Освободите карточку из другой позиции или получите новую</i>",
                parse_mode="html",
                reply_markup=InlineKeyboardBuilder()
                .add(InlineKeyboardButton(text="⬅️ Назад к составу", callback_data="sostav"))
                .as_markup()
            )
            return
        
        # ⚠️ ВАЖНО: Переводим пользователя в состояние ожидания ввода ID
        await state.set_state(SquadStates.viewing_cards_for_position)
        await state.update_data({
            "editing_position": position,
            "position_name": position_name,
            "available_cards": filtered_cards,  # Используем отфильтрованные карточки
            "current_page": 0,  # Начинаем с первой страницы
            "current_squad": current_squad  # Сохраняем текущий состав
        })
        
        # Показываем карточки для выбора с пагинацией
        await show_cards_for_selection_paginated(callback, state, 0)
        
    except Exception as e:
        logger.error(f"Ошибка в edit_position_callback для пользователя {user_id}: {e}")
        await callback.answer("❌ Ошибка при изменении позиции", show_alert=True)





async def show_cards_for_selection_paginated(callback: CallbackQuery, state: FSMContext, page: int):
    """Показывает карточки для выбора с пагинацией"""
    try:
        state_data = await state.get_data()
        position = state_data.get("editing_position")
        position_name = state_data.get("position_name")
        available_cards = state_data.get("available_cards", [])
        current_squad = state_data.get("current_squad", {})
        
        position_names = {
            "gk": "Вратарь (ГК)",
            "op": "Защитник (ОП)",
            "nap1": "Нападающий 1 (НАП)",
            "nap2": "Нападающий 2 (НАП)"
        }
        
        position_display = position_names.get(position, "Позиция")
        
        # Настройки пагинации
        CARDS_PER_PAGE = 5  # Количество карточек на странице
        total_cards = len(available_cards)
        total_pages = max(1, (total_cards + CARDS_PER_PAGE - 1) // CARDS_PER_PAGE)  # Округление вверх, минимум 1
        
        # Проверяем корректность номера страницы
        if page < 0:
            page = 0
        elif page >= total_pages:
            page = total_pages - 1
        
        # Получаем карточки для текущей страницы
        start_idx = page * CARDS_PER_PAGE
        end_idx = min(start_idx + CARDS_PER_PAGE, total_cards)
        current_cards = available_cards[start_idx:end_idx]
        
        # Получаем текущую карточку на этой позиции
        current_card_id = None
        if current_squad:
            current_card_id = current_squad.get(f'{position}_card_id')
        
        # Формируем текст сообщения
        message_text = f"<b>🎯 ВЫБОР КАРТОЧКИ: {position_display}</b>\n\n"
        message_text += f"<i>Страница {page + 1} из {total_pages}</i>\n"
        message_text += f"<i>Всего доступных карточек: {total_cards}</i>\n\n"
        
        if not current_cards:
            message_text += "<i>На этой странице нет карточек</i>\n\n"
        else:
            for i, card in enumerate(current_cards, 1):
                card_number = start_idx + i
                rarity_display = 'Эпический' if card['rarity'] == 'эпическая' else card['rarity']
                is_current = " (ТЕКУЩАЯ)" if card['id'] == current_card_id else ""
                
                message_text += (
                    f"<b>{card_number}. {card['nickname']}{is_current}</b>\n"
                    f"   🏟️ {card['club']} | 💎 {rarity_display}\n"
                    f"   🆔 ID: <code>{card['id']}</code>\n\n"
                )
        
        if total_cards == 0:
            message_text += (
                "<b>⚠️ Нет доступных карточек</b>\n\n"
                "Все ваши карточки для этой позиции уже используются "
                "в других позициях состава.\n\n"
                "<i>Освободите карточку из другой позиции или получите новую</i>"
            )
        else:
            message_text += (
                "<b>📝 Как выбрать карточку:</b>\n"
                "Введите <b>ID карточки</b>, которую хотите поставить на эту позицию\n\n"
                "<b>Пример ввода:</b> <code>123</code>\n\n"
                "<i>Или нажмите кнопку 'Отмена' ниже для выхода</i>"  # Изменено
            )
        
        # Создаем кнопки пагинации
        builder = InlineKeyboardBuilder()
        
        # Кнопки навигации (показываем только если больше 1 страницы)
        if total_pages > 1:
            nav_buttons = []
            
            # Кнопка "◀️" если не на первой странице
            if page > 0:
                nav_buttons.append(InlineKeyboardButton(
                    text="◀️",
                    callback_data=f"page_{position}_{page-1}"
                ))
            
            # Информация о текущей странице
            nav_buttons.append(InlineKeyboardButton(
                text=f"{page+1}/{total_pages}",
                callback_data="current_page"
            ))
            
            # Кнопка "▶️" если не на последней странице
            if page < total_pages - 1:
                nav_buttons.append(InlineKeyboardButton(
                    text="▶️",
                    callback_data=f"page_{position}_{page+1}"
                ))
            
            if nav_buttons:
                builder.row(*nav_buttons)
        
        # Кнопка отмены
        builder.row(
            InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="cancel_card_selection"
            )
        )
        
        # Кнопка для быстрого просмотра текущего состава
        builder.row(
            InlineKeyboardButton(
                text="👥 Посмотреть текущий состав",
                callback_data="sostav"
            )
        )
        
        # Обновляем текущую страницу в состоянии
        await state.update_data({"current_page": page})
        
        # Отправляем или редактируем сообщение
        try:
            if hasattr(callback.message, 'edit_text'):
                await callback.message.edit_text(
                    message_text,
                    parse_mode="html",
                    reply_markup=builder.as_markup()
                )
            else:
                # Если это новое сообщение
                await callback.message.answer(
                    message_text,
                    parse_mode="html",
                    reply_markup=builder.as_markup()
                )
        except Exception as e:
            # Если сообщение нельзя отредактировать
            try:
                await callback.message.delete()
            except:
                pass
            
            await callback.message.answer(
                message_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в show_cards_for_selection_paginated: {e}")
        await callback.answer("❌ Ошибка при загрузке карточек", show_alert=True)

@public_router_pvp.callback_query(F.data == "cancel_card_selection")
@handle_old_callback
async def cancel_card_selection_callback(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает отмену выбора карточки"""
    try:
        await state.clear()
        await callback.message.edit_text(
            "❌ Выбор карточки отменен",
            parse_mode="html",
            reply_markup=InlineKeyboardBuilder()
            .add(InlineKeyboardButton(text="👥 Вернуться к составу", callback_data="sostav"))
            .as_markup()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при отмене выбора карточки: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@public_router_pvp.callback_query(F.data.startswith("page_"))
@handle_old_callback
async def handle_pagination_callback(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает навигацию по страницам"""
    try:
        # Разбираем callback_data: page_gk_2 или page_op_0
        parts = callback.data.split("_")
        if len(parts) >= 3:
            position = parts[1]  # gk, op, nap1, nap2
            page = int(parts[2])  # номер страницы
            
            # Обновляем текущую страницу в состоянии
            await state.update_data({"current_page": page})
            
            # Показываем карточки для выбранной страницы
            await show_cards_for_selection_paginated(callback, state, page)
        else:
            await callback.answer("❌ Ошибка пагинации", show_alert=True)
            
    except Exception as e:
        logger.error(f"Ошибка в handle_pagination_callback: {e}")
        await callback.answer("❌ Ошибка при переключении страницы", show_alert=True)

@public_router_pvp.callback_query(F.data == "current_page")
@handle_old_callback
async def current_page_callback(callback: CallbackQuery):
    """Обрабатывает нажатие на кнопку текущей страницы (информационная)"""
    await callback.answer("Вы на этой странице", show_alert=False)

async def handle_create_squad_selection(message: Message, state: FSMContext):
    """Обрабатывает выбор карточки при создании нового состава"""
    user_id = message.from_user.id
    
    try:
        state_data = await state.get_data()
        current_position = state_data.get("current_position")  # gk, op, nap1, nap2
        selected_cards = state_data.get("selected_cards", {})
        available_cards = state_data.get("available_cards", [])
        
        if not available_cards:
            await message.reply(
                "❌ Список карточек не найден. Попробуйте заново.",
                parse_mode="html"
            )
            await state.clear()
            return
        
        # Проверяем отмену
        user_input = message.text.strip().lower()
        if user_input in ["отмена", "cancel", "назад", "отменить"]:
            await state.clear()
            await message.reply(
                "❌ Создание состава отменено",
                parse_mode="html",
                reply_markup=InlineKeyboardBuilder()
                .add(InlineKeyboardButton(text="👥 Вернуться к меню", callback_data="sostav"))
                .as_markup()
            )
            return
        
        # Проверяем, что введен ID
        try:
            selected_id = int(user_input)
        except ValueError:
            # Показываем доступные карточки
            cards_list = ""
            for i, card in enumerate(available_cards[:10], 1):
                rarity_display = 'Эпический' if card['rarity'].lower() in ['эпический', 'эпическая', 'эпик'] else card['rarity']
                cards_list += f"{i}. <b>{card['nickname']}</b> - ID: <code>{card['id']}</code> ({rarity_display})\n"
            
            await message.reply(
                f"❌ <b>Неверный формат!</b>\n\n"
                f"Введите числовой ID карточки.\n\n"
                f"<b>Доступные карточки:</b>\n{cards_list}\n"
                f"<i>Введите ID или 'отмена'</i>",
                parse_mode="html"
            )
            return
        
        # Ищем карточку
        selected_card = None
        for card in available_cards:
            if card['id'] == selected_id:
                selected_card = card
                break
        
        if not selected_card:
            await message.reply(
                f"❌ Карточка с ID {selected_id} не найдена!",
                parse_mode="html"
            )
            return
        
        # Проверяем, подходит ли карточка для позиции
        position_keywords = {
            "gk": ["гк", "вратарь"],
            "op": ["оп", "защитник"],
            "nap1": ["нап", "нападающий"],
            "nap2": ["нап", "нападающий"]
        }
        
        keywords = position_keywords.get(current_position, ["нап"])
        card_position_lower = selected_card['position'].lower() if selected_card['position'] else ""
        position_valid = any(keyword in card_position_lower for keyword in keywords)
        
        if not position_valid:
            await message.reply(
                f"❌ <b>Неверная позиция!</b>\n\n"
                f"Карточка '{selected_card['nickname']}' имеет позицию: {selected_card['position']}\n"
                f"Для этой позиции нужны: {', '.join(keywords)}",
                parse_mode="html"
            )
            return
        
        # Проверяем, не выбрана ли уже эта карточка
        if selected_id in selected_cards.values():
            # Находим, в какой позиции уже выбрана
            for pos, card_id in selected_cards.items():
                if card_id == selected_id:
                    pos_names = {"gk": "ГК", "op": "ОП", "nap1": "НАП1", "nap2": "НАП2"}
                    await message.reply(
                        f"❌ Эта карточка уже выбрана для позиции {pos_names.get(pos, pos)}!",
                        parse_mode="html"
                    )
                    return
        
        # Сохраняем выбор
        selected_cards[current_position] = selected_id
        await state.update_data({"selected_cards": selected_cards})
        
        # Определяем следующую позицию
        next_position = None
        if current_position == "gk":
            next_position = "op"
        elif current_position == "op":
            next_position = "nap1"
        elif current_position == "nap1":
            next_position = "nap2"
        
        if next_position:
            # Переходим к следующей позиции
            await state.update_data({"current_position": next_position})
            
            # Получаем карточки пользователя для следующей позиции
            user_id = message.from_user.id
            user_cards_result = get_user_cards(user_id)
            
            if not user_cards_result:
                await message.reply(
                    "❌ У вас нет карточек для следующей позиции!",
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
            selected_ids = set(selected_cards.values())
            
            available_cards_next = []
            for card in position_cards:
                if card['id'] not in selected_ids:
                    available_cards_next.append(card)
            
            if not available_cards_next:
                await message.reply(
                    f"❌ Нет доступных карточек для позиции {next_position.upper()}!\n"
                    f"Все карточки уже выбраны для других позиций.",
                    parse_mode="html"
                )
                return
            
            # Сохраняем доступные карточки
            await state.update_data({
                "available_cards": available_cards_next,
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
                f"<i>Доступно карточек: {len(available_cards_next)}</i>\n\n"
            )
            
            # Показываем первые 5 карточек
            for i, card in enumerate(available_cards_next[:5], 1):
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
            
            await message.reply(
                message_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
            
        else:
            # Все позиции выбраны, сохраняем состав
            success, result_msg = save_user_squad(
                user_id=user_id,
                gk_card_id=selected_cards.get("gk"),
                op_card_id=selected_cards.get("op"),
                nap1_card_id=selected_cards.get("nap1"),
                nap2_card_id=selected_cards.get("nap2"),
                squad_name="Мой состав"
            )
            
            if success:
                response_text = (
                    "✅ <b>СОСТАВ УСПЕШНО СОЗДАН!</b>\n\n"
                    "<b>Ваш состав:</b>\n"
                )
                
                # Показываем все выбранные карточки
                for pos_key, card_id in selected_cards.items():
                    pos_names = {"gk": "ГК", "op": "ОП", "nap1": "НАП1", "nap2": "НАП2"}
                    card = get_card_by_id(card_id)
                    if card:
                        rarity_display = 'Эпический' if card['rarity'].lower() in ['эпический', 'эпическая', 'эпик'] else card['rarity']
                        response_text += f"• <b>{pos_names.get(pos_key)}:</b> {card['nickname']} ({rarity_display})\n"
                
                response_text += "\n<i>Теперь вы можете участвовать в матчах!</i>"
                
                builder = InlineKeyboardBuilder()
                builder.row(
                    InlineKeyboardButton(text="👥 Посмотреть состав", callback_data="sostav")
                )
                builder.row(
                    InlineKeyboardButton(text="⚽ Играть", callback_data="play_match"),
                    InlineKeyboardButton(text="📊 Статистика", callback_data="statistics")
                )
                builder.row(
    InlineKeyboardButton(
        text="❌ Отменить создание",
        callback_data="cancel_squad_creation"
    )
)
                await message.reply(
                    response_text,
                    parse_mode="html",
                    reply_markup=builder.as_markup()
                )
            else:
                await message.reply(
                    f"❌ <b>Ошибка при создании состава!</b>\n\n{result_msg}",
                    parse_mode="html",
                    reply_markup=InlineKeyboardBuilder()
                    .add(InlineKeyboardButton(text="👥 Вернуться", callback_data="sostav"))
                    .as_markup()
                )
            
            await state.clear()
            
    except Exception as e:
        logger.error(f"Ошибка в handle_create_squad_selection: {e}")
        import traceback
        logger.error(f"Трейсбэк: {traceback.format_exc()}")
        
        await message.reply(
            "❌ Произошла ошибка при создании состава",
            parse_mode="html"
        )
        await state.clear()
@public_router_pvp.callback_query(F.data == "cancel_squad_creation")
@handle_old_callback
async def cancel_squad_creation_callback(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает отмену создания состава"""
    try:
        await state.clear()
        await callback.message.edit_text(
            "❌ Создание состава отменено",
            parse_mode="html",
            reply_markup=InlineKeyboardBuilder()
            .add(InlineKeyboardButton(text="👥 Вернуться к меню", callback_data="sostav"))
            .as_markup()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при отмене создания состава: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)
@public_router_pvp.message(F.text, SquadStates.selecting_gk)
@public_router_pvp.message(F.text, SquadStates.selecting_op)
@public_router_pvp.message(F.text, SquadStates.selecting_nap1)
@public_router_pvp.message(F.text, SquadStates.selecting_nap2)
async def process_card_selection_during_creation(message: Message, state: FSMContext):
    """Обрабатывает выбор карточки при создании нового состава"""
    await handle_create_squad_selection(message, state)


@public_router_pvp.message(F.text, SquadStates.viewing_cards_for_position)
async def process_card_selection_by_id(message: Message, state: FSMContext):
    """Обрабатывает выбор карточки для позиции по ID"""
    user_id = message.from_user.id
    
    try:
        # Получаем данные из состояния
        state_data = await state.get_data()
        
        # Проверяем, создаем ли мы новый состав или редактируем существующий
        is_creating = state_data.get("creating_squad", False)
        
        if is_creating:
            # Обработка для создания нового состава
            await handle_create_squad_selection(message, state)
            return
        
        # Обработка для редактирования существующего состава
        position = state_data.get("editing_position")  # gk, op, nap1, nap2
        available_cards = state_data.get("available_cards", [])
        current_squad = state_data.get("current_squad", {})
        
        if not available_cards:
            await message.reply(
                "❌ <b>ОШИБКА!</b>\n\n"
                "Список доступных карточек не найден. Попробуйте заново.",
                parse_mode="html"
            )
            await state.clear()
            return
        
        # Проверяем, не хочет ли пользователь отменить
        user_input = message.text.strip().lower()
        if user_input in ["отмена", "cancel", "назад", "отменить"]:
            await state.clear()
            await message.reply(
                "❌ Выбор карточки отменен",
                parse_mode="html",
                reply_markup=InlineKeyboardBuilder()
                .add(InlineKeyboardButton(text="👥 Вернуться к составу", callback_data="sostav"))
                .as_markup()
            )
            return
        
        # Проверяем, что пользователь ввел число (ID карточки)
        try:
            selected_id = int(user_input)
        except ValueError:
            # Показываем доступные карточки
            cards_list = ""
            for i, card in enumerate(available_cards[:10], 1):
                rarity_display = 'Эпический' if card['rarity'].lower() in ['эпический', 'эпическая', 'эпик'] else card['rarity']
                cards_list += f"{i}. <b>{card['nickname']}</b> - ID: <code>{card['id']}</code> ({rarity_display})\n"
            
            await message.reply(
                f"❌ <b>Неверный формат!</b>\n\n"
                f"Пожалуйста, введите числовой ID карточки.\n\n"
                f"<b>Пример ввода:</b> <code>123</code>\n\n"
                f"<b>Доступные карточки:</b>\n{cards_list}\n"
                f"<i>Введите ID карточки или 'отмена' для выхода</i>",
                parse_mode="html"
            )
            return
        
        # Ищем карточку с таким ID в доступных карточках
        selected_card = None
        for card in available_cards:
            if card['id'] == selected_id:
                selected_card = card
                break
        
        if not selected_card:
            # Показываем доступные карточки
            cards_list = ""
            for i, card in enumerate(available_cards[:10], 1):
                rarity_display = 'Эпический' if card['rarity'].lower() in ['эпический', 'эпическая', 'эпик'] else card['rarity']
                cards_list += f"{i}. <b>{card['nickname']}</b> - ID: <code>{card['id']}</code> ({rarity_display})\n"
            
            await message.reply(
                f"❌ <b>Карточка с ID {selected_id} не найдена!</b>\n\n"
                f"<b>Доступные карточки:</b>\n{cards_list}\n"
                f"<i>Введите правильный ID из списка выше или 'отмена' для выхода</i>",
                parse_mode="html"
            )
            return
        
        # Получаем текущий состав из базы данных (на всякий случай)
        squad_from_db = get_user_squad(user_id)
        if not squad_from_db:
            await message.reply(
                "❌ <b>Состав не найден!</b>\n\n"
                "Сначала создайте состав.",
                parse_mode="html",
                reply_markup=InlineKeyboardBuilder()
                .add(InlineKeyboardButton(text="🏗️ Создать состав", callback_data="create_squad"))
                .as_markup()
            )
            await state.clear()
            return
        
        # Проверяем, не используется ли карточка в других позициях
        card_already_used = False
        used_position_name = None
        
        # Определяем текущую карточку на редактируемой позиции
        position_key = f"{position}_card_id"
        current_card_on_this_position = squad_from_db.get(position_key)
        
        # Проверяем все позиции
        squad_positions = {
            'gk_card_id': 'Вратарь (ГК)',
            'op_card_id': 'Защитник (ОП)', 
            'nap1_card_id': 'Нападающий 1 (НАП)',
            'nap2_card_id': 'Нападающий 2 (НАП)'
        }
        
        for pos_key, pos_name in squad_positions.items():
            card_id = squad_from_db.get(pos_key)
            if card_id == selected_id:
                # Если это не текущая позиция, то карточка уже используется
                if pos_key != position_key:
                    card_already_used = True
                    used_position_name = pos_name
                    break
        
        if card_already_used:
            await message.reply(
                f"❌ <b>Карточка уже используется!</b>\n\n"
                f"Карточка <b>{selected_card['nickname']}</b> уже используется в позиции <b>{used_position_name}</b>.\n\n"
                "<i>Освободите карточку из другой позиции или выберите другую</i>",
                parse_mode="html"
            )
            return
        
        # Обновляем состав
        update_data = {
            'gk_card_id': squad_from_db.get('gk_card_id'),
            'op_card_id': squad_from_db.get('op_card_id'),
            'nap1_card_id': squad_from_db.get('nap1_card_id'),
            'nap2_card_id': squad_from_db.get('nap2_card_id'),
            'squad_name': squad_from_db.get('squad_name', 'Мой состав')
        }
        
        # Устанавливаем новую карточку для выбранной позиции
        update_data[position_key] = selected_id
        
        # Сохраняем изменения
        success, result_msg = save_user_squad(
            user_id=user_id,
            gk_card_id=update_data['gk_card_id'],
            op_card_id=update_data['op_card_id'],
            nap1_card_id=update_data['nap1_card_id'],
            nap2_card_id=update_data['nap2_card_id'],
            squad_name=update_data['squad_name']
        )
        
        if success:
            # Показываем результат
            position_names = {
                "gk": "Вратарь (ГК)",
                "op": "Защитник (ОП)", 
                "nap1": "Нападающий 1 (НАП)",
                "nap2": "Нападающий 2 (НАП)"
            }
            
            position_display = position_names.get(position, position)
            rarity_display = 'Эпический' if selected_card['rarity'].lower() in ['эпический', 'эпическая', 'эпик'] else selected_card['rarity']
            
            # Формируем красивый ответ
            response_text = (
                f"✅ <b>ПОЗИЦИЯ ОБНОВЛЕНА!</b>\n\n"
                f"<b>Позиция:</b> {position_display}\n"
                f"<b>Игрок:</b> {selected_card['nickname']}\n"
                f"<b>Клуб:</b> {selected_card['club']}\n"
                f"<b>Редкость:</b> {rarity_display}\n\n"
                "<i>Состав успешно обновлен!</i>"
            )
            
            # Создаем клавиатуру
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(
                    text="👥 Посмотреть состав",
                    callback_data="sostav"
                )
            )
            builder.row(
                InlineKeyboardButton(
                    text="⚽ Играть",
                    callback_data="play_match"
                ),
                InlineKeyboardButton(
                    text="✏️ Изменить другую позицию",
                    callback_data="sostav"
                )
            )
            
            await message.reply(
                response_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
        else:
            await message.reply(
                f"❌ <b>ОШИБКА ПРИ СОХРАНЕНИИ!</b>\n\n{result_msg}",
                parse_mode="html",
                reply_markup=InlineKeyboardBuilder()
                .add(InlineKeyboardButton(text="👥 Вернуться к составу", callback_data="sostav"))
                .as_markup()
            )
        
        # Очищаем состояние
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка в process_card_selection_by_id для пользователя {user_id}: {e}")
        import traceback
        logger.error(f"Трейсбэк: {traceback.format_exc()}")
        
        await message.reply(
            "❌ <b>Произошла критическая ошибка!</b>\n\n"
            "Пожалуйста, попробуйте еще раз или обратитесь к администратору.",
            parse_mode="html",
            reply_markup=InlineKeyboardBuilder()
            .add(InlineKeyboardButton(text="👥 Вернуться к составу", callback_data="sostav"))
            .as_markup()
        )
        await state.clear()

@public_router_pvp.callback_query(F.data == "edit_squad_name")
@handle_old_callback
async def edit_squad_name_callback(callback: CallbackQuery, state: FSMContext):
    """Начинает изменение названия состава"""
    user_id = callback.from_user.id
    
    try:
        # Получаем текущий состав
        squad = get_user_squad(user_id)
        
        if not squad:
            await callback.answer("❌ Состав не найден", show_alert=True)
            return
        
        await state.set_state(SquadStates.editing_squad)
        await state.update_data({
            "editing_field": "name",
            "current_name": squad.get('squad_name', 'Мой состав')
        })
        
        await callback.message.edit_text(
            f"🏆 <b>ИЗМЕНЕНИЕ НАЗВАНИЯ СОСТАВА</b>\n\n"
            f"<b>Текущее название:</b> {squad.get('squad_name', 'Мой состав')}\n\n"
            "📝 <b>Введите новое название:</b>\n\n"
            "<i>Максимум 30 символов</i>\n\n"
            "<b>Пример:</b> <code>Моя мечтательная команда</code>\n\n"
            "<i>Для отмены нажмите кнопку ниже</i>",
            parse_mode="html",
            reply_markup=InlineKeyboardBuilder()
            .add(InlineKeyboardButton(text="❌ Отмена", callback_data="sostav"))
            .as_markup()
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в edit_squad_name_callback для пользователя {user_id}: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@public_router_pvp.message(F.text, SquadStates.editing_squad)
async def process_squad_name(message: Message, state: FSMContext):
    """Обрабатывает изменение названия состава"""
    user_id = message.from_user.id
    
    try:
        state_data = await state.get_data()
        editing_field = state_data.get("editing_field")
        
        if editing_field == "name":
            new_name = message.text.strip()
            
            # Проверяем длину названия
            if len(new_name) > 30:
                await message.reply(
                    "❌ <b>Слишком длинное название!</b>\n\n"
                    "Максимальная длина: 30 символов\n"
                    f"Ваше название: {len(new_name)} символов",
                    parse_mode="html"
                )
                return
            
            # Получаем текущий состав
            squad = get_user_squad(user_id)
            
            if not squad:
                await message.reply("❌ Состав не найден", parse_mode="html")
                await state.clear()
                return
            
            # Обновляем название
            success, result_msg = save_user_squad(
                user_id=user_id,
                gk_card_id=squad.get('gk_card_id'),
                op_card_id=squad.get('op_card_id'),
                nap1_card_id=squad.get('nap1_card_id'),
                nap2_card_id=squad.get('nap2_card_id'),
                squad_name=new_name
            )
            
            if success:
                await message.reply(
                    f"✅ <b>НАЗВАНИЕ ИЗМЕНЕНО!</b>\n\n"
                    f"<b>Новое название:</b> {new_name}\n\n"
                    "<i>Состав успешно обновлен</i>",
                    parse_mode="html",
                    reply_markup=InlineKeyboardBuilder()
                    .add(InlineKeyboardButton(text="👥 Посмотреть состав", callback_data="sostav"))
                    .as_markup()
                )
            else:
                await message.reply(
                    f"❌ <b>ОШИБКА!</b>\n\n{result_msg}",
                    parse_mode="html"
                )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка в process_squad_name для пользователя {user_id}: {e}")
        await message.reply("❌ Произошла ошибка", parse_mode="html")
        await state.clear()


@public_router_pvp.callback_query(F.data.startswith("position_page_"))
@handle_old_callback
async def handle_position_pagination(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает пагинацию при выборе позиции"""
    try:
        # Разбираем callback_data: position_page_gk_2
        parts = callback.data.split("_")
        if len(parts) >= 4:
            position = parts[2]  # gk, op, nap1, nap2
            page = int(parts[3])  # номер страницы
            
            # Показываем карточки для выбранной страницы
            await show_cards_for_next_position(callback, state, position, page)
        else:
            await callback.answer("❌ Ошибка пагинации", show_alert=True)
            
    except Exception as e:
        logger.error(f"Ошибка в handle_position_pagination: {e}")
        await callback.answer("❌ Ошибка при переключении страницы", show_alert=True)

@public_router_pvp.callback_query(F.data == "page_info")
@handle_old_callback
async def page_info_callback(callback: CallbackQuery):
    """Обрабатывает нажатие на кнопку информации о странице"""
    await callback.answer("Информация о текущей странице", show_alert=False)



@public_router_pvp.callback_query(F.data == "back_to_play_menu")
@handle_old_callback
async def back_to_play_menu_callback(callback: CallbackQuery):
    """Возврат к игровому меню"""
    await callback.message.edit_text(
        "<b>🎮 Игровое меню:</b>",
        reply_markup=main_play,
        parse_mode="html"
    )
    await callback.answer()

format_match = InlineKeyboardMarkup(inline_keyboard=
                                    [
                                        [InlineKeyboardButton(text="🤖 Против бота", callback_data="withbot")],
                                        [InlineKeyboardButton(text="⚽ Против игрока", callback_data="withplayer")],
                                        [InlineKeyboardButton(text="⬅️", callback_data="nzd_pvp")]
                                    ])


@public_router_pvp.callback_query(F.data == "nzd_pvp")
@handle_old_callback
async def play_match_message(callback: CallbackQuery):
    await callback.message.edit_text("<b>🎮 Игровое меню:</b>", reply_markup=main_play, parse_mode="html")

@public_router_pvp.callback_query(F.data == "play_match")
@handle_old_callback
async def play_match_message(callback: CallbackQuery):
    await callback.message.edit_text("Выбери формат матча:", reply_markup=format_match)


# В начало файла mamopvp.py добавить импорты
import random
from datetime import datetime

# После создания public_router_pvp добавить:
class MatchStates(StatesGroup):
    confirming_match = State()  # Подтверждение готовности к матчу
    playing_match = State() 

# После основного роутера добавить эти классы
class MatchResult:
    def __init__(self, user_id: int, opponent_type: str, result: str, elo_change: int):
        self.user_id = user_id
        self.opponent_type = opponent_type
        self.result = result  # 'win', 'lose', 'draw'
        self.elo_change = elo_change
        self.timestamp = datetime.now()

class BotMatchSimulator:
    def __init__(self, user_squad, bot_squad=None):
        self.user_squad = user_squad
        self.bot_squad = bot_squad or self.generate_bot_squad()
        self.user_score = 0
        self.bot_score = 0
        self.minute = 0
        self.match_duration = 30  # 30 секунд матч
        self.match_events = []
        self.user_goals = []
        self.bot_goals = []
        self.current_tactic = 'balance'  # Текущая тактика
        
        # Расширенный список случайных событий со 100% шансом
        self.match_actions = [
            # Атаки
            "⚽ Атака через центр!", "🔀 Контратака!", "⚡ Быстрая атака по флангу",
            "🎯 Опасный момент у ворот!", "🚀 Дальний удар!", "🤹 Обводка защитников!",
            "👟 Прострел с фланга", "🎪 Комбинация в центре поля", "🔄 Смена атаки",
            "🎯 Точечный пас в штрафную", "⚡ Вертикальная атака", "👟 Навес на дальнюю штангу",
            
            # Защита
            "🛡️ Команда защищается...", "🧤 Вратарь в игре!", "🧱 Стена из игроков",
            "❌ Перехват мяча!", "🛡️ Блок удара!", "🧤 Вратарь парирует удар!",
            "🛡️ Отбор в подкате!", "🧱 Плотная оборона", "❌ Опасность отбита!",
            
            # Борьба за мяч
            "🎪 Игроки борются за мяч", "🤼 Борьба в воздухе", "🎪 Двусторонняя борьба",
            "🤼 Силовой прием", "🎪 Прессинг в центре поля",
            
            # Тактические моменты
            "🧠 Тактическая перестройка", "🔄 Замена позиций", "🎯 Ставка на контратаки",
            "🛡️ Компактная оборона", "⚡ Игра в высоком темпе", "🎯 Контроль темпа игры",
            
            # События без мяча
            "🔄 Смена владения", "🎪 Перепасовка в обороне", "⚡ Ускорение темпа",
            "🎯 Поиск свободной зоны", "🔄 Тактическая пауза",
            
            # Особые моменты
            "⚠️ Офсайд!", "🎯 Штанга! Мяч отскакивает от перекладины!", "🧤 Сейв вратаря!",
            "⚠️ Спорный момент...", "🎯 Мяч чуть выше ворот!", "❌ Блокировка удара рукой",
            
            # Командные взаимодействия
            "🤝 Связка игроков", "🎯 Голевая комбинация", "🔄 Кросс в штрафную",
            "🤹 Индивидуальный проход", "🎯 Прострел вдоль ворот",
            
            # Полевые моменты
            "🎪 Игра в центре поля", "⚡ Атака правым флангом", "⚡ Атака левым флангом",
            "🎯 Построение атаки", "🛡️ Организация обороны",
            
            # Случайные события
            "💨 Сильный ветер влияет на траекторию", "🌧️ Мокрое поле замедляет игру",
            "🎯 Игрок поскользнулся в решающий момент", "⚠️ Спорный фол...",
            "🎪 Накал страстей на поле", "👏 Болельщики поддерживают команду",
            
            # Голевые моменты
            "🎯 Опасная подача с углового!", "⚡ Прорыв один-на-один!",
            "🎯 Свободный удар у ворот!", "🤹 Обманное движение в штрафной",
            "🎯 Прострел на дальнюю штангу", "⚡ Скоростной дриблинг",
        ]
    
    def set_tactic(self, tactic: str):
        """Устанавливает тактику игры"""
        if tactic in ['attack', 'defense', 'balance']:
            self.current_tactic = tactic
    
    def get_progress_bar(self, current, total, length=20):
        """Создает прогресс-бар для отображения времени матча"""
        filled = int(length * current / total)
        bar = "🟩" * filled + "⬜" * (length - filled)
        percentage = int(100 * current / total)
        return f"{bar} {percentage}%"
    
    def get_random_action(self):
        """Возвращает случайное событие из списка (теперь 100% шанс)"""
        return random.choice(self.match_actions)
    
    def generate_bot_squad(self):
        """Генерирует случайный состав для бота"""
        bot_cards = []
        positions = ['гк', 'оп', 'нап', 'нап']
        
        for position in positions:
            result = db_operation(
                """SELECT id, nickname, club, position, rarity 
                FROM players_catalog 
                WHERE LOWER(position) LIKE ? 
                ORDER BY RANDOM() LIMIT 1""",
                (f"%{position}%",),
                fetch=True
            )
            
            if result:
                card_id, nickname, club, position, rarity = result[0]
                bot_cards.append({
                    'id': card_id,
                    'nickname': nickname,
                    'club': club,
                    'position': position,
                    'rarity': rarity
                })
        
        return {
            'gk': bot_cards[0] if len(bot_cards) > 0 else None,
            'op': bot_cards[1] if len(bot_cards) > 1 else None,
            'nap1': bot_cards[2] if len(bot_cards) > 2 else None,
            'nap2': bot_cards[3] if len(bot_cards) > 3 else None,
            'squad_name': 'MamoTinder Bot'  # Важно: добавляем название команды
        }
    
    def calculate_coefficient(self, squad):
        """Рассчитывает коэффициент силы состава. "уник" карточки имеют свою ценность."""
        # Добавляем значение для "уник"
        rarity_values = {
            'суперлегендарный': 4,
            'легендарный': 3,
            'эпический': 2,
            'редкий': 1,
            'eea': 5,
            'уник': 2.5  # <--- ДОБАВЛЯЕМ ЗНАЧЕНИЕ ДЛЯ "УНИК". Поставим между эпиком и легендой.
                         # Вы можете изменить это число на свое усмотрение.
        }

        total_coeff = 0
        cards = []

        # Получаем карточки из squad (как было раньше)
        if isinstance(squad, dict):
            cards = [squad.get('gk'), squad.get('op'), squad.get('nap1'), squad.get('nap2')]
        else:
            cards = [squad.gk, squad.op, squad.nap1, squad.nap2]

        for card in cards:
            if card and isinstance(card, dict) and card.get('rarity'):
                # Приводим к нижнему регистру для надежности
                rarity = card['rarity'].lower()
                if rarity in rarity_values:
                    total_coeff += rarity_values[rarity]
                else:
                    # Если редкость неизвестна (например, "эпическая" мы уже обработали выше),
                    # можно дать какое-то значение по умолчанию или пропустить.
                    # Пропустим, чтобы не искажать статистику.
                    logger.debug(f"Неизвестная редкость для расчета коэффициента: {rarity}")
            # else: карточки нет на позиции или она в другом формате

        # Возвращаем средний коэффициент (если есть хотя бы одна карточка)
        return total_coeff / 4 if cards and total_coeff > 0 else 1
    
    def calculate_goal_chance(self):
        """Рассчитывает шанс забить гол"""
        user_coeff = self.calculate_coefficient(self.user_squad)
        bot_coeff = self.calculate_coefficient(self.bot_squad)
        
        base_chance = 0.10  # Базовый шанс 10%
        user_bonus = (user_coeff - bot_coeff) * 0.05
        
        user_chance = max(0.05, min(0.95, base_chance + user_bonus))
        bot_chance = max(0.05, min(0.95, base_chance - user_bonus))
        
        return user_chance, bot_chance
    
    def apply_tactic_effects(self, user_chance, bot_chance):
        """Применяет эффекты текущей тактики к шансам"""
        if self.current_tactic == "attack":
            # Все в атаку: +15% забить, +30% пропустить
            user_chance = min(0.95, user_chance * 1.15)
            bot_chance = min(0.95, bot_chance * 1.30)
        elif self.current_tactic == "defense":
            # Все в защиту: -50% забить, -15% пропустить
            user_chance = max(0.05, user_chance * 0.50)
            bot_chance = max(0.05, bot_chance * 0.85)
        # tactic == "balance" - оставляем как есть
        
        return user_chance, bot_chance
    
    def _get_random_player_for_goal(self, squad, side):
        """Получает случайного игрока для гола с учетом шансов позиций"""
        players = []
        position_weights = []
        
        # Определяем название команды
        team_name = "Неизвестная команда"
        
        if side == "user":
            # Для текущего пользователя
            if isinstance(squad, dict):
                if 'squad_name' in squad:
                    team_name = squad.get('squad_name', 'Ваша команда')
                elif 'squad_name' in self.user_squad:
                    team_name = self.user_squad.get('squad_name', 'Ваша команда')
            else:
                team_name = "Ваша команда"
        else:
            # Для противника
            if hasattr(self, 'is_pvp') and self.is_pvp:
                # Это PvP режим - противник это другой игрок
                if isinstance(self.bot_squad, dict):
                    if 'squad_name' in self.bot_squad:
                        team_name = self.bot_squad.get('squad_name', 'Команда соперника')
                    else:
                        team_name = "Команда соперника"
            else:
                # Это бот
                team_name = "MamoTinder Bot"
        
        try:
            # Проверяем структуру squad
            if isinstance(squad, dict):
                # Формат 1: squad = {'gk': {...}, 'op': {...}, 'nap1': {...}, 'nap2': {...}, 'squad_name': '...'}
                if squad.get('gk') and isinstance(squad.get('gk'), dict):
                    # Это PvP формат или формат ботового состава
                    positions = [
                        ('nap1', squad.get('nap1'), 0.35),
                        ('nap2', squad.get('nap2'), 0.35),
                        ('op', squad.get('op'), 0.20),
                        ('gk', squad.get('gk'), 0.10)
                    ]
                    
                    for pos_name, card_data, weight in positions:
                        if card_data and isinstance(card_data, dict):
                            # Карточка уже в виде словаря с деталями
                            player_name = card_data.get('nickname')
                            if not player_name:
                                # Если нет nickname, попробуем другие поля
                                player_name = card_data.get('name') or card_data.get('player_name') or f"Игрок {pos_name}"
                            
                            players.append({
                                'name': player_name,
                                'team': team_name
                            })
                            position_weights.append(weight)
                
                # Формат 2: squad = {'gk_card_id': 123, 'op_card_id': 456, ... 'squad_name': '...'}
                elif squad.get('gk_card_id') or squad.get('op_card_id'):
                    # Это формат из базы данных
                    positions = [
                        ('nap1', squad.get('nap1_card_id'), 0.35),
                        ('nap2', squad.get('nap2_card_id'), 0.35),
                        ('op', squad.get('op_card_id'), 0.20),
                        ('gk', squad.get('gk_card_id'), 0.10)
                    ]
                    
                    for pos_name, card_id, weight in positions:
                        if card_id:
                            try:
                                card_details = get_card_details(card_id)
                                if card_details:
                                    players.append({
                                        'name': card_details.get('nickname', f'Игрок {pos_name}'),
                                        'team': team_name
                                    })
                                    position_weights.append(weight)
                            except Exception as e:
                                logger.error(f"Ошибка при получении карточки {card_id}: {e}")
                
                # Формат 3: squad = {'cards': [...]} (резервный формат)
                elif squad.get('cards') and isinstance(squad.get('cards'), list):
                    for card in squad['cards']:
                        if isinstance(card, dict):
                            player_name = card.get('nickname') or card.get('name') or f"Игрок {card.get('position', '')}"
                            players.append({
                                'name': player_name,
                                'team': team_name
                            })
                            position_weights.append(0.25)  # Равные шансы для всех карточек
            
            # Если после всех проверок игроки не найдены, создаем резервных
            if not players:
                # В PvP режиме используем разные имена для команд
                if hasattr(self, 'is_pvp') and self.is_pvp:
                    # Для команды соперника в PvP
                    if side == "bot":
                        bot_names = [
                            "Игрок соперника 1", "Игрок соперника 2", "Игрок соперника 3", "Игрок соперника 4"
                        ]
                    else:
                        # Для команды пользователя
                        bot_names = [
                            "Ваш игрок 1", "Ваш игрок 2", "Ваш игрок 3", "Ваш игрок 4"
                        ]
                else:
                    # Против бота
                    if "бот" in team_name.lower() or "mamo" in team_name.lower():
                        bot_names = [
                            "Ronaldo", "Messi", "Neymar", "Mbappé", "Haaland", "Benzema", 
                            "Lewandowski", "Kane", "Salah", "De Bruyne", "Modrić", "Kroos",
                            "Courtois", "Van Dijk", "Mané", "Griezmann", "Pogba", "Kante"
                        ]
                    else:
                        bot_names = [
                            "Игрок 1", "Игрок 2", "Игрок 3", "Игрок 4"
                        ]
                
                # Создаем 4 случайных игрока для резервного варианта
                for i in range(4):
                    name = random.choice(bot_names)
                    players.append({
                        'name': name,
                        'team': team_name
                    })
                    position_weights.append(0.25)
        
        except Exception as e:
            logger.error(f"Ошибка в _get_random_player_for_goal: {e}")
            # Резервный вариант при ошибке
            return {'name': "Игрок", 'team': team_name}
        
        # Выбираем случайного игрока с учетом весов
        if players and position_weights:
            try:
                total_weight = sum(position_weights)
                if total_weight > 0:
                    normalized_weights = [w / total_weight for w in position_weights]
                    selected_index = random.choices(range(len(players)), weights=normalized_weights, k=1)[0]
                    return players[selected_index]
            except Exception as e:
                logger.error(f"Ошибка при выборе игрока: {e}")
                return players[0] if players else {'name': "Игрок", 'team': team_name}
        
        # Резервный вариант
        return {'name': "Игрок", 'team': team_name}
    
    def simulate_second(self):
        """Симулирует одну секунду матча"""
        self.minute += 1
        
        # ВСЕГДА получаем случайное событие (100% шанс)
        action = self.get_random_action()
        
        # Проверяем шанс гола
        user_chance, bot_chance = self.calculate_goal_chance()
        
        # Применяем эффекты тактики
        user_chance, bot_chance = self.apply_tactic_effects(user_chance, bot_chance)
        
        current_second = self.minute
        
        # Проверяем гол пользователя
        if random.random() < user_chance:
            goal_info = self._get_random_player_for_goal(self.user_squad, "user")
            self.user_score += 1
            
            # В PvP режиме используем правильные названия команд
            if hasattr(self, 'is_pvp') and self.is_pvp:
                goal_event = f"<b>⚽ ГОООЛ! {goal_info['name']} ({goal_info['team']}) забивает!</b>"
            else:
                goal_event = f"<b>⚽ ГОООЛ! {goal_info['name']} ({goal_info['team']}) забивает!</b>"
            
            goal_data = {
                'name': goal_info['name'],
                'team': goal_info['team'],
                'minute': current_second
            }
            self.user_goals.append(goal_data)
            
            self.match_events.append({
                'minute': current_second,
                'event': goal_event,
                'is_goal': True,
                'scorer': "user",
                'scorer_name': goal_info['name'],
                'team_name': goal_info['team']
            })
            return goal_event

        # Проверяем гол бота/соперника
        elif random.random() < bot_chance:
            goal_info = self._get_random_player_for_goal(self.bot_squad, "bot")
            self.bot_score += 1
            
            # В PvP режиме используем правильные названия команд
            if hasattr(self, 'is_pvp') and self.is_pvp:
                goal_event = f"<b>⚽ ГОООЛ! {goal_info['name']} ({goal_info['team']}) забивает!</b>"
            else:
                goal_event = f"<b>⚽ ГОООЛ! {goal_info['name']} ({goal_info['team']}) забивает!</b>"
            
            goal_data = {
                'name': goal_info['name'],
                'team': goal_info['team'],
                'minute': current_second
            }
            self.bot_goals.append(goal_data)
            
            self.match_events.append({
                'minute': current_second,
                'event': goal_event,
                'is_goal': True,
                'scorer': "bot",
                'scorer_name': goal_info['name'],
                'team_name': goal_info['team']
            })
            return goal_event
        
        # Проверяем гол бота
        elif random.random() < bot_chance:
            goal_info = self._get_random_player_for_goal(self.bot_squad, "bot")
            self.bot_score += 1
            
            goal_event = f"<b>⚽ ГОООЛ! {goal_info['name']} ({goal_info['team']}) забивает!</b>"
            
            goal_data = {
                'name': goal_info['name'],
                'team': goal_info['team'],
                'minute': current_second
            }
            self.bot_goals.append(goal_data)
            
            self.match_events.append({
                'minute': current_second,
                'event': goal_event,
                'is_goal': True,
                'scorer': "bot",
                'scorer_name': goal_info['name'],
                'team_name': goal_info['team']
            })
            return goal_event
        
        # Если гол не забит, возвращаем обычное событие
        self.match_events.append({
            'minute': self.minute,
            'event': action,
            'is_goal': False,
            'scorer': None,
            'scorer_name': None,
            'team_name': None
        })
        return action       
    
    def get_match_summary(self):
        """Возвращает статистику матча"""
        user_coeff = self.calculate_coefficient(self.user_squad)
        bot_coeff = self.calculate_coefficient(self.bot_squad)
        
        summary = {
            'user_score': self.user_score,
            'bot_score': self.bot_score,
            'total_minutes': self.minute,
            'user_coeff': user_coeff,
            'bot_coeff': bot_coeff,
            'user_goals': len(self.user_goals),
            'bot_goals': len(self.bot_goals),
            'user_scorers': self.user_goals,
            'bot_scorers': self.bot_goals,
            'match_events': self.match_events,
            'tactic_used': self.current_tactic
        }
        
        return summary

# Функции для работы с ELO и статистикой
def init_user_elo_table():
    """Создает таблицу для ELO рейтинга пользователей"""
    try:
        db_operation('''
        CREATE TABLE IF NOT EXISTS user_elo (
            user_id INTEGER PRIMARY KEY,
            elo_rating INTEGER DEFAULT 200,
            total_matches INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            draws INTEGER DEFAULT 0,
            goals_scored INTEGER DEFAULT 0,
            goals_conceded INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES all_users (id)
        )
        ''')
        
        # Создаем таблицу для истории матчей
        db_operation('''
        CREATE TABLE IF NOT EXISTS match_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            opponent_type TEXT NOT NULL,  -- 'bot' или 'player'
            opponent_name TEXT,
            user_score INTEGER NOT NULL,
            opponent_score INTEGER NOT NULL,
            result TEXT NOT NULL,  -- 'win', 'lose', 'draw'
            elo_change INTEGER NOT NULL,
            match_duration INTEGER,  -- в минутах
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES all_users (id)
        )
        ''')
        
        # Индексы для быстрого поиска
        db_operation('''
        CREATE INDEX IF NOT EXISTS idx_match_history_user 
        ON match_history(user_id, created_at DESC)
        ''')
        
        logger.info("✅ Таблицы ELO и истории матчей созданы")
    except Exception as e:
        logger.error(f"❌ Ошибка при создании таблиц ELO: {e}")

@public_router_pvp.message(Command("resetelo"))
@require_role("старший-администратор")
async def reset_elo_command(message: Message, bot: Bot):
    """Сбрасывает ELO рейтинг указанного пользователя"""
    
    # Список ID администраторов (замените на реальные ID)
  # Добавьте сюда ID администраторов
    
    user_id = message.from_user.id
    
    # Проверяем, является ли пользователь администратором

    
    # Получаем аргументы команды
    args = message.text.split()
    
    if len(args) < 2:
        await message.reply(
            "📝 <b>Использование команды:</b>\n"
            "<code>/resetelo [ID_пользователя]</code>\n\n"
            "<b>Пример:</b>\n"
            "<code>/resetelo 123456789</code>\n\n"
            "<i>Для сброса собственного ELO:</i>\n"
            "<code>/resetelo self</code>",
            parse_mode="html"
        )
        return
    
    target_arg = args[1].lower()
    
    # Определяем ID целевого пользователя
    if target_arg == "self":
        target_user_id = user_id
        target_name = "ваш"
    else:
        try:
            target_user_id = int(target_arg)
            # Проверяем, существует ли пользователь
            result = db_operation(
                "SELECT id FROM all_users WHERE id = ?",
                (target_user_id,),
                fetch=True
            )
            
            if not result:
                await message.reply(
                    f"❌ <b>Пользователь не найден!</b>\n\n"
                    f"Пользователь с ID {target_user_id} не зарегистрирован в системе.",
                    parse_mode="html"
                )
                return
            
            target_name = f"пользователя {target_user_id}"
            
        except ValueError:
            await message.reply(
                "❌ <b>Неверный формат ID!</b>\n\n"
                "ID пользователя должен быть числом.\n\n"
                "<b>Пример:</b> <code>/resetelo 123456789</code>",
                parse_mode="html"
            )
            return
    
    try:
        # Получаем текущие данные ELO
        current_elo = get_user_elo(target_user_id)
        
        if not current_elo:
            await message.reply(
                f"❌ <b>ELO рейтинг не найден!</b>\n\n"
                f"У {target_name} еще нет статистики ELO.",
                parse_mode="html"
            )
            return
        
        # Сбрасываем ELO до стандартного значения (200)
        db_operation(
            """UPDATE user_elo 
               SET elo_rating = 200,
                   total_matches = 0,
                   wins = 0,
                   losses = 0,
                   draws = 0,
                   goals_scored = 0,
                   goals_conceded = 0,
                   updated_at = CURRENT_TIMESTAMP
               WHERE user_id = ?""",
            (target_user_id,)
        )
        
        # Также очищаем историю матчей
        db_operation(
            "DELETE FROM match_history WHERE user_id = ?",
            (target_user_id,)
        )
        
        # Очищаем очередь PvP если пользователь там есть
        remove_from_pvp_queue(target_user_id)
        
        # Формируем ответ
        if target_user_id == user_id:
            success_message = (
                "✅ <b>ELO СБРОШЕН!</b>\n\n"
                "Все статистические данные были сброшены:\n\n"
                f"• <b>ELO рейтинг:</b> 200 (было {current_elo['elo_rating']})\n"
                f"• <b>Всего матчей:</b> 0 (было {current_elo['total_matches']})\n"
                f"• <b>Побед:</b> 0 (было {current_elo['wins']})\n"
                f"• <b>Поражений:</b> 0 (было {current_elo['losses']})\n"
                f"• <b>Ничьих:</b> 0 (было {current_elo['draws']})\n\n"
                "<i>Игрок может начать все с чистого листа!</i>"
            )
        else:
            # Пытаемся получить имя пользователя
            try:

                target_user = await bot.get_chat(target_user_id)
                username = f"@{target_user.username}" if target_user.username else target_user.first_name
            except:
                username = f"ID: {target_user_id}"
            
            success_message = (
                "✅ <b>ELO СБРОШЕН!</b>\n\n"
                f"Статистика пользователя <b>{username}</b> была сброшена:\n\n"
                f"• <b>ELO рейтинг:</b> 200 (было {current_elo['elo_rating']})\n"
                f"• <b>Всего матчей:</b> 0 (было {current_elo['total_matches']})\n"
                f"• <b>Побед:</b> 0 (было {current_elo['wins']})\n"
                f"• <b>Поражений:</b> 0 (было {current_elo['losses']})\n"
                f"• <b>Ничьих:</b> 0 (было {current_elo['draws']})\n\n"
                "<i>Пользователь может начать с чистого листа!</i>"
            )
        
        await message.reply(
            success_message,
            parse_mode="html"
        )
        
        logger.info(f"ELO пользователя {target_user_id} сброшен администратором {user_id}")
        
    except Exception as e:
        logger.error(f"Ошибка при сбросе ELO: {e}")
        await message.reply(
            "❌ <b>Произошла ошибка!</b>\n\n"
            "Не удалось сбросить ELO рейтинг. Попробуйте позже.",
            parse_mode="html"
        )


def get_user_elo(user_id: int):
    """Получает ELO рейтинг пользователя"""
    try:
        result = db_operation(
            """SELECT elo_rating, total_matches, wins, losses, draws, 
                      goals_scored, goals_conceded 
               FROM user_elo 
               WHERE user_id = ?""",
            (user_id,),
            fetch=True
        )
        
        if result:
            elo_rating, total_matches, wins, losses, draws, goals_scored, goals_conceded = result[0]
            return {
                'elo_rating': elo_rating,
                'total_matches': total_matches,
                'wins': wins,
                'losses': losses,
                'draws': draws,
                'goals_scored': goals_scored,
                'goals_conceded': goals_conceded
            }
        else:
            # Создаем запись если нет
            db_operation(
                """INSERT INTO user_elo (user_id, elo_rating) 
                   VALUES (?, 200)""",
                (user_id,)
            )
            return {
                'elo_rating': 200,
                'total_matches': 0,
                'wins': 0,
                'losses': 0,
                'draws': 0,
                'goals_scored': 0,
                'goals_conceded': 0
            }
    except Exception as e:
        logger.error(f"Ошибка при получении ELO пользователя {user_id}: {e}")
        return None

def update_user_elo(user_id: int, result: str, elo_change: int, 
                    user_score: int = 0, opponent_score: int = 0):
    """Обновляет ELO рейтинг пользователя после матча"""
    try:
        # Определяем статистику в зависимости от результата
        if result == 'win':
            wins_change = 1
            losses_change = 0
            draws_change = 0
        elif result == 'lose':
            wins_change = 0
            losses_change = 1
            draws_change = 0
        else:  # draw
            wins_change = 0
            losses_change = 0
            draws_change = 1
        
        # Сначала проверяем, существует ли запись пользователя
        existing = db_operation(
            "SELECT user_id FROM user_elo WHERE user_id = ?",
            (user_id,),
            fetch=True
        )
        
        if existing:
            # Обновляем существующую запись
            db_operation(
                """UPDATE user_elo 
                   SET elo_rating = elo_rating + ?,
                       total_matches = total_matches + 1,
                       wins = wins + ?,
                       losses = losses + ?,
                       draws = draws + ?,
                       goals_scored = goals_scored + ?,
                       goals_conceded = goals_conceded + ?,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE user_id = ?""",
                (elo_change, wins_change, losses_change, draws_change, 
                 user_score, opponent_score, user_id)
            )
        else:
            # Создаем новую запись
            db_operation(
                """INSERT INTO user_elo 
                   (user_id, elo_rating, total_matches, wins, losses, draws, 
                    goals_scored, goals_conceded, updated_at)
                   VALUES (?, ?, 1, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (user_id, 200 + elo_change, wins_change, losses_change, draws_change, 
                 user_score, opponent_score)
            )
        
        # Сохраняем историю матча
        db_operation(
            """INSERT INTO match_history 
               (user_id, opponent_type, opponent_name, user_score, opponent_score,
                result, elo_change, match_duration, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (user_id, 'bot', 'MamoTinder Bot', user_score, opponent_score, 
             result, elo_change, 90)
        )
        
        logger.info(f"✅ ELO пользователя {user_id} обновлен: {result} ({elo_change:+d})")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при обновлении ELO пользователя {user_id}: {e}")
        import traceback
        logger.error(f"Трейсбэк: {traceback.format_exc()}")

def get_match_history(user_id: int, page: int = 0, opponent_type: str = None):
    """Получает историю матчей пользователя с пагинацией"""
    try:
        limit = 10
        offset = page * limit
        
        if opponent_type:
            query = """
                SELECT id, opponent_type, opponent_name, user_score, opponent_score,
                       result, elo_change, match_duration, created_at
                FROM match_history
                WHERE user_id = ? AND opponent_type = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """
            params = (user_id, opponent_type, limit, offset)
        else:
            query = """
                SELECT id, opponent_type, opponent_name, user_score, opponent_score,
                       result, elo_change, match_duration, created_at
                FROM match_history
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """
            params = (user_id, limit, offset)
        
        result = db_operation(query, params, fetch=True)
        
        matches = []
        for row in result:
            matches.append({
                'id': row[0],
                'opponent_type': row[1],
                'opponent_name': row[2],
                'user_score': row[3],
                'opponent_score': row[4],
                'result': row[5],
                'elo_change': row[6],
                'match_duration': row[7],
                'created_at': row[8]
            })
        
        return matches
        
    except Exception as e:
        logger.error(f"Ошибка при получении истории матчей пользователя {user_id}: {e}")
        return []

def get_total_match_pages(user_id: int, opponent_type: str = None):
    """Получает общее количество страниц истории матчей"""
    try:
        if opponent_type:
            query = "SELECT COUNT(*) FROM match_history WHERE user_id = ? AND opponent_type = ?"
            params = (user_id, opponent_type)
        else:
            query = "SELECT COUNT(*) FROM match_history WHERE user_id = ?"
            params = (user_id,)
        
        result = db_operation(query, params, fetch=True)
        total_matches = result[0][0] if result else 0
        
        return (total_matches + 9) // 10  # Округление вверх
        
    except Exception as e:
        logger.error(f"Ошибка при получении количества страниц матчей: {e}")
        return 1

# Вызовите инициализацию таблиц в начале
init_user_elo_table()

# Обработчик игры с ботом
@public_router_pvp.callback_query(F.data == "withbot")
@handle_old_callback
async def bot_play_match(callback: CallbackQuery, state: FSMContext):
    """Начинает матч с ботом с подтверждением готовности"""
    user_id = callback.from_user.id
    
    try:
        # Проверяем наличие состава
        user_squad = get_user_squad(user_id)
        
        if not user_squad:
            await callback.message.edit_text(
                "❌ <b>У вас нет состава!</b>\n\n"
                "Для игры с ботом сначала создайте состав.",
                parse_mode="html",
                reply_markup=InlineKeyboardBuilder()
                .add(InlineKeyboardButton(text="👥 Создать состав", callback_data="sostav"))
                .as_markup()
            )
            await callback.answer()
            return
        
        # Показываем подтверждение готовности
        await state.set_state(MatchStates.confirming_match)
        
        # Получаем детали состава для отображения
        squad_details_text = ""
        positions = [
            ("ГК (Вратарь)", user_squad['gk_card_id']),
            ("ОП (Защитник)", user_squad['op_card_id']),
            ("НАП 1 (Нападающий)", user_squad['nap1_card_id']),
            ("НАП 2 (Нападающий)", user_squad['nap2_card_id'])
        ]
        
        for pos_name, card_id in positions:
            if card_id:
                card_details = get_card_details(card_id)
                if card_details:
                    rarity_display = 'Эпический' if card_details['rarity'] == 'эпическая' else card_details['rarity']
                    squad_details_text += f"• <b>{pos_name}:</b> {card_details['nickname']} ({rarity_display})\n"
            else:
                squad_details_text += f"• <b>{pos_name}:</b> ❌ Не выбрано\n"
        
        message_text = (
            f"🤖 <b>МАТЧ ПРОТИВ БОТА</b>\n\n"
            f"🏆 <b>Ваш состав:</b> {user_squad.get('squad_name', 'Мой состав')}\n\n"
            f"{squad_details_text}\n"
            f"⚽ <b>Противник:</b> MamoTinder Bot (ИИ)\n\n"
            f"<b>📊 Правила матча:</b>\n"
            f"• 30 секунд игрового времени\n"  # ⚡️ Изменено с 90 минут
            f"• Редкости карточек влияют на шанс гола\n"
            f"• За победу: +3 ELO\n"
            f"• За поражение: -6 ELO\n"
            f"• За ничью: +1 ELO\n\n"
            f"<i>Вы готовы начать матч?</i>"
        )
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="✅ Готов к матчу",
                callback_data="confirm_match_start"
            ),
            InlineKeyboardButton(
                text="❌ Отменить",
                callback_data="back_to_play_menu"
            )
        )
        
        await callback.message.edit_text(
            message_text,
            parse_mode="html",
            reply_markup=builder.as_markup()
        )
        
        await state.update_data({
            'user_squad': user_squad,
            'user_id': user_id
        })
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в bot_play_match для пользователя {user_id}: {e}")
        await callback.answer("❌ Ошибка при начале матча", show_alert=True)

# Изменения в confirm_match_start для начального сообщения
@public_router_pvp.callback_query(F.data == "confirm_match_start")
@handle_old_callback
async def confirm_match_start(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Подтверждение начала матча"""
    user_id = callback.from_user.id
    
    try:
        state_data = await state.get_data()
        user_squad = state_data.get('user_squad')
        
        if not user_squad:
            await callback.answer("❌ Ошибка: состав не найден", show_alert=True)
            return
        
        # Получаем детали карточек состава
        squad_details = {}
        for pos_key in ['gk_card_id', 'op_card_id', 'nap1_card_id', 'nap2_card_id']:
            card_id = user_squad.get(pos_key)
            if card_id:
                card_details = get_card_details(card_id)
                if card_details:
                    squad_details[pos_key.replace('_card_id', '')] = card_details
        
        # Проверяем, что есть все необходимые карточки
        required_positions = ['gk', 'op', 'nap1', 'nap2']
        for pos in required_positions:
            if pos not in squad_details:
                await callback.answer(f"❌ Отсутствует карточка для позиции {pos}", show_alert=True)
                return
        
        # Создаем симулятор матча с правильной структурой
        # Создаем полный состав с названием команды
        full_user_squad = {
            'squad_name': user_squad.get('squad_name', 'Ваша команда'),
            'gk': squad_details.get('gk'),
            'op': squad_details.get('op'),
            'nap1': squad_details.get('nap1'),
            'nap2': squad_details.get('nap2')
        }
        
        match_simulator = BotMatchSimulator(full_user_squad)
        
        await state.update_data({
            'match_simulator': match_simulator,
            'minute': 0,
            'user_score': 0,
            'bot_score': 0,
            'squad_name': user_squad.get('squad_name', 'Ваша команда'),
            'is_match_running': True,
            'user_squad': user_squad,
            'current_tactic': 'balance'
        })
        
        # ... остальной код без изменений ...
        
        # Формируем начальное сообщение с прогресс-баром
        squad_name = user_squad.get('squad_name', 'Ваша команда')
        progress_bar = match_simulator.get_progress_bar(0, match_simulator.match_duration)
        
        message_text = (
            f"🎮 <b>ИГРА НАЧИНАЕТСЯ!</b>\n\n"
            f"🏆 <b>Матч:</b> {squad_name} 0:0 MamoTinder Bot\n"
            f"{'='*40}\n\n"
            f"⏳ <b>Прогресс матча:</b>\n"
            f"{progress_bar}\n\n"
            f"🔵 <b>Стартовый свисток!</b> Матч начался!\n\n"
            f"<i>Матч симулируется в реальном времени...</i>"
        )
        
        # Создаем клавиатуру для управления матчем
        builder = InlineKeyboardBuilder()
        
        match_message = await callback.message.edit_text(
            message_text,
            parse_mode="html",
            reply_markup=builder.as_markup()
        )
        
        # Сохраняем ID сообщения для обновления
        await state.update_data({
            'match_message_id': match_message.message_id,
            'chat_id': match_message.chat.id
        })
        
        # Запускаем симуляцию матча
        asyncio.create_task(run_match_simulation(
            callback.message.chat.id, 
            match_message.message_id, 
            user_id, 
            match_simulator, 
            state, 
            bot
        ))
        
        await callback.answer("✅ Матч начался!", show_alert=True)
        
    except Exception as e:
        logger.error(f"Ошибка в confirm_match_start для пользователя {user_id}: {e}")
        await callback.answer("❌ Ошибка при запуске матча", show_alert=True)


# Изменения в функции run_match_simulation
async def run_match_simulation(chat_id: int, message_id: int, user_id: int, match_simulator, state: FSMContext, bot: Bot):
    """Запускает симуляцию матча в отдельной задаче с поддержкой тактики"""
    try:
        state_data = await state.get_data()
        squad_name = state_data.get('squad_name', 'Ваша команда')
        
        # Сохраняем ссылку на задачу для возможности остановки
        match_task = asyncio.current_task()
        await state.update_data({'match_task': match_task})
        
        # Симулируем 30 секунд матча
        for second in range(1, match_simulator.match_duration + 1):
            # Проверяем, не завершен ли матч
            state_data = await state.get_data()
            if not state_data.get('is_match_running', True):
                break
            
            await asyncio.sleep(0.8)
            
            # Получаем текущую тактику и обновляем ее в симуляторе
            current_tactic = state_data.get('current_tactic', 'balance')
            match_simulator.set_tactic(current_tactic)
            
            # Обновляем время в симуляторе
            match_simulator.minute = second
            
            # Симулируем секунду матча с учетом тактики
            event = match_simulator.simulate_second()
            
            # Обновляем данные состояния
            await state.update_data({
                'minute': second,
                'user_score': match_simulator.user_score,
                'bot_score': match_simulator.bot_score,
                'match_simulator': match_simulator
            })
            
            # Получаем прогресс-бар
            progress_bar = match_simulator.get_progress_bar(second, match_simulator.match_duration)
            
            # Получаем описание текущей тактики
            tactic_descriptions = {
                'attack': '⚔️ Все в атаку! (+15% забить, +30% пропустить)',
                'defense': '🛡️ Все в защиту! (-50% забить, -15% пропустить)',
                'balance': '⚖️ Баланс (стандартные шансы)'
            }
            tactic_info = tactic_descriptions.get(current_tactic, '⚖️ Баланс')
            
            message_text = (
                f"🎮 <b>ИДЕТ МАТЧ!</b>\n\n"
                f"🏆 <b>Счет:</b> {squad_name} {match_simulator.user_score}:{match_simulator.bot_score} MamoTinder Bot\n"
                f"{'='*40}\n\n"
                f"⏳ <b>Прогресс матча:</b>\n"
                f"{progress_bar}\n\n"
                f"🎯 <b>Текущая тактика:</b> {tactic_info}\n\n"
                f"📢 <b>Событие:</b> {event}\n\n"
                f"<i>Матч продолжается...</i>"
            )
            
            # Создаем клавиатуру с тактическими кнопками
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(
                    text="⚔️ Все в атаку",
                    callback_data="tactic_attack"
                ),
                InlineKeyboardButton(
                    text="🛡️ Все в защиту",
                    callback_data="tactic_defense"
                ),
                InlineKeyboardButton(
                    text="⚖️ Баланс",
                    callback_data="tactic_balance"
                )
            )
            
            
            # Обновляем сообщение
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=message_text,
                    parse_mode="html",
                    reply_markup=builder.as_markup()
                )
            except Exception as e:
                logger.error(f"Не удалось обновить сообщение матча: {e}")
                break
        
        # После завершения цикла завершаем матч
        await finish_match_after_simulation(chat_id, message_id, user_id, match_simulator, state, bot)
        
    except asyncio.CancelledError:
        logger.info(f"Матч пользователя {user_id} был прерван")
    except Exception as e:
        logger.error(f"Ошибка в run_match_simulation для пользователя {user_id}: {e}")
        import traceback
        logger.error(f"Трейсбэк: {traceback.format_exc()}")
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="❌ <b>Ошибка в матче!</b>\n\nПроизошла техническая ошибка.",
                parse_mode="html",
                reply_markup=InlineKeyboardBuilder()
                .add(InlineKeyboardButton(text="🎮 Игровое меню", callback_data="back_to_play_menu"))
                .as_markup()
            )
        except:
            pass
@public_router_pvp.callback_query(F.data.startswith("tactic_"))
@handle_old_callback
async def handle_tactic_change(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает смену тактики во время матча"""
    try:
        tactic = callback.data.split("_")[1]  # attack, defense, balance
        
        # Сохраняем новую тактику в состоянии
        await state.update_data({'current_tactic': tactic})
        
        # Отправляем подтверждение
        tactic_names = {
            'attack': '⚔️ Все в атаку',
            'defense': '🛡️ Все в защиту',
            'balance': '⚖️ Баланс'
        }
        tactic_effects = {
            'attack': 'Шанс забить +15%, шанс пропустить +30%',
            'defense': 'Шанс забить -50%, шанс пропустить -15%',
            'balance': 'Стандартные шансы'
        }
        
        await callback.answer(
            f"Тактика изменена: {tactic_names.get(tactic, 'Неизвестно')}\n"
            f"Эффект: {tactic_effects.get(tactic, 'Нет эффекта')}",
            show_alert=True
        )
        
    except Exception as e:
        logger.error(f"Ошибка при смене тактики: {e}")
        await callback.answer("❌ Ошибка при смене тактики", show_alert=True)



async def finish_match_after_simulation(chat_id: int, message_id: int, user_id: int, match_simulator, state: FSMContext, bot: Bot):
    """Завершает матч после симуляции с расширенной статистикой"""
    try:
        match_summary = match_simulator.get_match_summary()
        
        # Получаем название команды пользователя
        state_data = await state.get_data()
        user_squad = state_data.get('user_squad', {})
        user_team_name = user_squad.get('squad_name', 'Ваша команда')
        
        # Название команды бота
        bot_team_name = "MamoTinder Bot"
        
        # Определяем результат
        if match_summary['user_score'] > match_summary['bot_score']:
            result = 'win'
            result_text = "🏆 ПОБЕДА!"
            elo_change = 3
            result_emoji = "✅"
        elif match_summary['user_score'] < match_summary['bot_score']:
            result = 'lose'
            result_text = "💥 ПОРАЖЕНИЕ"
            elo_change = -6
            result_emoji = "❌"
        else:
            result = 'draw'
            result_text = "🤝 НИЧЬЯ"
            elo_change = 1
            result_emoji = "⚖️"
        
        # Обновляем ELO
        update_user_elo(
            user_id=user_id,
            result=result,
            elo_change=elo_change,
            user_score=match_summary['user_score'],
            opponent_score=match_summary['bot_score']
        )
        
        # Получаем новый ELO
        user_elo = get_user_elo(user_id)
        
        # --- РАСШИРЕННАЯ СТАТИСТИКА ДЛЯ МАТЧА С БОТОМ ---
        
        # 1. Голевые моменты
        goals_stats = ""
        if match_summary.get('user_scorers') or match_summary.get('bot_scorers'):
            goals_stats += f"⚽ <b>ГОЛОВ ЗАБИТО:</b>\n"
            
            # Голы пользователя
            if match_summary.get('user_scorers'):
                goals_stats += f"<b>{user_team_name}:</b>\n"
                for i, scorer in enumerate(match_summary['user_scorers'], 1):
                    minute = scorer.get('minute', '?')
                    goals_stats += f"  {i}. {scorer.get('name', 'Неизвестный игрок')} ({minute}-я секунда)\n"
            
            # Голы бота
            if match_summary.get('bot_scorers'):
                goals_stats += f"<b>{bot_team_name}:</b>\n"
                for i, scorer in enumerate(match_summary['bot_scorers'], 1):
                    minute = scorer.get('minute', '?')
                    goals_stats += f"  {i}. {scorer.get('name', 'Неизвестный игрок')} ({minute}-я секунда)\n"
        
        # 2. Владение мячом
        user_possession = random.randint(45, 65)
        bot_possession = 100 - user_possession
        
        # 3. Удары по воротам
        user_shots = match_summary['user_goals'] + random.randint(5, 15)
        bot_shots = match_summary['bot_goals'] + random.randint(5, 15)
        
        # 4. Удары в створ
        user_shots_on_target = int(user_shots * random.uniform(0.7, 0.9))
        bot_shots_on_target = int(bot_shots * random.uniform(0.7, 0.9))
        
        # 5. Угловые
        user_corners = random.randint(3, 12)
        bot_corners = random.randint(3, 12)
        
        # 6. Фолы
        user_fouls = random.randint(5, 15)
        bot_fouls = random.randint(5, 15)
        
        # 7. Желтые карточки
        user_yellows = random.randint(0, 3)
        bot_yellows = random.randint(0, 3)
        
        # 8. Офсайды
        user_offsides = random.randint(0, 5)
        bot_offsides = random.randint(0, 5)
        
        # 9. Сейвы вратарей
        user_saves = max(0, bot_shots_on_target - match_summary['user_score'])
        bot_saves = max(0, user_shots_on_target - match_summary['bot_score'])
        
        # 10. Процент реализованных моментов
        user_conversion = round((match_summary['user_score'] / user_shots_on_target * 100), 1) if user_shots_on_target > 0 else 0
        bot_conversion = round((match_summary['bot_score'] / bot_shots_on_target * 100), 1) if bot_shots_on_target > 0 else 0
        
        # Формируем красивую статистику
        result_message = (
            f"🎯 <b>МАТЧ ЗАВЕРШЕН!</b>\n\n"
            f"🏁 <b>ФИНАЛЬНЫЙ СЧЕТ:</b>\n"
            f"📊 <b>{user_team_name}:</b> {match_summary['user_score']}\n"
            f"🤖 <b>{bot_team_name}:</b> {match_summary['bot_score']}\n\n"
        )
        
        # Определяем результат
        result_message += f"⭐ <b>РЕЗУЛЬТАТ:</b> {result_emoji} {result_text}\n"
        result_message += f"📈 <b>Изменение ELO:</b> {elo_change:+d}\n"
        result_message += f"🏅 <b>Текущий ELO:</b> {user_elo['elo_rating'] if user_elo else 200}\n\n"
        
        # Добавляем статистику голов
        if goals_stats:
            result_message += f"{goals_stats}\n"
        
        # Добавляем подробную статистику
        result_message += (
            f"📊 <b>ПОДРОБНАЯ СТАТИСТИКА МАТЧА:</b>\n"
            f"{'='*40}\n"
            f"• 🎯 <b>Удары:</b> {user_shots} | {bot_shots}\n"
            f"• 🎯 <b>Удары в створ:</b> {user_shots_on_target} | {bot_shots_on_target}\n"
            f"• ⚽ <b>Голы:</b> {match_summary['user_score']} | {match_summary['bot_score']}\n"
            f"• 🧤 <b>Сейвы:</b> {user_saves} | {bot_saves}\n"
            f"• 🏃 <b>Владение мячом:</b> {user_possession}% | {bot_possession}%\n"
            f"• 🎯 <b>Реализация:</b> {user_conversion}% | {bot_conversion}%\n"
            f"• 🎪 <b>Угловые:</b> {user_corners} | {bot_corners}\n"
            f"• ⚠️ <b>Фолы:</b> {user_fouls} | {bot_fouls}\n"
            f"• 🟨 <b>Желтые карточки:</b> {user_yellows} | {bot_yellows}\n"
            f"• 🚩 <b>Офсайды:</b> {user_offsides} | {bot_offsides}\n\n"
        )
        
        # Добавляем использованную тактику
        tactic_used = state_data.get('current_tactic', 'balance')
        tactic_display = {
            'attack': '⚔️ Все в атаку',
            'defense': '🛡️ Все в защиту',
            'balance': '⚖️ Баланс'
        }.get(tactic_used, '⚖️ Баланс')
        
        result_message += f"🧠 <b>ИСПОЛЬЗОВАННАЯ ТАКТИКА:</b> {tactic_display}\n\n"
        
        result_message += f"⏱️ <b>Длительность матча:</b> {match_summary['total_minutes']} секунд\n"
        result_message += f"<i>Спасибо за игру! 👏</i>"
        
        # Кнопки после матча
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="📊 Статистика", callback_data="statistics"),
            InlineKeyboardButton(text="⚽ Сыграть еще", callback_data="withbot")
        )
        builder.row(
            InlineKeyboardButton(text="🎮 Игровое меню", callback_data="back_to_play_menu")
        )
        
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=result_message,
            parse_mode="html",
            reply_markup=builder.as_markup()
        )
        
        # Очищаем состояние
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка в finish_match_after_simulation: {e}")
async def simulate_match(message: Message, state: FSMContext, user_id: int, match_simulator):
    """Симулирует матч в реальном времени"""
    try:
        state_data = await state.get_data()
        match_simulator = state_data.get('match_simulator')
        squad_name = state_data.get('squad_name', 'Ваша команда')
        
        if not match_simulator:
            return
        
        # Симулируем 90 минут матча (каждые 2 секунды = 1 минута игрового времени)
        for minute in range(1, 91):
            # Проверяем, не завершен ли матч
            current_state = await state.get_state()
            if current_state != MatchStates.playing_match.state:
                break
            
            await asyncio.sleep(2)  # 2 секунды между событиями
            
            # Симулируем минуту матча
            event = match_simulator.simulate_minute()
            
            # Обновляем данные состояния
            await state.update_data({
                'minute': minute,
                'user_score': match_simulator.user_score,
                'bot_score': match_simulator.bot_score
            })
            
            # Определяем тайм
            half = "1" if minute <= 45 else "2"
            
            message_text = (
                f"🎮 <b>ИДЕТ МАТЧ!</b>\n\n"
                f"🏆 <b>{half} тайм:</b> {squad_name} {match_simulator.user_score}:{match_simulator.bot_score} MamoTinder\n"
                f"{'='*40}\n\n"
                f"⏱️ <i>{minute}-я минута</i>\n"
                f"📢 {event}\n\n"
                f"<i>Матч продолжается...</i>"
            )
            
            # Создаем КАЖДЫЙ РАЗ новую клавиатуру с кнопками управления матчем
            builder = InlineKeyboardBuilder()
            builder.row(

            )
            
            # Обновляем сообщение с правильными кнопками
            try:
                await message.edit_text(
                    message_text,
                    parse_mode="html",
                    reply_markup=builder.as_markup()  # Важно: используем новую клавиатуру
                )
            except Exception as e:
                logger.error(f"Ошибка при обновлении сообщения матча: {e}")
                break
        
        # Матч завершен
        await finish_match(message, state, user_id, match_simulator)
        
    except Exception as e:
        logger.error(f"Ошибка в simulate_match: {e}")
        await message.edit_text(
            "❌ <b>Ошибка в матче!</b>\n\n"
            "Произошла техническая ошибка. Матч прерван.",
            parse_mode="html",
            reply_markup=InlineKeyboardBuilder()
            .add(InlineKeyboardButton(text="🎮 Игровое меню", callback_data="back_to_play_menu"))
            .as_markup()
        )


async def simulate_match(message: Message, state: FSMContext, user_id: int, match_simulator):
    """Симулирует матч в реальном времени"""
    try:
        state_data = await state.get_data()
        match_simulator = state_data.get('match_simulator')
        
        if not match_simulator:
            return
        
        # Симулируем 90 минут матча (каждые 2 секунды = 1 минута игрового времени)
        for minute in range(1, 91):
            # Проверяем, не завершен ли матч
            current_state = await state.get_state()
            if current_state != MatchStates.playing_match:
                break
            
            await asyncio.sleep(2)  # 2 секунды между событиями
            
            # Симулируем минуту матча
            event = match_simulator.simulate_minute()
            
            # Обновляем данные состояния
            await state.update_data({
                'minute': minute,
                'user_score': match_simulator.user_score,
                'bot_score': match_simulator.bot_score
            })
            
            # Формируем сообщение
            squad_name = (await state.get_data()).get('squad_name', 'Ваша команда')
            half = "1" if minute <= 45 else "2"
            
            message_text = (
                f"🎮 <b>ИДЕТ МАТЧ!</b>\n\n"
                f"🏆 <b>{half} тайм:</b> {squad_name} {match_simulator.user_score}:{match_simulator.bot_score} MamoTinder\n"
                f"{"="*40}\n\n"
                f"⏱️ <i>{minute}-я минута</i>\n"
                f"📢 {event}\n\n"
                f"<i>Матч продолжается...</i>"
            )
            
            # Обновляем сообщение
            try:
                await message.edit_text(
                    message_text,
                    parse_mode="html",
                    reply_markup=message.reply_markup
                )
            except Exception as e:
                logger.error(f"Ошибка при обновлении сообщения матча: {e}")
        
        # Матч завершен
        await finish_match(message, state, user_id, match_simulator)
        
    except Exception as e:
        logger.error(f"Ошибка в simulate_match: {e}")
        await message.edit_text(
            "❌ <b>Ошибка в матче!</b>\n\n"
            "Произошла техническая ошибка. Матч прерван.",
            parse_mode="html"
        )

async def finish_match(message: Message, state: FSMContext, user_id: int, match_simulator):
    """Завершает матч и показывает результат"""
    try:
        match_summary = match_simulator.get_match_summary()
        
        # Определяем результат
        if match_summary['user_score'] > match_summary['bot_score']:
            result = 'win'
            result_text = "🏆 ПОБЕДА!"
            elo_change = 8
        elif match_summary['user_score'] < match_summary['bot_score']:
            result = 'lose'
            result_text = "💥 ПОРАЖЕНИЕ"
            elo_change = -8
        else:
            result = 'draw'
            result_text = "🤝 НИЧЬЯ"
            elo_change = 3
        
        # Обновляем ELO
        update_user_elo(
            user_id=user_id,
            result=result,
            elo_change=elo_change,
            user_score=match_summary['user_score'],
            opponent_score=match_summary['bot_score']
        )
        
        # Получаем новый ELO
        user_elo = get_user_elo(user_id)
        
        # Формируем итоговое сообщение
        result_message = (
            f"🎯 <b>МАТЧ ЗАВЕРШЕН!</b>\n\n"
            f"🏁 <b>ФИНАЛЬНЫЙ СЧЕТ:</b>\n"
            f"📊 <b>Ваша команда:</b> {match_summary['user_score']}\n"
            f"🤖 <b>MamoTinder Bot:</b> {match_summary['bot_score']}\n\n"
            f"⭐ <b>РЕЗУЛЬТАТ:</b> {result_text}\n"
            f"📈 <b>Изменение ELO:</b> {elo_change:+d}\n"
            f"🏅 <b>Текущий ELO:</b> {user_elo['elo_rating'] if user_elo else 200}\n\n"
            f"📊 <b>СТАТИСТИКА МАТЧА:</b>\n"
            f"• Удары: {match_summary['user_goals'] + random.randint(5, 15)}\n"
            f"• Владение мячом: {random.randint(45, 65)}%\n"
            f"• Голевые моменты: {match_summary['user_goals'] + random.randint(2, 8)}\n"
            f"• Угловые: {random.randint(3, 12)}\n"
            f"• Фолы: {random.randint(5, 15)}\n\n"
            f"<i>Спасибо за игру!</i>"
        )
        
        # Кнопки после матча
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="📊 Статистика", callback_data="statistics"),
            InlineKeyboardButton(text="⚽ Сыграть еще", callback_data="withbot")
        )
        builder.row(
            InlineKeyboardButton(text="🎮 Игровое меню", callback_data="back_to_play_menu")
        )
        
        await message.edit_text(
            result_message,
            parse_mode="html",
            reply_markup=builder.as_markup()
        )
        
        # Очищаем состояние
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка в finish_match: {e}")
        await message.edit_text(
            "❌ <b>Ошибка при завершении матча!</b>\n\n"
            "Не удалось сохранить статистику.\n"
            "Пожалуйста, попробуйте еще раз.",
            parse_mode="html",
            reply_markup=InlineKeyboardBuilder()
            .add(InlineKeyboardButton(text="🎮 Игровое меню", callback_data="back_to_play_menu"))
            .as_markup()
        )



@public_router_pvp.callback_query(F.data == "back_to_play_menu")
@handle_old_callback
async def back_from_match_confirmation(callback: CallbackQuery, state: FSMContext):
    """Возврат из подтверждения матча или из игры"""
    try:
        current_state = await state.get_state()
        
        # Если мы находимся в состоянии подтверждения матча или игры
        if current_state in [MatchStates.confirming_match.state, MatchStates.playing_match.state]:
            # Если идет матч, останавливаем его
            if current_state == MatchStates.playing_match.state:
                # Отменяем все задачи матча
                await state.clear()
            
            await callback.message.edit_text(
                "❌ <b>Действие отменено</b>\n\n"
                "Вы вернулись в игровое меню.",
                parse_mode="html",
                reply_markup=main_play
            )
        else:
            # Если не в состоянии матча, просто показываем меню
            await callback.message.edit_text(
                "<b>🎮 Игровое меню:</b>",
                reply_markup=main_play,
                parse_mode="html"
            )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в back_from_match_confirmation: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


@public_router_pvp.callback_query(F.data == "statistics")
@handle_old_callback
async def show_statistics(callback: CallbackQuery, state: FSMContext):
    """Показывает статистику пользователя"""
    user_id = callback.from_user.id
    
    try:
        # Получаем ELO и статистику
        user_elo = get_user_elo(user_id)
        
        if not user_elo:
            await callback.message.edit_text(
                "❌ <b>Статистика не найдена!</b>\n\n"
                "Сыграйте хотя бы один матч, чтобы появилась статистика.",
                parse_mode="html",
                reply_markup=InlineKeyboardBuilder()
                .add(InlineKeyboardButton(text="⚽ Сыграть матч", callback_data="play_match"))
                .as_markup()
            )
            await callback.answer()
            return
        
        # Рассчитываем процент побед
        total_matches = user_elo['total_matches']
        win_rate = (user_elo['wins'] / total_matches * 100) if total_matches > 0 else 0
        
        # Формируем сообщение
        message_text = (
            f"📊 <b>ВАША СТАТИСТИКА</b>\n\n"
            f"🏅 <b>ELO рейтинг:</b> {user_elo['elo_rating']}\n"
            f"🎮 <b>Всего матчей:</b> {total_matches}\n"
            f"✅ <b>Побед:</b> {user_elo['wins']}\n"
            f"❌ <b>Поражений:</b> {user_elo['losses']}\n"
            f"🤝 <b>Ничьих:</b> {user_elo['draws']}\n"
            f"📈 <b>Процент побед:</b> {win_rate:.1f}%\n\n"
            f"⚽ <b>Забито голов:</b> {user_elo['goals_scored']}\n"
            f"🧱 <b>Пропущено голов:</b> {user_elo['goals_conceded']}\n\n"
            f"<i>Выберите тип матчей для просмотра истории:</i>"
        )
        
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="🤖 Против бота", callback_data="stats_bot_0"),
            InlineKeyboardButton(text="👤 Против игрока", callback_data="stats_player_0")
        )
        builder.row(
            InlineKeyboardButton(text="📋 Все матчи", callback_data="stats_all_0")
        )
        builder.row(
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_play_menu")
        )
        
        await callback.message.edit_text(
            message_text,
            parse_mode="html",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в show_statistics для пользователя {user_id}: {e}")
        await callback.answer("❌ Ошибка при загрузке статистики", show_alert=True)

@public_router_pvp.callback_query(F.data.startswith("stats_"))
@handle_old_callback
async def show_match_history(callback: CallbackQuery):
    """Показывает историю матчей"""
    user_id = callback.from_user.id
    
    try:
        parts = callback.data.split("_")
        if len(parts) >= 3:
            opponent_type = parts[1]  # 'bot', 'player', 'all'
            page = int(parts[2]) if parts[2].isdigit() else 0
        else:
            opponent_type = 'all'
            page = 0
        
        # Преобразуем тип для запроса
        if opponent_type == 'all':
            db_opponent_type = None
            display_type = "Все матчи"
        else:
            db_opponent_type = opponent_type
            display_type = "Против бота" if opponent_type == 'bot' else "Против игрока"
        
        # Получаем историю матчей
        matches = get_match_history(user_id, page, db_opponent_type)
        total_pages = get_total_match_pages(user_id, db_opponent_type)
        
        if not matches:
            message_text = (
                f"📋 <b>ИСТОРИЯ МАТЧЕЙ</b>\n\n"
                f"🎯 <b>Тип:</b> {display_type}\n\n"
                f"<i>У вас еще нет матчей этого типа.</i>\n\n"
                f"<b>Сыграйте первый матч!</b>"
            )
        else:
            message_text = (
                f"📋 <b>ИСТОРИЯ МАТЧЕЙ</b>\n\n"
                f"🎯 <b>Тип:</b> {display_type}\n"
                f"📄 <b>Страница:</b> {page + 1} из {total_pages}\n\n"
            )
            
            for i, match in enumerate(matches, 1):
                match_number = page * 10 + i
                result_emoji = {
                    'win': '✅',
                    'lose': '❌',
                    'draw': '🤝'
                }.get(match['result'], '⚽')
                
                # Форматируем дату
                match_date = datetime.strptime(match['created_at'], '%Y-%m-%d %H:%M:%S')
                date_str = match_date.strftime('%d.%m.%Y')
                
                message_text += (
                    f"{match_number}. {result_emoji} <b>{match['user_score']}:{match['opponent_score']}</b> "
                    f"vs {match['opponent_name']}\n"
                    f"   📈 ELO: {match['elo_change']:+d} | 📅 {date_str}\n\n"
                )
        
        builder = InlineKeyboardBuilder()
        
        # Кнопки навигации
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(
                text="◀️",
                callback_data=f"stats_{opponent_type}_{page-1}"
            ))
        
        nav_buttons.append(InlineKeyboardButton(
            text=f"{page+1}/{total_pages}",
            callback_data="page_info"
        ))
        
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(
                text="▶️",
                callback_data=f"stats_{opponent_type}_{page+1}"
            ))
        
        if nav_buttons:
            builder.row(*nav_buttons)
        
        # Кнопки выбора типа
        builder.row(
            InlineKeyboardButton(text="🤖 Против бота", callback_data="stats_bot_0"),
            InlineKeyboardButton(text="👤 Против игрока", callback_data="stats_player_0")
        )
        builder.row(
            InlineKeyboardButton(text="📋 Все матчи", callback_data="stats_all_0")
        )
        builder.row(
            InlineKeyboardButton(text="📊 Общая статистика", callback_data="statistics"),
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_play_menu")
        )
        
        await callback.message.edit_text(
            message_text,
            parse_mode="html",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в show_match_history для пользователя {user_id}: {e}")
        await callback.answer("❌ Ошибка при загрузке истории", show_alert=True)





@public_router_pvp.callback_query(F.data == "continue_match")
@handle_old_callback
async def continue_match(callback: CallbackQuery, state: FSMContext):
    """Продолжает матч после паузы"""
    # Получаем данные матча из сообщения
    # В реальном проекте нужно сохранять состояние матча
    await callback.message.edit_text(
        "❌ <b>Невозможно продолжить</b>\n\n"
        "Для продолжения матча начните новый.",
        parse_mode="html",
        reply_markup=InlineKeyboardBuilder()
        .add(InlineKeyboardButton(text="⚽ Начать новый матч", callback_data="withbot"))
        .as_markup()
    )
    await callback.answer()


@public_router_pvp.callback_query(F.data == "page_info")
@handle_old_callback
async def page_info_handler(callback: CallbackQuery):
    """Обработчик информационной кнопки страницы"""
    await callback.answer("Текущая страница", show_alert=False)

#PVP
# В mamopvp.py добавляем в начало файла после импортов:

# Состояния для PvP
class PvPStates(StatesGroup):
    waiting_for_opponent = State()  # Ожидание соперника
    confirming_pvp = State()       # Подтверждение готовности к PvP
    playing_pvp = State()          # Идет PvP матч

# Глобальные словари для управления PvP очередью и матчами
pvp_queue = {}  # {user_id: {'message_id': int, 'chat_id': int, 'time_joined': datetime}}
active_pvp_matches = {}  # {match_id: {'player1': user_id, 'player2': user_id, ...}}

# Таблица для статистики PvP
def init_pvp_tables():
    """Инициализирует таблицы для PvP"""
    try:
        # Создаем таблицу для очереди поиска PvP
        db_operation('''
        CREATE TABLE IF NOT EXISTS pvp_queue (
            user_id INTEGER PRIMARY KEY,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            elo_rating INTEGER,
            FOREIGN KEY (user_id) REFERENCES all_users (id)
        )
        ''')
        
        # Создаем таблицу для истории PvP матчей
        db_operation('''
        CREATE TABLE IF NOT EXISTS pvp_match_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id TEXT NOT NULL,
            player1_id INTEGER NOT NULL,
            player2_id INTEGER NOT NULL,
            player1_score INTEGER NOT NULL,
            player2_score INTEGER NOT NULL,
            player1_elo_change INTEGER NOT NULL,
            player2_elo_change INTEGER NOT NULL,
            match_duration INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player1_id) REFERENCES all_users (id),
            FOREIGN KEY (player2_id) REFERENCES all_users (id)
        )
        ''')
        
        # Индексы для быстрого поиска
        db_operation('''
        CREATE INDEX IF NOT EXISTS idx_pvp_queue_time 
        ON pvp_queue(joined_at)
        ''')
        
        db_operation('''
        CREATE INDEX IF NOT EXISTS idx_pvp_history_match 
        ON pvp_match_history(match_id)
        ''')
        
        logger.info("✅ Таблицы PvP инициализированы")
    except Exception as e:
        logger.error(f"❌ Ошибка при создании таблиц PvP: {e}")

# Вызываем инициализацию в начале
init_pvp_tables()

# Функции для работы с PvP очередью
def add_to_pvp_queue(user_id: int, elo_rating: int):
    """Добавляет пользователя в очередь PvP"""
    try:
        # Удаляем старые записи пользователя
        db_operation("DELETE FROM pvp_queue WHERE user_id = ?", (user_id,))
        
        # Добавляем новую запись
        db_operation(
            "INSERT INTO pvp_queue (user_id, elo_rating, joined_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (user_id, elo_rating)
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка при добавлении в очередь PvP: {e}")
        return False

def remove_from_pvp_queue(user_id: int):
    """Удаляет пользователя из очереди PvP"""
    try:
        db_operation("DELETE FROM pvp_queue WHERE user_id = ?", (user_id,))
        # Также удаляем из глобальной очереди
        if user_id in pvp_queue:
            del pvp_queue[user_id]
        return True
    except Exception as e:
        logger.error(f"Ошибка при удалении из очереди PvP: {e}")
        return False

def get_pvp_queue_size():
    """Возвращает количество игроков в очереди"""
    try:
        result = db_operation("SELECT COUNT(*) FROM pvp_queue", fetch=True)
        return result[0][0] if result else 0
    except Exception as e:
        logger.error(f"Ошибка при получении размера очереди: {e}")
        return 0

async def show_pvp_confirmation_to_both_players(user_id: int, opponent_info: dict, bot: Bot):
    """Показывает подтверждение готовности к матчу обоим игрокам"""
    try:
        opponent_id = opponent_info['opponent_id']
        
        # Получаем составы обоих игроков
        user_squad = get_user_squad(user_id)
        opponent_squad = get_user_squad(opponent_id)
        
        # Получаем ELO обоих игроков
        user_elo_data = get_user_elo(user_id)
        opponent_elo_data = get_user_elo(opponent_id)
        
        user_elo = user_elo_data['elo_rating'] if user_elo_data else 200
        opponent_elo = opponent_elo_data['elo_rating'] if opponent_elo_data else 200
        
        # Получаем названия команд
        user_squad_name = user_squad.get('squad_name', f'Команда {user_id}') if user_squad else f'Команда {user_id}'
        opponent_squad_name = opponent_squad.get('squad_name', f'Команда {opponent_id}') if opponent_squad else f'Команда {opponent_id}'
        
        # Получаем детали составов
        user_squad_details = await format_squad_details(user_squad) if user_squad else "❌ Состав не найден"
        opponent_squad_details = await format_squad_details(opponent_squad) if opponent_squad else "❌ Состав не найден"
        
        # 🔥 ВАЖНО: Создаем уникальный ID матча
        match_id = f"pvp_{min(user_id, opponent_id)}_{max(user_id, opponent_id)}_{int(time.time())}"
        
        # Формируем сообщение для ПЕРВОГО игрока
        user_message_text = (
            f"✅ <b>СОПЕРНИК НАЙДЕН!</b>\n\n"
            f"🏆 <b>Ваша команда:</b> {user_squad_name}\n"
            f"🏅 <b>Ваш ELO:</b> {user_elo}\n"
            f"{user_squad_details}\n"
            f"{'='*40}\n\n"
            f"👤 <b>Команда соперника:</b> {opponent_squad_name}\n"
            f"🎯 <b>ELO соперника:</b> {opponent_elo}\n"
            f"📊 <b>Разница в ELO:</b> {abs(user_elo - opponent_elo)}\n"
            f"{opponent_squad_details}\n"
            f"{'='*40}\n\n"
            f"⚽ <b>Правила PvP:</b>\n"
            f"• 30 секунд игрового времени\n"
            f"• Влияние редкости карточек\n"
            f"• Изменение ELO: ±5-15\n\n"
            f"<i>Подтвердите готовность к матчу:</i>"
        )
        
        # Формируем сообщение для ВТОРОГО игрока
        opponent_message_text = (
            f"✅ <b>СОПЕРНИК НАЙДЕН!</b>\n\n"
            f"🏆 <b>Ваша команда:</b> {opponent_squad_name}\n"
            f"🏅 <b>Ваш ELO:</b> {opponent_elo}\n"
            f"{opponent_squad_details}\n"
            f"{'='*40}\n\n"
            f"👤 <b>Команда соперника:</b> {user_squad_name}\n"
            f"🎯 <b>ELO соперника:</b> {user_elo}\n"
            f"📊 <b>Разница в ELO:</b> {abs(user_elo - opponent_elo)}\n"
            f"{user_squad_details}\n"
            f"{'='*40}\n\n"
            f"⚽ <b>Правила PvP:</b>\n"
            f"• 30 секунд игрового времени\n"
            f"• Влияние редкости карточек\n"
            f"• Изменение ELO: ±5-15\n\n"
            f"<i>Подтвердите готовность к матчу:</i>"
        )
        
        # Создаем клавиатуру с кнопками подтверждения
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="✅ Готов к матчу",
                callback_data="confirm_pvp_match"
            ),
            InlineKeyboardButton(
                text="❌ Отказаться",
                callback_data="cancel_pvp_match"
            )
        )
        
        # 🔥 Отправляем НОВЫЕ сообщения с подтверждением обоим игрокам
        try:
            user_message = await bot.send_message(
                chat_id=user_id,
                text=user_message_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
            
            opponent_message = await bot.send_message(
                chat_id=opponent_id,
                text=opponent_message_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
            
            # Сохраняем состояние подтверждения для ОБОИХ игроков
            pvp_confirmation_states[user_id] = {
                'opponent_id': opponent_id,
                'match_id': match_id,
                'confirmed': False,
                'confirmed_at': None,
                'message_id': user_message.message_id,
                'chat_id': user_message.chat.id,
                'squad_name': user_squad_name,
                'user_elo': user_elo
            }
            
            pvp_confirmation_states[opponent_id] = {
                'opponent_id': user_id,
                'match_id': match_id,
                'confirmed': False,
                'confirmed_at': None,
                'message_id': opponent_message.message_id,
                'chat_id': opponent_message.chat.id,
                'squad_name': opponent_squad_name,
                'user_elo': opponent_elo
            }
            
            logger.info(f"✅ Сообщения подтверждения отправлены обоим игрокам: {user_id} и {opponent_id}")
            
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщений подтверждения: {e}")
            # Если не удалось отправить, возвращаем в очередь
            add_to_pvp_queue(user_id, user_elo)
            add_to_pvp_queue(opponent_id, opponent_elo)
        
    except Exception as e:
        logger.error(f"Ошибка в show_pvp_confirmation_to_both_players: {e}")
        import traceback
        logger.error(f"Трейсбэк: {traceback.format_exc()}")


def find_pvp_opponent(user_id: int, max_elo_diff: int = 9999):
    """Ищет соперника для PvP матча - РАЗРЕШЕН ЛЮБОЙ ELO"""
    try:
        # Получаем ELO текущего пользователя
        user_elo_result = db_operation(
            "SELECT elo_rating FROM user_elo WHERE user_id = ?", 
            (user_id,), 
            fetch=True
        )
        
        if not user_elo_result:
            return None
        
        user_elo = user_elo_result[0][0]
        
        # Ищем ЛЮБОГО соперника в очереди
        opponent_result = db_operation(
            """SELECT user_id, elo_rating 
               FROM pvp_queue 
               WHERE user_id != ? 
               ORDER BY joined_at ASC 
               LIMIT 1""",
            (user_id,),
            fetch=True
        )
        
        if opponent_result:
            opponent_id, opponent_elo = opponent_result[0]
            
            # УДАЛЯЕМ СОПЕРНИКА ИЗ ОЧЕРЕДИ сразу при нахождении
            remove_from_pvp_queue(opponent_id)
            
            # ⚠️ ДОБАВЛЯЕМ УДАЛЕНИЕ ТЕКУЩЕГО ПОЛЬЗОВАТЕЛЯ ТОЖЕ!
            remove_from_pvp_queue(user_id)
            
            return {
                'opponent_id': opponent_id,
                'opponent_elo': opponent_elo,
                'elo_difference': abs(user_elo - opponent_elo)
            }
        
        return None
        
    except Exception as e:
        logger.error(f"Ошибка при поиске соперника: {e}")
        return None

# Модифицируем обработчик для "против игрока"
@public_router_pvp.callback_query(F.data == "withplayer")
@handle_old_callback
async def player_play_match(callback: CallbackQuery, state: FSMContext):
    """Начинает поиск PvP матча в одном сообщении - ИСПРАВЛЕНО"""
    await callback.answer()
    user_id = callback.from_user.id
    
    try:
        # Проверяем наличие состава
        user_squad = get_user_squad(user_id)
        
        if not user_squad:
            await callback.message.edit_text(
                "❌ <b>У вас нет состава!</b>\n\n"
                "Для PvP матчей сначала создайте состав.",
                parse_mode="html",
                reply_markup=InlineKeyboardBuilder()
                .add(InlineKeyboardButton(text="👥 Создать состав", callback_data="sostav"))
                .as_markup()
            )
            await callback.answer()
            return
        
        # Получаем ELO пользователя
        user_elo_data = get_user_elo(user_id)
        if not user_elo_data:
            await callback.answer("❌ Ошибка: не найден рейтинг", show_alert=True)
            return
        
        user_elo = user_elo_data['elo_rating']
        
        # Получаем название команды пользователя
        squad_name = user_squad.get('squad_name', f'Команда {user_id}')
        
        message_text = (
            f"🔍 <b>НАЧАЛО ПОИСКА СОПЕРНИКА</b>\n\n"
            f"🏆 <b>Ваша команда:</b> {squad_name}\n"
            f"🏅 <b>Ваш ELO:</b> {user_elo}\n"
            f"👥 <b>Игроков в очереди:</b> 0\n\n"
            f"<i>Подготовка к поиску...</i>"
        )
        
        # Создаем клавиатуру для отмены
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="❌ Отменить поиск",
                callback_data="cancel_pvp_search"
            )
        )
        
        await callback.message.edit_text(
            message_text,
            parse_mode="html",
            reply_markup=builder.as_markup()
        )
        
        # Сохраняем состояние
        await state.set_state(PvPStates.waiting_for_opponent)
        await state.update_data({
            'user_squad': user_squad,
            'user_elo': user_elo,
            'squad_name': squad_name,
            'waiting_start_time': datetime.now(),
            'search_message_id': callback.message.message_id,
            'chat_id': callback.message.chat.id
        })
        
        # Добавляем в очередь
        add_to_pvp_queue(user_id, user_elo)
        
        # Запускаем задачу поиска
        asyncio.create_task(
            run_pvp_search_in_single_message(
                callback.message.chat.id,
                callback.message.message_id,
                user_id,
                state,
                callback.bot
            )
        )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в player_play_match для пользователя {user_id}: {e}")
        await callback.answer("❌ Ошибка при поиске матча", show_alert=True)


async def run_pvp_search_in_single_message(chat_id: int, message_id: int, user_id: int, state: FSMContext, bot: Bot):
    """Запускает поиск PvP в одном сообщении с обновлением статуса - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    try:
        global search_messages_dict
        
        # Сохраняем информацию о сообщении поиска
        search_messages_dict[user_id] = (chat_id, message_id)
        
        state_data = await state.get_data()
        user_elo = state_data.get('user_elo', 200)
        squad_name = state_data.get('squad_name', f'Команда {user_id}')
        search_start_time = datetime.now()
        timeout = 30
        
        queue_size = get_pvp_queue_size()
        
        # Обновляем сообщение с началом поиска
        new_message_id = await update_search_message(
            chat_id, message_id, user_id, user_elo, squad_name, 0, timeout, bot, 
            queue_size=queue_size
        )
        
        # Если вернулся новый message_id, обновляем
        if new_message_id:
            message_id = new_message_id
            search_messages_dict[user_id] = (chat_id, message_id)
        
        await asyncio.sleep(2)
        
        for elapsed in range(2, timeout + 1):
            # Проверяем, не отменил ли пользователь поиск
            current_state = await state.get_state()
            if current_state != PvPStates.waiting_for_opponent.state:
                remove_from_pvp_queue(user_id)
                logger.info(f"Пользователь {user_id} отменил поиск")
                return
            
            # Проверяем, существует ли еще наше сообщение
            if user_id not in search_messages_dict:
                logger.info(f"Сообщение поиска удалено для пользователя {user_id}, останавливаем поиск")
                remove_from_pvp_queue(user_id)
                return
            
            # Ищем соперника
            opponent_info = find_pvp_opponent(user_id)
            
            if opponent_info:
                logger.info(f"Найден соперник {opponent_info['opponent_id']} для пользователя {user_id}")
                
                # СНАЧАЛА обновляем сообщение с найденным соперником
                new_message_id = await update_search_message(
                    chat_id, message_id, user_id, user_elo, squad_name, elapsed, timeout, bot,
                    queue_size=queue_size, found=True, opponent_info=opponent_info
                )
                
                # Затем очищаем сообщения поиска
                await cleanup_search_messages_on_match_found(user_id, opponent_info['opponent_id'], bot)
                
                # Показываем подтверждение готовности
                await show_pvp_confirmation_to_both_players(
                    user_id, opponent_info, bot
                )
                
                return
            
            queue_size = get_pvp_queue_size()
            
            # Обновляем сообщение с прогрессом
            new_message_id = await update_search_message(
                chat_id, message_id, user_id, user_elo, squad_name, elapsed, timeout, bot, 
                queue_size=queue_size
            )
            
            # Если вернулся новый message_id, обновляем
            if new_message_id:
                message_id = new_message_id
                search_messages_dict[user_id] = (chat_id, message_id)
            
            await asyncio.sleep(1)
        
        # Время вышло
        logger.info(f"Время поиска истекло для пользователя {user_id}")
        remove_from_pvp_queue(user_id)
        
        # Проверяем, существует ли сообщение перед обновлением
        if user_id in search_messages_dict:
            await cancel_pvp_search_timeout_in_single_message(
                chat_id, message_id, user_id, state, bot
            )
        else:
            # Просто отправляем новое сообщение
            await bot.send_message(
                chat_id=chat_id,
                text="⏱️ <b>Время поиска истекло</b>\n\n"
                     "Не удалось найти соперника за 30 секунд.",
                parse_mode="html"
            )
        
    except Exception as e:
        logger.error(f"Ошибка в run_pvp_search_in_single_message: {e}")
        remove_from_pvp_queue(user_id)
        try:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ <b>ОШИБКА ПРИ ПОИСКЕ</b>\n\nПроизошла техническая ошибка. Попробуйте снова.",
                parse_mode="html"
            )
        except:
            pass

async def cleanup_search_messages_on_match_found(user_id: int, opponent_id: int, bot: Bot):
    """Очищает сообщения поиска при нахождении соперника"""
    try:
        logger.info(f"🧹 Очистка сообщений поиска при найденном матче: user_id={user_id}, opponent_id={opponent_id}")
        
        global search_messages_dict
        
        # 1. Очищаем сообщения из search_messages_dict
        messages_to_delete = []
        
        # Для текущего пользователя
        if user_id in search_messages_dict:
            messages_to_delete.append((user_id, search_messages_dict[user_id]))
        
        # Для соперника
        if opponent_id in search_messages_dict:
            messages_to_delete.append((opponent_id, search_messages_dict[opponent_id]))
        
        # Удаляем все найденные сообщения
        for uid, (chat_id, message_id) in messages_to_delete:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message_id)
                logger.info(f"✅ Удалено сообщение поиска пользователя {uid}")
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщение поиска пользователя {uid}: {e}")
            finally:
                # Всегда удаляем из словаря
                if uid in search_messages_dict:
                    del search_messages_dict[uid]
        
        # 2. Очищаем состояния поиска
        remove_from_pvp_queue(user_id)
        remove_from_pvp_queue(opponent_id)
        
        logger.info(f"✅ Очистка завершена для матча {user_id} vs {opponent_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при очистке сообщений при найденном матче: {e}")

async def update_search_message(chat_id: int, message_id: int, user_id: int, user_elo: int, squad_name: str,
                               elapsed: int, timeout: int, bot: Bot,
                               queue_size: int = 0, found: bool = False, 
                               opponent_info: dict = None):
    """Обновляет сообщение поиска с показом составов - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    try:
        # Если сообщение было удалено (ошибка "not found"), прекращаем попытки обновления
        global search_messages_dict
        
        # Проверяем, существует ли еще это сообщение в нашем словаре
        if user_id in search_messages_dict:
            stored_chat_id, stored_message_id = search_messages_dict[user_id]
            if stored_chat_id != chat_id or stored_message_id != message_id:
                # ID сообщения изменилось, обновляем
                search_messages_dict[user_id] = (chat_id, message_id)
        else:
            # Если нет в словаре, добавляем
            search_messages_dict[user_id] = (chat_id, message_id)
        
        if found and opponent_info:
            logger.info(f"Обновление сообщения поиска: СОПЕРНИК НАЙДЕН для пользователя {user_id}")
            
            # Соперник найден
            progress_bar = "🟩" * 20  # Полная шкала
            
            opponent_id = opponent_info.get('opponent_id')
            
            # Получаем составы обоих игроков
            user_squad = get_user_squad(user_id)
            opponent_squad = get_user_squad(opponent_id) if opponent_id else None
            
            # Получаем детальные описания составов
            user_squad_details = await format_squad_details(user_squad) if user_squad else "❌ Состав не найден"
            opponent_squad_details = await format_squad_details(opponent_squad) if opponent_squad else "❌ Состав не найден"
            
            # Получаем название команды соперника
            opponent_squad_name = opponent_squad.get('squad_name', f'Команда {opponent_id}') if opponent_squad else f'Команда {opponent_id}'
            
            message_text = (
                f"✅ <b>СОПЕРНИК НАЙДЕН!</b>\n\n"
                f"🏆 <b>Ваша команда:</b> {squad_name}\n"
                f"🏅 <b>Ваш ELO:</b> {user_elo}\n"
                f"{user_squad_details}\n"
                f"{'='*40}\n\n"
                f"👤 <b>Команда соперника:</b> {opponent_squad_name}\n"
                f"🎯 <b>ELO соперника:</b> {opponent_info.get('opponent_elo', 200)}\n"
                f"📊 <b>Разница в ELO:</b> {opponent_info.get('elo_difference', 0)}\n"
                f"{opponent_squad_details}\n"
                f"{'='*40}\n\n"
                f"⏱️ <b>Время поиска:</b> {elapsed} секунд\n"
                f"{progress_bar}\n\n"
                f"⚽ <b>Правила PvP:</b>\n"
                f"• 30 секунд игрового времени\n"
                f"• Влияние редкости карточек\n"
                f"• Изменение ELO: ±5-15\n\n"
                f"<i>Подтвердите готовность к матчу:</i>"
            )
            
        else:
            # Идет поиск
            if timeout <= 0:
                timeout = 1
            
            progress_percentage = min(100, int((elapsed / timeout) * 100))
            progress_bars = int(progress_percentage / 5)
            progress_bar = "🟩" * progress_bars + "⬜" * (20 - progress_bars)
            
            remaining = timeout - elapsed if timeout > elapsed else 0
            
            message_text = (
                f"🔍 <b>ПОИСК СОПЕРНИКА</b>\n\n"
                f"🏆 <b>Ваша команда:</b> {squad_name}\n"
                f"🏅 <b>Ваш ELO:</b> {user_elo}\n"
                f"👥 <b>Игроков в очереди:</b> {queue_size}\n\n"
                f"⏱️ <b>Прошло:</b> {elapsed} секунд\n"
                f"⏳ <b>Осталось:</b> {remaining} секунд\n\n"
                f"{progress_bar} {progress_percentage}%\n\n"
                f"<i>Ищем соперника...</i>"
            )
        
        # Создаем клавиатуру
        builder = InlineKeyboardBuilder()
        
        if found:
            builder.row(
                InlineKeyboardButton(
                    text="✅ Готов к матчу",
                    callback_data="confirm_pvp_match"
                ),
                InlineKeyboardButton(
                    text="❌ Отказаться",
                    callback_data="cancel_pvp_match"
                )
            )
        else:
            builder.row(
                InlineKeyboardButton(
                    text="❌ Отменить поиск",
                    callback_data="cancel_pvp_search"
                )
            )
        
        # Используем безопасное редактирование с обработкой ошибок
        try:
            success = await safe_edit_message_text(
                bot=bot,
                chat_id=chat_id,
                message_id=message_id,
                text=message_text,
                parse_mode="html",
                reply_markup=builder.as_markup(),
                min_update_interval=1.0  # Увеличиваем интервал до 1 секунды
            )
            
            if not success:
                # Проверяем, не удалено ли сообщение
                try:
                    # Пробуем отправить тестовое сообщение
                    await bot.send_chat_action(chat_id=chat_id, action='typing')
                    
                    # Если дошло до сюда, сообщение, вероятно, было удалено
                    # Создаем новое сообщение поиска
                    logger.info(f"Сообщение поиска было удалено, создаем новое для пользователя {user_id}")
                    new_message = await bot.send_message(
                        chat_id=chat_id,
                        text=message_text,
                        parse_mode="html",
                        reply_markup=builder.as_markup()
                    )
                    
                    # Обновляем словарь с новым ID сообщения
                    search_messages_dict[user_id] = (chat_id, new_message.message_id)
                    
                    return new_message.message_id
                    
                except Exception as test_error:
                    # Не удалось отправить даже действие - вероятно, чат недоступен
                    logger.warning(f"Чат {chat_id} недоступен для пользователя {user_id}: {test_error}")
                    # Удаляем пользователя из словаря
                    if user_id in search_messages_dict:
                        del search_messages_dict[user_id]
                    return None
                
        except Exception as e:
            error_msg = str(e).lower()
            if "message to edit not found" in error_msg or "message not found" in error_msg:
                logger.info(f"Сообщение поиска {chat_id}_{message_id} было удалено для пользователя {user_id}")
                # Удаляем запись из словаря
                if user_id in search_messages_dict:
                    del search_messages_dict[user_id]
            else:
                logger.error(f"Другая ошибка при обновлении сообщения поиска для {user_id}: {e}")
        
    except Exception as e:
        logger.error(f"Критическая ошибка в update_search_message для пользователя {user_id}: {e}")
        # Не выбрасываем исключение дальше, чтобы не прерывать поиск




async def get_user_team_name(user_id: int) -> str:
    """Получает название команды пользователя. Если нет - 'Команда пользователя'"""
    try:
        # Пытаемся получить название команды из состава
        user_squad = get_user_squad(user_id)
        
        if user_squad and user_squad.get('squad_name'):
            return user_squad.get('squad_name')
        
        # Если нет названия команды, возвращаем стандартное имя
        return "Команда пользователя"
        
    except Exception as e:
        logger.error(f"Ошибка при получении названия команды пользователя {user_id}: {e}")
        return "Команда пользователя"


async def start_pvp_confirmation_in_single_message(chat_id: int, message_id: int, user_id: int, 
                                                  opponent_info: dict, state: FSMContext, bot: Bot):
    """Начинает подтверждение PvP в том же сообщении"""
    try:
        opponent_id = opponent_info['opponent_id']
        
        # Получаем ELO пользователя
        user_elo_data = get_user_elo(user_id)
        user_elo = user_elo_data['elo_rating'] if user_elo_data else 200
        
        # Получаем название команды пользователя
        user_squad = get_user_squad(user_id)
        user_team_name = user_squad.get('squad_name', f'Команда {user_id}') if user_squad else f'Команда {user_id}'
        
        # 🔥 ВАЖНОЕ ИСПРАВЛЕНИЕ: Сохраняем состояние для ПЕРВОГО игрока!
        # Создаем уникальный ID матча (должен быть таким же как у второго игрока)
        match_id = f"pvp_{min(user_id, opponent_id)}_{max(user_id, opponent_id)}_{int(time.time())}"
        
        # Сохраняем состояние для ПЕРВОГО игрока
        pvp_confirmation_states[user_id] = {
            'opponent_id': opponent_id,
            'match_id': match_id,
            'confirmed': False,
            'confirmed_at': None,
            'message_id': message_id,
            'chat_id': chat_id,
            'squad_name': user_team_name,
            'user_elo': user_elo
        }
        
        # Также сохраняем в состоянии FSM
        await state.set_state(PvPStates.confirming_pvp)
        await state.update_data({
            'opponent_id': opponent_id,
            'match_id': match_id,
            'confirm_message_id': message_id,
            'confirm_chat_id': chat_id
        })
        
        logger.info(f"✅ Состояние подтверждения создано для первого игрока {user_id}")
        
    except Exception as e:
        logger.error(f"Ошибка в start_pvp_confirmation_in_single_message: {e}")


async def notify_opponent_about_found_match(user_id: int, opponent_id: int, user_squad_name: str, bot: Bot, opponent_info: dict):
    """Уведомляет соперника о найденном матче - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    try:
        # Получаем данные соперника
        logger.info(f"Уведомление соперника {opponent_id} о найденном матче")
        
        opponent_squad = get_user_squad(opponent_id)
        opponent_elo_data = get_user_elo(opponent_id)
        opponent_elo = opponent_elo_data['elo_rating'] if opponent_elo_data else 200
        
        # Получаем детальные описания составов
        user_squad = get_user_squad(user_id)
        opponent_squad_details = await format_squad_details(opponent_squad) if opponent_squad else "❌ Состав не найден"
        user_squad_details = await format_squad_details(user_squad) if user_squad else "❌ Состав не найден"
        
        # Получаем названия команд
        opponent_squad_name = opponent_squad.get('squad_name', f'Команда {opponent_id}') if opponent_squad else f'Команда {opponent_id}'
        
        # Формируем сообщение для соперника
        message_text = (
            f"✅ <b>СОПЕРНИК НАЙДЕН!</b>\n\n"
            f"🏆 <b>Ваша команда:</b> {opponent_squad_name}\n"
            f"🏅 <b>Ваш ELO:</b> {opponent_elo}\n"
            f"{opponent_squad_details}\n"
            f"{'='*40}\n\n"
            f"👤 <b>Команда соперника:</b> {user_squad_name}\n"
            f"🎯 <b>ELO соперника:</b> {opponent_info.get('opponent_elo', 200)}\n"
            f"📊 <b>Разница в ELO:</b> {opponent_info.get('elo_difference', 0)}\n"
            f"{user_squad_details}\n"
            f"{'='*40}\n\n"
            f"⚽ <b>Правила PvP:</b>\n"
            f"• 30 секунд игрового времени\n"
            f"• Влияние редкости карточек\n"
            f"• Изменение ELO: ±5-15\n\n"
            f"<i>Подтвердите готовность к матчу:</i>"
        )
        
        # Создаем клавиатуру для соперника
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="✅ Готов к матчу",
                callback_data="confirm_pvp_match"
            ),
            InlineKeyboardButton(
                text="❌ Отказаться",
                callback_data="cancel_pvp_match"
            )
        )
        
        # Отправляем новое сообщение сопернику (не редактируем старое)
        try:
            opponent_message = await bot.send_message(
                chat_id=opponent_id,
                text=message_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
            
            # Сохраняем информацию о сообщении
            if opponent_id not in search_messages_dict:
                search_messages_dict[opponent_id] = (opponent_message.chat.id, opponent_message.message_id)
            
            logger.info(f"Отправлено сообщение сопернику {opponent_id} о найденном матче")
            
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение сопернику {opponent_id}: {e}")
            # Если не удалось отправить, возможно, бот заблокирован
            return
        
        # 🔥 ВАЖНОЕ ИСПРАВЛЕНИЕ: Сохраняем состояние для второго игрока!
        # Создаем уникальный ID матча
        match_id = f"pvp_{min(user_id, opponent_id)}_{max(user_id, opponent_id)}_{int(time.time())}"
        
        # Сохраняем состояние для ВТОРОГО игрока (соперника)
        pvp_confirmation_states[opponent_id] = {
            'opponent_id': user_id,  # Противник - это первый игрок
            'match_id': match_id,
            'confirmed': False,
            'confirmed_at': None,
            'message_id': opponent_message.message_id,
            'chat_id': opponent_message.chat.id,
            'squad_name': opponent_squad_name,
            'user_elo': opponent_elo
        }
        
        logger.info(f"✅ Состояние подтверждения создано для второго игрока {opponent_id}")
        
    except Exception as e:
        logger.error(f"Ошибка при уведомлении соперника {opponent_id}: {e}")
        import traceback
        logger.error(f"Трейсбэк: {traceback.format_exc()}")

async def cancel_pvp_search_timeout_in_single_message(chat_id: int, message_id: int, 
                                                     user_id: int, state: FSMContext, bot: Bot):
    """Отменяет поиск по таймауту в том же сообщении"""
    try:
        # Удаляем из очереди
        remove_from_pvp_queue(user_id)
        
        # Очищаем состояние
        await state.clear()
        
        message_text = (
            "⏱️ <b>ВРЕМЯ ПОИСКА ИСТЕКЛО</b>\n\n"
            "Поиск соперника занял более 30 секунд.\n"
            "Не удалось найти подходящего соперника.\n\n"
            "<i>Попробуйте позже или сыграйте против бота</i>"
        )
        
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="🤖 Против бота", callback_data="withbot"),
            InlineKeyboardButton(text="🔍 Попробовать снова", callback_data="withplayer")
        )
        builder.row(
            InlineKeyboardButton(text="🎮 Игровое меню", callback_data="back_to_play_menu")
        )
        
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=message_text,
            parse_mode="html",
            reply_markup=builder.as_markup()
        )
        
    except Exception as e:
        logger.error(f"Ошибка при отмене поиска по таймауту: {e}")

async def find_pvp_opponent_task(chat_id: int, message_id: int, user_id: int, state: FSMContext, bot: Bot):
    """Задача поиска соперника с обновлением статуса"""
    try:
        # Ждем 5 секунд перед началом поиска
        await asyncio.sleep(5)
        
        state_data = await state.get_data()
        waiting_start_time = state_data.get('waiting_start_time')
        
        if not waiting_start_time:
            return
        
        start_time = datetime.now()
        timeout = 30  # 30 секунд на поиск
        
        while (datetime.now() - start_time).seconds < timeout:
            # Проверяем, не отменил ли пользователь поиск
            current_state = await state.get_state()
            if current_state != PvPStates.waiting_for_opponent.state:
                return
            
            # Ищем соперника
            opponent_info = find_pvp_opponent(user_id)
            
            if opponent_info:
                # Нашли соперника! Начинаем подтверждение матча
                await start_pvp_confirmation(
    chat_id, message_id, user_id, opponent_info, state, bot
)
                return
            
            # Обновляем сообщение с прогрессом
            elapsed = (datetime.now() - start_time).seconds
            remaining = timeout - elapsed
            
            queue_size = get_pvp_queue_size()
            
            message_text = (
                f"🔍 <b>ПОИСК СОПЕРНИКА</b>\n\n"
                f"🏅 <b>Ваш ELO:</b> {state_data.get('user_elo', 200)}\n"
                f"👥 <b>Игроков в очереди:</b> {queue_size}\n\n"
                f"<i>Ищем соперника с похожим рейтингом...</i>\n\n"
                f"⏱️ <b>Прошло времени:</b> {elapsed} секунд\n"
                f"⏳ <b>Осталось:</b> {remaining} секунд\n\n"
                f"<i>Поиск займет до 30 секунд</i>"
            )
            
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(
                    text="❌ Отменить поиск",
                    callback_data="cancel_pvp_search"
                )
            )
            
            try:

                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=message_text,
                    parse_mode="html",
                    reply_markup=builder.as_markup()
                )
            except Exception as e:
                logger.error(f"Не удалось обновить сообщение: {e}")
            
            # Ждем перед следующей проверкой
            await asyncio.sleep(3)
        
        # Время вышло, отменяем поиск
        await cancel_pvp_search_timeout(chat_id, message_id, user_id, state,bot)
        
    except Exception as e:
        logger.error(f"Ошибка в find_pvp_opponent_task: {e}")

async def start_pvp_confirmation(chat_id: int, message_id: int, user_id: int, opponent_info: dict, state: FSMContext, bot: Bot):
    """Начинает процесс подтверждения PvP матча"""
    try:
        opponent_id = opponent_info['opponent_id']
        
        # ОЧИСТИМ СООБЩЕНИЯ ПОИСКА
        logger.info(f"Начало подтверждения PvP, очистка сообщений поиска")
        await cleanup_search_messages(user_id, opponent_id, bot)


        
        # 1. Сначала получаем данные текущего пользователя
        state_data = await state.get_data()
        user_squad = state_data.get('user_squad', {})
        user_elo = state_data.get('user_elo', 200)
        
        # 2. Определяем имя соперника ДО его использования
        opponent_name = ""
        try:
            opponent_user = await bot.get_chat(opponent_id)
            if opponent_user.username:
                opponent_name = f"@{opponent_user.username}"
            elif opponent_user.first_name:
                opponent_name = opponent_user.first_name
                if opponent_user.last_name:
                    opponent_name += f" {opponent_user.last_name}"
            else:
                opponent_name = f"Игрок {opponent_id}"
        except Exception as e:
            logger.error(f"Не удалось получить имя соперника {opponent_id}: {e}")
            opponent_name = f"Игрок {opponent_id}"
        
        # 3. Определяем имя текущего пользователя для соперника
        user_name = ""
        try:
            user = await bot.get_chat(user_id)
            if user.username:
                user_name = f"@{user.username}"
            elif user.first_name:
                user_name = user.first_name
                if user.last_name:
                    user_name += f" {user.last_name}"
            else:
                user_name = f"Игрок {user_id}"
        except Exception as e:
            logger.error(f"Не удалось получить имя пользователя {user_id}: {e}")
            user_name = f"Игрок {user_id}"
        
        # 4. Получаем ELO текущего пользователя
        user_elo_data = get_user_elo(user_id)
        user_elo_display = user_elo_data['elo_rating'] if user_elo_data else 200
        
        # 5. Получаем ELO соперника
        opponent_elo_data = get_user_elo(opponent_id)
        opponent_elo_display = opponent_elo_data['elo_rating'] if opponent_elo_data else 200
        
        # 6. Получаем состав соперника
        opponent_squad = get_user_squad(opponent_id)
        
        # 7. Сохраняем состояние для ЭТОГО пользователя
        await state.set_state(PvPStates.confirming_pvp)
        await state.update_data({
            'opponent_id': opponent_id,
            'opponent_name': opponent_name,
            'opponent_elo': opponent_info['opponent_elo'],
            'elo_difference': opponent_info['elo_difference'],
            'user_id': user_id,
            'user_elo': user_elo,
            'user_squad': user_squad,
            'match_info': opponent_info  # Сохраняем всю информацию о матче
        })
        
        # 8. Формируем сообщение с деталями матча для ТЕКУЩЕГО пользователя
        message_text = (
            f"🎮 <b>НАЙДЕН СОПЕРНИК!</b>\n\n"
            f"👤 <b>Соперник:</b> {opponent_name}\n"
            f"🏅 <b>Рейтинг соперника:</b> {opponent_info['opponent_elo']}\n"
            f"📊 <b>Разница в рейтинге:</b> {opponent_info['elo_difference']}\n\n"
            f"🏆 <b>Ваш состав:</b> {user_squad.get('squad_name', 'Мой состав')}\n"
            f"🏅 <b>Ваш рейтинг:</b> {user_elo}\n\n"
            f"⚽ <b>Правила PvP матча:</b>\n"
            f"• 30 секунд игрового времени\n"
            f"• Редкости карточек влияют на шанс гола\n"
            f"• За победу: +10-20 ELO (в зависимости от разницы)\n"
            f"• За поражение: -5-15 ELO\n"
            f"• За ничью: +0-10 ELO\n\n"
            f"<i>Подтвердите готовность к матчу:</i>"
        )
        
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="✅ Готов к матчу",
                callback_data="confirm_pvp_match"
            ),
            InlineKeyboardButton(
                text="❌ Отказаться",
                callback_data="cancel_pvp_match"
            )
        )
        
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=message_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
        except Exception as e:
            logger.error(f"Не удалось обновить сообщение: {e}")
        
        # 9. Удаляем обоих игроков из очереди
        remove_from_pvp_queue(user_id)
        remove_from_pvp_queue(opponent_id)
        
        # 10. Отправляем уведомление сопернику через ПРЯМОЕ сообщение
        try:
            # Формируем сообщение для соперника
            opponent_message_text = (
                f"🎮 <b>НАЙДЕН СОПЕРНИК!</b>\n\n"
                f"👤 <b>Соперник:</b> {user_name}\n"
                f"🏅 <b>Рейтинг соперника:</b> {user_elo_display}\n"
                f"📊 <b>Разница в рейтинге:</b> {opponent_info['elo_difference']}\n\n"
                f"🏆 <b>Ваш состав:</b> {(opponent_squad.get('squad_name', 'Мой состав') if opponent_squad else 'Мой состав')}\n"
                f"🏅 <b>Ваш рейтинг:</b> {opponent_elo_display}\n\n"
                f"⚽ <b>Правила PvP матча:</b>\n"
                f"• 30 секунд игрового времени\n"
                f"• Редкости карточек влияют на шанс гола\n"
                f"• За победу: +10-20 ELO (в зависимости от разницы)\n"
                f"• За поражение: -5-15 ELO\n"
                f"• За ничью: +0-10 ELO\n\n"
                f"<i>Подтвердите готовность к матчу:</i>"
            )
            
            opponent_builder = InlineKeyboardBuilder()
            opponent_builder.row(
                InlineKeyboardButton(
                    text="✅ Готов к матчу",
                    callback_data="confirm_pvp_match"
                ),
                InlineKeyboardButton(
                    text="❌ Отказаться",
                    callback_data="cancel_pvp_match"
                )
            )
            
            # Сохраняем ID сообщения для соперника в глобальном словаре
            opponent_message = await bot.send_message(
                chat_id=opponent_id,
                text=opponent_message_text,
                parse_mode="html",
                reply_markup=opponent_builder.as_markup()
            )
            
            # Сохраняем информацию о сообщении соперника
            pvp_queue[opponent_id] = {
                'message_id': opponent_message.message_id,
                'chat_id': opponent_id,
                'time_joined': datetime.now()
            }
            
            logger.info(f"Отправлено уведомление сопернику {opponent_id} о найденном матче")
            
        except Exception as e:
            logger.error(f"Ошибка при уведомлении соперника {opponent_id}: {e}")
            # Если не удалось отправить сообщение, возвращаем пользователя в очередь
            add_to_pvp_queue(user_id, user_elo)
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="❌ <b>ОШИБКА</b>\n\n"
                     "Не удалось связаться с соперником.\n"
                     "Вы возвращены в очередь поиска.",
                parse_mode="html",
                reply_markup=InlineKeyboardBuilder()
                .add(InlineKeyboardButton(text="🔍 Продолжить поиск", callback_data="withplayer"))
                .as_markup()
            )
            return
        
        logger.info(f"PvP подтверждение создано: {user_id} vs {opponent_id}")
        
    except Exception as e:
        logger.error(f"Ошибка в start_pvp_confirmation: {e}")
        import traceback
        logger.error(f"Трейсбэк: {traceback.format_exc()}")

@public_router_pvp.callback_query(F.data == "cancel_pvp_search")
@handle_old_callback
async def cancel_pvp_search_callback(callback: CallbackQuery, state: FSMContext):
    """Отменяет поиск PvP матча - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    user_id = callback.from_user.id
    
    try:
        logger.info(f"🔄 Отмена поиска PvP для пользователя {user_id}")
        
        # 1. Удаляем из очереди PvP в БД
        remove_from_pvp_queue(user_id)
        logger.info(f"✅ Пользователь {user_id} удален из очереди PvP")
        
        # 2. Очищаем состояние
        await state.clear()
        
        # 3. Показываем подтверждение отмены
        message_text = (
            "❌ <b>ПОИСК ОТМЕНЕН</b>\n\n"
            "Вы вышли из очереди поиска соперника.\n\n"
            "<i>Можете попробовать снова или сыграть против бота</i>"
        )
        
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="🔍 Попробовать снова", callback_data="withplayer"),
            InlineKeyboardButton(text="🤖 Против бота", callback_data="withbot")
        )
        builder.row(
            InlineKeyboardButton(text="🎮 Игровое меню", callback_data="back_to_play_menu")
        )
        
        # Пытаемся обновить текущее сообщение
        try:
            success = await safe_edit_message_text(
                bot=callback.bot,
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                text=message_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
            
            if not success:
                # Если не удалось обновить, отправляем новое сообщение
                await callback.message.answer(
                    message_text,
                    parse_mode="html",
                    reply_markup=builder.as_markup()
                )
                
        except Exception as e:
            # Если произошла ошибка, отправляем новое сообщение
            await callback.message.answer(
                message_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
        
        await callback.answer("🔍 Поиск отменен")
        logger.info(f"✅ Отмена поиска завершена для пользователя {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при отмене поиска: {e}")
        await callback.answer("❌ Ошибка при отмене поиска", show_alert=True)

async def cleanup_search_messages_on_cancel(user_id: int, opponent_id: int, bot: Bot, 
                                          current_chat_id: int = None, current_message_id: int = None):
    """Очищает сообщения поиска при отмене"""
    try:
        logger.info(f"🧹 Начало очистки сообщений поиска при отмене: user_id={user_id}, opponent_id={opponent_id}")
        
        messages_cleaned = 0
        
        # 1. Очищаем сообщение текущего пользователя
        if current_chat_id and current_message_id:
            try:
                await bot.delete_message(chat_id=current_chat_id, message_id=current_message_id)
                logger.info(f"✅ Удалено текущее сообщение поиска: chat_id={current_chat_id}, message_id={current_message_id}")
                messages_cleaned += 1
            except Exception as e:
                logger.warning(f"Не удалось удалить текущее сообщение: {e}")
        
        # 2. Очищаем из глобального словаря search_messages_dict
        global search_messages_dict
        
        # Для текущего пользователя
        if user_id in search_messages_dict:
            try:
                chat_id, message_id = search_messages_dict[user_id]
                await bot.delete_message(chat_id=chat_id, message_id=message_id)
                logger.info(f"✅ Удалено сообщение из search_messages_dict для пользователя {user_id}")
                messages_cleaned += 1
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщение из search_messages_dict для {user_id}: {e}")
            finally:
                del search_messages_dict[user_id]
        
        # Для соперника (если есть)
        if opponent_id and opponent_id in search_messages_dict:
            try:
                chat_id, message_id = search_messages_dict[opponent_id]
                await bot.delete_message(chat_id=chat_id, message_id=message_id)
                logger.info(f"✅ Удалено сообщение поиска соперника {opponent_id}")
                messages_cleaned += 1
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщение поиска соперника {opponent_id}: {e}")
            finally:
                del search_messages_dict[opponent_id]
        
        # 3. Очищаем из pvp_confirmation_states
        global pvp_confirmation_states
        
        # У текущего пользователя
        if user_id in pvp_confirmation_states:
            conf_state = pvp_confirmation_states[user_id]
            if 'message_id' in conf_state and 'chat_id' in conf_state:
                try:
                    await bot.delete_message(
                        chat_id=conf_state['chat_id'],
                        message_id=conf_state['message_id']
                    )
                    logger.info(f"✅ Удалено сообщение подтверждения для пользователя {user_id}")
                    messages_cleaned += 1
                except Exception as e:
                    logger.warning(f"Не удалось удалить сообщение подтверждения для {user_id}: {e}")
            del pvp_confirmation_states[user_id]
        
        # У соперника
        if opponent_id and opponent_id in pvp_confirmation_states:
            conf_state = pvp_confirmation_states[opponent_id]
            if 'message_id' in conf_state and 'chat_id' in conf_state:
                try:
                    await bot.delete_message(
                        chat_id=conf_state['chat_id'],
                        message_id=conf_state['message_id']
                    )
                    logger.info(f"✅ Удалено сообщение подтверждения для соперника {opponent_id}")
                    messages_cleaned += 1
                except Exception as e:
                    logger.warning(f"Не удалось удалить сообщение подтверждения для соперника {opponent_id}: {e}")
            del pvp_confirmation_states[opponent_id]
        
        logger.info(f"🧹 Очистка завершена. Удалено сообщений: {messages_cleaned}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при очистке сообщений поиска: {e}")

async def notify_opponent_about_cancellation(user_id: int, opponent_id: int, bot: Bot):
    """Уведомляет соперника об отмене матча"""
    try:
        # Пытаемся получить имя пользователя
        try:
            user = await bot.get_chat(user_id)
            user_name = f"@{user.username}" if user.username else user.first_name
        except:
            user_name = f"Игрок {user_id}"
        
        message_text = (
            f"❌ <b>СОПЕРНИК ОТМЕНИЛ МАТЧ</b>\n\n"
            f"<b>{user_name}</b> отменил матч.\n\n"
            f"<i>Вы будете возвращены в очередь поиска.</i>"
        )
        
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="🔍 Продолжить поиск", callback_data="withplayer"),
            InlineKeyboardButton(text="🎮 Игровое меню", callback_data="back_to_play_menu")
        )
        
        # Пытаемся отправить уведомление сопернику
        try:
            await bot.send_message(
                chat_id=opponent_id,
                text=message_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
            logger.info(f"✅ Соперник {opponent_id} уведомлен об отмене матча")
        except Exception as e:
            logger.warning(f"Не удалось уведомить соперника {opponent_id}: {e}")
        
        # Также удаляем соперника из очереди (на всякий случай)
        remove_from_pvp_queue(opponent_id)
        
    except Exception as e:
        logger.error(f"❌ Ошибка при уведомлении соперника: {e}")

async def cancel_pvp_search_timeout(chat_id: int, message_id: int, user_id: int, state: FSMContext, bot: Bot):
    """Автоматическая отмена поиска по таймауту"""
    try:
        # Удаляем из очереди
        remove_from_pvp_queue(user_id)
        
        # Очищаем состояние
        await state.clear()
        

        
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="⏱️ <b>ВРЕМЯ ВЫШЛО</b>\n\n"
                 "Поиск соперника занял более 30 секунд.\n\n"
                 "<i>Попробуйте позже или сыграйте против бота</i>",
            parse_mode="html",
            reply_markup=InlineKeyboardBuilder()
            .row(InlineKeyboardButton(text="🤖 Против бота", callback_data="withbot"))
            .row(InlineKeyboardButton(text="🎮 Игровое меню", callback_data="back_to_play_menu"))
            .as_markup()
        )
        
    except Exception as e:
        logger.error(f"Ошибка при отмене поиска по таймауту: {e}")

@public_router_pvp.callback_query(F.data == "confirm_pvp_match")
@handle_old_callback
async def confirm_pvp_match_callback(callback: CallbackQuery, state: FSMContext):
    """Подтверждение готовности к PvP матчу - ИСПРАВЛЕНО"""
    user_id = callback.from_user.id
    
    try:
        # Получаем данные из состояния пользователя
        state_data = await state.get_data()
        opponent_id = state_data.get('opponent_id')
        
        # Если opponent_id не в состоянии, ищем его в pvp_confirmation_states
        if not opponent_id:
            # Проверяем, есть ли запись о пользователе в pvp_confirmation_states
            user_confirmation = pvp_confirmation_states.get(user_id)
            if user_confirmation:
                opponent_id = user_confirmation.get('opponent_id')
            else:
                await callback.answer("❌ Ошибка: соперник не найден", show_alert=True)
                return
        
        if not opponent_id:
            await callback.answer("❌ Ошибка: соперник не найден", show_alert=True)
            return
        
        # Создаем уникальный ID матча
        match_id = f"pvp_{min(user_id, opponent_id)}_{max(user_id, opponent_id)}_{int(time.time())}"
        
        # Сохраняем подтверждение пользователя
        pvp_confirmation_states[user_id] = {
            'opponent_id': opponent_id,
            'match_id': match_id,
            'confirmed': True,
            'confirmed_at': datetime.now(),
            'message_id': callback.message.message_id,
            'chat_id': callback.message.chat.id
        }
        
        # Обновляем сообщение с подтверждением
        await callback.message.edit_text(
            "✅ <b>ВЫ ПОДТВЕРДИЛИ ГОТОВНОСТЬ</b>\n\n"
            "⏳ <i>Ожидаем подтверждения соперника...</i>",
            parse_mode="html"
        )
        
        await callback.answer("✅ Вы подтвердили готовность к матчу!")
        
        # Уведомляем соперника
        try:
            user_name = await get_user_display_name(callback.bot, user_id)
            await callback.bot.send_message(
                chat_id=opponent_id,
                text=f"✅ <b>СОПЕРНИК ГОТОВ!</b>\n\n"
                     f"<b>Соперник</b> подтвердил готовность к матчу.\n\n"
                     f"<i>Для начала матча подтвердите свою готовность в вашем сообщении с составом.</i>",
                parse_mode="html"
            )
        except Exception as e:
            logger.error(f"Ошибка при уведомлении соперника: {e}")
        
        # Проверяем, подтвердил ли уже соперник
        opponent_confirmation = pvp_confirmation_states.get(opponent_id)
        
        if opponent_confirmation and opponent_confirmation.get('confirmed'):
            # Проверяем, что это взаимное подтверждение
            is_mutual_confirmation = opponent_confirmation.get('opponent_id') == user_id
            
            if is_mutual_confirmation:
                # ОБА игрока подтвердили - запускаем матч!
                logger.info(f"Оба игрока подтвердили: {user_id} и {opponent_id}")
                
                # Используем match_id от любого игрока (они должны быть одинаковыми)
                final_match_id = match_id
                
                # Запускаем матч
                await start_pvp_match_for_both_players(
                    final_match_id, 
                    user_id, 
                    opponent_id, 
                    callback.bot
                )
                
    except Exception as e:
        logger.error(f"Ошибка в confirm_pvp_match_callback: {e}")
        import traceback
        logger.error(f"Трейсбэк: {traceback.format_exc()}")
        await callback.answer("❌ Ошибка при подтверждении", show_alert=True)

async def get_user_display_name(bot: Bot, user_id: int) -> str:
    """Получает отображаемое имя пользователя"""
    try:
        user = await bot.get_chat(user_id)
        if user.username:
            return f"@{user.username}"
        elif user.first_name:
            name = user.first_name
            if user.last_name:
                name += f" {user.last_name}"
            return name
        else:
            return f"Игрок {user_id}"
    except:
        return f"Игрок {user_id}"
async def cleanup_confirmation_messages(user1_id: int, user2_id: int, bot: Bot):
    """Очищает сообщения подтверждения у обоих игроков"""
    try:
        # У игрока 1
        if user1_id in pvp_confirmation_states:
            state1 = pvp_confirmation_states[user1_id]
            if 'confirm_message_id' in state1 and 'confirm_chat_id' in state1:
                try:
                    await bot.delete_message(
                        chat_id=state1['confirm_chat_id'],
                        message_id=state1['confirm_message_id']
                    )
                except:
                    pass
        
        # У игрока 2
        if user2_id in pvp_confirmation_states:
            state2 = pvp_confirmation_states[user2_id]
            if 'confirm_message_id' in state2 and 'confirm_chat_id' in state2:
                try:
                    await bot.delete_message(
                        chat_id=state2['confirm_chat_id'],
                        message_id=state2['confirm_message_id']
                    )
                except:
                    pass
                    
    except Exception as e:
        logger.error(f"Ошибка при очистке сообщений подтверждения: {e}")
async def start_pvp_match_for_both_players(match_id: str, player1_id: int, player2_id: int, bot: Bot):
    """Запускает PvP матч для обоих игроков - ИСПРАВЛЕНО (дублирование сообщений и ошибка started_matches)"""
    try:
        # ПРОВЕРЯЕМ, не запускался ли уже матч для этой пары
        match_key = f"{player1_id}_{player2_id}_{match_id}"
        
        # Используем глобальный словарь для отслеживания активных матчей вместо атрибута функции
        if not hasattr(start_pvp_match_for_both_players, 'active_matches_dict'):
            start_pvp_match_for_both_players.active_matches_dict = {}
        
        if match_key in start_pvp_match_for_both_players.active_matches_dict:
            logger.warning(f"Матч уже запущен для пары {player1_id}-{player2_id}")
            return
        
        # Добавляем в активные матчи
        start_pvp_match_for_both_players.active_matches_dict[match_key] = {
            'started_at': datetime.now(),
            'player1_id': player1_id,
            'player2_id': player2_id
        }
        
        # Получаем составы обоих игроков
        player1_squad = get_user_squad(player1_id)
        player2_squad = get_user_squad(player2_id)
        
        if not player1_squad or not player2_squad:
            logger.error(f"Один из игроков не имеет состава: {player1_id}, {player2_id}")
            
            # Уведомляем игроков об ошибке
            error_msg = "❌ <b>ОШИБКА ЗАПУСКА МАТЧА</b>\n\nОдин из игроков не имеет состава."
            
            try:
                await bot.send_message(player1_id, error_msg, parse_mode="html")
                await bot.send_message(player2_id, error_msg, parse_mode="html")
            except:
                pass
            
            # Удаляем из активных матчей
            if match_key in start_pvp_match_for_both_players.active_matches_dict:
                del start_pvp_match_for_both_players.active_matches_dict[match_key]
            return
        
        # Получаем ELO обоих игроков
        player1_elo = get_user_elo(player1_id)
        player2_elo = get_user_elo(player2_id)
        
        # Создаем детализированные составы
        player1_squad_details = {
            'gk': get_card_details(player1_squad.get('gk_card_id')),
            'op': get_card_details(player1_squad.get('op_card_id')),
            'nap1': get_card_details(player1_squad.get('nap1_card_id')),
            'nap2': get_card_details(player1_squad.get('nap2_card_id')),
            'squad_name': player1_squad.get('squad_name', 'Команда пользователя')
        }
        
        player2_squad_details = {
            'gk': get_card_details(player2_squad.get('gk_card_id')),
            'op': get_card_details(player2_squad.get('op_card_id')),
            'nap1': get_card_details(player2_squad.get('nap1_card_id')),
            'nap2': get_card_details(player2_squad.get('nap2_card_id')),
            'squad_name': player2_squad.get('squad_name', 'Команда пользователя')
        }
        
        # Создаем симулятор с двумя реальными игроками
        match_simulator = BotMatchSimulator(player1_squad_details)
        match_simulator.bot_squad = player2_squad_details
        
        # ОЧИЩАЕМ состояния игроков
        if player1_id in pvp_confirmation_states:
            del pvp_confirmation_states[player1_id]
        if player2_id in pvp_confirmation_states:
            del pvp_confirmation_states[player2_id]
        
        # Запускаем матч для обоих игроков (ОДИН раз!)
        logger.info(f"Запуск PvP матча: {player1_id} vs {player2_id}")
        
        await send_match_start_messages(
            match_id, 
            player1_id, player2_id, 
            player1_squad_details, player2_squad_details,
            player1_elo, player2_elo, 
            bot
        )
        await cleanup_search_messages(player1_id, player2_id, bot)
        # Очищаем запись о запущенном матче через некоторое время
        asyncio.create_task(cleanup_match_record_after_delay(match_key, 60))
        
    except Exception as e:
        logger.error(f"Ошибка при запуске PvP матча: {e}")
        import traceback
        logger.error(f"Трейсбэк: {traceback.format_exc()}")
        
        # Удаляем из активных матчей при ошибке
        match_key = f"{player1_id}_{player2_id}_{match_id}"
        if hasattr(start_pvp_match_for_both_players, 'active_matches_dict'):
            if match_key in start_pvp_match_for_both_players.active_matches_dict:
                del start_pvp_match_for_both_players.active_matches_dict[match_key]

async def cleanup_match_record_after_delay(match_key: str, delay_seconds: int = 60):
    """Очищает запись о матче через указанное время"""
    await asyncio.sleep(delay_seconds)
    
    if hasattr(start_pvp_match_for_both_players, 'active_matches_dict'):
        if match_key in start_pvp_match_for_both_players.active_matches_dict:
            del start_pvp_match_for_both_players.active_matches_dict[match_key]
            logger.info(f"Запись о матче {match_key} очищена после {delay_seconds} секунд")
async def send_match_start_messages(match_id: str, player1_id: int, player2_id: int,
                                   player1_squad: dict, player2_squad: dict,
                                   player1_elo: dict, player2_elo: dict,
                                   bot: Bot):
    """Отправляет сообщения о начале матча обоим игрокам с составами"""
    
    # СНАЧАЛА ОЧИСТИМ ВСЕ СООБЩЕНИЯ ПОИСКА
    logger.info(f"Отправка сообщений о начале матча, очистка сообщений поиска для {player1_id} и {player2_id}")
    await cleanup_search_messages(player1_id, player2_id, bot)
    
    # ПРОВЕРКА: Используем глобальный словарь для отслеживания отправленных сообщений
    if not hasattr(send_match_start_messages, 'message_sent'):
        send_match_start_messages.message_sent = {}
    
    match_key = f"{player1_id}_{player2_id}_{match_id}"
    
    # Если сообщение уже отправлено для этого матча - пропускаем
    if match_key in send_match_start_messages.message_sent:
        logger.info(f"Сообщения для матча {match_key} уже отправлены")
        return
    
    send_match_start_messages.message_sent[match_key] = datetime.now()
    
    # Получаем названия команд обоих игроков
    player1_team_name = await get_user_team_name(player1_id)
    player2_team_name = await get_user_team_name(player2_id)
    
    # Получаем детали составов
    player1_squad_details = await format_squad_details(player1_squad)
    player2_squad_details = await format_squad_details(player2_squad)
    
    # Текст для игрока 1 с составами
    player1_text = (
        f"🎮 <b>МАТЧ НАЧИНАЕТСЯ!</b>\n\n"
        f"⚽ <b>PvP МАТЧ: ВЫ против {player2_team_name}</b>\n\n"
        f"🏆 <b>Ваш состав:</b> {player1_squad.get('squad_name', 'Ваша команда')}\n"
        f"{player1_squad_details}\n"
        f"🏅 <b>Ваш ELO:</b> {player1_elo.get('elo_rating', 200) if player1_elo else 200}\n\n"
        f"{'='*40}\n\n"
        f"👤 <b>Соперник:</b> {player2_team_name}\n"
        f"🏆 <b>Состав соперника:</b> {player2_squad.get('squad_name', 'Команда соперника')}\n"
        f"{player2_squad_details}\n"
        f"🏅 <b>ELO соперника:</b> {player2_elo.get('elo_rating', 200) if player2_elo else 200}\n\n"
        f"⏱️ <b>Длительность матча:</b> 30 секунд\n\n"
        f"<i>Матч начинается через 5 секунд...</i>"
    )
    
    # Текст для игрока 2 с составами
    player2_text = (
        f"🎮 <b>МАТЧ НАЧИНАЕТСЯ!</b>\n\n"
        f"⚽ <b>PvP МАТЧ: ВЫ против {player1_team_name}</b>\n\n"
        f"🏆 <b>Ваш состав:</b> {player2_squad.get('squad_name', 'Ваша команда')}\n"
        f"{player2_squad_details}\n"
        f"🏅 <b>Ваш ELO:</b> {player2_elo.get('elo_rating', 200) if player2_elo else 200}\n\n"
        f"{'='*40}\n\n"
        f"👤 <b>Соперник:</b> {player1_team_name}\n"
        f"🏆 <b>Состав соперника:</b> {player1_squad.get('squad_name', 'Команда соперника')}\n"
        f"{player1_squad_details}\n"
        f"🏅 <b>ELO соперника:</b> {player1_elo.get('elo_rating', 200) if player1_elo else 200}\n\n"
        f"⏱️ <b>Длительность матча:</b> 30 секунд\n\n"
        f"<i>Матч начинается через 5 секунд...</i>"
    )
    
    # Отправляем сообщения обоим игрокам
    try:
        player1_msg = await bot.send_message(
            chat_id=player1_id,
            text=player1_text,
            parse_mode="html"
        )
        
        player2_msg = await bot.send_message(
            chat_id=player2_id,
            text=player2_text,
            parse_mode="html"
        )
        
        # Ждем 5 секунд перед началом матча, чтобы игроки увидели составы
        await asyncio.sleep(5)
        
        # Запускаем симуляцию матча для обоих игроков
        asyncio.create_task(
            run_pvp_match_simulation(
                player1_id, player1_msg.chat.id, player1_msg.message_id,
                player2_id, player2_msg.chat.id, player2_msg.message_id,
                player1_squad, player2_squad,
                match_id, bot
            )
        )
        
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщений о начале матча: {e}")
        # Удаляем из отправленных при ошибке
        if match_key in send_match_start_messages.sent_messages:
            send_match_start_messages.sent_messages.remove(match_key)



# Инициализируем глобальный словарь

async def format_squad_details(squad: dict) -> str:
    """Форматирует детали состава в читаемый вид"""
    if not squad:
        return "❌ Состав не найден"
    
    details = ""
    
    # Проверяем формат состава (для PvP vs обычного состава)
    is_pvp_format = 'gk' in squad and isinstance(squad['gk'], dict)
    
    if is_pvp_format:
        # PvP формат: squad = {'gk': {...}, 'op': {...}, 'nap1': {...}, 'nap2': {...}}
        positions = [
            ("ГК (Вратарь)", squad.get('gk')),
            ("ОП (Защитник)", squad.get('op')),
            ("НАП 1 (Нападающий)", squad.get('nap1')),
            ("НАП 2 (Нападающий)", squad.get('nap2'))
        ]
    else:
        # Обычный формат из БД: squad = {'gk_card_id': 123, ...}
        positions = [
            ("ГК (Вратарь)", squad.get('gk_card_id')),
            ("ОП (Защитник)", squad.get('op_card_id')),
            ("НАП 1 (Нападающий)", squad.get('nap1_card_id')),
            ("НАП 2 (Нападающий)", squad.get('nap2_card_id'))
        ]
    
    for pos_name, card_data in positions:
        if card_data:
            if is_pvp_format:
                # В PvP формате card_data уже является словарем с деталями карточки
                if isinstance(card_data, dict):
                    rarity_display = 'Эпический' if card_data.get('rarity') == 'эпическая' else card_data.get('rarity', 'Неизвестно')
                    details += f"  • {pos_name}: {card_data.get('nickname', 'Неизвестно')} ({rarity_display})\n"
                else:
                    details += f"  • {pos_name}: ❌ Неверный формат данных\n"
            else:
                # В обычном формате card_data - это ID карточки
                card_details = get_card_details(card_data)
                if card_details:
                    rarity_display = 'Эпический' if card_details['rarity'] == 'эпическая' else card_details['rarity']
                    details += f"  • {pos_name}: {card_details['nickname']} ({rarity_display})\n"
                else:
                    details += f"  • {pos_name}: ❌ Карточка не найдена\n"
        else:
            details += f"  • {pos_name}: ❌ Не выбрано\n"
    
    return details
async def periodic_confirmation_cleanup(bot: Bot):
    """Периодически очищает старые подтверждения"""
    while True:
        await asyncio.sleep(60)  # Каждую минуту
        
        try:
            current_time = datetime.now()
            to_remove = []
            
            for user_id, state in list(pvp_confirmation_states.items()):
                # Удаляем подтверждения старше 10 минут
                if (current_time - state.get('confirmed_at', current_time)).seconds > 600:
                    to_remove.append(user_id)
                    
            for user_id in to_remove:
                if user_id in pvp_confirmation_states:
                    # Пытаемся удалить сообщение подтверждения
                    state = pvp_confirmation_states[user_id]
                    if 'confirm_message_id' in state and 'confirm_chat_id' in state:
                        try:
                            await bot.delete_message(
                                chat_id=state['confirm_chat_id'],
                                message_id=state['confirm_message_id']
                            )
                        except:
                            pass
                    del pvp_confirmation_states[user_id]
                    
            if to_remove:
                logger.info(f"Очищено {len(to_remove)} старых подтверждений")
                
        except Exception as e:
            logger.error(f"Ошибка при очистке подтверждений: {e}")
async def run_pvp_match_simulation(player1_id: int, player1_chat_id: int, player1_message_id: int,
                                   player2_id: int, player2_chat_id: int, player2_message_id: int,
                                   player1_squad: dict, player2_squad: dict,
                                   match_id: str, bot: Bot):
    """Запускает симуляцию PvP матча для обоих игроков"""
    
    # Добавляем матч в активные
    pvp_active_matches[match_id] = {
        'player1_id': player1_id,
        'player2_id': player2_id,
        'start_time': datetime.now(),
        'player1_chat_id': player1_chat_id,
        'player1_message_id': player1_message_id,
        'player2_chat_id': player2_chat_id,
        'player2_message_id': player2_message_id
    }
    
    # Инициализируем тактики по умолчанию
    pvp_tactics[match_id] = {
        player1_id: 'balance',
        player2_id: 'balance'
    }
    
    try:
        # Создаем два симулятора - один для каждого игрока
        # Игрок 1 видит себя как user, игрока 2 как bot
        match_simulator_player1 = BotMatchSimulator(player1_squad)
        match_simulator_player1.bot_squad = player2_squad
        match_simulator_player1.is_pvp = True  # Добавляем флаг PvP

        # Игрок 2 видит себя как user, игрока 1 как bot
        match_simulator_player2 = BotMatchSimulator(player2_squad)
        match_simulator_player2.bot_squad = player1_squad
        match_simulator_player2.is_pvp = True  # Добавляем флаг PvP
        
        # Синхронизируем счет между симуляторами
        match_simulator_player1.user_score = 0
        match_simulator_player1.bot_score = 0
        match_simulator_player2.user_score = 0
        match_simulator_player2.bot_score = 0
        
        # Получаем названия команд обоих игроков
        player1_team_name = await get_user_team_name(player1_id)
        player2_team_name = await get_user_team_name(player2_id)
        
        # Флаг для отслеживания, обновлялось ли сообщение
        last_update_time_player1 = time.time()
        last_update_time_player2 = time.time()
        update_interval = 0.8  # минимальный интервал между обновлениями
        
        # Симулируем 30 секунд матча
        for second in range(1, match_simulator_player1.match_duration + 1):
            await asyncio.sleep(update_interval)
            
            # Получаем текущие тактики игроков из глобального словаря
            player1_tactic = pvp_tactics.get(match_id, {}).get(player1_id, 'balance')
            player2_tactic = pvp_tactics.get(match_id, {}).get(player2_id, 'balance')
            
            # Устанавливаем тактику для каждого симулятора
            match_simulator_player1.set_tactic(player1_tactic)
            match_simulator_player2.set_tactic(player2_tactic)
            
            # Симулируем секунду матча для игрока 1
            match_simulator_player1.minute = second
            event1 = match_simulator_player1.simulate_second()
            
            # Симулируем секунду матча для игрока 2 (синхронизированный счет)
            match_simulator_player2.minute = second
            # Для игрока 2 счет должен быть зеркальным
            match_simulator_player2.user_score = match_simulator_player1.bot_score
            match_simulator_player2.bot_score = match_simulator_player1.user_score
            
            # Для второго игрока генерируем свое событие, но с тем же результатом по голам
            match_simulator_player2.match_events = []
            event2 = match_simulator_player2.get_random_action()
            
            # Проверяем, забит ли гол в событии игрока 1
            if "ГОООЛ!" in event1:
                # Определяем, кто забил
                if match_simulator_player1.user_score > match_simulator_player2.bot_score:
                    # Игрок 1 забил
                    goal_player = match_simulator_player1._get_random_player_for_goal(player1_squad, "user")
                    event2 = f"<b>⚽ ГОООЛ! {goal_player['name']} ({goal_player['team']}) забивает!</b>"
                else:
                    # Игрок 2 забил (с точки зрения игрока 2 это его гол)
                    goal_player = match_simulator_player2._get_random_player_for_goal(player2_squad, "user")
                    event2 = f"<b>⚽ ГОООЛ! {goal_player['name']} ({goal_player['team']}) забивает!</b>"
            
            # Обновляем сообщения у обоих игроков только если прошло достаточно времени
            current_time = time.time()
            
            # Для игрока 1
            if current_time - last_update_time_player1 >= update_interval:
                try:
                    progress_bar = match_simulator_player1.get_progress_bar(second, match_simulator_player1.match_duration)
                    
                    # Получаем описание текущей тактики игрока 1
                    tactic_descriptions = {
                        'attack': '⚔️ Все в атаку! (+15% забить, +30% пропустить)',
                        'defense': '🛡️ Все в защиту! (-50% забить, -15% пропустить)',
                        'balance': '⚖️ Баланс (стандартные шансы)'
                    }
                    tactic_info = tactic_descriptions.get(player1_tactic, '⚖️ Баланс')
                    
                    # Текст для игрока 1 (со своей стороны)
                    player1_text = (
                        f"🎮 <b>ИДЕТ PvP МАТЧ!</b>\n\n"
                        f"🏆 <b>Счет:</b> {player1_team_name} {match_simulator_player1.user_score}:{match_simulator_player1.bot_score} {player2_team_name}\n"
                        f"{'='*40}\n\n"
                        f"⏳ <b>Прогресс матча:</b>\n"
                        f"{progress_bar}\n\n"
                        f"🎯 <b>Текущая тактика:</b> {tactic_info}\n\n"
                        f"📢 <b>Событие:</b> {event1}\n\n"
                        f"<i>Матч продолжается...</i>"
                    )
                    
                    # Создаем клавиатуру с тактическими кнопками для игрока 1
                    builder = InlineKeyboardBuilder()
                    builder.row(
                        InlineKeyboardButton(
                            text="⚔️ Все в атаку",
                            callback_data=f"pvp_tactic_attack_{match_id}"
                        ),
                        InlineKeyboardButton(
                            text="🛡️ Все в защиту",
                            callback_data=f"pvp_tactic_defense_{match_id}"
                        ),
                        InlineKeyboardButton(
                            text="⚖️ Баланс",
                            callback_data=f"pvp_tactic_balance_{match_id}"
                        )
                    )
                    
                    await bot.edit_message_text(
                        chat_id=player1_chat_id,
                        message_id=player1_message_id,
                        text=player1_text,
                        parse_mode="html",
                        reply_markup=builder.as_markup()
                    )
                    last_update_time_player1 = current_time
                except Exception as e:
                    logger.error(f"Не удалось обновить сообщение игроку 1: {e}")
            
            # Для игрока 2
            if current_time - last_update_time_player2 >= update_interval:
                try:
                    progress_bar = match_simulator_player2.get_progress_bar(second, match_simulator_player2.match_duration)
                    
                    # Получаем описание текущей тактики игрока 2
                    tactic_descriptions = {
                        'attack': '⚔️ Все в атаку! (+15% забить, +30% пропустить)',
                        'defense': '🛡️ Все в защиту! (-50% забить, -15% пропустить)',
                        'balance': '⚖️ Баланс (стандартные шансы)'
                    }
                    tactic_info = tactic_descriptions.get(player2_tactic, '⚖️ Баланс')
                    
                    # Текст для игрока 2 (со своей стороны)
                    player2_text = (
                        f"🎮 <b>ИДЕТ PvP МАТЧ!</b>\n\n"
                        f"🏆 <b>Счет:</b> {player2_team_name} {match_simulator_player2.user_score}:{match_simulator_player2.bot_score} {player1_team_name}\n"
                        f"{'='*40}\n\n"
                        f"⏳ <b>Прогресс матча:</b>\n"
                        f"{progress_bar}\n\n"
                        f"🎯 <b>Текущая тактика:</b> {tactic_info}\n\n"
                        f"📢 <b>Событие:</b> {event2}\n\n"
                        f"<i>Матч продолжается...</i>"
                    )
                    
                    # Создаем клавиатуру с тактическими кнопками для игрока 2
                    builder = InlineKeyboardBuilder()
                    builder.row(
                        InlineKeyboardButton(
                            text="⚔️ Все в атаку",
                            callback_data=f"pvp_tactic_attack_{match_id}"
                        ),
                        InlineKeyboardButton(
                            text="🛡️ Все в защиту",
                            callback_data=f"pvp_tactic_defense_{match_id}"
                        ),
                        InlineKeyboardButton(
                            text="⚖️ Баланс",
                            callback_data=f"pvp_tactic_balance_{match_id}"
                        )
                    )
                    
                    await bot.edit_message_text(
                        chat_id=player2_chat_id,
                        message_id=player2_message_id,
                        text=player2_text,
                        parse_mode="html",
                        reply_markup=builder.as_markup()
                    )
                    last_update_time_player2 = current_time
                except Exception as e:
                    logger.error(f"Не удалось обновить сообщение игроку 2: {e}")
        
        # Матч завершен, сохраняем финальные результаты
        final_results = {
            'player1_score': match_simulator_player1.user_score,
            'player2_score': match_simulator_player1.bot_score,
            'player1_tactic': player1_tactic,
            'player2_tactic': player2_tactic,
            'match_simulator': match_simulator_player1  # Используем симулятор игрока 1 как основной
        }
        
        # Удаляем матч из активных перед завершением
        if match_id in pvp_active_matches:
            del pvp_active_matches[match_id]
        if match_id in pvp_tactics:
            del pvp_tactics[match_id]
            
        # Показываем результаты
        await finish_pvp_match(
            player1_id, player1_chat_id, player1_message_id,
            player2_id, player2_chat_id, player2_message_id,
            final_results, player1_team_name, player2_team_name,
            match_id, bot
        )
        
    except Exception as e:
        logger.error(f"Ошибка в симуляции PvP матча: {e}")
        import traceback
        logger.error(f"Трейсбэк: {traceback.format_exc()}")
        
        # При ошибке очищаем
        if match_id in pvp_active_matches:
            del pvp_active_matches[match_id]
        if match_id in pvp_tactics:
            del pvp_tactics[match_id]
            
        # Пытаемся уведомить игроков об ошибке
        try:
            error_msg = "❌ <b>ОШИБКА В МАТЧЕ</b>\n\nПроизошла техническая ошибка. Матч прерван."
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text="⚽ Сыграть еще", callback_data="withplayer"),
                InlineKeyboardButton(text="🎮 Игровое меню", callback_data="back_to_play_menu")
            )
            
            await bot.edit_message_text(
                chat_id=player1_chat_id,
                message_id=player1_message_id,
                text=error_msg,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
            
            await bot.edit_message_text(
                chat_id=player2_chat_id,
                message_id=player2_message_id,
                text=error_msg,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
        except:
            pass
# Добавляем обработчик для кнопок тактики в PvP:

@public_router_pvp.callback_query(F.data.startswith("pvp_tactic_"))
@handle_old_callback
async def handle_pvp_tactic_change(callback: CallbackQuery):
    """Обрабатывает смену тактики во время PvP матча"""
    try:
        # Разбираем callback_data: pvp_tactic_attack_match123
        parts = callback.data.split("_")
        if len(parts) < 3:
            await callback.answer("❌ Ошибка формата тактики", show_alert=True)
            return
        
        tactic = parts[2]  # attack, defense, balance
        match_id = "_".join(parts[3:]) if len(parts) > 3 else ""
        
        if not match_id:
            await callback.answer("❌ Не найден ID матча", show_alert=True)
            return
        
        user_id = callback.from_user.id
        
        # Проверяем, существует ли такой матч
        if match_id not in pvp_active_matches:
            await callback.answer("❌ Матч не найден или завершен", show_alert=True)
            return
        
        match_info = pvp_active_matches[match_id]
        
        # Проверяем, является ли пользователь участником матча
        if user_id not in [match_info.get('player1_id'), match_info.get('player2_id')]:
            await callback.answer("❌ Вы не участвуете в этом матче", show_alert=True)
            return
        
        # Сохраняем тактику
        if match_id not in pvp_tactics:
            pvp_tactics[match_id] = {}
        
        pvp_tactics[match_id][user_id] = tactic
        
        # Отправляем подтверждение
        tactic_names = {
            'attack': '⚔️ Все в атаку',
            'defense': '🛡️ Все в защиту',
            'balance': '⚖️ Баланс'
        }
        tactic_effects = {
            'attack': 'Шанс забить +15%, шанс пропустить +30%',
            'defense': 'Шанс забить -50%, шанс пропустить -15%',
            'balance': 'Стандартные шансы'
        }
        
        await callback.answer(
            f"Тактика изменена: {tactic_names.get(tactic, 'Неизвестно')}\n"
            f"Эффект: {tactic_effects.get(tactic, 'Нет эффекта')}",
            show_alert=True
        )
        
    except Exception as e:
        logger.error(f"Ошибка при смене тактики PvP: {e}")
        await callback.answer("❌ Ошибка при смене тактики", show_alert=True)

# Также обновляем функцию finish_pvp_match чтобы сохранять использованные тактики:
async def finish_pvp_match(player1_id: int, player1_chat_id: int, player1_message_id: int,
                          player2_id: int, player2_chat_id: int, player2_message_id: int,
                          match_results: dict, player1_name: str, player2_name: str,
                          match_id: str, bot: Bot):
    """Завершает PvP матч и показывает результаты с расширенной статистикой и составами"""
    try:
        player1_score = match_results['player1_score']
        player2_score = match_results['player2_score']
        player1_tactic = match_results['player1_tactic']
        player2_tactic = match_results['player2_tactic']
        
        # Получаем составы игроков
        player1_squad = get_user_squad(player1_id)
        player2_squad = get_user_squad(player2_id)
        
        # Получаем детали составов
        player1_squad_details = await format_squad_details(player1_squad) if player1_squad else "❌ Состав не найден"
        player2_squad_details = await format_squad_details(player2_squad) if player2_squad else "❌ Состав не найден"
        
        # Получаем названия команд
        player1_team_name = await get_user_team_name(player1_id)
        player2_team_name = await get_user_team_name(player2_id)
        
        # Определяем результат
        if player1_score > player2_score:
            # Игрок 1 выиграл
            player1_result = 'win'
            player2_result = 'lose'
            player1_elo_change = 8
            player2_elo_change = -8
            result_text_display = f"🏆 <b>ПОБЕДИТЕЛЬ:</b> {player1_team_name}!\n\n"
        elif player1_score < player2_score:
            # Игрок 2 выиграл
            player1_result = 'lose'
            player2_result = 'win'
            player1_elo_change = -8
            player2_elo_change = 8
            result_text_display = f"🏆 <b>ПОБЕДИТЕЛЬ:</b> {player2_team_name}!\n\n"
        else:
            # Ничья
            player1_result = 'draw'
            player2_result = 'draw'
            player1_elo_change = 3
            player2_elo_change = 3
            result_text_display = f"🤝 <b>НИЧЬЯ!</b>\n\n"
        
        # Обновляем ELO
        update_user_elo_with_opponent_type(
            player1_id, player1_result, player1_elo_change, 
            player1_score, player2_score,
            opponent_type='player', opponent_name=player2_team_name
        )
        
        update_user_elo_with_opponent_type(
            player2_id, player2_result, player2_elo_change,
            player2_score, player1_score,
            opponent_type='player', opponent_name=player1_team_name
        )
        
        # Получаем ELO после обновления
        player1_elo = get_user_elo(player1_id)
        player2_elo = get_user_elo(player2_id)
        
        # Генерируем статистику
        player1_possession = random.randint(45, 65)
        player2_possession = 100 - player1_possession
        
        player1_shots = player1_score + random.randint(5, 15)
        player2_shots = player2_score + random.randint(5, 15)
        
        player1_shots_on_target = int(player1_shots * random.uniform(0.7, 0.9))
        player2_shots_on_target = int(player2_shots * random.uniform(0.7, 0.9))
        
        player1_saves = max(0, player2_shots_on_target - player1_score)
        player2_saves = max(0, player1_shots_on_target - player2_score)
        
        # Формируем текст результата с составами
        result_text = (
            f"🏁 <b>МАТЧ ЗАВЕРШЕН!</b>\n\n"
            f"⚽ <b>ФИНАЛЬНЫЙ СЧЕТ:</b>\n"
            f"📊 <b>{player1_team_name}:</b> {player1_score}\n"
            f"📊 <b>{player2_team_name}:</b> {player2_score}\n\n"
            f"{result_text_display}"
        )
        
        # Добавляем составы после матча
        result_text += f"👥 <b>СОСТАВЫ КОМАНД:</b>\n"
        result_text += f"<b>{player1_team_name}:</b>\n{player1_squad_details}\n"
        result_text += f"{'='*30}\n"
        result_text += f"<b>{player2_team_name}:</b>\n{player2_squad_details}\n\n"
        
        # Добавляем изменение ELO
        result_text += f"📈 <b>ИЗМЕНЕНИЕ ELO:</b>\n"
        result_text += f"• {player1_team_name}: {player1_elo_change:+d} (теперь: {player1_elo['elo_rating'] if player1_elo else 200})\n"
        result_text += f"• {player2_team_name}: {player2_elo_change:+d} (теперь: {player2_elo['elo_rating'] if player2_elo else 200})\n\n"
        
        # Добавляем информацию о тактиках
        tactic_display = {
            'attack': '⚔️ Все в атаку',
            'defense': '🛡️ Все в защиту',
            'balance': '⚖️ Баланс'
        }
        
        result_text += f"🧠 <b>ИСПОЛЬЗОВАННЫЕ ТАКТИКИ:</b>\n"
        result_text += f"• {player1_team_name}: {tactic_display.get(player1_tactic, '⚖️ Баланс')}\n"
        result_text += f"• {player2_team_name}: {tactic_display.get(player2_tactic, '⚖️ Баланс')}\n\n"
        
        # Добавляем статистику матча
        result_text += (
            f"📊 <b>СТАТИСТИКА МАТЧА:</b>\n"
            f"{'='*40}\n"
            f"• 🎯 <b>Удары:</b> {player1_shots} | {player2_shots}\n"
            f"• 🎯 <b>Удары в створ:</b> {player1_shots_on_target} | {player2_shots_on_target}\n"
            f"• ⚽ <b>Голы:</b> {player1_score} | {player2_score}\n"
            f"• 🧤 <b>Сейвы:</b> {player1_saves} | {player2_saves}\n"
            f"• 🏃 <b>Владение мячом:</b> {player1_possession}% | {player2_possession}%\n"
            f"• ⏱️ <b>Длительность матча:</b> 30 секунд\n\n"
            f"<i>Спасибо за игру! 👏</i>"
        )
        
        # Кнопки для переигрывания
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="⚽ Сыграть еще", callback_data="withplayer"),
            InlineKeyboardButton(text="📊 Статистика", callback_data="statistics")
        )
        builder.row(
            InlineKeyboardButton(text="🎮 Игровое меню", callback_data="back_to_play_menu")
        )
        
        # Отправляем результаты обоим игрокам
        try:
            await bot.edit_message_text(
                chat_id=player1_chat_id,
                message_id=player1_message_id,
                text=result_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
        except Exception as e:
            logger.error(f"Не удалось обновить сообщение игроку 1: {e}")
            # Пытаемся отправить новое сообщение
            try:
                await bot.send_message(
                    chat_id=player1_id,
                    text=result_text,
                    parse_mode="html",
                    reply_markup=builder.as_markup()
                )
            except:
                pass
        
        try:
            await bot.edit_message_text(
                chat_id=player2_chat_id,
                message_id=player2_message_id,
                text=result_text,
                parse_mode="html",
                reply_markup=builder.as_markup()
            )
        except Exception as e:
            logger.error(f"Не удалось обновить сообщение игроку 2: {e}")
            # Пытаемся отправить новое сообщение
            try:
                await bot.send_message(
                    chat_id=player2_id,
                    text=result_text,
                    parse_mode="html",
                    reply_markup=builder.as_markup()
                )
            except:
                pass
        
        # Сохраняем историю PvP матча
        save_pvp_match_history(
            match_id, player1_id, player2_id, 
            player1_score, player2_score,
            player1_elo_change, player2_elo_change,
            player1_team_name, player2_team_name
        )
        
        logger.info(f"PvP матч завершен: {player1_id} {player1_score}:{player2_score} {player2_id}")
        
    except Exception as e:
        logger.error(f"Ошибка при завершении PvP матча: {e}")
        import traceback
        logger.error(f"Трейсбэк: {traceback.format_exc()}")
def update_user_elo_with_opponent_type(user_id: int, result: str, elo_change: int, 
                                      user_score: int = 0, opponent_score: int = 0,
                                      opponent_type: str = 'bot', opponent_name: str = ''):
    """Обновляет ELO рейтинг пользователя после матча с учетом типа оппонента"""
    try:
        # Определяем статистику в зависимости от результата
        if result == 'win':
            wins_change = 1
            losses_change = 0
            draws_change = 0
        elif result == 'lose':
            wins_change = 0
            losses_change = 1
            draws_change = 0
        else:  # draw
            wins_change = 0
            losses_change = 0
            draws_change = 1
        
        # Сначала проверяем, существует ли запись пользователя
        existing = db_operation(
            "SELECT user_id FROM user_elo WHERE user_id = ?",
            (user_id,),
            fetch=True
        )
        
        if existing:
            # Обновляем существующую запись
            db_operation(
                """UPDATE user_elo 
                   SET elo_rating = elo_rating + ?,
                       total_matches = total_matches + 1,
                       wins = wins + ?,
                       losses = losses + ?,
                       draws = draws + ?,
                       goals_scored = goals_scored + ?,
                       goals_conceded = goals_conceded + ?,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE user_id = ?""",
                (elo_change, wins_change, losses_change, draws_change, 
                 user_score, opponent_score, user_id)
            )
        else:
            # Создаем новую запись
            db_operation(
                """INSERT INTO user_elo 
                   (user_id, elo_rating, total_matches, wins, losses, draws, 
                    goals_scored, goals_conceded, updated_at)
                   VALUES (?, ?, 1, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (user_id, 200 + elo_change, wins_change, losses_change, draws_change, 
                 user_score, opponent_score)
            )
        
        # Сохраняем историю матча
        db_operation(
            """INSERT INTO match_history 
               (user_id, opponent_type, opponent_name, user_score, opponent_score,
                result, elo_change, match_duration, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (user_id, opponent_type, opponent_name, user_score, opponent_score, 
             result, elo_change, 90)
        )
        
        logger.info(f"✅ ELO пользователя {user_id} обновлен: {result} vs {opponent_type} ({elo_change:+d})")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при обновлении ELO пользователя {user_id}: {e}")
        import traceback
        logger.error(f"Трейсбэк: {traceback.format_exc()}")


def save_pvp_match_history(match_id: str, player1_id: int, player2_id: int,
                          player1_score: int, player2_score: int,
                          player1_elo_change: int, player2_elo_change: int,
                          player1_team_name: str, player2_team_name: str):
    """Сохраняет историю PvP матча - ИСПРАВЛЕНО"""
    try:
        db_operation(
            """INSERT INTO pvp_match_history 
               (match_id, player1_id, player2_id, player1_score, player2_score,
                player1_elo_change, player2_elo_change, match_duration, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (match_id, player1_id, player2_id, player1_score, player2_score,
             player1_elo_change, player2_elo_change, 30)
        )
        
        logger.info(f"✅ История PvP матча сохранена: {player1_team_name} vs {player2_team_name}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении истории PvP матча: {e}")


# ... остальной код остается без изменений ...

@public_router_pvp.callback_query(F.data == "cancel_pvp_match")
@handle_old_callback
async def cancel_pvp_match_callback(callback: CallbackQuery, state: FSMContext):
    """Отмена PvP матча"""
    user_id = callback.from_user.id
    
    try:
        state_data = await state.get_data()
        opponent_id = state_data.get('opponent_id')
        user_team_name = state_data.get('squad_name', f'Команда {user_id}')
        
        if not opponent_id:
            await callback.answer("❌ Ошибка: соперник не найден", show_alert=True)
            return
        
        # Обновляем сообщение у текущего пользователя
        await callback.message.edit_text(
            f"❌ <b>МАТЧ ОТМЕНЕН</b>\n\n"
            f"Вы отказались от матча.",
            parse_mode="html",
            reply_markup=InlineKeyboardBuilder()
            .add(InlineKeyboardButton(text="🎮 Игровое меню", callback_data="back_to_play_menu"))
            .as_markup()
        )
        
        # Уведомляем соперника
        try:
            await callback.bot.send_message(
                chat_id=opponent_id,
                text=f"❌ <b>СОПЕРНИК ОТМЕНА</b>\n\n"
                     f"<b>{user_team_name}</b> отказался от матча.\n\n"
                     f"<i>Чтобы найти нового соперника, нажмите кнопку ниже:</i>",
                parse_mode="html",
                reply_markup=InlineKeyboardBuilder()
                .add(InlineKeyboardButton(text="🔍 Найти нового соперника", callback_data="withplayer"))
                .as_markup()
            )
        except Exception as e:
            logger.error(f"Ошибка при уведомлении соперника {opponent_id}: {e}")
        
        # Очищаем состояние текущего пользователя
        await state.clear()
        
        # Удаляем текущего пользователя из очереди
        remove_from_pvp_queue(user_id)
        
        await callback.answer("Матч отменен")
        
    except Exception as e:
        logger.error(f"Ошибка при отмене матча: {e}")
        await callback.answer("❌ Ошибка при отмене матча", show_alert=True)

# Также нужно обновить функцию confirm_match_start для ботовых матчей
@public_router_pvp.callback_query(F.data == "confirm_match_start")
@handle_old_callback
async def confirm_match_start(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Подтверждение начала матча - ИСПРАВЛЕНО"""
    user_id = callback.from_user.id
    
    try:
        state_data = await state.get_data()
        user_squad = state_data.get('user_squad')
        
        if not user_squad:
            await callback.answer("❌ Ошибка: состав не найден", show_alert=True)
            return
        
        # Получаем детали карточек состава
        squad_details = {}
        for pos_key in ['gk_card_id', 'op_card_id', 'nap1_card_id', 'nap2_card_id']:
            card_id = user_squad.get(pos_key)
            if card_id:
                card_details = get_card_details(card_id)
                if card_details:
                    squad_details[pos_key.replace('_card_id', '')] = card_details
        
        # Проверяем, что есть все необходимые карточки
        required_positions = ['gk', 'op', 'nap1', 'nap2']
        for pos in required_positions:
            if pos not in squad_details:
                await callback.answer(f"❌ Отсутствует карточка для позиции {pos}", show_alert=True)
                return
        
        # Создаем симулятор матча
        match_simulator = BotMatchSimulator(squad_details)
        squad_name = user_squad.get('squad_name', 'Ваша команда')
        
        await state.update_data({
            'match_simulator': match_simulator,
            'minute': 0,
            'user_score': 0,
            'bot_score': 0,
            'squad_name': squad_name,
            'is_match_running': True,
            'user_squad': user_squad,
            'current_tactic': 'balance'
        })
        
        # Переходим в состояние игры
        await state.set_state(MatchStates.playing_match)
        
        # Формируем начальное сообщение
        progress_bar = match_simulator.get_progress_bar(0, match_simulator.match_duration)
        
        message_text = (
            f"🎮 <b>ИГРА НАЧИНАЕТСЯ!</b>\n\n"
            f"🏆 <b>Матч:</b> {squad_name} 0:0 MamoTinder Bot\n"
            f"{'='*40}\n\n"
            f"⏳ <b>Прогресс матча:</b>\n"
            f"{progress_bar}\n\n"
            f"🔵 <b>Стартовый свисток!</b> Матч начался!\n\n"
            f"<i>Матч симулируется в реальном времени...</i>"
        )
        
        # Создаем клавиатуру
        builder = InlineKeyboardBuilder()
        
        match_message = await callback.message.edit_text(
            message_text,
            parse_mode="html",
            reply_markup=builder.as_markup()
        )
        
        # Сохраняем ID сообщения
        await state.update_data({
            'match_message_id': match_message.message_id,
            'chat_id': match_message.chat.id
        })
        
        # Запускаем симуляцию матча
        asyncio.create_task(run_match_simulation(
            callback.message.chat.id, 
            match_message.message_id, 
            user_id, 
            match_simulator, 
            state, 
            bot
        ))
        
        await callback.answer("✅ Матч начался!", show_alert=True)
        
    except Exception as e:
        logger.error(f"Ошибка в confirm_match_start для пользователя {user_id}: {e}")
        await callback.answer("❌ Ошибка при запуске матча", show_alert=True)
async def cleanup_old_confirmations():
    """Очищает старые подтверждения PvP матчей"""
    while True:
        await asyncio.sleep(300)  # Каждые 5 минут
        
        try:
            current_time = datetime.now()
            confirmations_to_remove = []
            
            for user_id, confirmation in list(pvp_confirmation_states.items()):
                if (current_time - confirmation['confirmed_at']).seconds > 300:  # 5 минут
                    confirmations_to_remove.append(user_id)
            
            for user_id in confirmations_to_remove:
                del pvp_confirmation_states[user_id]
            
            if confirmations_to_remove:
                logger.info(f"Очищено {len(confirmations_to_remove)} старых подтверждений")
                
        except Exception as e:
            logger.error(f"Ошибка при очистке подтверждений: {e}")
# Запуск фоновых задач

    # Запускаем очистку очереди PvP

    
# В основном файле бота вызовите эту функцию при старте
@public_router_pvp.callback_query(F.data == "cancel_pvp_match")
@handle_old_callback
async def cancel_pvp_match_callback(callback: CallbackQuery, state: FSMContext):
    """Отмена PvP матча"""
    user_id = callback.from_user.id
    
    try:
        state_data = await state.get_data()
        opponent_id = state_data.get('opponent_id')
        
        if not opponent_id:
            await callback.answer("❌ Ошибка: соперник не найден", show_alert=True)
            return
        
        # Получаем имя отменившего игрока
        user_name = await get_user_display_name(callback.bot, user_id)
        
        # Обновляем сообщение у текущего пользователя
        await callback.message.edit_text(
            f"❌ <b>МАТЧ ОТМЕНЕН</b>\n\n"
            f"Вы отказались от матча.",
            parse_mode="html",
            reply_markup=InlineKeyboardBuilder()
            .add(InlineKeyboardButton(text="🎮 Игровое меню", callback_data="back_to_play_menu"))
            .as_markup()
        )
        
        # Уведомляем соперника
        try:
            # Проверяем, есть ли сообщение у соперника в глобальной очереди
            opponent_has_message = opponent_id in pvp_queue
            
            if opponent_has_message:
                opp_info = pvp_queue[opponent_id]
                try:
                    await callback.bot.edit_message_text(
                        chat_id=opp_info['chat_id'],
                        message_id=opp_info['message_id'],
                        text=f"❌ <b>СОПЕРНИК ОТМЕНА</b>\n\n"
                             f"<b>{user_name}</b> отказался от матча.\n\n"
                             f"<i>Поиск нового соперника...</i>",
                        parse_mode="html",
                        reply_markup=InlineKeyboardBuilder()
                        .add(InlineKeyboardButton(text="🔍 Продолжить поиск", callback_data="withplayer"))
                        .adjust(1)
                        .as_markup()
                    )
                except:
                    # Если не удалось отредактировать, отправляем новое сообщение
                    await callback.bot.send_message(
                        chat_id=opponent_id,
                        text=f"❌ <b>СОПЕРНИК ОТМЕНА</b>\n\n"
                             f"<b>{user_name}</b> отказался от матча.\n\n"
                             f"<i>Чтобы найти нового соперника, нажмите кнопку ниже:</i>",
                        parse_mode="html",
                        reply_markup=InlineKeyboardBuilder()
                        .add(InlineKeyboardButton(text="🔍 Найти нового соперника", callback_data="withplayer"))
                        .as_markup()
                    )
            else:
                # Просто отправляем новое сообщение
                await callback.bot.send_message(
                    chat_id=opponent_id,
                    text=f"❌ <b>СОПЕРНИК ОТМЕНА</b>\n\n"
                         f"<b>{user_name}</b> отказался от матча с вами.\n\n"
                         f"<i>Чтобы найти нового соперника, нажмите кнопку ниже:</i>",
                    parse_mode="html",
                    reply_markup=InlineKeyboardBuilder()
                    .add(InlineKeyboardButton(text="🔍 Найти нового соперника", callback_data="withplayer"))
                    .as_markup()
                )
            
            # Удаляем информацию о сопернике из очереди
            if opponent_id in pvp_queue:
                del pvp_queue[opponent_id]
            
        except Exception as e:
            logger.error(f"Ошибка при уведомлении соперника {opponent_id}: {e}")
        
        # Очищаем состояние текущего пользователя
        await state.clear()
        
        # Удаляем текущего пользователя из очереди
        if user_id in pvp_queue:
            del pvp_queue[user_id]
        
        await callback.answer("Матч отменен")
        
    except Exception as e:
        logger.error(f"Ошибка при отмене матча: {e}")
        await callback.answer("❌ Ошибка при отмене матча", show_alert=True)

        

async def start_pvp_match(match_id: str, player1_id: int, player2_id: int, bot: Bot):
    """Запускает PvP матч"""
    try:
        # Получаем составы обоих игроков
        player1_squad = get_user_squad(player1_id)
        player2_squad = get_user_squad(player2_id)
        
        if not player1_squad or not player2_squad:
            logger.error(f"Один из игроков не имеет состава: {player1_id}, {player2_id}")
            return
        
        # Получаем ELO обоих игроков
        player1_elo = get_user_elo(player1_id)
        player2_elo = get_user_elo(player2_id)
        
        # Создаем симулятор для каждого игрока
        # Для PvP оба игрока играют против друг друга в одном матче
        match_simulator = BotMatchSimulator(player1_squad)
        
        # Генерируем состав для второго игрока (в реальной PvP это должен быть состав игрока 2)
        # Для упрощения используем ботовый состав, но с карточками игрока 2
        player2_cards_squad = {
            'gk': get_card_details(player2_squad.get('gk_card_id')),
            'op': get_card_details(player2_squad.get('op_card_id')),
            'nap1': get_card_details(player2_squad.get('nap1_card_id')),
            'nap2': get_card_details(player2_squad.get('nap2_card_id')),
            'squad_name': player2_squad.get('squad_name', 'Соперник')
        }
        
        match_simulator.bot_squad = player2_cards_squad
        
        # Запускаем матч для обоих игроков
        # В реальной системе нужно обновлять интерфейс обоих игроков
        # Здесь упрощенная версия
        
        logger.info(f"PvP матч начался: {player1_id} vs {player2_id}")
        
    except Exception as e:
        logger.error(f"Ошибка при запуске PvP матча: {e}")

# Периодическая очистка очереди (запускать при старте бота)
async def cleanup_pvp_queue():
    """Очищает старые записи из очереди PvP"""
    try:
        # Удаляем записи старше 5 минут
        db_operation(
            "DELETE FROM pvp_queue WHERE joined_at < datetime('now', '-5 minutes')"
        )
        
        # Также очищаем глобальный словарь
        current_time = datetime.now()
        users_to_remove = []
        
        for user_id, info in pvp_queue.items():
            if (current_time - info['time_joined']).seconds > 300:  # 5 минут
                users_to_remove.append(user_id)
        
        for user_id in users_to_remove:
            del pvp_queue[user_id]
            
        logger.info(f"Очищена очередь PvP: удалено {len(users_to_remove)} записей")
        
    except Exception as e:
        logger.error(f"Ошибка при очистке очереди PvP: {e}")

# Запускаем периодическую очистку при старте
async def start_pvp_cleanup_scheduler():
    """Запускает периодическую очистку очереди PvP"""
    import asyncio
    while True:
        await asyncio.sleep(300)  # Каждые 5 минут
        await cleanup_pvp_queue()
def init_pvp_system():
    """Инициализирует PvP систему"""
    # Инициализируем таблицы
    init_pvp_tables()
    
    # Запускаем очистку очереди в фоновом режиме
    # Это будет сделано при запуске бота
    logger.info("✅ PvP система инициализирована")

# Вызываем инициализацию
init_pvp_system()
# Запускаем задачу очистки при импорте модуля


# Глобальный словарь для ожидающих подтверждения матчей
pending_pvp_matches = {}  # {match_key: {'player1': user_id, 'player2': user_id, 'player1_ready': bool, 'player2_ready': bool}}

def create_pvp_match(player1_id: int, player2_id: int):
    """Создает ожидающий PvP матч"""
    match_key = f"{min(player1_id, player2_id)}_{max(player1_id, player2_id)}"
    
    pending_pvp_matches[match_key] = {
        'player1_id': player1_id,
        'player2_id': player2_id,
        'player1_ready': False,
        'player2_ready': False,
        'created_at': datetime.now()
    }
    
    return match_key

def update_pvp_match_ready(match_key: str, user_id: int):
    """Обновляет статус готовности игрока"""
    if match_key in pending_pvp_matches:
        match = pending_pvp_matches[match_key]
        
        if user_id == match['player1_id']:
            match['player1_ready'] = True
        elif user_id == match['player2_id']:
            match['player2_ready'] = True
        
        # Проверяем, готовы ли оба игрока
        if match['player1_ready'] and match['player2_ready']:
            # Оба готовы - можно начинать матч
            return True, match
        else:
            return False, match
    
    return False, None

async def cleanup_pending_matches():
    """Очищает зависшие ожидающие матчи"""
    try:
        current_time = datetime.now()
        matches_to_remove = []
        
        for match_key, match_data in pending_pvp_matches.items():
            if (current_time - match_data['created_at']).seconds > 300:  # 5 минут
                matches_to_remove.append(match_key)
        
        for match_key in matches_to_remove:
            del pending_pvp_matches[match_key]
        
        logger.info(f"Очищено {len(matches_to_remove)} зависших матчей")
        
    except Exception as e:
        logger.error(f"Ошибка при очистке матчей: {e}")


async def get_user_name_for_stats(bot: Bot, user_id: int) -> str:
    """Получает имя пользователя для отображения в статистике"""
    try:
        user = await bot.get_chat(user_id)
        if user.username:
            return f"@{user.username}"
        elif user.first_name:
            name = user.first_name
            if user.last_name:
                name += f" {user.last_name}"
            return name
        else:
            return f"Игрок {user_id}"
    except:
        return f"Игрок {user_id}"
    
@public_router_pvp.message(Command("addelo"))
@require_role("старший-администратор")
async def add_elo_command(message: Message, bot: Bot):
    """Добавляет ELO указанному пользователю"""
    
    # Получаем аргументы команды
    args = message.text.split()
    
    if len(args) < 3:
        await message.reply(
            "📝 <b>Использование команды:</b>\n"
            "<code>/addelo [ID_пользователя] [количество_ELO]</code>\n\n"
            "<b>Пример:</b>\n"
            "<code>/addelo 123456789 50</code>\n\n"
            "<i>Можно добавить отрицательное значение для уменьшения ELO</i>",
            parse_mode="html"
        )
        return
    
    try:
        target_user_id = int(args[1])
        elo_amount = int(args[2])
        
        # Проверяем, существует ли пользователь
        result = db_operation(
            "SELECT id FROM all_users WHERE id = ?",
            (target_user_id,),
            fetch=True
        )
        
        if not result:
            await message.reply(
                f"❌ <b>Пользователь не найден!</b>\n\n"
                f"Пользователь с ID {target_user_id} не зарегистрирован в системе.",
                parse_mode="html"
            )
            return
        
        # Получаем текущие данные ELO пользователя
        current_elo = get_user_elo(target_user_id)
        
        # Добавляем ELO
        new_elo_rating = (current_elo['elo_rating'] if current_elo else 200) + elo_amount
        
        # Обновляем ELO в базе
        db_operation(
            """UPDATE user_elo 
               SET elo_rating = ?,
                   updated_at = CURRENT_TIMESTAMP
               WHERE user_id = ?""",
            (new_elo_rating, target_user_id)
        )
        
        # Если записи не было, создаем
        if not current_elo:
            db_operation(
                """INSERT INTO user_elo 
                   (user_id, elo_rating, total_matches, wins, losses, draws, 
                    goals_scored, goals_conceded, updated_at)
                   VALUES (?, ?, 0, 0, 0, 0, 0, 0, CURRENT_TIMESTAMP)""",
                (target_user_id, new_elo_rating)
            )
        
        # Пытаемся получить имя пользователя для отображения
        try:
            target_user = await bot.get_chat(target_user_id)
            username = f"@{target_user.username}" if target_user.username else target_user.first_name
        except:
            username = f"ID: {target_user_id}"
        
        # Формируем ответ
        success_message = (
            f"✅ <b>ELO УСПЕШНО ИЗМЕНЕН!</b>\n\n"
            f"Пользователь: <b>{username}</b>\n"
            f"Изменение: {elo_amount:+d} ELO\n"
            f"Старое значение: {current_elo['elo_rating'] if current_elo else 200}\n"
            f"Новое значение: {new_elo_rating}\n\n"
            f"<i>Изменение выполнено администратором {message.from_user.first_name}</i>"
        )
        
        await message.reply(
            success_message,
            parse_mode="html"
        )
        
        logger.info(f"ELO пользователя {target_user_id} изменен на {elo_amount:+d} администратором {message.from_user.id}")
        
        # Отправляем уведомление пользователю
        try:
            await bot.send_message(
                chat_id=target_user_id,
                text=f"📈 <b>ИЗМЕНЕНИЕ РЕЙТИНГА</b>\n\n"
                     f"Ваш ELO рейтинг был изменен администратором.\n\n"
                     f"• <b>Изменение:</b> {elo_amount:+d}\n"
                     f"• <b>Новый рейтинг:</b> {new_elo_rating}\n\n"
                     f"<i>Спасибо за участие в MamoTinder!</i>",
                parse_mode="html"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление пользователю {target_user_id}: {e}")
        
    except ValueError:
        await message.reply(
            "❌ <b>Неверный формат аргументов!</b>\n\n"
            "ID пользователя и количество ELO должны быть числами.\n\n"
            "<b>Пример:</b> <code>/addelo 123456789 50</code>",
            parse_mode="html"
        )
    except Exception as e:
        logger.error(f"Ошибка при добавлении ELO: {e}")
        await message.reply(
            "❌ <b>Произошла ошибка!</b>\n\n"
            "Не удалось изменить ELO рейтинг. Попробуйте позже.",
            parse_mode="html"
        )

@public_router_pvp.message(Command("setelo"))
@require_role("старший-администратор")
async def set_elo_command(message: Message, bot: Bot):
    """Устанавливает конкретное значение ELO для пользователя"""
    
    # Получаем аргументы команды
    args = message.text.split()
    
    if len(args) < 3:
        await message.reply(
            "📝 <b>Использование команды:</b>\n"
            "<code>/setelo [ID_пользователя] [новое_значение_ELO]</code>\n\n"
            "<b>Пример:</b>\n"
            "<code>/setelo 123456789 500</code>\n\n"
            "<i>Устанавливает точное значение ELO рейтинга</i>",
            parse_mode="html"
        )
        return
    
    try:
        target_user_id = int(args[1])
        new_elo_value = int(args[2])
        
        # Проверяем валидность значения
        if new_elo_value < 0:
            await message.reply(
                "❌ <b>Некорректное значение ELO!</b>\n\n"
                "ELO рейтинг не может быть отрицательным.",
                parse_mode="html"
            )
            return
        
        # Проверяем, существует ли пользователь
        result = db_operation(
            "SELECT id FROM all_users WHERE id = ?",
            (target_user_id,),
            fetch=True
        )
        
        if not result:
            await message.reply(
                f"❌ <b>Пользователь не найден!</b>\n\n"
                f"Пользователь с ID {target_user_id} не зарегистрирован в системе.",
                parse_mode="html"
            )
            return
        
        # Получаем текущие данные ELO пользователя
        current_elo = get_user_elo(target_user_id)
        old_elo = current_elo['elo_rating'] if current_elo else 200
        
        # Обновляем ELO в базе
        if current_elo:
            db_operation(
                """UPDATE user_elo 
                   SET elo_rating = ?,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE user_id = ?""",
                (new_elo_value, target_user_id)
            )
        else:
            db_operation(
                """INSERT INTO user_elo 
                   (user_id, elo_rating, total_matches, wins, losses, draws, 
                    goals_scored, goals_conceded, updated_at)
                   VALUES (?, ?, 0, 0, 0, 0, 0, 0, CURRENT_TIMESTAMP)""",
                (target_user_id, new_elo_value)
            )
        
        # Пытаемся получить имя пользователя для отображения
        try:
            target_user = await bot.get_chat(target_user_id)
            username = f"@{target_user.username}" if target_user.username else target_user.first_name
        except:
            username = f"ID: {target_user_id}"
        
        # Формируем ответ
        success_message = (
            f"✅ <b>ELO УСПЕШНО УСТАНОВЛЕН!</b>\n\n"
            f"Пользователь: <b>{username}</b>\n"
            f"Старое значение: {old_elo}\n"
            f"Новое значение: {new_elo_value}\n"
            f"Изменение: {new_elo_value - old_elo:+d}\n\n"
            f"<i>Изменение выполнено администратором {message.from_user.first_name}</i>"
        )
        
        await message.reply(
            success_message,
            parse_mode="html"
        )
        
        logger.info(f"ELO пользователя {target_user_id} установлен в {new_elo_value} администратором {message.from_user.id}")
        
        # Отправляем уведомление пользователю
        try:
            await bot.send_message(
                chat_id=target_user_id,
                text=f"📊 <b>ОБНОВЛЕНИЕ РЕЙТИНГА</b>\n\n"
                     f"Ваш ELO рейтинг был обновлен администратором.\n\n"
                     f"• <b>Старый рейтинг:</b> {old_elo}\n"
                     f"• <b>Новый рейтинг:</b> {new_elo_value}\n"
                     f"• <b>Изменение:</b> {new_elo_value - old_elo:+d}\n\n"
                     f"<i>Спасибо за участие в MamoTinder!</i>",
                parse_mode="html"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление пользователю {target_user_id}: {e}")
        
    except ValueError:
        await message.reply(
            "❌ <b>Неверный формат аргументов!</b>\n\n"
            "ID пользователя и значение ELO должны быть числами.\n\n"
            "<b>Пример:</b> <code>/setelo 123456789 500</code>",
            parse_mode="html"
        )
    except Exception as e:
        logger.error(f"Ошибка при установке ELO: {e}")
        await message.reply(
            "❌ <b>Произошла ошибка!</b>\n\n"
            "Не удалось установить ELO рейтинг. Попробуйте позже.",
            parse_mode="html"
        )

@public_router_pvp.message(Command("viewelo"))
@require_role("старший-администратор")
async def view_elo_command(message: Message, bot: Bot):
    """Просмотр ELO рейтинга пользователя"""
    
    # Получаем аргументы команды
    args = message.text.split()
    
    if len(args) < 2:
        await message.reply(
            "📝 <b>Использование команды:</b>\n"
            "<code>/viewelo [ID_пользователя]</code>\n\n"
            "<b>Пример:</b>\n"
            "<code>/viewelo 123456789</code>\n\n"
            "<i>Для просмотра собственного ELO:</i>\n"
            "<code>/viewelo self</code>",
            parse_mode="html"
        )
        return
    
    target_arg = args[1].lower()
    
    # Определяем ID целевого пользователя
    if target_arg == "self":
        target_user_id = message.from_user.id
    else:
        try:
            target_user_id = int(target_arg)
        except ValueError:
            await message.reply(
                "❌ <b>Неверный формат ID!</b>\n\n"
                "ID пользователя должен быть числом.\n\n"
                "<b>Пример:</b> <code>/viewelo 123456789</code>",
                parse_mode="html"
            )
            return
    
    try:
        # Получаем данные ELO
        user_elo = get_user_elo(target_user_id)
        
        if not user_elo:
            await message.reply(
                f"❌ <b>Статистика не найдена!</b>\n\n"
                f"У пользователя с ID {target_user_id} еще нет статистики ELO.",
                parse_mode="html"
            )
            return
        
        # Пытаемся получить имя пользователя
        try:
            target_user = await bot.get_chat(target_user_id)
            username = f"@{target_user.username}" if target_user.username else target_user.first_name
        except:
            username = f"ID: {target_user_id}"
        
        # Рассчитываем процент побед
        total_matches = user_elo['total_matches']
        win_rate = (user_elo['wins'] / total_matches * 100) if total_matches > 0 else 0
        
        # Формируем подробную статистику
        stats_message = (
            f"📊 <b>СТАТИСТИКА ИГРОКА</b>\n\n"
            f"👤 <b>Игрок:</b> {username}\n"
            f"🆔 <b>ID:</b> {target_user_id}\n\n"
            f"🏅 <b>ELO рейтинг:</b> {user_elo['elo_rating']}\n"
            f"🎮 <b>Всего матчей:</b> {total_matches}\n"
            f"✅ <b>Побед:</b> {user_elo['wins']}\n"
            f"❌ <b>Поражений:</b> {user_elo['losses']}\n"
            f"🤝 <b>Ничьих:</b> {user_elo['draws']}\n"
            f"📈 <b>Процент побед:</b> {win_rate:.1f}%\n\n"
            f"⚽ <b>Забито голов:</b> {user_elo['goals_scored']}\n"
            f"🧱 <b>Пропущено голов:</b> {user_elo['goals_conceded']}\n"
            f"📊 <b>Разница голов:</b> {user_elo['goals_scored'] - user_elo['goals_conceded']:+d}\n\n"
        )
        
        # Добавляем средние показатели
        if total_matches > 0:
            avg_goals_scored = user_elo['goals_scored'] / total_matches
            avg_goals_conceded = user_elo['goals_conceded'] / total_matches
            
            stats_message += (
                f"📈 <b>Средние показатели за матч:</b>\n"
                f"• Голы забитые: {avg_goals_scored:.2f}\n"
                f"• Голы пропущенные: {avg_goals_conceded:.2f}\n"
            )
        
        await message.reply(
            stats_message,
            parse_mode="html"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при просмотре ELO: {e}")
        await message.reply(
            "❌ <b>Произошла ошибка!</b>\n\n"
            "Не удалось получить статистику. Попробуйте позже.",
            parse_mode="html"
        )



@public_router_pvp.message(Command("resethistory"))
@require_role("старший-администратор")
async def reset_history_command(message: Message, bot: Bot):
    """Сбрасывает историю матчей пользователя"""
    
    # Получаем аргументы команды
    args = message.text.split()
    
    if len(args) < 2:
        await message.reply(
            "📝 <b>Использование команды:</b>\n"
            "<code>/resethistory [ID_пользователя]</code>\n\n"
            "<b>Пример:</b>\n"
            "<code>/resethistory 123456789</code>\n\n"
            "<i>Для сброса собственной истории:</i>\n"
            "<code>/resethistory self</code>\n\n"
            "<b>⚠️ Внимание:</b> Это действие нельзя отменить!",
            parse_mode="html"
        )
        return
    
    target_arg = args[1].lower()
    
    # Определяем ID целевого пользователя
    if target_arg == "self":
        target_user_id = message.from_user.id
        target_name = "вашу"
    else:
        try:
            target_user_id = int(target_arg)
            # Проверяем, существует ли пользователь
            result = db_operation(
                "SELECT id FROM all_users WHERE id = ?",
                (target_user_id,),
                fetch=True
            )
            
            if not result:
                await message.reply(
                    f"❌ <b>Пользователь не найден!</b>\n\n"
                    f"Пользователь с ID {target_user_id} не зарегистрирован в системе.",
                    parse_mode="html"
                )
                return
            
            target_name = f"пользователя {target_user_id}"
            
        except ValueError:
            await message.reply(
                "❌ <b>Неверный формат ID!</b>\n\n"
                "ID пользователя должен быть числом.\n\n"
                "<b>Пример:</b> <code>/resethistory 123456789</code>",
                parse_mode="html"
            )
            return
    
    # Подтверждение действия
    confirmation_text = (
        f"⚠️ <b>ПОДТВЕРЖДЕНИЕ ДЕЙСТВИЯ</b>\n\n"
        f"Вы собираетесь сбросить историю матчей {target_name}.\n\n"
        f"<b>Будут удалены:</b>\n"
        f"• Вся история матчей против ботов\n"
        f"• Вся история PvP матчей\n"
        f"• Статистика будет сохранена\n\n"
        f"<i>Это действие нельзя отменить!</i>\n\n"
        f"Для подтверждения введите:\n"
        f"<code>/confirmresethistory {target_user_id}</code>"
    )
    
    await message.reply(
        confirmation_text,
        parse_mode="html"
    )

@public_router_pvp.message(Command("confirmresethistory"))
@require_role("старший-администратор")
async def confirm_reset_history_command(message: Message, bot: Bot):
    """Подтверждение сброса истории матчей"""
    
    # Получаем аргументы команды
    args = message.text.split()
    
    if len(args) < 2:
        await message.reply(
            "❌ <b>Не указан ID пользователя!</b>",
            parse_mode="html"
        )
        return
    
    try:
        target_user_id = int(args[1])
        
        # Проверяем, существует ли пользователь
        result = db_operation(
            "SELECT id FROM all_users WHERE id = ?",
            (target_user_id,),
            fetch=True
        )
        
        if not result:
            await message.reply(
                f"❌ <b>Пользователь не найден!</b>",
                parse_mode="html"
            )
            return
        
        # Получаем текущую статистику перед удалением
        current_elo = get_user_elo(target_user_id)
        
        # Удаляем историю матчей
        deleted_count = 0
        
        # Удаляем обычную историю матчей
        result1 = db_operation(
            "DELETE FROM match_history WHERE user_id = ?",
            (target_user_id,)
        )
        
        # Удаляем историю PvP матчей
        result2 = db_operation(
            "DELETE FROM pvp_match_history WHERE player1_id = ? OR player2_id = ?",
            (target_user_id, target_user_id)
        )
        
        # Удаляем из очереди PvP
        remove_from_pvp_queue(target_user_id)
        
        # Пытаемся получить имя пользователя
        try:
            target_user = await bot.get_chat(target_user_id)
            username = f"@{target_user.username}" if target_user.username else target_user.first_name
        except:
            username = f"ID: {target_user_id}"
        
        # Формируем ответ
        success_message = (
            f"✅ <b>ИСТОРИЯ УСПЕШНО СБРОШЕНА!</b>\n\n"
            f"Пользователь: <b>{username}</b>\n"
            f"ID: {target_user_id}\n\n"
            f"<b>Удалено:</b>\n"
            f"• Вся история матчей\n"
            f"• Вся история PvP матчей\n"
            f"• Записи из очереди PvP\n\n"
            f"<b>Сохранено:</b>\n"
            f"• ELO рейтинг: {current_elo['elo_rating'] if current_elo else 200}\n"
            f"• Общая статистика\n\n"
            f"<i>История успешно очищена администратором {message.from_user.first_name}</i>"
        )
        
        await message.reply(
            success_message,
            parse_mode="html"
        )
        
        logger.info(f"История матчей пользователя {target_user_id} сброшена администратором {message.from_user.id}")
        
        # Отправляем уведомление пользователю
        try:
            await bot.send_message(
                chat_id=target_user_id,
                text=f"🔄 <b>ИСТОРИЯ ОБНОВЛЕНА</b>\n\n"
                     f"Ваша история матчей была сброшена администратором.\n\n"
                     f"• <b>Статистика сохранена:</b> Да\n"
                     f"• <b>ELO рейтинг:</b> {current_elo['elo_rating'] if current_elo else 200}\n\n"
                     f"<i>Теперь вы можете начать новую историю матчей!</i>",
                parse_mode="html"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление пользователю {target_user_id}: {e}")
        
    except ValueError:
        await message.reply(
            "❌ <b>Неверный формат ID!</b>",
            parse_mode="html"
        )
    except Exception as e:
        logger.error(f"Ошибка при сбросе истории: {e}")
        await message.reply(
            "❌ <b>Произошла ошибка!</b>\n\n"
            "Не удалось сбросить историю матчей. Попробуйте позже.",
            parse_mode="html"
        )

def get_top_players_by_elo(limit: int = 10):
    """Получает топ игроков по ELO рейтингу"""
    try:
        result = db_operation('''
            SELECT u.user_id, 
                   COALESCE(u.telegram_id, u.user_id) as telegram_id,
                   e.elo_rating, 
                   e.total_matches,
                   e.wins,
                   e.losses,
                   e.draws,
                   e.goals_scored,
                   e.goals_conceded
            FROM user_elo e
            LEFT JOIN all_users u ON e.user_id = u.id
            WHERE e.total_matches > 0
            ORDER BY e.elo_rating DESC
            LIMIT ?
        ''', (limit,), fetch=True)
        
        players = []
        for row in result:
            players.append({
                'user_id': row[0],
                'telegram_id': row[1],
                'elo_rating': row[2],
                'total_matches': row[3],
                'wins': row[4],
                'losses': row[5],
                'draws': row[6],
                'goals_scored': row[7],
                'goals_conceded': row[8]
            })
        
        return players
    except Exception as e:
        logger.error(f"Ошибка при получении топ игроков: {e}")
        return []
    
@public_router_pvp.callback_query(F.data == "top_players")
@handle_old_callback
async def show_top_players(callback: CallbackQuery):
    """Показывает топ игроков по ELO рейтингу"""
    try:
        # Получаем топ 10 игроков из базы данных
        result = db_operation(
            """SELECT user_id, elo_rating, total_matches, wins, 
                      (SELECT username FROM all_users WHERE id = user_elo.user_id) as username
               FROM user_elo 
               WHERE total_matches > 0
               ORDER BY elo_rating DESC
               LIMIT 10""",
            fetch=True
        )
        
        if not result:
            await callback.message.edit_text(
                "📊 <b>ТОП ИГРОКОВ</b>\n\n"
                "🎮 Пока нет игроков с рейтингом ELO.\n\n"
                "⚽ <b>Сыграйте первый матч, чтобы попасть в рейтинг!</b>",
                parse_mode="html",
                reply_markup=InlineKeyboardBuilder()
                .add(InlineKeyboardButton(text="⚽ Сыграть матч", callback_data="play_match"))
                .add(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_play_menu"))
                .adjust(2)
                .as_markup()
            )
            await callback.answer()
            return
        
        # Формируем сообщение с топом
        message_text = "🏆 <b>ТОП 10 ИГРОКОВ ПО ELO</b>\n\n"
        
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        
        for i, row in enumerate(result):
            user_id, elo_rating, total_matches, wins, username = row
            
            # Рассчитываем процент побед
            win_rate = (wins / total_matches * 100) if total_matches > 0 else 0
            
            # Форматируем имя пользователя
            if username:
                if username.startswith('@'):
                    display_name = username
                else:
                    display_name = username
            else:
                display_name = f"Игрок {user_id}"
            
            # Ограничиваем длину имени
            if len(display_name) > 15:
                display_name = display_name[:12] + "..."
            
            # Добавляем строку в топ
            medal = medals[i] if i < len(medals) else f"{i+1}."
            message_text += (
                f"{medal} <b>{display_name}</b>\n"
                f"   🏅 ELO: <b>{elo_rating}</b>\n"
                f"   🎮 Матчей: {total_matches} | ✅ Побед: {wins} ({win_rate:.1f}%)\n\n"
            )
        
        message_text += (
            "<i>Рейтинг обновляется после каждого матча.</i>\n"
            "<i>Чем больше побед — тем выше рейтинг!</i>"
        )
        
        # Создаем клавиатуру
        builder = InlineKeyboardBuilder()
        
        # Кнопки навигации
        builder.row(
            InlineKeyboardButton(text="📊 Моя статистика", callback_data="statistics"),
            InlineKeyboardButton(text="⚽ Играть", callback_data="play_match")
        )
        builder.row(
            InlineKeyboardButton(text="🔄 Обновить", callback_data="top_players"),
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_play_menu")
        )
        
        await callback.message.edit_text(
            message_text,
            parse_mode="html",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка при показе топа игроков: {e}")
        await callback.message.edit_text(
            "❌ <b>Ошибка при загрузке топа игроков</b>\n\n"
            "Попробуйте обновить или обратитесь к администратору.",
            parse_mode="html",
            reply_markup=InlineKeyboardBuilder()
            .add(InlineKeyboardButton(text="🔄 Обновить", callback_data="top_players"))
            .add(InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_play_menu"))
            .adjust(2)
            .as_markup()
        )
        await callback.answer("❌ Ошибка", show_alert=True)