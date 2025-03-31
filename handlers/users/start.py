import asyncio
import logging
import re
from datetime import datetime, timedelta
import pytz  # O‘zbekiston vaqtini olish uchun
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from loader import dp, bot, db
from data.config import ADMINS
from data.services import SERVICES

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OrderState(StatesGroup):
    service = State()
    subject = State()
    pages = State()
    deadline = State()
    phone = State()
    confirm = State()
    edit_choice = State()

CARD_NUMBER = "9860600408900816"
ADMIN_PHONE = "+998339666999"
ADMIN_USERNAME = "FattoyevAbdufattoh"  # Yangi admin profili
ORDER_LIMIT = 5
ORDER_COOLDOWN = 24 * 60 * 60
REMINDER_DELAY = 12 * 60 * 60  # 12 soatlik eslatma

# Klaviaturalar
def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("📽 Prezentatsiya"),
        KeyboardButton("📑 Mustaqil ish"),
        KeyboardButton("📜 Referat"),
        KeyboardButton("📝 Esselar"),
        KeyboardButton("🔠 Boshqa xizmatlar"),
        KeyboardButton("📞 Admin bilan bog'lanish")
    )
    return markup

def get_step_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("🔙 Ortga"), KeyboardButton("❌ Bekor"))
    return markup

def get_phone_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("📱 Kontaktni yuborish", request_contact=True),
        KeyboardButton("➡️ O'tkazib yuborish")
    )
    markup.add(KeyboardButton("❌ Bekor"))
    return markup

def get_deadline_inline_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("⏳ Bugun", callback_data="deadline_today"),
        InlineKeyboardButton("📅 3 kun", callback_data="deadline_3days"),
        InlineKeyboardButton("📅 1 hafta", callback_data="deadline_1week"),
        InlineKeyboardButton("⌨️ Boshqa sana", callback_data="deadline_custom"),
        InlineKeyboardButton("❌ Bekor", callback_data="cancel_order")
    )
    return markup

def get_edit_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("📌 Mavzu"),
        KeyboardButton("📄 Varaq"),
        KeyboardButton("⏳ Deadline"),
        KeyboardButton("📞 Telefon"),
        KeyboardButton("❌ Bekor")
    )
    return markup

# Xabar yuborish yoki tahrirlash
async def safe_edit_or_send(chat_id, message_id, text, markup=None, parse_mode="HTML"):
    try:
        await bot.delete_message(chat_id, message_id)
    except:
        pass
    msg = await bot.send_message(chat_id, text, reply_markup=markup, parse_mode=parse_mode)
    return msg.message_id

# Eslatma yuborish funksiyasi
async def send_reminder(order_id, user_id):
    await asyncio.sleep(REMINDER_DELAY)
    order = db.get_order_by_id(order_id)
    if order and order[11] == "Jarayonda":  # Agar hali tasdiqlanmagan bo‘lsa
        await bot.send_message(
            user_id,
            f"⏳ <b>Buyurtma #{order_id} hali tasdiqlanmadi!</b>\n"
            f"ℹ️ Shoshilinch bo‘lsa, admin bilan bog‘laning: @{ADMIN_USERNAME}",
            parse_mode="HTML"
        )

# Bekor qilish
@dp.message_handler(state='*', text="❌ Bekor")
async def cancel_order(message: types.Message, state: FSMContext):
    data = await state.get_data()
    message_id = data.get('message_id')
    chat_id = message.chat.id
    text = "✅ <b>Buyurtma bekor qilindi!</b>\n🌟 <i>Quyidan xizmat tanlang:</i>"
    new_msg_id = await safe_edit_or_send(chat_id, message_id, text, get_main_menu())
    await state.finish()
    await OrderState.service.set()
    await state.update_data(message_id=new_msg_id)
    await message.delete()

