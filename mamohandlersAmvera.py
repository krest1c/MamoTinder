# mamohandlers.py
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

from mamodatabases import init_databases, logger, BASE_DIR, db_operation,log_command, log_admin_action, log_mute_action,log_profile_action, format_moscow_time,get_card_by_id,get_players_from_source,get_user_filter,save_user_filter,validate_input,seed_players_catalog, SimpleLogger
from mamoadmins import is_user_banned, get_ban_info, get_mute_info, get_admin_role, get_all_muted_users, require_role, SupportStates, get_random_card_image, is_muted, unmute_user, get_card_by_nickname_db, getcard_command, get_specific_card_image,get_card_owners_count, get_all_cards_from_db,get_fammo_cooldown_status,get_user_card_stats, update_user_coins
from mamofkarta import get_user_info, get_purchase_history, get_new_card_for_user


router = Router()
router.message.filter(F.chat.type == "private")
router.callback_query.filter(F.message.chat.type == "private")


public_router = Router()


group_of_admins = -1003615487276
#-----------------------
MOSCOW_TZ = pytz.timezone('Europe/Moscow')
from mamoadmins import scheduler, scheduler_initialized
def setup_scheduler(bot: Bot):
    """Настройка и запуск планировщика для рассылки"""
    global scheduler, scheduler_initialized
    
    if scheduler_initialized:
        return scheduler
    
    scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)
    
    # Рассылка в 12:00 по МСК
    scheduler.add_job(
        send_broadcast_message,
        CronTrigger(hour=10, minute=0, timezone=MOSCOW_TZ),
        args=[bot],
        id='broadcast_12_00',
        replace_existing=True,
        misfire_grace_time=300  # 5 минут на опоздание
    )
    scheduler.add_job(
        cleanup_old_logs_daily,
        CronTrigger(hour=3, minute=0, timezone="Europe/Moscow"),
        id="daily_log_cleanup",
        replace_existing=True,
        name="Ежедневная очистка старых логов"
    )
    
    
    # Рассылка в 18:00 по МСК
    scheduler.add_job(
        send_broadcast_message,
        CronTrigger(hour=20, minute=00, timezone=MOSCOW_TZ),
        args=[bot],
        id='broadcast_18_00',
        replace_existing=True,
        misfire_grace_time=300
    )
    
  
    
    scheduler_initialized = True
    return scheduler
async def cleanup_old_logs_daily():
    """Ежедневная автоматическая очистка логов старше 7 дней"""
    try:
        from mamodatabases import cleanup_all_logs
        deleted_count = cleanup_all_logs(days=7)
        if deleted_count > 0:
            logger.info(f"🗑️ Автоматическая очистка логов: удалено {deleted_count} файлов старше 7 дней")
        return deleted_count
    except Exception as e:
        logger.error(f"Ошибка при автоматической очистке логов: {e}")
        return 0
async def send_broadcast_message(bot: Bot):
    """Отправка рассылки всем пользователям"""
    try:
        logger.info("🔄 Начинаю автоматическую рассылку...")
        
        # Получаем всех пользователей
        users = db_operation(
            "SELECT id FROM all_users",
            fetch=True
        )
        
        if not users:
            logger.info("📭 Нет пользователей для рассылки")
            return
        
        total_users = len(users)
        success_count = 0
        fail_count = 0
        
        message_text = (
            "🎮 <b>Твои карточки ждут! Заходи в бота и оживи свои ФМАМО!</b>\n\n"
            "👉 @mamoballtinder\n"
            "<i>Удачи в матчах</i> 🍀"
        )
        
        # Отправляем сообщение каждому пользователю
        for user_tuple in users:
            user_id = user_tuple[0]
            
            try:
                await bot.send_message(
                    user_id,
                    message_text,
                    parse_mode="html"
                )
                success_count += 1
                
                # Пауза между отправками, чтобы не получить flood control
                await asyncio.sleep(0.1)
                
            except Exception as e:
                fail_count += 1
                # Логируем только серьезные ошибки (не блокировки бота)
                if "blocked" not in str(e).lower() and "deactivated" not in str(e).lower():
                    logger.warning(f"Не удалось отправить рассылку пользователю {user_id}: {str(e)[:50]}")
        
        # Логируем результат
        logger.info(
            f"📊 Рассылка завершена. "
            f"Успешно: {success_count}, Ошибок: {fail_count}, Всего: {total_users}"
        )
        
        # Отправляем отчет администраторам
        await send_broadcast_report_to_admins(bot, success_count, fail_count, total_users)
        
    except Exception as e:
        logger.error(f"❌ Ошибка при выполнении рассылки: {str(e)}")

async def send_broadcast_report_to_admins(bot: Bot, success: int, fail: int, total: int):
    """Отправка отчета о рассылке администраторам"""
    try:
        report_message = (
            f"📊 <b>Отчет об автоматической рассылке</b>\n\n"
            f"🕐 <b>Время:</b> {datetime.now(MOSCOW_TZ).strftime('%H:%M %d.%m.%Y')}\n"
            f"👥 <b>Всего пользователей:</b> {total}\n"
            f"✅ <b>Успешно отправлено:</b> {success}\n"
            f"❌ <b>Ошибок:</b> {fail}\n"
            f"📈 <b>Процент доставки:</b> {round((success/total)*100, 1) if total > 0 else 0}%\n\n"
            f"<i>Рассылка выполнена автоматически</i>"
        )
        
        # Отправляем каждому администратору

        await bot.send_message(1088006569, report_message, parse_mode="html")
        await asyncio.sleep(0.1)

                
    except Exception as e:
        logger.error(f"Ошибка при отправке отчета админам: {e}")

@router.message(F.text == "❌ Отмена заявки")
async def otmena_request(message: Message, state: FSMContext):
    await state.clear()
    await message.reply("❌ Создание заявки отменено.", reply_markup=ReplyKeyboardRemove())

@router.message(Command("request"))
async def request_message(message: Message, state: FSMContext):
    text = """🎫 <b>Перед подачей заявки в ФМАМОКАРТУ, ознакомьтесь с правилами:</b>

⚠️ <b>Важно:</b>
• Рофл заявка — <b>бан в боте</b> ❌
• Оскорбление, оффтоп и т.д. — <b>мут на 5 дней</b> 🔇
• Отправление не по форме — <b>заявка рассматриваться НЕ будет</b> 📝

━━━━━━━━━━━━━━━━━━━━

📋 <b>ФОРМА ЗАЯВКИ:</b>
1️⃣ <b>Ник</b>
2️⃣ <b>Клуб</b>
3️⃣ <b>Позиция</b>
4️⃣ <b>Редкость</b> (по умолчанию — редкая ⭐)
   • Эпик — 15 звёзд 🌟
   • Легендарная — 25 звёзд 🌟🌟
   • Суперлегендарная — 50 звёзд 🌟🌟🌟
   <i>(оплата на аккаунт)</i>
5️⃣ <b>Требуется ли привязка игрока</b> (да/нет) 
   • Стоимость — 15 звёзд 💎
   <i>Привязка работает следующим образом:</i>
   После одобрения заявки администратором в чате с @kirik1231zzap 
   Вы сможете написать игрока, который будет закреплён за Вами.
   Только <b>ВАША</b> карточка будет иметь данного ИГРОКА 👤
6️⃣ <b>Если ЕЕА — див, в котором играете</b> 🎮

━━━━━━━━━━━━━━━━━━━━

⏳ <b>Процесс после подачи:</b>
1. <b>Дождитесь одобрения</b> администратором ✅
2. <b>Получите уведомление</b> в боте 📲
3. <b>Свяжитесь с овнером</b> для оплаты (если требуется) 💬
4. <b>Произведите оплату</b> 💳
5. <b>Ваша карточка будет добавлена</b>! 🎊

━━━━━━━━━━━━━━━━━━━━

📝 <b>Напишите заявку по форме выше (ОБЯЗАТЕЛЬНО УКАЗАТЬ 6 ПУНКТОВ):</b>"""
    
    await message.reply(text,reply_markup=kb.request_otmena_kb, parse_mode="HTML")
    await state.set_state(SupportStates.waiting_for_request)



@router.message(SupportStates.waiting_for_request)
async def request_message1(message: Message, state: FSMContext, bot: Bot):
    request_from_user = message.text 
    user_id = message.from_user.id
    username = message.from_user.username or "без username"
    group_id = 1088006569  # ID чата админа
    
    await message.reply("✅ Ваша заявка отправлена!\n\nОжидайте ответа в ближайшие 72 часа.")
    
    # Сохраняем user_id в состоянии перед очисткой
    await state.update_data(user_id=user_id)
    
    # Отправляем заявку админу
    msg_text = f"📋 <b>Новая заявка</b>\n\n👤 <b>Пользователь:</b> @{username}\n🆔 <b>ID:</b> <code>{user_id}</code>\n\n📝 <b>Заявка:</b>\n{request_from_user}"
    
    sent_message = await bot.send_message(
        group_id, 
        msg_text,
        parse_mode="HTML",
        reply_markup=kb.request_keyboard
    )
    
    # Сохраняем данные о заявке в словарь или БД
    # Для простоты используем глобальный словарь
    from datetime import datetime
    import hashlib
    
    # Создаем уникальный ID для заявки
    request_hash = hashlib.md5(f"{user_id}_{datetime.now().timestamp()}".encode()).hexdigest()[:8]
    
    # Сохраняем в памяти (в реальном проекте лучше использовать БД)
    if not hasattr(bot, 'requests_data'):
        bot.requests_data = {}
    
    bot.requests_data[request_hash] = {
        'user_id': user_id,
        'username': username,
        'request_text': request_from_user,
        'group_message_id': sent_message.message_id,
        'status': 'pending',
        'timestamp': datetime.now()
    }
    
    # Добавляем hash в callback_data
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Одобрить заявку", callback_data=f"accept_{request_hash}")],
        [InlineKeyboardButton(text="❌ Отклонить заявку", callback_data=f"deny_{request_hash}")]
    ])
    
    # Редактируем сообщение с новыми кнопками
    await sent_message.edit_reply_markup(reply_markup=keyboard)
    
    await state.clear()


@router.callback_query(F.data.startswith("accept_"))
async def accept_request_callback(callback: CallbackQuery, bot: Bot):
    try:
        request_hash = callback.data.split("_")[1]
        
        # Получаем данные заявки
        if not hasattr(bot, 'requests_data') or request_hash not in bot.requests_data:
            await callback.answer("❌ Заявка не найдена или устарела", show_alert=True)
            return
        
        request_data = bot.requests_data[request_hash]
        user_id = request_data['user_id']
        username = request_data['username']
        request_text = request_data['request_text']
        
        # Обновляем статус
        request_data['status'] = 'accepted'
        
        # Пробуем отправить сообщение пользователю
        try:
            await bot.send_message(
                user_id, 
                "✅ Ваша заявка одобрена. Если Вам нужно что-то оплатить, перейдите в чат @kirik1231zzap"
            )
            user_notified = True
        except Exception as e:
            user_notified = False
            print(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
        
        # Редактируем сообщение с заявкой
        admin_username = callback.from_user.username or callback.from_user.first_name
        notification_status = "✅ Пользователь уведомлён" if user_notified else "⚠️ Не удалось уведомить пользователя"
        
        edited_text = f"""✅ <b>Заявка одобрена администратором @{admin_username}</b>
{notification_status}

👤 <b>Пользователь:</b> @{username}
🆔 <b>ID:</b> <code>{user_id}</code>

📝 <b>Заявка:</b>
{request_text}"""
        
        await callback.message.edit_text(
            edited_text,
            parse_mode="HTML",
            reply_markup=None
        )
        
        if user_notified:
            await callback.answer("✅ Заявка одобрена. Пользователь уведомлён.")
        else:
            await callback.answer("✅ Заявка одобрена, но не удалось уведомить пользователя", show_alert=True)
        
    except Exception as e:
        print(f"Ошибка в accept_request_callback: {e}")
        await callback.answer(f"❌ Произошла ошибка: {str(e)[:100]}", show_alert=True)


@router.callback_query(F.data.startswith("deny_"))
async def deny_request_callback(callback: CallbackQuery, bot: Bot):
    try:
        request_hash = callback.data.split("_")[1]
        
        # Получаем данные заявки
        if not hasattr(bot, 'requests_data') or request_hash not in bot.requests_data:
            await callback.answer("❌ Заявка не найдена или устарела", show_alert=True)
            return
        
        request_data = bot.requests_data[request_hash]
        user_id = request_data['user_id']
        username = request_data['username']
        request_text = request_data['request_text']
        
        # Обновляем статус
        request_data['status'] = 'denied'
        
        # Пробуем отправить сообщение пользователю
        try:
            await bot.send_message(
                user_id, 
                "❌ Ваша заявка отклонена. Попробуйте перезаполнить."
            )
            user_notified = True
        except Exception as e:
            user_notified = False
            print(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
        
        # Редактируем сообщение с заявкой
        admin_username = callback.from_user.username or callback.from_user.first_name
        notification_status = "✅ Пользователь уведомлён" if user_notified else "⚠️ Не удалось уведомить пользователя"
        
        edited_text = f"""❌ <b>Заявка отклонена администратором @{admin_username}</b>
{notification_status}

👤 <b>Пользователь:</b> @{username}
🆔 <b>ID:</b> <code>{user_id}</code>

📝 <b>Заявка:</b>
{request_text}"""
        
        await callback.message.edit_text(
            edited_text,
            parse_mode="HTML",
            reply_markup=None
        )
        
        if user_notified:
            await callback.answer("❌ Заявка отклонена. Пользователь уведомлён.")
        else:
            await callback.answer("❌ Заявка отклонена, но не удалось уведомить пользователя", show_alert=True)
        
    except Exception as e:
        print(f"Ошибка в deny_request_callback: {e}")
        await callback.answer(f"❌ Произошла ошибка: {str(e)[:100]}", show_alert=True)

#-----------------------

@router.message(CommandStart())
@log_command
async def cmd_start_bot(message: Message, bot: Bot):
    if message.chat.type != "private":
        await message.reply(
            "⚠️ <b>Этот бот работает только в личных сообщениях!</b>\n\n"
            "Пожалуйста, напишите мне в личные сообщения: @mamoballtinder_bot\n\n"
            "Или нажмите кнопку ниже:",
            parse_mode="html",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🤖 Написать боту",
                            url="https://t.me/mamoballtinder_bot"
                        )
                    ]
                ]
            )
        )
        return
    try:
        # ПЕРВОЕ: Проверяем, не забанен ли пользователь
        if is_user_banned(message.from_user.id):
            ban_info = get_ban_info(message.from_user.id)
            if ban_info:
                ban_reason = ban_info['ban_reason']
                banned_at = ban_info['banned_at']
                await message.reply(
                    f"🚫 <b>Вы забанены в боте MamoTinder</b>\n\n"
                    f"<b>Дата бана:</b> {banned_at} (по Гринвичу)\n"
                    f"<b>Причина:</b> {ban_reason}\n\n"
                    f"<i>Вы можете оспорить это решение, написав напрямую @kirik1231zzap</i> ",
                    parse_mode="html",
                    reply_markup=kb.register
                )
            else:
                await message.reply(
                    "🚫 <b>Вы забанены в боте MamoTinder</b>\n\n"
                    f"<i>Вы можете оспорить это решение, написав напрямую @kirik1231zzap</i> ",
                    parse_mode="html",
                    reply_markup=kb.register
                )
            return
            
        # ВТОРОЕ: Проверяем подписку на ОБА ОБЯЗАТЕЛЬНЫХ канала
        try:
            # Проверяем подписку на @mamoballtinder
            member_tinder = await bot.get_chat_member(chat_id="@mamoballtinder", user_id=message.from_user.id)
            status_tinder = member_tinder.status
            
            # Проверяем подписку на @romamamoball
            member_roma = await bot.get_chat_member(chat_id='@romamamoball', user_id=message.from_user.id)
            status_roma = member_roma.status
            
            # Проверяем, подписан ли пользователь на ОБА канала
            is_tinder_subscribed = status_tinder in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
            is_roma_subscribed = status_roma in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
            
            missing_channels = []
            if not is_tinder_subscribed:
                missing_channels.append("@mamoballtinder")
            if not is_roma_subscribed:
                missing_channels.append("@romamamoball")
            
            if missing_channels:
                channels_text = " и ".join(missing_channels)
                await message.reply(
                    f"📢 <b>Для использования бота необходимо подписаться на каналы:</b>\n\n"
                    f"📌 <b>Обязательные каналы:</b>\n"
                    f"• @mamoballtinder\n"
                    f"• @romamamoball\n\n"
                    f"❌ <b>Вы не подписаны на:</b> {channels_text}\n\n"
                    f"После подписки нажмите /start еще раз.",
                    parse_mode="html",
                    reply_markup=kb.get_subscription_keyboard_all()
                )
                return
                
        except Exception as channel_error:
            logger.warning(f"Не удалось проверить подписку: {channel_error}")
            # Продолжаем, но с предупреждением
            await message.reply(
                "⚠️ <b>Не удалось проверить подписку на каналы.</b>\n\n"
                "Пожалуйста, убедитесь, что вы подписаны на ОБА канала:\n"
                "1. @mamoballtinder\n"
                "2. @romamamoball\n\n"
                "Для продолжения нажмите /start еще раз.",
                parse_mode="html",
                reply_markup=kb.get_subscription_keyboard_all()
            )
            return

        # ТРЕТЬЕ: Проверяем регистрацию пользователя
        result = db_operation(
            "SELECT id FROM all_users WHERE id = ?",
            (message.from_user.id,),
            fetch=True
        )
        
        if result:
            # Пользователь уже зарегистрирован - показываем общее меню
            await message.reply(
                "✅ Вы уже зарегистрированы!\n"
                "📌 Помните: Для использования бота вы должны оставаться подписанным на оба канала:\n"
                "• @mamoballtinder\n"
                "• @romamamoball\n\n"
                "Помощь по боту: /help",
                reply_markup=kb.main_general  # НОВОЕ ОБЩЕЕ МЕНЮ
            )
        else:
            # Новый пользователь - показываем регистрацию
            await bot.send_message(
                message.chat.id,
                "✅ <b>Подписка на оба канала подтверждена!</b>\n\n"
                "<b>Привет! Перед началом нашей совместной работы давай <u>зарегистрируемся!</u></b>",
                parse_mode="html",
                reply_markup=kb.register
            )
                
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Ошибка при запуске бота: {error_msg}")
        
        if "member list is inaccessible" in error_msg:
            await bot.send_message(
                message.chat.id,
                "⚠️ <b>Не удалось проверить подписку.</b>\n\n"
                "Пожалуйста, убедитесь, что вы подписаны на ОБА канала:\n"
                "1. @mamoballtinder\n"
                "2. @romamamoball\n\n"
                "и повторите попытку через /start",
                parse_mode="html",
                reply_markup=kb.get_subscription_keyboard_all()
            )
        else:
            await message.reply(
                f"❌ Ошибка при запуске: {str(e)[:100]}\n\n"
                "Попробуйте еще раз через /start",
                reply_markup=kb.main_general)   

