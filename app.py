import os
from aiogram import executor
from dotenv import load_dotenv
from loader import dp, db
import middlewares, filters, handlers
from utils.notify_admins import on_startup_notify
from utils.set_bot_commands import set_default_commands

load_dotenv()

async def on_startup(dispatcher):
    await set_default_commands(dispatcher)
    try:
        db.create_tables()
    except Exception as e:
        print(f"DB xatosi: {e}")
    await on_startup_notify(dispatcher)

if __name__ == '__main__':
    executor.start_polling(dp, on_startup=on_startup, skip_updates=True)