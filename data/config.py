from environs import Env

# environs kutubxonasidan foydalanish
env = Env()
env.read_env()

# .env fayl ichidan o‘qiymiz
BOT_TOKEN = env.str("BOT_TOKEN")  # Bot token
IP = env.str("ip", "localhost")   # Xosting IP manzili, standart qiymat qo‘shildi

# Adminlarni statik ro‘yxat sifatida aniqlaymiz (test uchun)
ADMINS = ["37054118","973358587"]  # Sizning ID’ingizni qo‘lda kiritamiz

# Agar .env dan o‘qimoqchi bo‘lsangiz, quyidagini faollashtiring:
# ADMINS = env.list("ADMINS", default=["37054118"])