# Admin paneliga kirish
@dp.message_handler(commands=['admin'], state='*')
async def admin_panel(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if user_id not in ADMINS:
        await message.answer("🚫 <b>Bu buyruq faqat adminlar uchun!</b>", parse_mode="HTML")
        return
    await state.finish()
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📋 Buyurtmalar", callback_data="view_orders"),
        InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="view_users"),
        InlineKeyboardButton("📊 Statistika", callback_data="stats"),
        InlineKeyboardButton("🕒 Tarix", callback_data="order_history"),
        InlineKeyboardButton("💰 Narxlar", callback_data="manage_prices"),
        InlineKeyboardButton("👨‍💻 Adminlar", callback_data="manage_admins")
    )
    await message.answer(
        "👨‍💻 <b>Admin Paneli</b>\n"
        "🎨 <i>Kerakli bo‘limni tanlang:</i>",
        reply_markup=markup, parse_mode="HTML"
    )
    logger.info(f"Admin {user_id} panelga kirdi.")

# Start
@dp.message_handler(commands=['start'], state='*')
async def bot_start(message: types.Message, state: FSMContext):
    await state.finish()
    user_id = message.from_user.id
    username = message.from_user.username or f"User_{user_id}"
    try:
        if not db.select_user(user_id):
            db.add_user(user_id, username)
            user_count = db.count_users()
            for admin in ADMINS:
                await bot.send_message(admin, f"🆕 <b>Yangi foydalanuvchi:</b> @{username}\n👥 <b>Jami:</b> {user_count}", parse_mode="HTML")
        db.update_last_active(user_id)
    except Exception as e:
        logger.error(f"DB error in bot_start: {e}")
        await message.answer("⚠️ <b>Serverda xatolik yuz berdi, keyinroq urinib ko‘ring!</b>", parse_mode="HTML")
        return

    text = "👋 <b>Assalomu alaykum!</b>\n🌟 <i>Buyurtma berish uchun xizmat tanlang:</i>"
    msg = await message.answer(text, reply_markup=get_main_menu(), parse_mode="HTML")
    await state.update_data(message_id=msg.message_id, chat_id=message.chat.id)
    await OrderState.service.set()

# Admin bilan bog‘lanish
@dp.message_handler(text="📞 Admin bilan bog'lanish", state='*')
async def contact_admin(message: types.Message, state: FSMContext):
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("📩 Yozish", url=f"https://t.me/{ADMIN_USERNAME}"))
    text = (
        "📞 <b>Admin bilan bog‘lanish:</b>\n"
        f"📱 <b>Telefon:</b> <code>{ADMIN_PHONE}</code>\n"
        f"💬 <b>Telegram:</b> @{ADMIN_USERNAME}"
    )
    await message.answer(text, reply_markup=markup, parse_mode="HTML")
    msg = await message.answer("🌟 <i>Xizmat tanlang:</i>", reply_markup=get_main_menu(), parse_mode="HTML")
    await state.update_data(message_id=msg.message_id)
    await OrderState.service.set()

# Boshqa xizmatlar
@dp.message_handler(text="🔠 Boshqa xizmatlar", state='*')
async def other_services(message: types.Message, state: FSMContext):
    text = "✍️ <b>Kerakli xizmat nomini yozing:</b>\n<i>Masalan: Kurs ishi, Diplom ishi</i>"
    msg = await message.answer(text, reply_markup=get_step_menu(), parse_mode="HTML")
    await state.update_data(message_id=msg.message_id, from_other_services=True)
    await OrderState.service.set()
    await message.delete()

@dp.message_handler(state=OrderState.service)
async def process_service(message: types.Message, state: FSMContext):
    data = await state.get_data()
    chat_id = message.chat.id
    message_id = data.get('message_id', None)

    if message.text == "🔙 Ortga":
        text = "🌟 <i>Buyurtma berish uchun xizmat tanlang:</i>"
        msg = await safe_edit_or_send(chat_id, message_id, text, get_main_menu())
        # Agar msg Message obyekti bo'lsa, message_id ni olish
        new_message_id = msg.message_id if hasattr(msg, 'message_id') else msg
        await state.update_data(message_id=new_message_id)
        await message.delete()
        return

    valid_services = ["📽 Prezentatsiya", "📑 Mustaqil ish", "📜 Referat", "📝 Esselar"]
    if message.text not in valid_services and not data.get('from_other_services', False):
        text = "⚠️ <b>Menyudan xizmat tanlang yoki \"🔠 Boshqa xizmatlar\"ni bosing!</b>"
        msg = await safe_edit_or_send(chat_id, message_id, text, get_main_menu())
        new_message_id = msg.message_id if hasattr(msg, 'message_id') else msg
        await state.update_data(message_id=new_message_id)
        await message.delete()
        return

    service = message.text
    price = SERVICES.get(service, {}).get('price', 5000)
    min_pages = SERVICES.get(service, {}).get('min_pages', 5)
    await state.update_data(service=service, price=price, min_pages=min_pages)
    text = (
        f"📋 <b>Buyurtma:</b>\n"
        f"🌟 Xizmat: <i>{service}</i>\n"
        f"💰 Narx: <b>{price:,}</b> so'm/varaq\n"
        f"📝 <i>Ish mavzusini yozing:</i>"
    )
    msg = await safe_edit_or_send(chat_id, message_id, text, get_step_menu())
    new_message_id = msg.message_id if hasattr(msg, 'message_id') else msg
    await state.update_data(message_id=new_message_id)
    await OrderState.subject.set()
    await message.delete()