#---------------------------
#Fmamokarta
public_router = Router()

#===================
#команда /allcards


#===================




















































































































#==========================
#---------------------------
@router.callback_query(F.data == "check_subscription_all")
async def check_subscription_all_handler(callback: CallbackQuery, bot: Bot):
    """Проверка подписки на ОБА канала после нажатия кнопки"""
    try:
        # Проверяем подписку на @mamoballtinder
        member_tinder = await bot.get_chat_member(chat_id="@mamoballtinder", user_id=callback.from_user.id)
        status_tinder = member_tinder.status
        
        # Проверяем подписку на @romamamoball
        member_roma = await bot.get_chat_member(chat_id='@romamamoball', user_id=callback.from_user.id)
        status_roma = member_roma.status
        
        # Проверяем, подписан ли пользователь на ОБА канала
        is_tinder_subscribed = status_tinder in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
        is_roma_subscribed = status_roma in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
        
        if is_tinder_subscribed and is_roma_subscribed:
            await callback.message.edit_text(
                "✅ <b>Отлично! Подписка на оба канала подтверждена.</b>\n\n"
                "Теперь вы можете использовать бота.\n"
                "Нажмите /start для начала работы.",
                parse_mode="html"
            )
        elif is_tinder_subscribed and not is_roma_subscribed:
            await callback.answer(
                "❌ Вы подписаны только на @mamoballtinder\n"
                "Подпишитесь также на @romamamoball!",
                show_alert=True
            )
        elif not is_tinder_subscribed and is_roma_subscribed:
            await callback.answer(
                "❌ Вы подписаны только на @romamamoball\n"
                "Подпишитесь также на @mamoballtinder!",
                show_alert=True
            )
        else:
            await callback.answer(
                "❌ Вы не подписаны ни на один из каналов!\n"
                "Подпишитесь на @mamoballtinder и @romamamoball!",
                show_alert=True
            )
            
    except Exception as e:
        logger.error(f"Ошибка при проверке подписки: {e}")
        await callback.answer(
            "❌ Ошибка при проверке подписки. Попробуйте позже.",
            show_alert=True
        )

# В mamohandlersTEST.py добавьте функцию:

async def check_user_subscription_all(user_id: int, bot: Bot) -> tuple[bool, list]:
    """
    Проверяет подписку пользователя на оба канала.
    Возвращает (is_subscribed, missing_channels)
    """
    try:
        missing_channels = []
        
        # Проверяем подписку на @mamoballtinder
        try:
            member_tinder = await bot.get_chat_member(chat_id="@mamoballtinder", user_id=user_id)
            status_tinder = member_tinder.status
            if status_tinder not in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                missing_channels.append("@mamoballtinder")
        except Exception as e:
            logger.warning(f"Не удалось проверить подписку на @mamoballtinder: {e}")
            missing_channels.append("@mamoballtinder")
        
        # Проверяем подписку на @romamamoball
        try:
            member_roma = await bot.get_chat_member(chat_id='@romamamoball', user_id=user_id)
            status_roma = member_roma.status
            if status_roma not in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                missing_channels.append("@romamamoball")
        except Exception as e:
            logger.warning(f"Не удалось проверить подписку на @romamamoball: {e}")
            missing_channels.append("@romamamoball")
        
        return len(missing_channels) == 0, missing_channels
        
    except Exception as e:
        logger.error(f"Ошибка при проверке подписки пользователя {user_id}: {e}")
        return False, ["@mamoballtinder", "@romamamoball"]
#---------------------------
@router.message(Command("help"))
async def help_command(message: Message):
    await message.reply(
       "Пропиши ФМАМО в любом чате, где есть бот и получи свою карточку!\n",
        parse_mode="html"
    )
#---------------------------

