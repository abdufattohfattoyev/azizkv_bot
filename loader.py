from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from dotenv import load_dotenv
import os
from data import config
from utils.db_api.database import Database

# .env faylidan tokenni olish
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN") or config.BOT_TOKEN

# Bot va Dispatcher
bot = Bot(token=BOT_TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Ma’lumotlar bazasi (Users va Orders uchun yagona)
db = Database(db_name="data/main.db")
user_db = db  # user_db sifatida ham ishlatiladi (compatability uchun)