# Mavzu kiritish
@dp.message_handler(state=OrderState.subject)
async def process_subject(message: types.Message, state: FSMContext):
    data = await state.get_data()
    chat_id = message.chat.id
    message_id = data.get('message_id')

    if message.text == "🔙 Ortga":
        text = "🌟 <i>Xizmat tanlang:</i>"
        msg = await safe_edit_or_send(chat_id, message_id, text, get_main_menu())
        await state.update_data(message_id=msg)
        await OrderState.service.set()
        await message.delete()
        return

    if len(message.text) < 5:
        text = (
            f"📋 <b>Buyurtma:</b>\n"
            f"🌟 Xizmat: <i>{data['service']}</i>\n"
            "⚠️ <b>Mavzu kamida 5 belgidan iborat bo‘lsin!</b>"
        )
        msg = await safe_edit_or_send(chat_id, message_id, text, get_step_menu())
        await state.update_data(message_id=msg)
        await message.delete()
        return

    await state.update_data(subject=message.text)
    text = (
        f"📋 <b>Buyurtma:</b>\n"
        f"🌟 Xizmat: <i>{data['service']}</i>\n"
        f"📌 Mavzu: <i>{message.text}</i>\n"
        "📄 <i>Varaq sonini kiriting:</i>"
    )
    msg = await safe_edit_or_send(chat_id, message_id, text, get_step_menu())
    await state.update_data(message_id=msg)
    await OrderState.pages.set()
    await message.delete()

# Varaq soni
@dp.message_handler(state=OrderState.pages)
async def process_pages(message: types.Message, state: FSMContext):
    data = await state.get_data()
    chat_id = message.chat.id
    message_id = data.get('message_id')

    if message.text == "🔙 Ortga":
        text = (
            f"📋 <b>Buyurtma:</b>\n"
            f"🌟 Xizmat: <i>{data['service']}</i>\n"
            "📝 <i>Mavzuni yozing:</i>"
        )
        msg = await safe_edit_or_send(chat_id, message_id, text, get_step_menu())
        await state.update_data(message_id=msg)
        await OrderState.subject.set()
        await message.delete()
        return

    if not message.text.isdigit():
        text = (
            f"📋 <b>Buyurtma:</b>\n"
            f"🌟 Xizmat: <i>{data['service']}</i>\n"
            f"📌 Mavzu: <i>{data['subject']}</i>\n"
            "⚠️ <b>Faqat raqam kiriting!</b>"
        )
        msg = await safe_edit_or_send(chat_id, message_id, text, get_step_menu())
        await state.update_data(message_id=msg)
        await message.delete()
        return

    pages = int(message.text)
    if pages < data['min_pages']:
        text = (
            f"📋 <b>Buyurtma:</b>\n"
            f"🌟 Xizmat: <i>{data['service']}</i>\n"
            f"📌 Mavzu: <i>{data['subject']}</i>\n"
            f"⚠️ <b>Minimal varaq soni {data['min_pages']} ta!</b>"
        )
        msg = await safe_edit_or_send(chat_id, message_id, text, get_step_menu())
        await state.update_data(message_id=msg)
        await message.delete()
        return

    await state.update_data(pages=pages)
    text = (
        f"📋 <b>Buyurtma:</b>\n"
        f"🌟 Xizmat: <i>{data['service']}</i>\n"
        f"📌 Mavzu: <i>{data['subject']}</i>\n"
        f"📄 Varaq: <i>{pages} ta</i>\n"
        "⏳ <i>Muddatni tanlang:</i>"
    )
    msg = await safe_edit_or_send(chat_id, message_id, text, get_deadline_inline_keyboard())
    await state.update_data(message_id=msg)
    await OrderState.deadline.set()
    await message.delete()