@router.callback_query(F.data == "registerTrue")
async def register1(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки регистрации с проверкой бана"""
    try:
        # Проверяем, не забанен ли пользователь
        if is_user_banned(callback.from_user.id):
            ban_info = get_ban_info(callback.from_user.id)
            if ban_info:
                ban_reason = ban_info['ban_reason']
                await callback.answer(
                    f"🚫 Вы забанены в боте. Причина: {ban_reason}",
                    show_alert=True
                )
            else:
                await callback.answer(
                    "🚫 Вы забанены в боте и не можете регистрироваться",
                    show_alert=True
                )
            return
        
        # Если не забанен - продолжаем регистрацию
        await callback.message.edit_text("<b>Как мне тебя называть?</b>", parse_mode="html")
        await state.set_state(SupportStates.nickname_of_user)
        
    except Exception as e:
        logger.error(f"Ошибка в обработчике регистрации: {e}")
        await callback.answer("❌ Ошибка при регистрации", show_alert=True)


@router.message(SupportStates.nickname_of_user)
async def nickname_of_user(message: Message, state: FSMContext):
    try:
        nickname_of_user = message.text.lower()
        
        try:
            # Регистрируем пользователя без типа (user_type будет NULL или можно установить 'general')
            db_operation(
                "INSERT INTO all_users (username, id, first_name, is_premium, country, nickname) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    message.from_user.username,
                    message.from_user.id,
                    message.from_user.first_name,
                    str(message.from_user.is_premium),
                    message.from_user.language_code,
                    nickname_of_user
                    # user_type НЕ указываем - пользователь без роли
                )
            )
            
            # Сразу показываем общее меню
            await message.reply(
                f"✅ Вы успешно зарегистрированы! Добро пожаловать, <b>{nickname_of_user}</b>\n\n"
                "📌 Помните: Для использования бота вы должны оставаться подписанным на оба канала:\n"
                "• @mamoballtinder\n"
                "• @romamamoball\n\n"
                "Помощь по боту: /help",
                parse_mode="html",
                reply_markup=kb.main_general  # НОВОЕ МЕНЮ ДЛЯ ВСЕХ ПОЛЬЗОВАТЕЛЕЙ
            )
            await state.clear()
            
        except sqlite3.IntegrityError:
            await message.reply(
                "❌ Этот никнейм уже занят или вы уже зарегистрированы. Попробуйте другой никнейм.",
                reply_markup=kb.main_general
            )
            await state.clear()
            
    except Exception as e:
        await message.reply(f"❌ Ошибка при регистрации: {str(e)[:100]}", reply_markup=kb.main_general)
        await state.clear()


@router.message(F.text == "👤 Я ищу клуб")
async def select_player_type(message: Message):
    """Пользователь выбирает роль игрока"""
    try:
        # Обновляем тип пользователя в базе
        db_operation(
            "UPDATE all_users SET user_type = ? WHERE id = ?",
            ('player', message.from_user.id)
        )
        
        await message.reply(
            "✅ Вы зарегистрированы как <b>игрок</b>!\n\n"
            "Теперь вы можете создать анкету для поиска клуба.",
            parse_mode="html",
            reply_markup=kb.main_player
        )
    except Exception as e:
        await message.reply(f"❌ Ошибка: {str(e)[:100]}", reply_markup=kb.main)



# Добавим в секцию с другими декораторами (после log_mute_action):
# Декоратор для логирования мэтчей (взаимных лайков)
def log_match_action():
    """
    Декоратор для логирования взаимных лайков (мэтчей).
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                # Выполняем оригинальную функцию
                result = await func(*args, **kwargs)
                
                # После успешного выполнения проверяем на мэтч
                # Получаем объект сообщения
                message = None
                for arg in args:
                    if hasattr(arg, 'from_user'):
                        message = arg
                        break
                
                if message:
                    user_id = message.from_user.id
                    user_info = f"@{message.from_user.username}" if message.from_user.username else f"ID: {message.from_user.id}"
                    
                    # Определяем тип пользователя
                    user_type_result = db_operation(
                        "SELECT user_type FROM all_users WHERE id = ?",
                        (user_id,),
                        fetch=True
                    )
                    
                    if user_type_result:
                        user_type = user_type_result[0][0]
                        
                        if user_type == 'player':
                            # Игрок лайкнул клуб - проверяем взаимность
                            await check_and_log_player_match(user_id, user_info)
                        elif user_type == 'owner':
                            # Овнер лайкнул игрока - проверяем взаимность
                            await check_and_log_owner_match(user_id, user_info)
                
                return result
                
            except Exception as e:
                # Если ошибка, все равно возвращаем результат оригинальной функции
                if 'result' in locals():
                    return result
                raise
            
        return wrapper
    return decorator

async def check_and_log_player_match(player_id: int, player_info: str):
    """Проверяет и логирует мэтч для игрока (после того как он лайкнул клуб)"""
    try:
        # Находим последний лайк игрока
        last_like = db_operation(
            "SELECT liked_club_id FROM player_likes WHERE player_id = ? ORDER BY created_at DESC LIMIT 1",
            (player_id,),
            fetch=True
        )
        
        if last_like:
            club_id = last_like[0][0]
            
            # Проверяем, лайкал ли этот клуб данного игрока ранее
            mutual_like = db_operation(
                "SELECT * FROM owner_likes WHERE owner_id = ? AND liked_player_id = ?",
                (club_id, player_id),
                fetch=True
            )
            
            if mutual_like:
                # Это мэтч! Логируем его
                # Получаем информацию о клубе
                club_info_result = db_operation(
                    "SELECT club_name FROM owners_search_players WHERE owner_id = ?",
                    (club_id,),
                    fetch=True
                )
                
                club_name = club_info_result[0][0] if club_info_result else "Неизвестный клуб"
                
                # Получаем информацию о владельце
                owner_info_result = db_operation(
                    "SELECT username, nickname FROM all_users WHERE id = ?",
                    (club_id,),
                    fetch=True
                )
                
                owner_username = ""
                owner_nickname = ""
                if owner_info_result:
                    owner_username = owner_info_result[0][0] or ""
                    owner_nickname = owner_info_result[0][1] or ""
                
                owner_contact = f"@{owner_username}" if owner_username else f"Ник: {owner_nickname}" if owner_nickname else f"ID: {club_id}"
                
                # Получаем информацию об игроке
                player_profile = db_operation(
                    "SELECT nickname FROM users_search_club WHERE player_id = ?",
                    (player_id,),
                    fetch=True
                )
                
                player_nickname = player_profile[0][0] if player_profile else "Неизвестный игрок"
                
                # Получаем username игрока
                player_username_result = db_operation(
                    "SELECT username FROM all_users WHERE id = ?",
                    (player_id,),
                    fetch=True
                )
                
                player_username = player_username_result[0][0] if player_username_result else ""
                player_contact = f"@{player_username}" if player_username else f"Ник: {player_nickname}" if player_nickname else f"ID: {player_id}"
                
                # Логируем мэтч С ВЫВОДОМ ЮЗЕРОВ
                logger.info(
                    f"❤️ МЭТЧ: Игрок @{player_username} ({player_nickname}) и клуб '{club_name}' (владелец: @{owner_username})!\n"
                    f"   Игрок ID: {player_id} (@{player_username}), Клуб ID: {club_id} (@{owner_username})"
                )
                
    except Exception as e:
        logger.error(f"Ошибка при проверке мэтча игрока: {str(e)[:100]}")
@router.message(F.text == "🧐Инфо")
async def main_bot_command(message: Message):
    await message.reply(
        "⚙️Бот разработан стаффом ММБ-организации <b>RGNM</b>\n"
        "<tg-spoiler>https://t.me/romamamoball</tg-spoiler>\n\n<i>Официальный ТГК бота:</i><tg-spoiler>@mamoballtinder</tg-spoiler>\n\n"
        "Обратная связь доступна по кнопке '📣Репорт' в главном меню.\nПоддержка донатом:\n<b>https://www.donationalerts.com/r/mamotinder</b>\n\n\n\n\n<i>Version BETA 4.2.02.26</i>",
        parse_mode="html"
    )
async def check_and_log_owner_match(owner_id: int, owner_info: str):
    """Проверяет и логирует мэтч для владельца клуба (после того как он лайкнул игрока)"""
    try:
        # Находим последний лайк овнера
        last_like = db_operation(
            "SELECT liked_player_id FROM owner_likes WHERE owner_id = ? ORDER BY created_at DESC LIMIT 1",
            (owner_id,),
            fetch=True
        )
        
        if last_like:
            player_id = last_like[0][0]
            
            # Проверяем, лайкал ли этот игрок данный клуб ранее
            mutual_like = db_operation(
                "SELECT * FROM player_likes WHERE player_id = ? AND liked_club_id = ?",
                (player_id, owner_id),
                fetch=True
            )
            
            if mutual_like:
                # Это мэтч! Логируем его
                # Получаем информацию о клубе
                club_info_result = db_operation(
                    "SELECT club_name FROM owners_search_players WHERE owner_id = ?",
                    (owner_id,),
                    fetch=True
                )
                
                club_name = club_info_result[0][0] if club_info_result else "Неизвестный клуб"
                
                # Получаем информацию об игроке
                player_info_result = db_operation(
                    "SELECT username, nickname FROM all_users WHERE id = ?",
                    (player_id,),
                    fetch=True
                )
                
                player_username = ""
                player_nickname = ""
                if player_info_result:
                    player_username = player_info_result[0][0] or ""
                    player_nickname = player_info_result[0][1] or ""
                
                player_contact = f"@{player_username}" if player_username else f"Ник: {player_nickname}" if player_nickname else f"ID: {player_id}"
                
                # Получаем информацию о владельце
                owner_username_result = db_operation(
                    "SELECT username FROM all_users WHERE id = ?",
                    (owner_id,),
                    fetch=True
                )
                
                owner_username = owner_username_result[0][0] if owner_username_result else ""
                owner_contact = f"@{owner_username}" if owner_username else f"Ник: {owner_info}" if owner_info else f"ID: {owner_id}"
                
                # Получаем игровой никнейм
                player_profile = db_operation(
                    "SELECT nickname FROM users_search_club WHERE player_id = ?",
                    (player_id,),
                    fetch=True
                )
                
                player_game_nickname = player_profile[0][0] if player_profile else "Неизвестный игрок"
                
                # Логируем мэтч С ВЫВОДОМ ЮЗЕРОВ
                logger.info(
                    f"❤️ МЭТЧ: Клуб '{club_name}' (владелец: @{owner_username}) и игрок @{player_username} ({player_game_nickname})!\n"
                    f"   Клуб ID: {owner_id} (@{owner_username}), Игрок ID: {player_id} (@{player_username})"
                )
                
    except Exception as e:
        logger.error(f"Ошибка при проверке мэтча овнера: {str(e)[:100]}")



# И УДАЛЯЕМ вызовы этой функции в двух местах:

@router.message(F.text == "👑 Я ищу игроков")
async def select_owner_type(message: Message):
    """Пользователь выбирает роль владельца клуба"""
    try:
        # Обновляем тип пользователя в базе
        db_operation(
            "UPDATE all_users SET user_type = ? WHERE id = ?",
            ('owner', message.from_user.id)
        )
        
        await message.reply(
            "✅ Вы зарегистрированы как <b>владелец клуба</b>!\n\n"
            "Теперь вы можете создать анкету для поиска игроков.",
            parse_mode="html",
            reply_markup=kb.main_owner
        )
    except Exception as e:
        await message.reply(f"❌ Ошибка: {str(e)[:100]}", reply_markup=kb.main)


@router.message(F.text == "⬅️ Назад")
async def back_to_main(message: Message):
    """Возврат в главное меню в зависимости от типа пользователя"""
    try:
        # Получаем тип пользователя
        result = db_operation(
            "SELECT user_type FROM all_users WHERE id = ?",
            (message.from_user.id,),
            fetch=True
        )
        
        if result:
            user_type = result[0][0]
            if user_type == 'player':
                await message.reply("Главное меню:", reply_markup=kb.main_player)
            elif user_type == 'owner':
                await message.reply("Главное меню:", reply_markup=kb.main_owner)
            else:
                await message.reply("Главное меню:", reply_markup=kb.main)
        else:
            await message.reply("Главное меню:", reply_markup=kb.main)
    except Exception as e:
        await message.reply("Главное меню:", reply_markup=kb.main)


# ============== ✏️Мой профиль ==============

@router.message(F.text == "✏️Мой профиль")
async def my_profile(message: Message):
    """Показывает меню профиля"""
    try:
        # Проверяем тип пользователя
        result = db_operation(
            "SELECT user_type FROM all_users WHERE id = ?",
            (message.from_user.id,),
            fetch=True
        )
        
        if not result:
            await message.reply("Сначала зарегистрируйтесь через /start")
            return
            
        user_type = result[0][0]
        
        if user_type == 'player':
            await message.reply("👤 <b>✏️Мой профиль (игрок)</b>", parse_mode="html", reply_markup=kb.vibor_for_player)
        elif user_type == 'owner':
            await message.reply("👑 <b>✏️Мой профиль (владелец)</b>", parse_mode="html", reply_markup=kb.vibor_for_owner)
        else:
            await message.reply("👤 <b>✏️Мой профиль</b>", parse_mode="html", reply_markup=kb.vibor_for_user)
            
    except Exception as e:
        await message.reply(f"❌ Ошибка: {str(e)[:100]}", reply_markup=kb.main)


@router.message(F.text == "👤 Моя анкета")
async def my_anketa(message: Message):
    """Показывает анкету пользователя в зависимости от его типа"""
    try:
        # Проверяем тип пользователя
        result = db_operation(
            "SELECT user_type FROM all_users WHERE id = ?",
            (message.from_user.id,),
            fetch=True
        )
        
        if not result:
            await message.reply("Сначала зарегистрируйтесь через /start")
            return
            
        user_type = result[0][0]
        
        if user_type == 'player':
            # Показываем анкету игрока
            anketa = db_operation(
                "SELECT nickname, player_position, experience, clubs_played_before, created_at FROM users_search_club WHERE player_id = ?",
                (message.from_user.id,),
                fetch=True
            )
            
            if not anketa:
                await message.reply(
                    "❌ У вас еще нет анкеты.\n\n"
                    "Нажмите '📝 Создать анкету' в меню '✏️Мой профиль', чтобы создать анкету игрока.",
                    reply_markup=kb.vibor_for_player
                )
                return
            
            nickname, position, exp, clubs, created_at = anketa[0]
            
            response = (
                "👤 <b>Ваша анкета (игрок):</b>\n\n"
                f"<b>Игровой никнейм:</b> {nickname}\n"
                f"<b>Позиция:</b> {position}\n"
                f"<b>Опыт игры:</b> {exp}\n"
                f"<b>Предыдущие клубы:</b> {clubs}\n"
                f"<b>Создана:</b> {created_at} (по Гринвичу)\n\n\n"
                "<i>Для изменения анкеты сначала удалите текущую через '🗑️ Удалить анкету' и создайте новую.</i>"
            )
            
            await message.reply(response, parse_mode="html", reply_markup=kb.vibor_for_player)
            
        elif user_type == 'owner':
            # Показываем анкету овнера
            anketa = db_operation(
                "SELECT club_name, needed_positions, owner_comment, created_at FROM owners_search_players WHERE owner_id = ?",
                (message.from_user.id,),
                fetch=True
            )
            
            if not anketa:
                await message.reply(
                    "❌ У вас еще нет анкеты.\n\n"
                    "Нажмите '📝 Создать анкету' в меню '✏️Мой профиль', чтобы создать анкету клуба.",
                    reply_markup=kb.vibor_for_owner
                )
                return
            
            club_name, positions, comment, created_at = anketa[0]
            
            response = (
                "👑 <b>Ваша анкета (владелец):</b>\n\n"
                f"<b>Название клуба:</b> {club_name}\n"
                f"<b>Искомые позиции:</b> {positions}\n"
                f"<b>Комментарий:</b> {comment}\n"
                f"<b>Создана:</b> {created_at} (по Гринвичу)\n\n\n"
                "<i>Для изменения анкеты сначала удалите текущую через '🗑️ Удалить анкету' и создайте новую.</i>"
            )
            
            await message.reply(response, parse_mode="html", reply_markup=kb.vibor_for_owner)
            
    except Exception as e:
        await message.reply(f"❌ Ошибка при загрузке анкеты: {str(e)[:100]}", reply_markup=kb.main)
#===========ПАКИ==========
import asyncio
import random
from aiogram.types import PreCheckoutQuery, LabeledPrice
import aiogram.exceptions

tovars_newyearpack = ["подарок за 25 звезд", "билет на матч 'Ромы'", 
          "возможность наблюдать и участвовать в бета-тестировании бота", 
          "вип-подписку на 3 дня", "ничего"]
weights_price_newyearpack = [0.001, 0.2, 0.005, 0.003, 0.7]



@router.message(F.text == "🎁 Паки")
async def packs_of_bot(message: Message):
    await message.reply(
        "<b>❄️Новый Год - пора подарков! Поэтому наш бот организует для Вас возможность выигрывать ценные призы!\n\n🍀 Открывай паки, активно пользуйся ботом и участвуй в конкурсах. Удачи!</b>\n\n\n✅ Доступные паки:",
        parse_mode="html", 
        reply_markup=kb.packs
    )
# Данные для Lucky Pack
tovars_luckypack = [
    "150 коинов",           # 0: 150 коинов
    "1 легендарная карта",  # 1: 1 легендарная карта
    "3 эпических карточки", # 2: 3 эпических карточки
    "5 редких карт"         # 3: 5 редких карт
]

weights_luckypack = [0.3, 0.1, 0.25, 0.35]  # Вероятности для каждого приза

# Обработчик кнопки Lucky Pack
@router.callback_query(F.data == "luckypack")
async def luckypack_data(callback: CallbackQuery):
    await callback.message.edit_text(
        "<b>🍀 Лаки Пак - удача на вашей стороне!</b>\n\n"
        "💲 <b>Стоимость:</b> 5 звезд✨\n\n"
        "🎁 <b>Возможные призы:</b>\n"
        "1. 150 коинов\n"
        "2. 1 легендарная карта\n"
        "3. 3 эпических карточки\n"
        "4. 5 редких карт\n\n"
        "<i>Приз выдается автоматически сразу после оплаты!</i>",
        parse_mode="html", 
        reply_markup=kb.get_luckypack_keyboard()
    )

# Обработчик оплаты Lucky Pack
@router.callback_query(F.data == "oplata_yes_luckypack")
async def oplata_yes_luckypack(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    price = [LabeledPrice(label="XTR", amount=5)]  # 5 звезд
    
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.edit_text(
            "💳 <b>Оплата Лаки Пака</b>\n\nСтоимость: 5 звезд\n\nНажмите кнопку ниже для оплаты:",
            parse_mode="html",
            reply_markup=kb.get_payment_invoice_keyboard()
        )
    except aiogram.exceptions.TelegramBadRequest:
        await callback.message.answer_invoice(
            title="MamoTinder - Лаки Пак",
            description="🍀 Лаки Пак\n\nПризы:\n1. 150 коинов\n2. 1 легендарная карта\n3. 3 эпических карточки\n4. 5 редких карт\n\nПриз выдается автоматически!",
            prices=price,
            provider_token="YOUR_PROVIDER_TOKEN",  # Замените на реальный токен
            payload="luckypack_roulette",
            currency="XTR",
            reply_markup=kb.get_payment_invoice_keyboard()
        )
        try:
            await callback.message.delete()
        except:
            pass
@router.message(F.successful_payment)
async def ruletka_start(message: Message, bot: Bot):
    user_id = message.from_user.id
    user_name = message.from_user.username or message.from_user.first_name
    
    # Проверяем payload для определения типа пака
    invoice_payload = message.successful_payment.invoice_payload
    
    if invoice_payload == "kartezhnik_pack_payment":
        await message.reply("✅ Оплата Картежник пака успешно прошла.")
        
        await asyncio.sleep(2)
        await message.reply("🎲 Открываем Картежник пак...")
        
        # Получаем 7 случайных карточек
        received_cards = []
        for i in range(7):
            card = get_new_card_for_user(user_id)
            if card:
                # Добавляем карточку пользователю
                add_card_to_user(user_id, card['id'])
                received_cards.append(card)
        
        if not received_cards:
            await message.reply(
                "❌ <b>ОШИБКА!</b>\n\n"
                "Не удалось получить карточки из пакета.\n"
                "Попробуйте позже или обратитесь к администратору.",
                parse_mode="html",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ К пакам", callback_data="back_to_packs")]
                    ]
                )
            )
            return
        
        # Формируем сообщение с результатами
        message_text = (
            f"🎉 <b>КАРТЕЖНИК ПАК УСПЕШНО ОТКРЫТ!</b>\n\n"
            f"👤 <b>Покупатель:</b> {user_name}\n"
            f"🎲 <b>Пакет:</b> Картежник (7 карточек)\n"
            f"💰 <b>Стоимость:</b> 7 звезд\n\n"
            f"<b>Полученные карточки:</b>\n"
        )
        
        # Группируем карточки по редкости
        cards_by_rarity = {}
        for card in received_cards:
            rarity = card['rarity']
            # Нормализуем названия редкостей
            if rarity.lower() in ['эпическая', 'эпический', 'эпик']:
                rarity = 'Эпический'
            elif rarity.lower() in ['легендарная', 'легендарный']:
                rarity = 'Легендарный'
            elif rarity.lower() in ['суперлегендарная', 'суперлегендарный']:
                rarity = 'Суперлегендарный'
            elif rarity.lower() in ['редкая', 'редкий']:
                rarity = 'Редкий'
            
            if rarity not in cards_by_rarity:
                cards_by_rarity[rarity] = []
            cards_by_rarity[rarity].append(card)
        
        # Отображаем карточки по группам редкости
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
                message_text += f"\n{icon} <b>{rarity}</b> ({len(cards_by_rarity[rarity])}):\n"
                
                for card in cards_by_rarity[rarity]:
                    message_text += f"  • {card['nickname']} ({card['club']})\n"
        
        # Добавляем статистику
        stats = get_user_card_stats(user_id)
        if stats:
            message_text += (
                f"\n📊 <b>Ваша коллекция теперь:</b>\n"
                f"• Карточек: {stats['user_cards']}/{stats['total_cards']}\n"
                f"• Завершено: {stats['completion_percentage']}%\n\n"
            )
        
        message_text += (
            "<i>Все 7 карточек добавлены в вашу коллекцию!</i>"
        )
        
        # Создаем клавиатуру
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="📚 Моя коллекция", callback_data="view_my_cards"),
            InlineKeyboardButton(text="🎲 Еще пак", callback_data="kartezhnikpack")
        )
        builder.row(
            InlineKeyboardButton(text="🛒 К покупкам", callback_data="bay_cards"),
            InlineKeyboardButton(text="⬅️ К пакам", callback_data="back_to_packs")
        )
        
        # Отправляем уведомление админу
        try:
            admin_message = (
                f"🎲 <b>НОВЫЙ ПАК 'КАРТЕЖНИК' КУПЛЕН!</b>\n\n"
                f"<b>Покупатель:</b> @{user_name}\n"
                f"<b>ID:</b> <code>{user_id}</code>\n"
                f"<b>Пакет:</b> Картежник (7 карточек)\n"
                f"<b>Стоимость:</b> 7 звезд\n"
                f"<b>Получено карточек:</b> {len(received_cards)}\n"
                f"<b>Время:</b> {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}\n\n"
            )
            
            # Группируем для админа
            admin_message += "<b>Полученные карточки:</b>\n"
            for rarity in rarity_order:
                if rarity in cards_by_rarity and cards_by_rarity[rarity]:
                    admin_message += f"\n<b>{rarity}:</b> {len(cards_by_rarity[rarity])} шт.\n"
                    for card in cards_by_rarity[rarity][:3]:  # Показываем первые 3 каждой редкости
                        admin_message += f"  • {card['nickname']}\n"
                    if len(cards_by_rarity[rarity]) > 3:
                        admin_message += f"  • ...и еще {len(cards_by_rarity[rarity]) - 3}\n"
            
            await bot.send_message(
                group_of_admins,  # ID админа
                text=admin_message,
                parse_mode="html"
            )
        except Exception as admin_error:
            logger.error(f"Ошибка при отправке уведомления админу: {admin_error}")
        
        await message.reply(
            message_text,
            parse_mode="html",
            reply_markup=builder.as_markup()
        )
        
        # Логируем покупку
        logger.warning(f"🎲 Пакет 'Картежник' куплен пользователем {user_name} ({user_id}): получено {len(received_cards)} карточек за 7 звезд")
    
    # Обработка новогоднего пака (существующая логика)
    elif invoice_payload == "by_stars_roulette":
        await message.reply("✅ Оплата успешно прошла.")
        
        await asyncio.sleep(2)
        await message.reply("🔥 Вы запустили рулетку...")
        
        final_price = random.choices(tovars_newyearpack, weights=weights_price_newyearpack, k=1)
        text = "".join(final_price).lower()
        
        if text == "ничего":
            await message.reply(
                "😓 К сожалению, вы <b>ничего не выиграли</b>.\n\n😇 Ничего, повезет в следующий раз!\n\nХотите сыграть еще?",
                parse_mode="html"
            )
        else:
            await message.reply(
                f"💥 Вы выиграли <b>{text}</b>! \nПоздравляем!\n\nДля получения приза обратитесь @kirik1231zzap",
                parse_mode="html"
            )
        
        await bot.send_message(
            1088006569, 
            f"Пользователь <b>{message.from_user.id}</b> открыл рулетку и выиграл <b><i>{text}</i></b>", 
            parse_mode="html"
        )
