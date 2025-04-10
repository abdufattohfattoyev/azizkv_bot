import logging
import json
import os
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, MessageEntity
from loader import dp, bot, db
from data.config import ADMINS
from data.services import SERVICES

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AdminState(StatesGroup):
    reject_reason = State()
    send_message = State()
    edit_price = State()
    add_admin = State()
    remove_admin = State()

CARD_NUMBER = "9860600408900816"
CARD_OWNER = "Azizbek Sultonov"  # Yangi karta egasi

# Adminlar ro‘yxatini JSON fayldan yuklash va saqlash
ADMINS_FILE = "admins.json"

def load_admins():
    global ADMINS
    if os.path.exists(ADMINS_FILE):
        with open(ADMINS_FILE, "r") as f:
            ADMINS = json.load(f)
    return ADMINS

def save_admins():
    with open(ADMINS_FILE, "w") as f:
        json.dump(ADMINS, f)

# Admin tekshiruvi
def is_admin(user_id):
    return str(user_id) in load_admins()

# Admin paneli
@dp.message_handler(commands=['admin'], state='*')
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("🚫 <b>Bu buyruq faqat adminlar uchun!</b>", parse_mode="HTML")
        return
    logger.info(f"Admin {message.from_user.id} panelga kirdi.")
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

# Narxlarni ko‘rish
@dp.callback_query_handler(lambda c: c.data == "manage_prices")
async def show_prices(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("🚫 Faqat adminlar uchun!", show_alert=True)
        return
    text = "💰 <b>Joriy narxlar:</b>\n"
    markup = InlineKeyboardMarkup(row_width=2)
    for service, info in SERVICES.items():
        text += f"🌟 {service}: <b>{info['price']:,}</b> so'm/varaq\n"
        markup.add(InlineKeyboardButton(f"✏️ {service}", callback_data=f"edit_price_{service}"))
    markup.add(InlineKeyboardButton("🔙 Panel", callback_data="back_to_panel"))
    await callback_query.message.edit_text(text, reply_markup=markup, parse_mode="HTML")

# Narxni tahrirlash
@dp.callback_query_handler(lambda c: c.data.startswith("edit_price_"))
async def edit_price(callback_query: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("🚫 Faqat adminlar uchun!", show_alert=True)
        return
    service = callback_query.data.replace("edit_price_", "")
    await state.update_data(service=service)
    text = (
        f"💰 <b>{service}</b>\n"
        f"📈 Joriy narx: <b>{SERVICES[service]['price']:,}</b> so'm/varaq\n"
        "✏️ <i>Yangi narxni kiriting (faqat raqam):</i>"
    )
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Narxlar", callback_data="manage_prices"))
    await callback_query.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    await AdminState.edit_price.set()

@dp.message_handler(state=AdminState.edit_price)
async def process_new_price(message: types.Message, state: FSMContext):
    data = await state.get_data()
    service = data['service']
    if not message.text.isdigit():
        await message.answer("⚠️ <b>Faqat raqam kiriting!</b>", parse_mode="HTML")
        return
    new_price = int(message.text)
    SERVICES[service]['price'] = new_price
    text = (
        f"✅ <b>{service}</b> narxi yangilandi: <b>{new_price:,}</b> so'm/varaq\n"
        "💰 <i>Boshqa narxlarni o‘zgartirish:</i>"
    )
    markup = InlineKeyboardMarkup(row_width=2)
    for s in SERVICES.keys():
        markup.add(InlineKeyboardButton(f"✏️ {s}", callback_data=f"edit_price_{s}"))
    markup.add(InlineKeyboardButton("🔙 Panel", callback_data="back_to_panel"))
    await message.answer(text, reply_markup=markup, parse_mode="HTML")
    await state.finish()
    logger.info(f"Admin {message.from_user.id} {service} narxini {new_price:,} so'm qildi.")

# Buyurtmalarni ko‘rish
@dp.callback_query_handler(lambda c: c.data == "view_orders")
async def show_orders(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("🚫 Faqat adminlar uchun!", show_alert=True)
        return
    try:
        orders = db.get_orders()
    except Exception as e:
        logger.error(f"DB error in get_orders: {e}")
        await callback_query.message.edit_text("⚠️ <b>Serverda xatolik yuz berdi!</b>", parse_mode="HTML")
        return
    if not orders:
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Panel", callback_data="back_to_panel"))
        await callback_query.message.edit_text("📭 <b>Hozircha buyurtmalar yo‘q.</b>", reply_markup=markup, parse_mode="HTML")
        return

    text = "📋 <b>Aktiv Buyurtmalar:</b>\n"
    for order in orders:
        status_emoji = "⏳" if order[11] == "Jarayonda" else "✅" if order[11] == "Qabul qilindi" else "❌" if order[11] == "Rad etildi" else "✔️"
        text += (
            f"{status_emoji} <b>#{order[0]}</b> - <i>{order[11]}</i>\n"
            f"👤 {order[2]} (@{order[3] or 'Noma’lum'})\n"
            f"📦 {order[5]}\n"
            "➖➖➖➖➖\n"
        )
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("⏳ Jarayonda", callback_data="filter_pending"),
        InlineKeyboardButton("✅ Qabul qilingan", callback_data="filter_accepted"),
        InlineKeyboardButton("❌ Rad etilgan", callback_data="filter_rejected"),
        InlineKeyboardButton("🔙 Panel", callback_data="back_to_panel")
    )
    await callback_query.message.edit_text(text, reply_markup=markup, parse_mode="HTML")

# Buyurtmalarni filtr qilish
@dp.callback_query_handler(lambda c: c.data.startswith("filter_"))
async def filter_orders(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("🚫 Faqat adminlar uchun!", show_alert=True)
        return
    filter_type = callback_query.data.split("_")[1]
    try:
        orders = db.get_orders()
    except Exception as e:
        logger.error(f"DB error in get_orders: {e}")
        await callback_query.message.edit_text("⚠️ <b>Serverda xatolik yuz berdi!</b>", parse_mode="HTML")
        return
    if filter_type == "pending":
        filtered = [o for o in orders if o[11] == "Jarayonda"]
        filter_name = "Jarayondagi"
    elif filter_type == "accepted":
        filtered = [o for o in orders if o[11] == "Qabul qilindi"]
        filter_name = "Qabul qilingan"
    elif filter_type == "rejected":
        filtered = [o for o in orders if o[11] == "Rad etildi"]
        filter_name = "Rad etilgan"
    else:
        filtered = orders
        filter_name = "Barcha"

    text = f"📋 <b>{filter_name} Buyurtmalar:</b>\n"
    for order in filtered:
        status_emoji = "⏳" if order[11] == "Jarayonda" else "✅" if order[11] == "Qabul qilindi" else "❌" if order[11] == "Rad etildi" else "✔️"
        text += (
            f"{status_emoji} <b>#{order[0]}</b> - <i>{order[11]}</i>\n"
            f"👤 {order[2]} (@{order[3] or 'Noma’lum'})\n"
            f"📦 {order[5]}\n"
            "➖➖➖➖➖\n"
        )
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Buyurtmalar", callback_data="view_orders"))
    await callback_query.message.edit_text(text or f"📭 <b>{filter_name} buyurtmalar yo‘q</b>", reply_markup=markup, parse_mode="HTML")

# Buyurtma detallari
@dp.callback_query_handler(lambda c: c.data.startswith("details_"))
async def show_order_details(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("🚫 Faqat adminlar uchun!", show_alert=True)
        return
    order_id = int(callback_query.data.split("_")[1])
    try:
        order = db.get_order_by_id(order_id)
    except Exception as e:
        logger.error(f"DB error in get_order_by_id: {e}")
        await callback_query.message.edit_text("⚠️ <b>Serverda xatolik yuz berdi!</b>", parse_mode="HTML")
        return
    if not order:
        await callback_query.answer("⚠️ Buyurtma topilmadi!", show_alert=True)
        return

    text = (
        f"📋 <b>Buyurtma #{order[0]}</b> - <i>{order[11]}</i>\n"
        f"👤 <b>Foydalanuvchi:</b> {order[2]} (@{order[3] or 'Noma’lum'})\n"
        f"🆔 <b>ID:</b> {order[1]}\n"
        f"📱 <b>Telefon:</b> {order[4] or 'Kiritilmadi'}\n"
        f"📦 <b>Xizmat:</b> {order[5]}\n"
        f"📌 <b>Mavzu:</b> {order[6]}\n"
        f"📊 <b>Varaq:</b> {order[7]} ta\n"
        f"💵 <b>Jami:</b> {order[9]:,} so'm\n"
        f"⏳ <b>Muddat:</b> {order[10]}\n"
    )
    if order[13]:
        admin_user = await bot.get_chat(order[13])
        text += f"👨‍💻 <b>Tasdiqlagan:</b> @{admin_user.username or 'Noma’lum'}"

    markup = InlineKeyboardMarkup(row_width=2)
    if order[11] == "Jarayonda":
        markup.add(
            InlineKeyboardButton("✅ Qabul", callback_data=f"accept_{order_id}"),
            InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_{order_id}"),
            InlineKeyboardButton("✔️ Bajarildi", callback_data=f"complete_{order_id}")
        )
    elif order[11] == "Qabul qilindi":
        markup.add(InlineKeyboardButton("✔️ Bajarildi", callback_data=f"complete_{order_id}"))
    markup.add(
        InlineKeyboardButton("📩 Xabar", callback_data=f"send_{order_id}"),
        InlineKeyboardButton("💬 Bog‘lanish", url=f"tg://user?id={order[1]}"),
        InlineKeyboardButton("🔙 Buyurtmalar", callback_data="view_orders")
    )
    await callback_query.message.edit_text(text, reply_markup=markup, parse_mode="HTML")

# Foydalanuvchilar soni
@dp.callback_query_handler(lambda c: c.data == "view_users")
async def show_users(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("🚫 Faqat adminlar uchun!", show_alert=True)
        return
    try:
        total_users = db.count_users()
    except Exception as e:
        logger.error(f"DB error in count_users: {e}")
        await callback_query.message.edit_text("⚠️ <b>Serverda xatolik yuz berdi!</b>", parse_mode="HTML")
        return
    text = f"👥 <b>Foydalanuvchilar soni:</b> <i>{total_users}</i>"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Panel", callback_data="back_to_panel"))
    await callback_query.message.edit_text(text, reply_markup=markup, parse_mode="HTML")

# Statistika
@dp.callback_query_handler(lambda c: c.data == "stats")
async def show_stats(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("🚫 Faqat adminlar uchun!", show_alert=True)
        return
    try:
        total_orders = len(db.get_orders())
        total_users = db.count_users()
        total_income = sum(o[9] for o in db.get_orders() if o[11] == "Qabul qilindi")
        rejected_orders = len([o for o in db.get_orders() if o[11] == "Rad etildi"])
        completed_orders = len([o for o in db.get_orders() if o[11] == "Bajarildi"])
    except Exception as e:
        logger.error(f"DB error in stats: {e}")
        await callback_query.message.edit_text("⚠️ <b>Serverda xatolik yuz berdi!</b>", parse_mode="HTML")
        return
    text = (
        f"📊 <b>Statistika:</b>\n"
        f"👥 Foydalanuvchilar: {total_users}\n"
        f"📋 Jami buyurtmalar: {total_orders}\n"
        f"✅ Qabul qilingan: {completed_orders}\n"
        f"❌ Rad etilgan: {rejected_orders}\n"
        f"💰 Jami daromad: {total_income:,} so'm"
    )
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Panel", callback_data="back_to_panel"))
    await callback_query.message.edit_text(text, reply_markup=markup, parse_mode="HTML")

# Buyurtmalar tarixi
@dp.callback_query_handler(lambda c: c.data == "order_history")
async def show_order_history(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("🚫 Faqat adminlar uchun!", show_alert=True)
        return
    try:
        orders = db.cursor.execute("SELECT * FROM Orders ORDER BY created_at DESC LIMIT 10").fetchall()
    except Exception as e:
        logger.error(f"DB error in order_history: {e}")
        await callback_query.message.edit_text("⚠️ <b>Serverda xatolik yuz berdi!</b>", parse_mode="HTML")
        return
    if not orders:
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Panel", callback_data="back_to_panel"))
        await callback_query.message.edit_text("🕒 <b>Tarixda buyurtmalar yo‘q</b>", reply_markup=markup, parse_mode="HTML")
        return

    text = "🕒 <b>Oxirgi 10 ta buyurtma:</b>\n"
    markup = InlineKeyboardMarkup(row_width=2)
    for order in orders:
        status_emoji = "⏳" if order[11] == "Jarayonda" else "✅" if order[11] == "Qabul qilindi" else "❌" if order[11] == "Rad etildi" else "✔️"
        text += (
            f"{status_emoji} <b>#{order[0]}</b> - <i>{order[11]}</i>\n"
            f"👤 {order[2]} (@{order[3] or 'Noma’lum'})\n"
            f"📦 {order[5]}\n"
            f"⏳ {order[10]}\n"
            "➖➖➖➖➖\n"
        )
        markup.add(InlineKeyboardButton(f"#{order[0]} Batafsil", callback_data=f"details_{order[0]}"))
    markup.add(InlineKeyboardButton("🔙 Panel", callback_data="back_to_panel"))
    await callback_query.message.edit_text(text, reply_markup=markup, parse_mode="HTML")

# Adminlar boshqaruvi
@dp.callback_query_handler(lambda c: c.data == "manage_admins")
async def manage_admins(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("🚫 Faqat adminlar uchun!", show_alert=True)
        return
    text = "👨‍💻 <b>Adminlar ro‘yxati:</b>\n"
    markup = InlineKeyboardMarkup(row_width=2)
    for admin_id in ADMINS:
        user = await bot.get_chat(admin_id)
        text += f"🌟 @{user.username or 'Noma’lum'} (ID: {admin_id})\n"
        markup.add(InlineKeyboardButton(f"➖ @{user.username or admin_id}", callback_data=f"remove_admin_{admin_id}"))
    markup.add(
        InlineKeyboardButton("➕ Admin qo‘shish", callback_data="add_admin"),
        InlineKeyboardButton("🔙 Panel", callback_data="back_to_panel")
    )
    await callback_query.message.edit_text(text, reply_markup=markup, parse_mode="HTML")

# Admin qo‘shish
@dp.callback_query_handler(lambda c: c.data == "add_admin")
async def add_admin_prompt(callback_query: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("🚫 Faqat adminlar uchun!", show_alert=True)
        return
    text = (
        "➕ <b>Yangi admin qo‘shish:</b>\n"
        "✏️ <i>Foydalanuvchi Telegram ID sini kiriting:</i>"
    )
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Adminlar", callback_data="manage_admins"))
    await callback_query.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    await AdminState.add_admin.set()

@dp.message_handler(state=AdminState.add_admin)
async def process_add_admin(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ <b>Faqat raqam kiriting (Telegram ID)!</b>", parse_mode="HTML")
        return
    new_admin_id = message.text
    if new_admin_id in ADMINS:
        await message.answer("⚠️ <b>Bu foydalanuvchi allaqachon admin!</b>", parse_mode="HTML")
        return
    ADMINS.append(new_admin_id)
    save_admins()
    try:
        user = await bot.get_chat(new_admin_id)
        await message.answer(f"✅ <b>@{user.username or 'Noma’lum'} admin qilib qo‘shildi!</b>", parse_mode="HTML")
    except:
        await message.answer(f"✅ <b>ID: {new_admin_id} admin qilib qo‘shildi!</b>\nℹ️ Foydalanuvchi topilmadi.", parse_mode="HTML")
    await state.finish()

# Admin o‘chirish
@dp.callback_query_handler(lambda c: c.data.startswith("remove_admin_"))
async def process_remove_admin(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("🚫 Faqat adminlar uchun!", show_alert=True)
        return
    admin_id = callback_query.data.replace("remove_admin_", "")
    if admin_id not in ADMINS:
        await callback_query.answer("⚠️ Bu ID adminlar ro‘yxatida yo‘q!", show_alert=True)
        return
    if len(ADMINS) <= 1:
        await callback_query.answer("⚠️ Oxirgi adminni o‘chirib bo‘lmaydi!", show_alert=True)
        return
    ADMINS.remove(admin_id)
    save_admins()
    try:
        user = await bot.get_chat(admin_id)
        await callback_query.message.edit_text(
            f"✅ <b>@{user.username or 'Noma’lum'} adminlikdan olindi!</b>",
            reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Adminlar", callback_data="manage_admins")),
            parse_mode="HTML"
        )
    except:
        await callback_query.message.edit_text(
            f"✅ <b>ID: {admin_id} adminlikdan olindi!</b>",
            reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Adminlar", callback_data="manage_admins")),
            parse_mode="HTML"
        )

# Admin panelga qaytish
@dp.callback_query_handler(lambda c: c.data == "back_to_panel")
async def back_to_admin_panel(callback_query: types.CallbackQuery):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("🚫 Faqat adminlar uchun!", show_alert=True)
        return
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📋 Buyurtmalar", callback_data="view_orders"),
        InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="view_users"),
        InlineKeyboardButton("📊 Statistika", callback_data="stats"),
        InlineKeyboardButton("🕒 Tarix", callback_data="order_history"),
        InlineKeyboardButton("💰 Narxlar", callback_data="manage_prices"),
        InlineKeyboardButton("👨‍💻 Adminlar", callback_data="manage_admins")
    )
    await callback_query.message.edit_text(
        "👨‍💻 <b>Admin Paneli</b>\n"
        "🎨 <i>Kerakli bo‘limni tanlang:</i>",
        reply_markup=markup, parse_mode="HTML"
    )

# Buyurtma qabul qilish, rad etish, yakunlash
@dp.callback_query_handler(lambda c: c.data.startswith(('accept_', 'reject_', 'complete_', 'send_')))
async def process_admin_response(callback_query: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback_query.from_user.id):
        await callback_query.answer("🚫 Faqat adminlar uchun!", show_alert=True)
        return
    action, order_id = callback_query.data.split('_', 1)
    order_id = int(order_id)
    try:
        order = db.get_order_by_id(order_id)
    except Exception as e:
        logger.error(f"DB error in get_order_by_id: {e}")
        await callback_query.message.edit_text("⚠️ <b>Serverda xatolik yuz berdi!</b>", parse_mode="HTML")
        return
    if not order:
        await callback_query.answer("⚠️ Buyurtma topilmadi!", show_alert=True)
        return

    admin_chat_id = callback_query.message.chat.id
    admin_message_id = callback_query.message.message_id  # Har doim mavjud
    user_chat_id = order[1]
    HALF_PAYMENT = order[9] // 2

    if action == "accept":
        if order[11] != "Jarayonda":
            await callback_query.answer("⚠️ Bu buyurtma allaqachon tasdiqlangan yoki rad etilgan!", show_alert=True)
            return
        try:
            db.update_order_status(order_id, "Qabul qilindi", confirmed_by_admin_id=callback_query.from_user.id)
        except Exception as e:
            logger.error(f"DB error in update_order_status: {e}")
            await callback_query.message.edit_text("⚠️ <b>Serverda xatolik yuz berdi!</b>", parse_mode="HTML")
            return
        admin_text = (
            f"✅ <b>Buyurtma #{order_id} qabul qilindi!</b>\n"
            "────────────────────\n"
            f"👤 Mijoz: {order[2]} (@{order[3] or 'Noma’lum'})\n"
            f"📦 Xizmat: {order[5]}\n"
            f"💵 Jami: {order[9]:,} so'm\n"
            f"👨‍💻 Tasdiqlagan: @{callback_query.from_user.username or 'Admin'}"
        )
        user_text = (
            f"🎉 <b>Buyurtma #{order_id} qabul qilindi!</b>\n"
            "────────────────────\n"
            f"📋 Xizmat: <i>{order[5]}</i>\n"
            f"📌 Mavzu: <i>{order[6]}</i>\n"
            f"📄 Varaq: <i>{order[7]} ta</i>\n"
            f"💵 Jami: <b>{order[9]:,} so'm</b>\n"
            f"💳 50% avans: <b>{HALF_PAYMENT:,} so'm</b>\n"
            f"🔹 Karta: <code>{CARD_NUMBER}</code>\n"
            f"👤 Egasi: <i>{CARD_OWNER}</i>\n"
            f"👨‍💻 Admin: @{callback_query.from_user.username or 'FattoyevAbdufattoh'}\n"
            "────────────────────\n"
            "ℹ️ <i>50% to‘lovni amalga oshirib, skrinshotni admin ga yuboring. To‘lov tasdiqlangach ish boshlanadi!</i>"
        )
        entities = [MessageEntity(type="code", offset=user_text.find(CARD_NUMBER), length=len(CARD_NUMBER))]
        for admin_id in ADMINS:
            if str(admin_id) != str(callback_query.from_user.id):
                try:
                    await bot.send_message(
                        admin_id,
                        f"ℹ️ <b>Buyurtma #{order_id} qabul qilindi!</b>\n"
                        f"👨‍💻 Tasdiqlagan: @{callback_query.from_user.username or 'Admin'}",
                        parse_mode="HTML"
                    )
                except:
                    logger.error(f"Admin {admin_id} ga xabar yuborib bo‘lmadi.")

    elif action == "complete":
        if order[11] != "Qabul qilindi" or str(order[13]) != str(callback_query.from_user.id):
            await callback_query.answer("⚠️ Bu buyurtmani faqat tasdiqlagan admin yakunlay oladi!", show_alert=True)
            return
        try:
            db.update_order_status(order_id, "Bajarildi")
        except Exception as e:
            logger.error(f"DB error in update_order_status: {e}")
            await callback_query.message.edit_text("⚠️ <b>Serverda xatolik yuz berdi!</b>", parse_mode="HTML")
            return
        admin_text = (
            f"✔️ <b>Buyurtma #{order_id} bajarildi!</b>\n"
            "────────────────────\n"
            f"👤 Mijoz: {order[2]} (@{order[3] or 'Noma’lum'})\n"
            f"📦 Xizmat: {order[5]}\n"
            f"💵 Jami: {order[9]:,} so'm"
        )
        user_text = (
            f"✔️ <b>Buyurtma #{order_id} tayyor!</b>\n"
            "────────────────────\n"
            f"📋 Xizmat: <i>{order[5]}</i>\n"
            f"💵 Jami: <b>{order[9]:,} so'm</b>\n"
            "────────────────────\n"
            f"📥 <i>Faylni olish uchun @{callback_query.from_user.username or 'FattoyevAbdufattoh'} bilan bog‘laning.</i>"
        )
        entities = None
    elif action == "reject":
        if order[11] != "Jarayonda":
            await callback_query.answer("⚠️ Bu buyurtma allaqachon tasdiqlangan yoki rad etilgan!", show_alert=True)
            return
        await state.update_data(order_id=order_id, admin_message_id=admin_message_id)
        await callback_query.message.edit_text(
            f"❌ <b>Buyurtma #{order_id} rad etilmoqda</b>\n"
            "📝 <i>Rad etish sababini kiriting:</i>",
            parse_mode="HTML"
        )
        await AdminState.reject_reason.set()
        return
    elif action == "send":
        await state.update_data(order_id=order_id, user_chat_id=user_chat_id, admin_message_id=admin_message_id)
        await callback_query.message.edit_text(
            f"📩 <b>Mijozga xabar:</b> #{order_id}\n"
            "✍️ <i>Xabar matnini kiriting:</i>",
            parse_mode="HTML"
        )
        await AdminState.send_message.set()
        return

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("📩 Xabar", callback_data=f"send_{order_id}"),
        InlineKeyboardButton("💬 Bog‘lanish", url=f"tg://user?id={user_chat_id}"),
        InlineKeyboardButton("🔙 Buyurtmalar", callback_data="view_orders")
    )
    await bot.edit_message_text(admin_text, admin_chat_id, admin_message_id, reply_markup=markup, parse_mode="HTML")
    await bot.send_message(user_chat_id, user_text, parse_mode="HTML", entities=entities)
    await callback_query.answer()

# Rad etish sababi
@dp.message_handler(state=AdminState.reject_reason)
async def process_reject_reason(message: types.Message, state: FSMContext):
    data = await state.get_data()
    order_id = data['order_id']
    try:
        order = db.get_order_by_id(order_id)
        db.update_order_status(order_id, "Rad etildi")
    except Exception as e:
        logger.error(f"DB error in reject_reason: {e}")
        await message.answer("⚠️ <b>Serverda xatolik yuz berdi!</b>", parse_mode="HTML")
        return
    reason = message.text
    admin_text = (
        f"❌ <b>Buyurtma #{order_id} rad etildi</b>\n"
        "────────────────────\n"
        f"👤 Mijoz: {order[2]}\n"
        f"📋 Sabab: <i>{reason}</i>"
    )
    user_text = (
        f"❌ <b>Buyurtma #{order_id} rad etildi</b>\n"
        "────────────────────\n"
        f"📋 Sabab: <i>{reason}</i>\n"
        "────────────────────\n"
        "ℹ️ <i>Savollar uchun:</i> @FattoyevAbdufattoh"
    )
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Buyurtmalar", callback_data="view_orders"))
    await bot.edit_message_text(admin_text, message.chat.id, data['admin_message_id'], reply_markup=markup, parse_mode="HTML")
    await bot.send_message(order[1], user_text, parse_mode="HTML")
    await state.finish()


# Mijozga xabar yuborish
@dp.message_handler(state=AdminState.send_message)
async def process_send_message(message: types.Message, state: FSMContext):
    data = await state.get_data()
    order_id = data['order_id']
    user_chat_id = data['user_chat_id']

    # Foydalanuvchiga yuboriladigan xabar
    user_text = (
        f"📩 <b>Buyurtma #{order_id} bo‘yicha xabar:</b>\n"
        "────────────────────\n"
        f"✍️ <i>{message.text}</i>\n"
        "────────────────────\n"
        "ℹ️ <i>Javob uchun:</i> @FattoyevAbdufattoh"
    )

    # Adminga yangilanadigan xabar
    admin_text = (
        f"✅ <b>Xabar yuborildi:</b> #{order_id}\n"
        f"📝 <i>{message.text}</i>"
    )

    # Adminga tasdiq xabari
    confirmation_text = (
        f"✅ <b>Xabar muvaffaqiyatli yuborildi!</b>\n"
        f"📋 Buyurtma: #{order_id}\n"
        f"👤 Foydalanuvchi: {user_chat_id}"
    )

    # Foydalanuvchiga xabar yuborish
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🔙 Buyurtmalar", callback_data="view_orders"))
    await bot.send_message(user_chat_id, user_text, parse_mode="HTML")

    # Adminga joriy xabarni yangilash yoki yangi xabar yuborish
    if 'admin_message_id' in data:
        await bot.edit_message_text(admin_text, message.chat.id, data['admin_message_id'], reply_markup=markup,
                                    parse_mode="HTML")
    else:
        await bot.send_message(message.chat.id, admin_text, reply_markup=markup, parse_mode="HTML")

    # Adminga qo‘shimcha tasdiq xabari yuborish
    await bot.send_message(message.chat.id, confirmation_text, parse_mode="HTML")

    await state.finish()