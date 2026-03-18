import asyncio
import datetime
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest
from dotenv import load_dotenv
import re
# Импорт модулей
from mamohandlersAmvera import router, public_router, setup_scheduler
from mamoadmins import router_admins, public_router_admins
from mamodatabases import load_players_catalog
from mamofkarta import public_router_fkarta, router_fkarta
from mamopvp import (
    public_router_pvp, 
    start_pvp_cleanup_scheduler, 
    cleanup_old_confirmations, 
    periodic_confirmation_cleanup
)

# Загрузка токена
load_dotenv("token.env")
TOKEN = os.getenv("TOKEN")



async def cleanup_confirmation_background(bot: Bot):
    """Фоновая задача для очистки сообщений подтверждения"""
    while True:
        await asyncio.sleep(60)  # Каждую минуту
        try:
            # Здесь можно реализовать дополнительную логику очистки
            pass
        except Exception as e:
            print(f"Ошибка при очистке подтверждений: {e}")

async def main():
    """Основная функция запуска бота"""
    try:
        # Проверка токена
        if not TOKEN:
            print("Ошибка: Токен не найден!")
            return
        
        # 1. Загружаем каталог игроков
        load_players_catalog()
        
        # 2. Инициализируем бота и диспетчер
        bot = Bot(token=TOKEN)
        storage = MemoryStorage()
        dp = Dispatcher(storage=storage, ignore_old_callback_queries=True)
        
        # 3. Настраиваем порядок обработчиков
        # Сначала регистрируем глобальный обработчик для непубличных команд

        
        # 4. Подключаем все роутеры в правильном порядке
        # Сначала публичные команды
        dp.include_router(public_router_admins)
        dp.include_router(public_router)          # Здесь должен быть public_router из mamohandlersAmvera
        dp.include_router(public_router_pvp)
        dp.include_router(public_router_fkarta)   # Или здесь, если команда в mamofkarta

        # Затем приватные команды
        dp.include_router(router_fkarta)
        dp.include_router(router_admins)
        dp.include_router(router)
        # 5. Настраиваем и запускаем планировщик
        scheduler = setup_scheduler(bot)
        scheduler.start()
        
        # 6. Запускаем фоновые задачи очистки PvP
        asyncio.create_task(start_pvp_cleanup_scheduler())
        asyncio.create_task(cleanup_old_confirmations())
        asyncio.create_task(periodic_confirmation_cleanup(bot))
        
        # 7. Запускаем фоновую задачу очистки подтверждений
        asyncio.create_task(cleanup_confirmation_background(bot))
        
        # 8. Запускаем бота
        print("Бот запускается...")
        await dp.start_polling(bot)
        
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            # Игнорируем ошибку "message is not modified"
            print("Возникла ошибка 'message is not modified' - игнорируем")
        else:
            raise
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        raise

if __name__ == "__main__":
    """Точка входа в программу"""
    try: 
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nОстановка бота.")
        now = datetime.datetime.now()
        print(f"Бот выключен в {now}")
    except Exception as e:
        print(f"Ошибка при запуске бота: {e}")