# Обработка успешной оплаты Lucky Pack
@router.message(F.successful_payment)
async def luckypack_result(message: Message, bot: Bot):
    user_id = message.from_user.id
    
    # Проверяем payload для определения типа пака
    if message.successful_payment.invoice_payload == "luckypack_roulette":
        await message.reply("✅ Оплата Лаки Пака успешно прошла.")
        
        await asyncio.sleep(2)
        await message.reply("🎲 Вы запустили Лаки Пак...")
        
        # Выбираем случайный приз
        final_price = random.choices(tovars_luckypack, weights=weights_luckypack, k=1)
        prize_text = "".join(final_price)
        
        # Получаем индекс приза для логики выдачи
        prize_index = tovars_luckypack.index(prize_text)
        
        # Выдача приза в зависимости от типа
        prize_message = await process_luckypack_prize(user_id, prize_index, prize_text)
        
        await message.reply(
            f"🎉 Вы выиграли: <b>{prize_text}</b>\n\n{prize_message}",
            parse_mode="html"
        )
        
        # Отправляем уведомление администратору
        await bot.send_message(
            group_of_admins,
            f"Пользователь <b>{message.from_user.id}</b> (@{message.from_user.username or 'без username'}) "
            f"открыл Лаки Пак и выиграл <b><i>{prize_text}</i></b>",
            parse_mode="html"
        )
    
    # Обработка других пакетов остается без изменений
    elif message.successful_payment.invoice_payload == "by_stars_roulette":
        # Существующая логика для новогоднего и суперпака
        pass

async def process_luckypack_prize(user_id: int, prize_index: int, prize_text: str) -> str:
    """
    Обрабатывает выдачу приза из Lucky Pack
    Возвращает сообщение для пользователя
    """
    try:
        if prize_index == 0:  # 150 коинов
            add_user_coins(user_id, 150)
            user_coins = get_user_coins(user_id)
            return f"💰 150 коинов добавлены на ваш счет!\nТекущий баланс: {user_coins} коинов"
        
        elif prize_index == 1:  # 1 легендарная карта
            # Ищем все легендарные карты
            result = db_operation(
                "SELECT id, nickname FROM players_catalog WHERE rarity IN ('Легендарный', 'Легендарная')",
                fetch=True
            )
            
            if not result:
                return "❌ Ошибка: в базе нет легендарных карт"
            
            # Выбираем случайную легендарную карту
            card_data = random.choice(result)
            card_id, card_nickname = card_data
            
            # Проверяем, есть ли уже эта карта у пользователя
            if user_has_card(user_id, card_id):
                # Если карта уже есть, даем другую или добавляем коины
                add_user_coins(user_id, 50)  # Компенсация
                return f"⚠️ У вас уже есть карта '{card_nickname}'.\nВместо этого вы получили 50 коинов в качестве компенсации!"
            
            # Добавляем карту пользователю
            add_card_to_user(user_id, card_id)
            return f"🎴 Вы получили легендарную карту: <b>{card_nickname}</b>"
        
        elif prize_index == 2:  # 3 эпических карточки
            # Ищем все эпические карты
            result = db_operation(
                "SELECT id, nickname FROM players_catalog WHERE rarity IN ('Эпический', 'Эпическая', 'Эпик')",
                fetch=True
            )
            
            if not result:
                return "❌ Ошибка: в базе нет эпических карт"
            
            # Выбираем 3 случайные эпические карты (уникальные)
            if len(result) >= 3:
                selected_cards = random.sample(result, 3)
            else:
                selected_cards = result
            
            added_cards = []
            compensation_coins = 0
            
            for card_id, card_nickname in selected_cards:
                if not user_has_card(user_id, card_id):
                    add_card_to_user(user_id, card_id)
                    added_cards.append(card_nickname)
                else:
                    compensation_coins += 15  # Компенсация за дубликат
            
            message = f"🎴 Вы получили {len(added_cards)} эпических карт:\n"
            for i, card_name in enumerate(added_cards, 1):
                message += f"{i}. {card_name}\n"
            
            if compensation_coins > 0:
                add_user_coins(user_id, compensation_coins)
                message += f"\nЗа дубликаты вы получили {compensation_coins} коинов компенсации"
            
            return message
        
        elif prize_index == 3:  # 5 редких карт
            # Ищем все редкие карты
            result = db_operation(
                "SELECT id, nickname FROM players_catalog WHERE rarity IN ('Редкий', 'Редкая')",
                fetch=True
            )
            
            if not result:
                return "❌ Ошибка: в базе нет редких карт"
            
            # Выбираем 5 случайных редких карт (уникальные)
            if len(result) >= 5:
                selected_cards = random.sample(result, 5)
            else:
                selected_cards = result
            
            added_cards = []
            compensation_coins = 0
            
            for card_id, card_nickname in selected_cards:
                if not user_has_card(user_id, card_id):
                    add_card_to_user(user_id, card_id)
                    added_cards.append(card_nickname)
                else:
                    compensation_coins += 5  # Компенсация за дубликат
            
            message = f"🎴 Вы получили {len(added_cards)} редких карт:\n"
            for i, card_name in enumerate(added_cards, 1):
                message += f"{i}. {card_name}\n"
            
            if compensation_coins > 0:
                add_user_coins(user_id, compensation_coins)
                message += f"\nЗа дубликаты вы получили {compensation_coins} коинов компенсации"
            
            return message
        
        return "⚠️ Неизвестный приз"
        
    except Exception as e:
        logger.error(f"Ошибка при обработке приза Lucky Pack: {e}")
        return "❌ Произошла ошибка при выдаче приза. Обратитесь к администратору."

# Вспомогательная функция для проверки наличия карты у пользователя
def user_has_card(user_id: int, card_id: int) -> bool:
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

# Вспомогательная функция для добавления карточки пользователю
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



# ===================
# СИСТЕМА ПАКОВ - КАРТЕЖНИК ПАК
# ===================

@router.callback_query(F.data == "kartezhnikpack")
async def kartezhnikpack_callback(callback: CallbackQuery):
    """Обработчик пакета Картежник"""
    try:
        pack_info = (
            "🎲 <b>ПАК 'КАРТЕЖНИК'</b>\n\n"
            "💰 <b>Стоимость:</b> 7 звезд (⭐️)\n"
            "🃏 <b>Содержимое:</b> 7 случайных карточек\n\n"
            "🎯 <b>Что вы получите:</b>\n"
            "• 7 случайных карточек из каталога\n"
            "• Шанс на получение редких карточек\n"
            "• Возможность получить дубли для крафта\n\n"
            "📊 <b>Шансы на редкость:</b>\n"
            "🟢 Редкий - 50%\n"
            "🟣 Эпический - 30%\n"
            "🟡 Легендарный - 15%\n"
            "🔴 Суперлегендарный - 5%\n\n"
            "<i>Идеально для пополнения коллекции и получения карточек для крафта!</i>"
        )
        
        await callback.message.edit_text(
            pack_info,
            parse_mode="html",
            reply_markup=kb.get_kartezhnik_keyboard()
        )
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в kartezhnikpack_callback: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

@router.callback_query(F.data == "kartezhnik_info")
async def kartezhnik_info_callback(callback: CallbackQuery):
    """Информация о пакете Картежник"""
    await callback.answer(
        "🎲 Картежник пак:\n"
        "• Стоимость: 7⭐️\n"
        "• 7 случайных карточек\n"
        "• Отличный способ пополнить коллекцию!",
        show_alert=True
    )