# Muddat tanlash (O‘zbekiston vaqti bilan va bugun uchun 2 soat qolish sharti)
@dp.callback_query_handler(lambda c: c.data.startswith('deadline_'), state=OrderState.deadline)
async def process_deadline_choice(callback_query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    chat_id = callback_query.message.chat.id
    message_id = data.get('message_id')
    uz_tz = pytz.timezone("Asia/Tashkent")  # O‘zbekiston vaqt zonasi
    today = datetime.now(uz_tz)

    if callback_query.data == "deadline_today":
        if today.hour >= 22:  # 22:00 dan keyin bugun tanlanmasin (2 soat qolish uchun)
            await callback_query.answer(
                "⚠️ Bugun uchun yetarli vaqt qolmadi!\n"
                f"📅 Boshqa kunni tanlang yoki shoshilinch bo‘lsa @{ADMIN_USERNAME} ga murojaat qiling!",
                show_alert=True
            )
            return
        deadline = today.strftime("%d.%m.%Y")
    elif callback_query.data == "deadline_3days":
        deadline = (today + timedelta(days=3)).strftime("%d.%m.%Y")
    elif callback_query.data == "deadline_1week":
        deadline = (today + timedelta(weeks=1)).strftime("%d.%m.%Y")
    elif callback_query.data == "deadline_custom":
        text = (
            f"📋 <b>Buyurtma:</b>\n"
            f"🌟 Xizmat: <i>{data['service']}</i>\n"
            f"📌 Mavzu: <i>{data['subject']}</i>\n"
            f"📄 Varaq: <i>{data['pages']} ta</i>\n"
            "📅 <i>Sanani DD.MM.YYYY formatida kiriting:</i>"
        )
        msg = await safe_edit_or_send(chat_id, message_id, text, get_step_menu())
        await state.update_data(message_id=msg)
        await callback_query.answer()
        return

    await state.update_data(deadline=deadline)
    text = (
        f"📋 <b>Buyurtma:</b>\n"
        f"🌟 Xizmat: <i>{data['service']}</i>\n"
        f"📌 Mavzu: <i>{data['subject']}</i>\n"
        f"📄 Varaq: <i>{data['pages']} ta</i>\n"
        f"⏳ Deadline: <i>{deadline}</i>\n"
        "📞 <i>Telefon raqamingiz (ixtiyoriy):</i>"
    )
    msg = await safe_edit_or_send(chat_id, message_id, text, get_phone_menu())
    await state.update_data(message_id=msg)
    await OrderState.phone.set()
    await callback_query.answer()

# Maxsus muddat
@dp.message_handler(state=OrderState.deadline)
async def process_custom_deadline(message: types.Message, state: FSMContext):
    data = await state.get_data()
    chat_id = message.chat.id
    message_id = data.get('message_id')
    uz_tz = pytz.timezone("Asia/Tashkent")
    today = datetime.now(uz_tz)

    if message.text == "🔙 Ortga":
        text = (
            f"📋 <b>Buyurtma:</b>\n"
            f"🌟 Xizmat: <i>{data['service']}</i>\n"
            f"📌 Mavzu: <i>{data['subject']}</i>\n"
            f"📄 Varaq: <i>{data['pages']} ta</i>\n"
            "⏳ <i>Muddatni tanlang:</i>"
        )
        msg = await safe_edit_or_send(chat_id, message_id, text, get_deadline_inline_keyboard())
        await state.update_data(message_id=msg)
        await message.delete()
        return

    try:
        deadline = datetime.strptime(message.text, "%d.%m.%Y").replace(tzinfo=uz_tz)
        if deadline < today:
            text = (
                f"📋 <b>Buyurtma:</b>\n"
                f"🌟 Xizmat: <i>{data['service']}</i>\n"
                f"📌 Mavzu: <i>{data['subject']}</i>\n"
                f"📄 Varaq: <i>{data['pages']} ta</i>\n"
                "⚠️ <b>Muddat o‘tmishda bo‘lmasligi kerak!</b>"
            )
            msg = await safe_edit_or_send(chat_id, message_id, text, get_deadline_inline_keyboard())
            await state.update_data(message_id=msg)
            await message.delete()
            return
        await state.update_data(deadline=deadline.strftime("%d.%m.%Y"))
        text = (
            f"📋 <b>Buyurtma:</b>\n"
            f"📦 Xizmat: <i>{data['service']}</i>\n"
            f"📌 Mavzu: <i>{data['subject']}</i>\n"
            f"📄 Varaq: <i>{data['pages']} ta</i>\n"
            f"⏳ Deadline: <i>{deadline.strftime('%d.%m.%Y')}</i>\n"
            "📞 <i>Telefon raqamingiz (ixtiyoriy):</i>"
        )
        msg = await safe_edit_or_send(chat_id, message_id, text, get_phone_menu())
        await state.update_data(message_id=msg)
        await OrderState.phone.set()
    except ValueError:
        text = (
            f"📋 <b>Buyurtma:</b>\n"
            f"🌟 Xizmat: <i>{data['service']}</i>\n"
            f"📌 Mavzu: <i>{data['subject']}</i>\n"
            f"📄 Varaq: <i>{data['pages']} ta</i>\n"
            "⚠️ <b>Noto‘g‘ri format! DD.MM.YYYY da kiriting:</b>"
        )
        msg = await safe_edit_or_send(chat_id, message_id, text, get_step_menu())
        await state.update_data(message_id=msg)
    await message.delete()

# Telefon kiritish (faqat +998 bilan boshlanadigan va 12 belgili)
@dp.message_handler(state=OrderState.phone, content_types=['contact', 'text'])
async def process_phone(message: types.Message, state: FSMContext):
    data = await state.get_data()
    chat_id = message.chat.id
    message_id = data.get('message_id')

    if message.text == "🔙 Ortga":
        text = (
            f"📋 <b>Buyurtma:</b>\n"
            f"🌟 Xizmat: <i>{data['service']}</i>\n"
            f"📌 Mavzu: <i>{data['subject']}</i>\n"
            f"📄 Varaq: <i>{data['pages']} ta</i>\n"
            "⏳ <i>Muddatni tanlang:</i>"
        )
        msg = await safe_edit_or_send(chat_id, message_id, text, get_deadline_inline_keyboard())
        await state.update_data(message_id=msg)
        await OrderState.deadline.set()
        await message.delete()
        return

    if message.contact:
        phone = message.contact.phone_number
    elif message.text == "➡️ O'tkazib yuborish":
        phone = None
    else:
        if not re.match(r'^\+998\d{9}$', message.text):  # Faqat +998 bilan boshlanadigan 12 belgili raqam
            text = (
                f"📋 <b>Buyurtma:</b>\n"
                f"🌟 Xizmat: <i>{data['service']}</i>\n"
                f"📌 Mavzu: <i>{data['subject']}</i>\n"
                f"📄 Varaq: <i>{data['pages']} ta</i>\n"
                f"⏳ Deadline: <i>{data['deadline']}</i>\n"
                "⚠️ <b>Telefon +998 bilan boshlanib, 12 belgidan iborat bo‘lsin! Masalan: +998901234567</b>"
            )
            msg = await safe_edit_or_send(chat_id, message_id, text, get_phone_menu())
            await state.update_data(message_id=msg)
            await message.delete()
            return
        phone = message.text

    await state.update_data(phone=phone)
    total_price = data['pages'] * data['price']
    text = (
        f"📋 <b>Buyurtma tasdiqlash:</b>\n"
        f"🌟 Xizmat: <i>{data['service']}</i>\n"
        f"📌 Mavzu: <i>{data['subject']}</i>\n"
        f"📄 Varaq: <i>{data['pages']} ta</i>\n"
        f"💰 Narx: <b>{data['price']:,}</b> so'm/varaq\n"
        f"💵 Jami: <b>{total_price:,}</b> so'm\n"
        f"⏳ Deadline: <i>{data['deadline']}</i>\n"
        f"📞 Telefon: <i>{phone or 'Kiritilmadi'}</i>\n"
        "✅ <i>Tasdiqlaysizmi?</i>"
    )
    markup = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm_order"),
        InlineKeyboardButton("✏️ Tahrirlash", callback_data="edit_order"),
        InlineKeyboardButton("❌ Bekor", callback_data="cancel_order")
    )
    msg = await safe_edit_or_send(chat_id, message_id, text, markup)
    await state.update_data(message_id=msg)
    await OrderState.confirm.set()
    await message.delete()