# В секции обработчика Картежник пак
@router.callback_query(F.data == "oplata_yes_kartezhnik")
async def oplata_yes_kartezhnik_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик оплаты пакета Картежник"""
    await callback.answer()
    
    # Стоимость пакета Картежник: 7 звезд (⭐️)
    price = [LabeledPrice(label="Картежник пак", amount=7)]  # 700 = 7.00 звезд
    
    try:
        # Пытаемся отредактировать сообщение
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.edit_text(
            "💳 <b>ОПЛАТА ПАКЕТА 'КАРТЕЖНИК'</b>\n\n"
            "🎲 <b>Картежник пак</b> - 7 случайных карточек\n"
            "💰 <b>Стоимость:</b> 7 звезд\n\n"
            "🎯 <b>Что вы получите:</b>\n"
            "• 7 случайных карточек из каталога\n"
            "• Шанс на получение редких карточек\n"
            "• Возможность получить дубли для крафта\n\n"
            "📊 <b>Шансы на редкость:</b>\n"
            "🟢 Редкий - 50%\n"
            "🟣 Эпический - 30%\n"
            "🟡 Легендарный - 15%\n"
            "🔴 Суперлегендарный - 5%\n\n"
            "<i>Нажмите кнопку ниже для оплаты:</i>",
            parse_mode="html",
            reply_markup=kb.get_payment_invoice_keyboard()
        )
    except aiogram.exceptions.TelegramBadRequest:
        # Если не получается отредактировать, отправляем новое сообщение с инвойсом
        await callback.message.answer_invoice(
            title="MamoTinder - Картежник пак",
            description="🎲 Картежник пак - 7 случайных карточек\n\n"
                       "🎁 Вы получите 7 случайных карточек из каталога с разными уровнями редкости.\n"
                       "Идеально для пополнения коллекции и получения карточек для крафта!\n\n"
                       "📊 Шансы на редкость:\n"
                       "• Редкий - 50%\n"
                       "• Эпический - 30%\n"
                       "• Легендарный - 15%\n"
                       "• Суперлегендарный - 5%",
            prices=price,
            provider_token="YOUR_PROVIDER_TOKEN",  # Замените на реальный токен
            payload="kartezhnik_pack_payment",  # Уникальный payload для этого пака
            currency="XTR",  # Или другая валюта, которую вы используете
            reply_markup=kb.get_payment_invoice_keyboard()
        )
        # Пробуем удалить старое сообщение
        try:
            await callback.message.delete()
        except:
            pass

@router.callback_query(F.data == "process_kartezhnik_pack")
async def process_kartezhnik_pack_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Обработка выдачи карточек из пакета Картежник"""
    user_id = callback.from_user.id
    user_name = callback.from_user.username or callback.from_user.first_name
    
    try:
        # Имитация выдачи 7 случайных карточек
        await callback.message.edit_text(
            f"🎲 <b>ОТКРЫВАЕМ ПАКЕТ 'КАРТЕЖНИК'...</b>\n\n"
            f"👤 <b>Покупатель:</b> {user_name}\n"
            f"🎯 <b>Получаем 7 карточек:</b>\n\n"
            f"<i>Идет обработка...</i>",
            parse_mode="html"
        )
        
        # Даем небольшую задержку для реалистичности
        await asyncio.sleep(2)
        
        # Получаем 7 случайных карточек
        received_cards = []
        for i in range(7):
            card = get_new_card_for_user(user_id)
            if card:
                # Добавляем карточку пользователю
                add_card_to_user(user_id, card['id'])
                received_cards.append(card)
        
        if not received_cards:
            await callback.message.edit_text(
                "❌ <b>ОШИБКА!</b>\n\n"
                "Не удалось получить карточки из пакета.\n"
                "Попробуйте позже или обратитесь к администратору.",
                parse_mode="html",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="⬅️ К пакам", callback_data="back_to_packs")]
                    ]
                )
            )
            return
        
        # Формируем сообщение с результатами
        message_text = (
            f"🎉 <b>ПАКЕТ УСПЕШНО ОТКРЫТ!</b>\n\n"
            f"👤 <b>Покупатель:</b> {user_name}\n"
            f"🎲 <b>Пакет:</b> Картежник (7 карточек)\n\n"
            f"<b>Полученные карточки:</b>\n"
        )
        
        # Группируем карточки по редкости
        cards_by_rarity = {}
        for card in received_cards:
            rarity = card['rarity']
            if rarity == 'эпическая':
                rarity = 'Эпический'
            if rarity not in cards_by_rarity:
                cards_by_rarity[rarity] = []
            cards_by_rarity[rarity].append(card)
        
        # Отображаем карточки по группам редкости
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
                message_text += f"\n{icon} <b>{rarity}</b> ({len(cards_by_rarity[rarity])}):\n"
                
                for card in cards_by_rarity[rarity]:
                    message_text += f"  • {card['nickname']} ({card['club']})\n"
        
        # Добавляем статистику
        stats = get_user_card_stats(user_id)
        if stats:
            message_text += (
                f"\n📊 <b>Ваша коллекция теперь:</b>\n"
                f"• Карточек: {stats['user_cards']}/{stats['total_cards']}\n"
                f"• Завершено: {stats['completion_percentage']}%\n\n"
            )
        
        message_text += (
            "<i>Все карточки добавлены в вашу коллекцию!</i>"
        )
        
        # Создаем клавиатуру
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="📚 Моя коллекция", callback_data="view_my_cards"),
            InlineKeyboardButton(text="🎲 Еще пак", callback_data="kartezhnikpack")
        )
        builder.row(
            InlineKeyboardButton(text="🛒 К покупкам", callback_data="bay_cards"),
            InlineKeyboardButton(text="⬅️ К пакам", callback_data="back_to_packs")
        )
        
        # Отправляем уведомление админу
        try:
            admin_message = (
                f"🎲 <b>НОВЫЙ ПАК 'КАРТЕЖНИК' КУПЛЕН!</b>\n\n"
                f"<b>Покупатель:</b> @{user_name}\n"
                f"<b>ID:</b> <code>{user_id}</code>\n"
                f"<b>Пакет:</b> Картежник (7 карточек)\n"
                f"<b>Получено карточек:</b> {len(received_cards)}\n"
                f"<b>Время:</b> {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}\n\n"
            )
            
            # Группируем для админа
            admin_message += "<b>Полученные карточки:</b>\n"
            for rarity in rarity_order:
                if rarity in cards_by_rarity and cards_by_rarity[rarity]:
                    admin_message += f"\n<b>{rarity}:</b> {len(cards_by_rarity[rarity])} шт.\n"
                    for card in cards_by_rarity[rarity][:3]:  # Показываем первые 3 каждой редкости
                        admin_message += f"  • {card['nickname']}\n"
                    if len(cards_by_rarity[rarity]) > 3:
                        admin_message += f"  • ...и еще {len(cards_by_rarity[rarity]) - 3}\n"
            
            await bot.send_message(
                group_of_admins,  # ID админа
                text=admin_message,
                parse_mode="html"
            )
        except Exception as admin_error:
            logger.error(f"Ошибка при отправке уведомления админу: {admin_error}")
        
        await callback.message.edit_text(
            message_text,
            parse_mode="html",
            reply_markup=builder.as_markup()
        )
        
        # Логируем покупку
        logger.warning(f"🎲 Пакет 'Картежник' куплен пользователем {user_name} ({user_id}): получено {len(received_cards)} карточек")
        
    except Exception as e:
        logger.error(f"Ошибка в process_kartezhnik_pack_callback: {e}")
        await callback.message.edit_text(
            "❌ <b>ОШИБКА ПРИ ОТКРЫТИИ ПАКЕТА!</b>\n\n"
            "Произошла ошибка при выдаче карточек.\n"
            "Обратитесь к администратору.",
            parse_mode="html",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="kartezhnikpack")],
                    [InlineKeyboardButton(text="📞 Техподдержка", url="https://t.me/kirik1231zzap")]
                ]
            )
        )

@router.callback_query(F.data == "back_to_packs")
async def back_to_packs_callback(callback: CallbackQuery):
    """Возврат к списку пакетов"""
    await callback.message.edit_text(
        "🎁 <b>ВЫБЕРИТЕ ПАКЕТ</b>\n\n"
        "<i>Каждый пакет содержит уникальные карточки и бонусы</i>",
        parse_mode="html",
        reply_markup=kb.packs
    )
    await callback.answer()

@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    """Обработчик предварительной проверки оплаты"""
    # Проверяем, не забанен ли пользователь
    user_id = pre_checkout_query.from_user.id
    
    if is_user_banned(user_id):
        await pre_checkout_query.answer(
            ok=False,
            error_message="Вы забанены и не можете совершать покупки"
        )
        return
    
    # Проверяем payload для Картежник пака
    payload = pre_checkout_query.invoice_payload
    
    if payload in ["kartezhnik_pack_payment", "by_stars_roulette"]:
        await pre_checkout_query.answer(ok=True)
    else:
        await pre_checkout_query.answer(
            ok=False,
            error_message="Неверный тип платежа"
        )


#обработка Новогоднего пака
@router.callback_query(F.data == "newyearpack")
async def newyearpack(callback: CallbackQuery):
    await callback.answer()
    
    try:
        # Пробуем отредактировать сообщение
        await callback.message.edit_text(
            "<b>🎄 Новогодний пак - <i>рулетка.</i> Вы можете выиграть:</b>\n\n1. Подарок за 25 звезд\n2. Билет на матч 'Ромы'\n3. Возможность участвовать в бета-тестировании бота\n4. Будущую ВИП-подписку в боте\n",
            parse_mode="html",
            reply_markup=kb.get_newyear_pack_keyboard()
        )
    except aiogram.exceptions.TelegramBadRequest:
        # Если не получается отредактировать, отправляем новое сообщение
        await callback.message.answer(
            "<b>🎄 Новогодний пак - <i>рулетка.</i> Вы можете выиграть:</b>\n\n1. Подарок за 25 звезд\n2. Билет на матч 'Ромы'\n3. Возможность участвовать в бета-тестировании бота\n4. Будущую ВИП-подписку в боте на 3 дня\n",
            parse_mode="html",
            reply_markup=kb.get_newyear_pack_keyboard()
        )
        # Пробуем удалить старое сообщение
        try:
            await callback.message.delete()
        except:
            pass

@router.callback_query(F.data == "oplata_yes_new_year_pack")
async def oplata_yes_func(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    price = [LabeledPrice(label="XTR", amount=1)]
    
    try:
        # Сначала пытаемся отредактировать сообщение
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.edit_text(
            "💳 <b>Оплата рулетки</b>\n\nСтоимость: 1 звезда\n\nНажмите кнопку ниже для оплаты:",
            parse_mode="html",
            reply_markup=kb.get_payment_invoice_keyboard()
        )
    except aiogram.exceptions.TelegramBadRequest:
        # Если не получается отредактировать, отправляем новое сообщение
        await callback.message.answer_invoice(
            title="MamoTinder",
            description="🎄 Новогодний пак\n\nВы можете выиграть:\n1. Подарок за 25 звезд\n2. Билет на матч 'Ромы'\n3. Возможность участвовать в бета-тестировании бота\n4. Будущую ВИП-подписку в боте на 3 дня\n",
            prices=price,
            provider_token="YOUR_PROVIDER_TOKEN",  # Замените на реальный токен
            payload="by_stars_roulette",
            currency="XTR",
            reply_markup=kb.get_payment_invoice_keyboard()
        )
        # Пробуем удалить старое сообщение
        try:
            await callback.message.delete()
        except:
            pass

@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    # Здесь можно добавить проверки
    await pre_checkout_query.answer(ok=True)

@router.message(F.successful_payment)
async def ruletka_start(message: Message, bot: Bot):
    await message.reply("✅ Оплата успешно прошла.")
    
    await asyncio.sleep(2)  # Используйте асинхронный sleep
    await message.reply("🔥 Вы запустили рулетку...")
    
    final_price = random.choices(tovars_newyearpack, weights=weights_price_newyearpack, k=1)
    text = "".join(final_price).lower()
    
    if text == "ничего":
        await message.reply(
            "😓 К сожалению, вы <b>ничего не выиграли</b>.\n\n😇 Ничего, повезет в следующий раз!\n\nХотите сыграть еще?",
            parse_mode="html"
        )
    else:
        await message.reply(
            f"💥 Вы выиграли <b>{text}</b>! \nПоздравляем!\n\nДля получения приза обратитесь @kirik1231zzap",
            parse_mode="html"
        )
    
    await bot.send_message(
        1088006569, 
        f"Пользователь <b>{message.from_user.id}</b> открыл рулетку и выиграл <b><i>{text}</i></b>", 
        parse_mode="html"
    )
#конец обработки новогоднего пака
#обработка супер-пака
tovars_superpack = ["подарок за 50 звезд", "бесконечную вип-подписку", "подарок за 100 звезд", "подарок за 15 звезд", "бесплатный пиар любого Вашего проекта", "ничего" ]
weights_superpack = [0.001, 0.01, 0.0001, 0.01,0.1, 0.8]
@router.callback_query(F.data == "superpack")
async def superpackdata(callback: CallbackQuery):
    await callback.message.edit_text("<b>❄️Супер-пак - это уникальная рулетка, в которой Вы можете выиграть:</b>\n1. Подарок 50 звезд\n2. Бесконечную ВИП-подписку в боте\n3. Подарок за 100 звезд\n4. Подарок за 15 звезд\n5. Бесплатный ПИАР любого Вашего проекта/клуба в боте",parse_mode="html", reply_markup=kb.get_superpack_keyboard())



@router.callback_query(F.data == "oplata_yes_superpack")
async def oplata_yes_func(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    price = [LabeledPrice(label="XTR", amount=30)]
    
    try:
        # Сначала пытаемся отредактировать сообщение
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.edit_text(
            "💳 <b>Оплата суперпака</b>\n\nСтоимость: 30 звезд\n\nНажмите кнопку ниже для оплаты:",
            parse_mode="html",
            reply_markup=kb.get_payment_invoice_keyboard()
        )
    except aiogram.exceptions.TelegramBadRequest:
        # Если не получается отредактировать, отправляем новое сообщение
        await callback.message.answer_invoice(
            title="MamoTinder",
            description="❄️Супер-пак\n\n🎁Вы можете выиграть:\n1. Подарок 50 звезд\n2. Бесконечную ВИП-подписку в боте\n3. Подарок за 100 звезд\n4. Подарок за 15 звезд\n5. Бесплатный ПИАР любого Вашего проекта/клуба в боте", 
            prices=price,
            provider_token="YOUR_PROVIDER_TOKEN",  # Замените на реальный токен
            payload="by_stars_roulette",
            currency="XTR",
            reply_markup=kb.get_payment_invoice_keyboard()
        )
        # Пробуем удалить старое сообщение
        try:
            await callback.message.delete()
        except:
            pass

@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    # Здесь можно добавить проверки
    await pre_checkout_query.answer(ok=True)

@router.message(F.successful_payment)
async def ruletka_start(message: Message, bot: Bot):
    await message.reply("✅ Оплата успешно прошла.")
    
    await asyncio.sleep(2)  # Используйте асинхронный sleep
    await message.reply("🔥 Вы открыли суперпак...")
    
    final_price = random.choices(tovars_superpack, weights=weights_superpack, k=1)
    text = "".join(final_price).lower()
    
    if text == "ничего":
        await message.reply(
            "😓 К сожалению, вы <b>ничего не выиграли</b>.\n\n😇 Ничего, повезет в следующий раз!\n\nХотите сыграть еще?",
            parse_mode="html"
        )
    else:
        await message.reply(
            f"💥 Вы выиграли <b>{text}</b>! \nПоздравляем!\n\nДля получения приза обратитесь @kirik1231zzap",
            parse_mode="html"
        )
    
    await bot.send_message(
        1088006569, 
        f"Пользователь <b>{message.from_user.id}</b> открыл СУПЕРПАК и выиграл <b><i>{text}</i></b>", 
        parse_mode="html"
    )




#обработка отказа от оплаты
@router.callback_query(F.data == "oplata_no")
async def otmena_oplati(callback: CallbackQuery):
    await callback.answer()
    
    try:
        # Пытаемся отредактировать сообщение на главное меню пакетов
        await callback.message.edit_text(
            "<b>❄️Новый Год - пора подарков! Поэтому наш бот организует для Вас возможность выигрывать ценные призы!\n\n🍀 Открывай паки, активно пользуйся ботом и участвуй в конкурсах. Удачи!</b>\n\n\n✅ Доступные паки:",
            parse_mode="html", 
            reply_markup=kb.packs
        )
    except aiogram.exceptions.TelegramBadRequest:
        # Если не получается отредактировать, отправляем новое сообщение
        await callback.message.answer(
            "<b>❄️Новый Год - пора подарков! Поэтому наш бот организует для Вас возможность выигрывать ценные призы!\n\n🍀 Открывай паки, активно пользуйся ботом и участвуй в конкурсах. Удачи!</b>\n\n\n✅ Доступные паки:",
            parse_mode="html", 
            reply_markup=kb.packs
        )
        # Пробуем удалить старое сообщение
        try:
            await callback.message.delete()
        except:
            pass
#===========================================================


@router.message(F.text == "📨 Входящие")
async def incoming_likes(message: Message):
    """Показывает лайки в зависимости от типа пользователя с инлайн-клавиатурами для связи"""
    try:
        user_id = message.from_user.id
        
        # Проверяем тип пользователя
        result = db_operation(
            "SELECT user_type FROM all_users WHERE id = ?",
            (user_id,),
            fetch=True
        )
        
        if not result:
            await message.reply("Сначала зарегистрируйтесь через /start")
            return
        
        user_type = result[0][0]
        
        if user_type == 'player':
            # Для игрока показываем лайки от овнеров (приглашения в клубы)
            # Добавляем created_at из owners_search_players
            likes = db_operation(
                """SELECT ol.owner_id, ol.created_at, o.club_name, o.needed_positions, o.owner_comment, 
                   u.username, u.first_name, u.nickname, o.created_at as club_profile_created_at
                   FROM owner_likes ol 
                   JOIN owners_search_players o ON ol.owner_id = o.owner_id 
                   JOIN all_users u ON ol.owner_id = u.id
                   WHERE ol.liked_player_id = ? 
                   ORDER BY ol.created_at DESC""",
                (user_id,),
                fetch=True
            )
            
            if not likes:
                await message.reply(
                    "📭 <b>У вас пока нет входящих лайков</b>\n\n"
                    "Когда владельцы клубов увидят вашу анкету и заинтересуются, "
                    "они смогут поставить вам лайк, и он появится здесь!",
                    parse_mode="html",
                    reply_markup=kb.vibor_for_player
                )
                return
            
            # Отправляем каждую заявку отдельным сообщением с клавиатурой
            for i, (owner_id, liked_at, club_name, positions, comment, 
                   owner_username, owner_first_name, owner_nickname, club_created_at) in enumerate(likes, 1):
                
                # Формируем контактную информацию о владельце
                owner_contact_info = owner_username or owner_nickname or str(owner_id)
                if owner_username:
                    owner_contact = f"@{owner_username}"
                elif owner_nickname:
                    owner_contact = f"Ник: {owner_nickname}"
                else:
                    owner_contact = f"ID: {owner_id}"
                
                # Форматируем дату создания анкеты клуба по МСК
                club_created_moscow = format_moscow_time(club_created_at) if club_created_at else "Не указана"
                
                response = (
                    f"<b>🎉 Приглашение в клуб #{i}</b>\n\n"
                    f"🏆 <b>Клуб:</b> {club_name}\n"
                    f"👑 <b>Владелец:</b> {owner_first_name or owner_nickname}\n"
                    f"📱 <b>Контакт:</b> {owner_contact}\n"
                    f"⚽ <b>Ищут позиции:</b> {positions}\n"
                    f"💬 <b>О клубе:</b> {comment}\n"
                    f"📅 <b>Дата создания анкеты клуба:</b> {club_created_moscow}\n"
                    f"🕐 <b>Приглашение получено:</b> {liked_at}\n\n"
                    f"<i>Хотите связаться с владельцем клуба?</i>"
                )
                
                # Создаем уникальную клавиатуру для этого сообщения с callback_data содержащей ID
                contact_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📞 Связаться с клубом", 
                                         callback_data=f"contact_club:{owner_id}")],
                    [InlineKeyboardButton(text="❌ Отклонить", 
                                         callback_data=f"reject_club:{owner_id}")]
                ])
                
                await message.reply(response, parse_mode="html", reply_markup=contact_keyboard)
                
                # Небольшая задержка между сообщениями
                await asyncio.sleep(0.5)
            
            # Итоговое сообщение
            await message.reply(
                f"📊 <b>Всего приглашений:</b> {len(likes)}\n\n"
                f"<i>Нажмите '📞 Связаться с клубом' чтобы начать общение!</i>",
                parse_mode="html",
                reply_markup=kb.main_player
            )
            
        elif user_type == 'owner':
            # Для владельца показываем лайки от игроков (заявки в клуб)
            likes = db_operation(
                """SELECT pl.player_id, pl.created_at, u.username, u.first_name, u.nickname,
                   usc.nickname as game_nickname, usc.player_position, usc.experience,
                   usc.clubs_played_before, usc.created_at as profile_created_at
                   FROM player_likes pl 
                   JOIN all_users u ON pl.player_id = u.id 
                   LEFT JOIN users_search_club usc ON pl.player_id = usc.player_id 
                   WHERE pl.liked_club_id = ? 
                   ORDER BY pl.created_at DESC""",
                (user_id,),
                fetch=True
            )
            
            if not likes:
                await message.reply(
                    "📭 <b>У вашего клуба пока нет входящих лайков</b>\n\n"
                    "Когда игроки увидят вашу анкету и заинтересуются, "
                    "они смогут отправить заявку, и она появится здесь!",
                    parse_mode="html",
                    reply_markup=kb.vibor_for_owner
                )
                return
            
            # Отправляем каждую заявку отдельным сообщением с клавиатурой
            for i, (player_id, liked_at, player_username, player_first_name, player_nickname,
                   game_nickname, position, experience, clubs, profile_created_at) in enumerate(likes, 1):
                
                # Форматируем дату создания анкеты игрока по МСК
                profile_created_moscow = format_moscow_time(profile_created_at) if profile_created_at else "Не указана"
                
                # Формируем контактную информацию об игроке
                player_contact_info = player_username or player_nickname or str(player_id)
                if player_username:
                    player_contact = f"@{player_username}"
                elif player_nickname:
                    player_contact = f"Ник: {player_nickname}"
                else:
                    player_contact = f"ID: {player_id}"
                
                response = (
                    f"<b>🎉 Заявка от игрока #{i}</b>\n\n"
                    f"👤 <b>Игрок:</b> {player_first_name or player_nickname}\n"
                    f"📱 <b>Контакт:</b> {player_contact}\n"
                    f"🎮 <b>Игровой никнейм:</b> {game_nickname or 'Не указан'}\n"
                    f"⚽ <b>Позиция:</b> {position or 'Не указана'}\n"
                    f"📅 <b>Опыт:</b> {experience or 'Не указан'}\n"
                    f"🏆 <b>Предыдущие клубы:</b> {clubs[:50] + '...' if clubs and len(clubs) > 50 else clubs or 'Нет опыта'}\n"
                    f"📅 <b>Дата создания анкеты игрока:</b> {profile_created_moscow}\n"
                    f"🕐 <b>Заявка получена:</b> {liked_at}\n\n"
                    f"<i>Хотите связаться с игроком?</i>"
                )
                
                # Создаем уникальную клавиатуру для этого сообщения с callback_data содержащей ID
                contact_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📞 Связаться с игроком", 
                                         callback_data=f"contact_player:{player_id}")],
                    [InlineKeyboardButton(text="❌ Отклонить заявку", 
                                         callback_data=f"reject_player:{player_id}")]
                ])
                
                await message.reply(response, parse_mode="html", reply_markup=contact_keyboard)
                
                # Небольшая задержка между сообщениями
                await asyncio.sleep(0.5)
            
            # Итоговое сообщение
            await message.reply(
                f"📊 <b>Всего заявок:</b> {len(likes)}\n\n"
                f"<i>Нажмите '📞 Связаться с игроком' чтобы начать общение!</i>",
                parse_mode="html",
                reply_markup=kb.main_owner
            )
            
    except Exception as e:
        logger.error(f"Ошибка в incoming_likes: {str(e)[:100]}")
        await message.reply(f"❌ Ошибка при загрузке входящих: {str(e)[:100]}", reply_markup=kb.main)
# ============== ПОИСК КЛУБОВ (ИГРОК) ==============

@router.message(F.text == "🔎 Искать клубы")
async def search_clubs_main(message: Message, state: FSMContext):
    """Начинает поиск клубов (только для игроков)"""
    try:
        # Проверяем, что пользователь - игрок
        result = db_operation(
            "SELECT user_type FROM all_users WHERE id = ?",
            (message.from_user.id,),
            fetch=True
        )
        
        if not result:
            await message.reply("Сначала зарегистрируйтесь через /start")
            return
            
        if result[0][0] != 'player':
            await message.reply(
                "❌ Эта функция доступна только для игроков.\n\n",  
            )
            return
        
        # Проверяем, есть ли у игрока анкета
        player_anketa = db_operation(
            "SELECT * FROM users_search_club WHERE player_id = ?",
            (message.from_user.id,),
            fetch=True
        )
        
        if not player_anketa:
            await message.reply(
                "❌ Сначала создайте анкету игрока!\n\n"
                "Перейдите в '✏️Мой профиль' → '📝 Создать анкету'",
                reply_markup=kb.vibor_for_player
            )
            return
        
        await message.reply("🔍 Начинаю поиск клубов...")
        
        
        # Получаем ВСЕ анкеты клубов
        all_ankets = db_operation(
    "SELECT owner_id, club_name, needed_positions, owner_comment, created_at FROM owners_search_players ORDER BY created_at DESC",
    fetch=True
)
        
        if not all_ankets:
            await message.reply("📭 Пока нет анкет клубов для просмотра.")
            return
        
        # Фильтруем уже лайкнутые анкеты
        filtered_ankets = []
        for anket in all_ankets:
            club_id = anket[0]
            
            # Проверяем, лайкали ли уже этот клуб
            liked = db_operation(
                "SELECT * FROM player_likes WHERE player_id = ? AND liked_club_id = ?",
                (message.from_user.id, club_id),
                fetch=True
            )
            
            # Если не лайкали - добавляем в список
            if not liked:
                filtered_ankets.append(anket)
        
        if not filtered_ankets:
            await message.reply(
                "✅ Вы просмотрели все доступные анкеты клубов!\n",
                reply_markup=kb.main_player
            )
            return
        
        # Сохраняем анкеты и индекс в state
        await state.update_data(
            club_ankets=filtered_ankets,
            current_club_index=0
        )
        
        # Показываем первую анкету
        await show_club_anket_player(message, state, 0)
        await state.set_state(SupportStates.viewing_clubs)
        
    except Exception as e:
        await message.reply(f"❌ Ошибка при поиске клубов: {str(e)[:100]}")


async def show_club_anket_player(message: Message, state: FSMContext, index: int):
    """Показывает анкету клуба игроку с датой создания по МСК"""
    try:
        data = await state.get_data()
        ankets = data.get('club_ankets', [])
        
        if index >= len(ankets):
            await message.reply(
                "🏁 Вы просмотрели все доступные анкеты клубов!\n"
                "Можете вернуться позже для просмотра новых анкет.",
                reply_markup=kb.main_player
            )
            await state.clear()
            return
        
        # Получаем все данные из анкеты
        owner_id = ankets[index][0]
        club_name = ankets[index][1]
        positions = ankets[index][2]
        comment = ankets[index][3]
        created_at = ankets[index][4]  # created_at теперь на позиции 4
        
        # Получаем информацию о владельце клуба
        owner_info = db_operation(
            "SELECT username, first_name, nickname FROM all_users WHERE id = ?",
            (owner_id,),
            fetch=True
        )
        
        if owner_info:
            username = owner_info[0][0] or "Не указан"
            first_name = owner_info[0][1] or "Не указано"
            owner_nickname = owner_info[0][2] or "Не указано"
        else:
            username = "Не указан"
            first_name = "Не указано"
            owner_nickname = "Не указано"
        
        # Форматируем дату создания по МСК
        created_at_moscow = format_moscow_time(created_at)
        
        # Формируем сообщение с анкетой
        anketa_message = (
            f"👑 <b>Анкета клуба #{index + 1} из {len(ankets)}</b>\n\n"
            f"<b>🏷️ Название клуба:</b> {club_name}\n"
            f"<b>👤 Владелец:</b> {owner_nickname} ({first_name})\n"
            f"<b>🎮 Ищем позиции:</b> {positions}\n"
            f"<b>🏆 О клубе:</b> {comment}\n"
            f"<b>📅 Дата создания анкеты:</b> {created_at_moscow}\n\n"
            f"<i>Хотите отправить заявку в этот клуб?</i>"
        )
        
        await message.reply(
            anketa_message,
            parse_mode="html",
            reply_markup=kb.anketa_like_dislike_player
        )
        
        # Сохраняем текущий индекс
        await state.update_data(current_club_index=index)
        
    except Exception as e:
        logger.error(f"Ошибка в show_club_anket_player: {e}")
        await message.reply(f"❌ Ошибка при отображении анкеты: {str(e)[:100]}")
        await state.clear()



#===================================================
#лайк с сообщением

@router.message(F.text == "📧 Отправить заявку с сообщением")
async def like_club_with_message_player(message: Message, state: FSMContext):
    """Игрок хочет отправить заявку в клуб с сообщением"""
    try:
        # Проверяем, что мы в режиме просмотра клубов
        if await state.get_state() != SupportStates.viewing_clubs:
            return
        
        data = await state.get_data()
        current_index = data.get('current_club_index', 0)
        ankets = data.get('club_ankets', [])
        
        if current_index < len(ankets):
            club_id = ankets[current_index][0]
            
            # Сохраняем ID клуба для отправки сообщения
            await state.update_data(
                club_for_message=club_id,
                club_index_for_message=current_index
            )
            
            await message.reply(
                "💌 <b>Напишите сообщение для владельца клуба:</b>\n\n"
                "<i>В этом сообщении вы можете рассказать о себе, своем опыте "
                "или задать вопросы о клубе.</i>",
                parse_mode="html",
                reply_markup=kb.cancel_message_keyboard
            )
            await state.set_state(SupportStates.waiting_for_club_message)
        else:
            await message.reply("❌ Ошибка: анкета не найдена.")
            
    except Exception as e:
        await message.reply(f"❌ Ошибка: {str(e)[:100]}")
        await state.clear()




#============================

# ============== СОЗДАНИЕ АНКЕТЫ ==============

@router.message(F.text == "📣Репорт")
@log_command
async def report1(message: Message, state: FSMContext):
    # Если уже есть активное состояние, предлагаем отменить его
    if await state.get_state():
        await message.reply(
            "У вас есть незавершенное действие. Нажмите '❌ Отмена' чтобы отменить его.",
            reply_markup=kb.otmena
        )
        await state.clear()
        return
        
    user_id = message.from_user.id
    
    # Проверяем, находится ли пользователь в муте
    if is_muted(user_id):
        mute_info = get_mute_info(user_id)
        if mute_info:
            unmute_time = mute_info['unmute_time'].strftime("%d.%m.%Y в %H:%M")
            time_left = mute_info['unmute_time'] - datetime.now()
            
            # Рассчитываем оставшееся время
            total_seconds = int(time_left.total_seconds())
            if total_seconds <= 0:
                unmute_user(user_id)
                # Разрешаем отправку Репорта, если мут истек
                await message.reply("Перед отправкой Репорта вы ПОЛНОСТЬЮ и БЕЗОГОВОРОЧНО принимаете условия написания обращения:\nЗАПРЕЩАЕТСЯ:\n1.Оффтоп\n2.Спам\n3.Ложные жалобы\n4.Оскорбления\n5.Использование кнопки Репорт не по назначению\n6.Пустые и бессмысленные репорты\n\n\n📨 Введите ваше обращение:", reply_markup=kb.report_cancel)
                await state.set_state(SupportStates.waiting_report)
                return
            
            hours_left = total_seconds // 3600
            minutes_left = (total_seconds % 3600) // 60
            
            await message.reply(
                f"🚫 <b>Вы не можете отправлять Репорты!</b>\n"
                f"⏳ Вы находитесь в муте до {unmute_time}\n"
                f"⏰ Осталось: {hours_left}ч {minutes_left}м\n\n",
                parse_mode="HTML"
            )
            return
    
    # Если пользователь не в муте, продолжаем как обычно
    await message.reply("Перед отправкой Репорта вы ПОЛНОСТЬЮ и БЕЗОГОВОРОЧНО принимаете условия написания обращения:\nЗАПРЕЩАЕТСЯ:\n1.Оффтоп\n2.Спам\n3.Ложные жалобы\n4.Оскорбления\n5.Использование кнопки Репорт не по назначению\n6.Пустые и бессмысленные репорты\n\n\n📨 Введите ваше обращение:", reply_markup=kb.report_cancel)
    await state.set_state(SupportStates.waiting_report)