# Tasdiqlash
@dp.callback_query_handler(lambda c: c.data in ['confirm_order', 'edit_order', 'cancel_order'],
                           state=OrderState.confirm)
async def process_confirmation(callback_query: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = callback_query.from_user
    chat_id = callback_query.message.chat.id
    message_id = data.get('message_id')

    if callback_query.data == "cancel_order":
        text = "✅ <b>Buyurtma bekor qilindi!</b>\n🌟 <i>Xizmat tanlang:</i>"
        msg = await safe_edit_or_send(chat_id, message_id, text, get_main_menu())
        await state.finish()
        await state.update_data(message_id=msg)
        await OrderState.service.set()
        await callback_query.answer()
        return

    if callback_query.data == "edit_order":
        text = "✏️ <b>Qaysi qismni tahrirlamoqchisiz?</b>"
        msg = await safe_edit_or_send(chat_id, message_id, text, get_edit_keyboard())
        await state.update_data(message_id=msg)
        await OrderState.edit_choice.set()
        await callback_query.answer()
        return

    if callback_query.data == "confirm_order":
        # Vaqt zonasi bilan ishlash uchun tz o‘zgaruvchisi
        tz = pytz.timezone("Asia/Tashkent")

        # Buyurtmalarni olish va vaqtni offset-aware qilish
        recent_orders = [
            o for o in db.get_orders()
            if o[1] == user.id and (
                    tz.localize(datetime.strptime(o[12], "%Y-%m-%d %H:%M:%S")) -
                    datetime.now(tz)
            ).total_seconds() < ORDER_COOLDOWN
        ]
        if len(recent_orders) >= ORDER_LIMIT:
            await callback_query.answer("⚠️ 24 soat ichida ko‘p buyurtma berdingiz!", show_alert=True)
            return

        total_price = data['pages'] * data['price']
        order = {
            'user_id': user.id,
            'user': user.full_name,
            'username': user.username,
            'phone': data['phone'],
            'service': data['service'],
            'subject': data['subject'],
            'pages': data['pages'],
            'price': data['price'],
            'total_price': total_price,
            'deadline': data['deadline'],
            'status': 'Jarayonda'
        }
        try:
            order_id = db.add_order(order)
        except Exception as e:
            logger.error(f"DB error in add_order: {e}")
            await callback_query.message.edit_text("⚠️ <b>Serverda xatolik yuz berdi, keyinroq urinib ko‘ring!</b>",
                                                   parse_mode="HTML")
            return

        # Buyurtma tasdiqlanganligi haqida xabar
        text = (
            f"✅ <b>Buyurtmangiz qabul qilindi!</b>\n"
            f"📋 Buyurtma: <b>#{order_id}</b>\n"
            f"🌟 Xizmat: <i>{data['service']}</i>\n"
            f"📌 Mavzu: <i>{data['subject']}</i>\n"
            f"📄 Varaq: <i>{data['pages']} ta</i>\n"
            f"💵 Jami: <b>{total_price:,}</b> so'm\n"
            f"⏳ Deadline: <i>{data['deadline']}</i>\n"
            f"📞 Telefon: <i>{data['phone'] or 'Kiritilmadi'}</i>\n"
            "⏳ <i>Admin javobini kuting!</i>"
        )
        msg = await safe_edit_or_send(chat_id, message_id, text)
        await state.update_data(message_id=msg)

        # Adminlarga xabar yuborish
        for admin_id in ADMINS:
            admin_text = (
                f"🚀 <b>Yangi buyurtma!</b>\n"
                f"📋 Buyurtma: <b>#{order_id}</b>\n"
                f"👤 {user.full_name} (@{user.username or 'Noma’lum'})\n"
                f"📱 Telefon: <i>{data['phone'] or 'Kiritilmadi'}</i>\n"
                f"📦 Xizmat: <i>{data['service']}</i>\n"
                f"📌 Mavzu: <i>{data['subject']}</i>\n"
                f"📄 Varaq: <i>{data['pages']} ta</i>\n"
                f"💵 Jami: <b>{total_price:,}</b> so'm\n"
                f"⏳ Deadline: <i>{data['deadline']}</i>"
            )
            markup = InlineKeyboardMarkup(row_width=2).add(
                InlineKeyboardButton("✅ Qabul", callback_data=f"accept_{order_id}"),
                InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_{order_id}")
            )
            await bot.send_message(admin_id, admin_text, reply_markup=markup, parse_mode="HTML")

        # Eslatma vazifasini ishga tushirish
        asyncio.create_task(send_reminder(order_id, user.id))

        # State ni tozalash va yangi buyurtma uchun tayyorlash
        await state.finish()  # Oldingi holatni tozalash

        # Foydalanuvchiga yangi buyurtma uchun knopkalar bilan xabar
        start_text = "🌟 <i>Yana buyurtma berish uchun xizmat tanlang:</i>"
        msg = await bot.send_message(chat_id, start_text, reply_markup=get_main_menu(), parse_mode="HTML")
        await state.update_data(message_id=msg.message_id)  # Yangi message_id ni saqlash
        await OrderState.service.set()  # Yangi buyurtma jarayonini boshlash

        await callback_query.answer("Buyurtma tasdiqlandi! Yana buyurtma berishingiz mumkin.")

# Tahrirlash tanlovi
@dp.message_handler(state=OrderState.edit_choice)
async def process_edit_choice(message: types.Message, state: FSMContext):
    data = await state.get_data()
    chat_id = message.chat.id
    message_id = data.get('message_id')

    if message.text == "📌 Mavzu":
        text = (
            f"📋 <b>Buyurtma tahrirlash:</b>\n"
            f"🌟 Xizmat: <i>{data['service']}</i>\n"
            f"📌 Joriy mavzu: <i>{data['subject']}</i>\n"
            "📝 <i>Yangi mavzuni yozing:</i>"
        )
        msg = await safe_edit_or_send(chat_id, message_id, text, get_step_menu())
        await state.update_data(message_id=msg)
        await OrderState.subject.set()
    elif message.text == "📄 Varaq":
        text = (
            f"📋 <b>Buyurtma tahrirlash:</b>\n"
            f"🌟 Xizmat: <i>{data['service']}</i>\n"
            f"📄 Joriy varaq: <i>{data['pages']} ta</i>\n"
            "📄 <i>Yangi varaq sonini kiriting:</i>"
        )
        msg = await safe_edit_or_send(chat_id, message_id, text, get_step_menu())
        await state.update_data(message_id=msg)
        await OrderState.pages.set()
    elif message.text == "⏳ Deadline":
        text = (
            f"📋 <b>Buyurtma tahrirlash:</b>\n"
            f"🌟 Xizmat: <i>{data['service']}</i>\n"
            f"⏳ Joriy deadline: <i>{data['deadline']}</i>\n"
            "⏳ <i>Yangi muddatni tanlang:</i>"
        )
        msg = await safe_edit_or_send(chat_id, message_id, text, get_deadline_inline_keyboard())
        await state.update_data(message_id=msg)
        await OrderState.deadline.set()
    elif message.text == "📞 Telefon":
        text = (
            f"📋 <b>Buyurtma tahrirlash:</b>\n"
            f"🌟 Xizmat: <i>{data['service']}</i>\n"
            f"📞 Joriy telefon: <i>{data['phone'] or 'Kiritilmadi'}</i>\n"
            "📞 <i>Yangi telefon raqamingiz (ixtiyoriy):</i>"
        )
        msg = await safe_edit_or_send(chat_id, message_id, text, get_phone_menu())
        await state.update_data(message_id=msg)
        await OrderState.phone.set()
    else:
        text = "⚠️ <b>Noto‘g‘ri tanlov!</b>\n<i>Tugmalardan birini tanlang:</i>"
        msg = await safe_edit_or_send(chat_id, message_id, text, get_edit_keyboard())
        await state.update_data(message_id=msg)
    await message.delete()