@router.message(F.text == "❌ Отменить обращение")
async def cancel_report(message: Message, state: FSMContext):
    """Отмена создания репорта"""
    try:
        # Проверяем, находимся ли мы в состоянии ожидания репорта
        current_state = await state.get_state()
        
        if current_state == SupportStates.waiting_report:
            await state.clear()
            
            # Возвращаем пользователя в главное меню в зависимости от его типа
            result = db_operation(
                "SELECT user_type FROM all_users WHERE id = ?",
                (message.from_user.id,),
                fetch=True
            )
            
            reply_markup = kb.main  # по умолчанию
            
            if result:
                user_type = result[0][0]
                if user_type == 'player':
                    reply_markup = kb.main_player
                elif user_type == 'owner':
                    reply_markup = kb.main_owner
            
            await message.reply(
                "❌ Создание обращения отменено. Возвращаю в главное меню.",
                reply_markup=kb.main_general
            )
        else:
            # Если не в состоянии ожидания репорта, просто очищаем состояние
            await state.clear()
            await message.reply(
                "❌ Действие отменено.",
                reply_markup=kb.main
            )
            
    except Exception as e:
        await state.clear()
        await message.reply(
            "❌ Действие отменено. Возвращаю в главное меню.",
            reply_markup=kb.main
        )
        logger.error(f"Ошибка при отмене репорта: {str(e)[:100]}")


@router.message(SupportStates.waiting_report)
async def report2(message: Message, state: FSMContext, bot: Bot):
    # Проверяем, не пытается ли пользователь отменить обращение
    if message.text == "❌ Отменить обращение":
        await cancel_report(message, state)
        return
    
    # Продолжаем обработку репорта как обычно
    report_from_user = message.text
    user_id = message.from_user.id
    username_from_user = message.from_user.username if message.from_user.username else f"ID: {message.from_user.id}"
    
    # Отправляем подтверждение пользователю
    # Получаем тип пользователя для правильного меню
    result = db_operation(
        "SELECT user_type FROM all_users WHERE id = ?",
        (user_id,),
        fetch=True
    )
    
    reply_markup = kb.main  # по умолчанию
    if result:
        user_type = result[0][0]
        if user_type == 'player':
            reply_markup = kb.main_player
        elif user_type == 'owner':
            reply_markup = kb.main_owner
    
    await message.reply("💡 Ваше сообщение передано администрации!", reply_markup=kb.main_general)
    
    try:
        # Отправляем репорт в группу админов
        group_id = -1003615487276 # ID группы администраторов
        await bot.send_message(
            group_id,
            f"📬 <b>Входящий репорт</b>\n━━━━━━━━━━━━━━\n\n"
            f"{report_from_user}\n\n"
            f"━━━━━━━━━━━━━━\n"
            f"<i>⚡ Отправитель: @{username_from_user if isinstance(username_from_user, str) and username_from_user.startswith('@') else username_from_user} (ID: {user_id})</i>\n"
            f"<i>⚡ Ответьте на него в боте, используя /writeto</i>\n"
            f"<b>Не забудьте написать в чат группы о том, что возьметесь за ответ на репорт</b>\n\n"
            f"📌 #репорты",
            parse_mode="html"
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке репорта в группу: {e}")
        # Продолжаем отправку админам даже если не удалось отправить в группу
    
    # Отправляем репорт каждому администратору индивидуально
    sent_to_admins = 0

    await bot.send_message(
                1088006569,
                f"<b>📢 Вам пришел 📣Репорт от пользователя @{username_from_user} с ID {user_id}!</b>\n\n"
                f"<b>Текст репорта:</b>\n\n"
                f"==========\n"
                f"{report_from_user}\n"
                f"==========\n\n"
                f"<i>Чтобы ответить, введите команду /writeto</i>\n"
                f"<i>ID пользователя для ответа: {user_id}</i>", 
                parse_mode="html"
            )
    sent_to_admins += 1

    
    # Логируем результат
    if sent_to_admins > 0:
        logger.info(f"Репорт от пользователя {user_id} (@{username_from_user}) отправлен {sent_to_admins} администраторам")
    else:
        logger.warning(f"Репорт от пользователя {user_id} (@{username_from_user}) не был отправлен ни одному администратору")
    
    # Очищаем состояние после отправки
    await state.clear()
    

@router.message(Command("addcoins"))
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

@router.callback_query(F.data.startswith("admin_addcoins_"))
async def admin_addcoins_callback(callback: CallbackQuery):
    """Кнопка изменения коинов"""
    try:
        target_user_id = int(callback.data.split("_")[2])
        await callback.answer(f"Используйте /addcoins {target_user_id} [количество] [комментарий]")
    except:
        await callback.answer("❌ Ошибка", show_alert=True)

@router.callback_query(F.data.startswith("admin_addcard_"))
async def admin_addcard_callback(callback: CallbackQuery):
    """Кнопка добавления карточки"""
    try:
        target_user_id = int(callback.data.split("_")[2])
        await callback.answer(f"Используйте /addcard [ник_игрока] {target_user_id}")
    except:
        await callback.answer("❌ Ошибка", show_alert=True)

@router.callback_query(F.data.startswith("admin_stats_"))
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
#================
#BONUS-SYSTEM
from datetime import date
def get_moscow_time() -> datetime:
    """Возвращает текущее время по Москве"""
    moscow_tz = pytz.timezone('Europe/Moscow')
    # Создаем datetime с правильной временной зоной
    moscow_now = datetime.now(moscow_tz)
    return moscow_now

def get_moscow_date() -> date:
    """Возвращает текущую дату по Москве"""
    return get_moscow_time().date()

BONUS_SYSTEM = {
    1: 5,   # День 1: +1 коин
    2: 7,   # День 2: +3 коина
    3: 9,   # День 3: +5 коинов
    4: 12,   # День 4: +6 коинов
    5: 15,   # День 5: +7 коинов
    6: 20,   # День 6: +8 коинов
    7: 25,  # День 7: +10 коинов
}
# После 7 дня сбрасывается к дню 1
MAX_STREAK_DAYS = 7

def process_daily_bonus(user_id: int):
    """Обрабатывает ежедневный бонус пользователя (по московскому времени)"""
    try:
        # Получаем текущее московское время
        moscow_tz = pytz.timezone('Europe/Moscow')
        utc_now = datetime.now(pytz.UTC)
        moscow_now = utc_now.astimezone(moscow_tz)
        
        # Для хранения в БД используем UTC (чтобы избежать путаницы с часовыми поясами)
        utc_datetime_str = utc_now.strftime('%Y-%m-%d %H:%M:%S')
        moscow_date = moscow_now.date()
        
        logger.info(f"🎁 Пользователь {user_id} пытается получить бонус. Дата МСК: {moscow_date}")
        
        # Проверяем существование пользователя
        user_check = db_operation(
            "SELECT 1 FROM all_users WHERE id = ?",
            (user_id,),
            fetch=True
        )
        
        if not user_check:
            logger.warning(f"Пользователь {user_id} не найден при попытке получения бонуса")
            return False, "Пользователь не найден. Пройдите регистрацию /start", 0, 0, 0
        
        # Получаем информацию о бонусе пользователя
        result = db_operation(
            """SELECT last_bonus_moscow, streak_days, total_bonus_coins 
               FROM user_daily_bonus 
               WHERE user_id = ?""",
            (user_id,),
            fetch=True
        )
        
        if result:
            last_bonus_str, streak_days, total_coins = result[0]
            logger.info(f"Пользователь {user_id}: last_bonus_str={last_bonus_str}, streak={streak_days}, total_coins={total_coins}")
            
            if last_bonus_str:
                try:
                    # Время в БД хранится в UTC
                    last_bonus_utc = datetime.strptime(last_bonus_str, '%Y-%m-%d %H:%M:%S')
                    last_bonus_utc = pytz.UTC.localize(last_bonus_utc)
                    
                    # Конвертируем в московское время для сравнения дат
                    last_bonus_moscow = last_bonus_utc.astimezone(moscow_tz)
                    last_bonus_date = last_bonus_moscow.date()
                    
                    logger.info(f"Дата последнего бонуса: {last_bonus_date} (МСК), текущая дата: {moscow_date} (МСК)")
                    
                    # КРИТИЧЕСКАЯ ПРОВЕРКА: Уже получал бонус сегодня?
                    if last_bonus_date == moscow_date:
                        next_date = last_bonus_date + timedelta(days=1)
                        next_time_str = next_date.strftime('%d.%m.%Y')
                        logger.warning(f"Пользователь {user_id} уже получал бонус сегодня {last_bonus_date}")
                        return False, f"Вы уже получили бонус сегодня!\n\nСледующий бонус доступен: {next_time_str} (по МСК)", streak_days, 0, total_coins
                    
                    # Проверяем, не прервана ли серия
                    days_diff = (moscow_date - last_bonus_date).days
                    logger.info(f"Разница дней: {days_diff}")
                    
                    if days_diff > 1:
                        # Серия прервана
                        new_streak = 1
                        streak_message = f"Серия прервана! Начинаем заново с {BONUS_SYSTEM[1]} коина."
                        logger.info(f"Серия прервана, начинаем заново с дня {new_streak}")
                    else:
                        # Серия продолжается
                        new_streak = streak_days + 1
                        if new_streak > MAX_STREAK_DAYS:
                            new_streak = 1
                            streak_message = f"7-дневная серия завершена! Начинаем новый цикл с {BONUS_SYSTEM[1]} коина."
                        else:
                            streak_message = f"День {new_streak} из 7! Продолжайте в том же духе!"
                        logger.info(f"Серия продолжается, день {new_streak}")
                        
                except Exception as e:
                    logger.error(f"Ошибка парсинга даты {last_bonus_str}: {e}")
                    # Если ошибка парсинга, начинаем заново
                    new_streak = 1
                    streak_message = f"Начинаем серию бонусов! {BONUS_SYSTEM[1]} коин."
                    total_coins = 0
            else:
                # Нет записи о последнем бонусе
                new_streak = 1
                streak_message = f"Ваш первый ежедневный бонус! {BONUS_SYSTEM[1]} коин."
                total_coins = 0
                logger.info(f"Первый бонус для пользователя {user_id}")
        else:
            # Первый бонус пользователя
            new_streak = 1
            total_coins = 0
            streak_message = f"Ваш первый ежедневный бонус! {BONUS_SYSTEM[1]} коин."
            logger.info(f"Первый бонус для нового пользователя {user_id}")
        
        # Получаем количество коинов за сегодня
        today_bonus = BONUS_SYSTEM.get(new_streak, 1)
        logger.info(f"Бонус за день {new_streak}: {today_bonus} коинов")
        
        # ОБНОВЛЯЕМ ИНФОРМАЦИЮ О БОНУСЕ (храним время в UTC)
        db_operation(
            """INSERT OR REPLACE INTO user_daily_bonus 
               (user_id, last_bonus_moscow, streak_days, total_bonus_coins, updated_at) 
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, utc_datetime_str, new_streak, total_coins + today_bonus, utc_datetime_str)
        )
        logger.info(f"Запись в БД обновлена: last_bonus={utc_datetime_str} (UTC), streak={new_streak}")
        
        # ДОБАВЛЯЕМ КОИНЫ ПОЛЬЗОВАТЕЛЮ
        add_user_coins(user_id, today_bonus)
        
        # Получаем актуальный баланс
        current_coins = get_user_coins(user_id)
        
        # Формируем сообщение с московским временем
        bonus_message = (
            f"🎁 <b>ЕЖЕДНЕВНЫЙ БОНУС</b> 🎁\n\n"
            f"📅 <b>Дата:</b> {moscow_now.strftime('%d.%m.%Y')} (по МСК)\n"
            f"🕐 <b>Время получения:</b> {moscow_now.strftime('%H:%M')} (МСК)\n"
            f"🔥 <b>День серии:</b> {new_streak}/7\n"
            f"💰 <b>Получено коинов:</b> +{today_bonus}\n"
            f"🏦 <b>Ваш баланс:</b> {current_coins} коинов\n\n"
            f"{streak_message}\n\n"
            f"<i>Следующий бонус будет доступен завтра в 00:00 (по МСК)</i>"
        )
        
        logger.info(f"✅ БОНУС ВЫДАН: Пользователь {user_id} получил {today_bonus} коинов (день {new_streak}) в {moscow_now.strftime('%H:%M')} МСК")
        
        return True, bonus_message, new_streak, today_bonus, current_coins
        
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке бонуса для пользователя {user_id}: {e}")
        import traceback
        logger.error(f"Трейсбэк: {traceback.format_exc()}")
        return False, f"❌ Произошла ошибка: {str(e)[:100]}", 0, 0, 0
    
def add_user_coins(user_id: int, amount: int):
    """Добавляет коины пользователю"""
    try:
        # Сначала проверим существование записи
        current_coins = get_user_coins(user_id)
        new_amount = current_coins + amount
        
        logger.info(f"Добавление коинов пользователю {user_id}: {current_coins} + {amount} = {new_amount}")
        
        db_operation(
            """INSERT OR REPLACE INTO user_coins (user_id, coins, updated_at) 
               VALUES (?, ?, CURRENT_TIMESTAMP)""",
            (user_id, new_amount)
        )
        
        # Проверим, что коины действительно добавились
        check_coins = get_user_coins(user_id)
        logger.info(f"Проверка после добавления: {check_coins} коинов")
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при добавлении коинов пользователю {user_id}: {e}")
        return False

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
    
@router.message(Command("bonus"))
@log_command
async def daily_bonus_command(message: Message):
    """Выдача ежедневного бонуса"""
    user_id = message.from_user.id
    user_name = message.from_user.username or message.from_user.first_name
    
    try:
        # Проверяем бан пользователя
        if is_user_banned(user_id):
            await message.reply(
                "🚫 <b>Вы забанены и не можете получать бонусы!</b>\n\n"
                "Для обжалования обратитесь: @kirik1231zzap",
                parse_mode="html"
            )
            return
        
        # Обрабатываем бонус
        success, bonus_message, streak_day, coins_received, total_coins = process_daily_bonus(user_id)
        
        # Создаем клавиатуру
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🛒 Купить карточки", 
                        callback_data="bay_cards"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="📊 Статистика бонусов", 
                        callback_data="bonus_stats"
                    )
                ]
            ]
        )
        
        await message.reply(
            bonus_message,
            parse_mode="html",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Ошибка в команде /bonus для пользователя {user_id}: {e}")
        await message.reply(
            "❌ <b>Ошибка при выдаче бонуса!</b>\n\n"
            "Попробуйте позже или обратитесь к администратору.",
            parse_mode="html"
        )
@router.callback_query(F.data == "bonus_stats")
@router.message(Command("bonus_stats"))
@log_command
async def bonus_stats_command(update: Message | CallbackQuery):
    """Показывает статистику по бонусам"""
    try:
        if isinstance(update, CallbackQuery):
            message = update.message
            user_id = update.from_user.id
            user_name = update.from_user.username or update.from_user.first_name
            is_callback = True
        else:
            message = update
            user_id = update.from_user.id
            user_name = update.from_user.username or update.from_user.first_name
            is_callback = False
        
        # Получаем информацию о бонусе
        result = db_operation(
            """SELECT last_bonus_moscow, streak_days, total_bonus_coins 
               FROM user_daily_bonus 
               WHERE user_id = ?""",
            (user_id,),
            fetch=True
        )
        
        moscow_now = get_moscow_time()
        current_coins = get_user_coins(user_id)
        
        if not result:
            # Пользователь еще не получал бонусы
            stats_message = (
                f"📊 <b>СТАТИСТИКА БОНУСОВ</b>\n\n"
                f"👤 <b>Пользователь:</b> {user_name}\n"
                f"💰 <b>Текущий баланс:</b> {current_coins} коинов\n\n"
                f"🎁 <b>Ежедневные бонусы:</b>\n"
                f"• Вы еще не получали бонусы\n"
                f"• Первый бонус: +1 коин\n"
                f"• Максимальный бонус: +10 коинов (7-й день)\n\n"
                f"⏰ <b>Текущее время:</b> {moscow_now.strftime('%H:%M %d.%m.%Y')} (по МСК)\n\n"
                f"<i>Используйте команду /bonus чтобы получить первый бонус!</i>"
            )
        else:
            last_bonus_str, streak_days, total_bonus_coins = result[0]
            
            # Парсим время последнего бонуса
            try:
                last_bonus = datetime.strptime(last_bonus_str, '%Y-%m-%d %H:%M:%S')
                last_bonus = pytz.UTC.localize(last_bonus).astimezone(pytz.timezone('Europe/Moscow'))
                last_bonus_date = last_bonus.date()
                last_bonus_formatted = last_bonus.strftime('%d.%m.%Y в %H:%M')
            except:
                last_bonus_formatted = last_bonus_str
                last_bonus_date = datetime.strptime(last_bonus_str.split()[0], '%Y-%m-%d').date()
            
            # Проверяем, можно ли получить бонус сегодня
            moscow_date = moscow_now.date()
            can_get_today = last_bonus_date < moscow_date
            
            # Определяем следующий бонус
            next_bonus_day = streak_days + 1 if streak_days < 7 else 1
            next_bonus_coins = BONUS_SYSTEM.get(next_bonus_day, 1)
            
            # Формируем прогресс-бар серии
            progress_bar = ""
            for day in range(1, 8):
                if day <= streak_days:
                    progress_bar += "🟢"  # Пройденные дни
                else:
                    progress_bar += "⚪"  # Предстоящие дни
            
            stats_message = (
                f"📊 <b>СТАТИСТИКА БОНУСОВ</b>\n\n"
                f"👤 <b>Пользователь:</b> {user_name}\n"
                f"💰 <b>Текущий баланс:</b> {current_coins} коинов\n"
                f"🏦 <b>Всего получено бонусов:</b> {total_bonus_coins} коинов\n\n"
                
                f"🎁 <b>Текущая серия:</b> День {streak_days}/7\n"
                f"{progress_bar}\n\n"
                
                f"📅 <b>Последний бонус:</b>\n"
                f"{last_bonus_formatted} (по МСК)\n\n"
            )
            
            if can_get_today:
                today_bonus = BONUS_SYSTEM.get(streak_days + 1 if streak_days < 7 else 1, 1)
                stats_message += (
                    f"✅ <b>Сегодня можно получить:</b> +{today_bonus} коинов\n\n"
                    f"<i>Используйте команду /bonus</i>"
                )
            else:
                next_date = last_bonus_date + timedelta(days=1)
                next_date_str = next_date.strftime('%d.%m.%Y')
                stats_message += (
                    f"⏳ <b>Следующий бонус:</b>\n"
                    f"• Дата: {next_date_str} (после 00:00 МСК)\n"
                    f"• День серии: {next_bonus_day}/7\n"
                    f"• Коинов: +{next_bonus_coins}\n\n"
                    f"<i>Возвращайтесь завтра!</i>"
                )
        
        # Создаем клавиатуру
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🎁 Получить бонус", 
                        callback_data="get_bonus_callback" if can_get_today else "noop"
                    ) if can_get_today else InlineKeyboardButton(
                        text="⏳ Бонус завтра", 
                        callback_data="noop"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="💰 Мой профиль", 
                        callback_data="trade_profile"
                    ),
                    InlineKeyboardButton(
                        text="🔄 Обновить", 
                        callback_data="bonus_stats"
                    )
                ]
            ]
        )
        
        if is_callback:
            await message.edit_text(
                stats_message,
                parse_mode="html",
                reply_markup=keyboard
            )
            await update.answer()
        else:
            await message.reply(
                stats_message,
                parse_mode="html",
                reply_markup=keyboard
            )
            
    except Exception as e:
        logger.error(f"Ошибка в bonus_stats_command для пользователя {user_id}: {e}")
        error_msg = "❌ Ошибка при загрузке статистики"
        if isinstance(update, CallbackQuery):
            await update.answer(error_msg, show_alert=True)
        else:
            await update.reply(error_msg)



@router.message(Command("delete_all_ankets"))
@log_command
@log_admin_action("удаление всех анкет")
async def delete_all_ankets(message: Message):
    """Удаляет все анкеты из базы данных"""
    
    # Проверяем права администратора
    if message.from_user.id != 1088006569:
        await message.reply("❌ У вас нет прав для выполнения этой команды.")
        return
    
    # Создаем клавиатуру подтверждения
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(
            text="✅ Да, удалить все анкеты",
            callback_data="confirm_delete_ankets"
        ),
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="cancel_delete_ankets"
        )
    )
    
    await message.reply(
        "⚠️ <b>ВНИМАНИЕ!</b>\n\n"
        "Вы собираетесь удалить <b>ВСЕ анкеты</b> из базы данных.\n"
        "Это действие нельзя отменить!\n\n"
        "Вы уверены?",
        parse_mode="HTML",
        reply_markup=keyboard.as_markup()
    )

@router.callback_query(F.data == "confirm_delete_ankets")
async def confirm_delete_all_ankets(callback: CallbackQuery):
    """Подтверждение удаления всех анкет"""
    try:
        # Удаляем все анкеты из всех таблиц
        db_operation("DELETE FROM users_search_club")
        db_operation("DELETE FROM owners_search_players")
        
        # Также удаляем лайки
        db_operation("DELETE FROM owner_likes")
        db_operation("DELETE FROM player_likes")
        
        await callback.message.edit_text(
            "✅ Все анкеты успешно удалены!\n\n"
            "Удалено:\n"
            "• Анкеты игроков (ищущих клуб)\n"
            "• Анкеты клубов (ищущих игроков)\n"
            "• Все лайки"
        )
        
        logger.warning(f"👑 АДМИН: Все анкеты удалены пользователем {callback.from_user.id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при удалении всех анкет: {e}")
        await callback.message.edit_text(f"❌ Произошла ошибка: {str(e)[:200]}")

@router.callback_query(F.data == "cancel_delete_ankets")
async def cancel_delete_all_ankets(callback: CallbackQuery):
    """Отмена удаления всех анкет"""
    await callback.message.edit_text("❌ Удаление анкет отменено.")

@router.callback_query(F.data == "get_bonus_callback")
async def get_bonus_callback_handler(callback: CallbackQuery):
    """Обработчик кнопки получения бонуса"""
    await daily_bonus_command(callback.message)
    await callback.answer()
# Мидлварь для проверки мута (блокировка кнопки "📣Репорт")
@router.callback_query(lambda c: c.data == "send_report")
async def process_report(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    # Проверяем мут (синхронный вызов!)
    if is_muted(user_id):
        await callback_query.answer(
            "🚫 Вы не можете отправлять 📣Репорты, так как находитесь в муте!\n"
            "⏳ Дождитесь окончания мута.",
            show_alert=True
        )
        return
    
    # Если пользователь не в муте, продолжаем обработку Репорта
    await callback_query.answer("📣Репорт отправлен!", show_alert=False)
    # ... остальная логика обработки Репорта ...

# Мидлварь для проверки мута
@router.message()
async def check_mute_on_message(message: Message):
    """Проверяем мут при каждом сообщении"""
    user_id = message.from_user.id
    
    # Проверяем мут (синхронный вызов!)
    if is_muted(user_id):
        # Если пользователь в муте и пытается использовать команду Репорт
        text_lower = message.text.lower() if message.text else ""
        
        # Проверяем различные варианты команды Репорта
        report_triggers = [
            "📣Репорт", 
            "/report", 
            "жалоба", 
            "/report@",  # если бот в группе
            "/📣Репорт"
            "📣Репорт"
        ]
        
        for trigger in report_triggers:
            if trigger in text_lower:
                # Получаем информацию о муте
                mute_info = get_mute_info(user_id)
                if mute_info:
                    unmute_time = mute_info['unmute_time'].strftime("%d.%m.%Y в %H:%M")
                    time_left = mute_info['unmute_time'] - datetime.now()
                    hours_left = int(time_left.total_seconds() // 3600)
                    minutes_left = int((time_left.total_seconds() % 3600) // 60)
                    
                    await message.reply(
                        f"🚫 <b>Вы не можете отправлять 📣Репорты!</b>\n"
                        f"⏳ Вы находитесь в муте до {unmute_time}\n"
                        f"⏰ Осталось: {hours_left}ч {minutes_left}м",
                        parse_mode="HTML"
                    )
                
                # Удаляем сообщение
                try:
                    await message.delete()
                except:
                    pass
                return

@router.message(F.text == "❌Отмена")
async def cancel_action(message: Message, state: FSMContext):
    """Обработчик кнопки отмены - универсальный для всех состояний"""
    try:
        # Получаем текущее состояние
        current_state = await state.get_state()
        
        # Определяем тип пользователя для правильной клавиатуры
        result = db_operation(
            "SELECT user_type FROM all_users WHERE id = ?",
            (message.from_user.id,),
            fetch=True
        )
        
        # Выбираем соответствующую клавиатуру
        if result:
            user_type = result[0][0]
            if user_type == 'player':
                keyboard = kb.main_player
                user_type_text = "игрок"
            elif user_type == 'owner':
                keyboard = kb.main_owner
                user_type_text = "владелец клуба"
            else:
                keyboard = kb.main
                user_type_text = "пользователь"
        else:
            keyboard = kb.main
            user_type_text = "пользователь"
        
        # Определяем, в каком состоянии находимся
        state_messages = {
            SupportStates.anketa_nickname: "создания анкеты (никнейм)",
            SupportStates.anketa_position: "создания анкеты (позиция)",
            SupportStates.anketa_experience: "создания анкеты (опыт)",
            SupportStates.anketa_clubs: "создания анкеты (клубы)",
            SupportStates.anketa_position_selection: "выбора позиции",
            SupportStates.owner_club_name: "создания анкеты клуба (название)",
            SupportStates.owner_needed_positions: "создания анкеты клуба (позиции)",
            SupportStates.owner_positions_selection: "выбора позиций для клуба",
            SupportStates.owner_comment: "создания анкеты клуба (комментарий)",
            SupportStates.viewing_players: "просмотра игроков",
            SupportStates.viewing_clubs: "просмотра клубов",
            SupportStates.waiting_for_player_message: "отправки сообщения игроку",
            SupportStates.waiting_for_club_message: "отправки сообщения клубу",
            SupportStates.waiting_for_message_for_rassilka: "рассылки",
            SupportStates.waiting_for_ban_id1: "выдачи бана (ID)",
            SupportStates.waiting_for_ban_id2: "выдачи бана (причина)",
            SupportStates.waiting_for_id1: "ответа на репорт (ID)",
            SupportStates.waiting_for_id2: "ответа на репорт (сообщение)",
            SupportStates.waiting_id_for_mute1: "выдачи мута (ID)",
            SupportStates.waiting_id_for_mute2: "выдачи мута (время)",
            SupportStates.waiting_report: "отправки репорта",
            SupportStates.waiting_filter_position: "выбора фильтра",
            SupportStates.nickname_of_user: "регистрации (никнейм)",
            SupportStates.waiting_for_request: "заявка на добавление в фмамокарту",
        }
        
        # Получаем понятное описание состояния
        current_action = state_messages.get(current_state, "действия")
        
        # Отправляем сообщение об отмене
        if current_state:
            await message.reply(
                f"❌ Отмена {current_action}.\n\n"
                f"Вы вернулись в главное меню как {user_type_text}.",
                reply_markup=keyboard
            )
        else:
            # Если нет активного состояния
            await message.reply(
                f"✅ Вы уже в главном меню как {user_type_text}.",
                reply_markup=keyboard
            )
        
        # Очищаем состояние
        await state.clear()
        
        # Логируем отмену
        logger.info(f"Пользователь {message.from_user.id} отменил {current_action}")
        
    except Exception as e:
        logger.error(f"Ошибка в обработчике отмены: {str(e)[:100]}")
        
        # В случае ошибки все равно очищаем состояние и возвращаем в главное меню
        await state.clear()
        await message.reply(
            "❌ Произошла ошибка при отмене действия.\n"
            "Вы возвращены в главное меню.",
            reply_markup=kb.main
        )

#обработчик для групп
@router.message()
async def handle_non_private(message: Message):
    """Обработчик для сообщений не из личных чатов (должен быть ПОСЛЕ всех других хендлеров)"""
    if message.chat.type != "private":
        try:
            await message.reply(
                "⚠️ <b>Этот бот работает только в личных сообщениях!</b>\n\n"
                "Пожалуйста, напишите мне в личные сообщения: @mamoballtinder_bot",
                parse_mode="html"
            )
        except:
            pass  # Игнорируем ошибки при отправке в группах
        return

@router.callback_query()
async def handle_non_private_callback(callback: CallbackQuery):
    """Обработчик для колбэков не из личных чатов (должен быть ПОСЛЕ всех других колбэк-хендлеров)"""
    if callback.message.chat.type != "private":
        await callback.answer(
            "Этот бот работает только в личных сообщениях!",
            show_alert=True
        )
        return
    
