import sqlite3
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_name="data/main.db"):
        """Ma'lumotlar bazasiga ulanish"""
        self.db_name = db_name  # Fayl nomini saqlash
        try:
            self.conn = sqlite3.connect(db_name, check_same_thread=False)
            self.cursor = self.conn.cursor()
            self.create_tables()
        except sqlite3.Error as e:
            logger.error(f"Ma'lumotlar bazasiga ulanishda xato: {e}")
            raise

    def create_tables(self):
        """Foydalanuvchilar va buyurtmalar jadvallarini yaratish"""
        try:
            # Users jadvali
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS Users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id BIGINT NOT NULL UNIQUE,
                    username VARCHAR(255) NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_active DATETIME NULL
                )
            ''')
            # Orders jadvali
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS Orders (
                    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id BIGINT,
                    user TEXT,
                    username TEXT,
                    phone TEXT,
                    service TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    pages INTEGER NOT NULL,
                    price INTEGER NOT NULL,
                    total_price INTEGER NOT NULL,
                    deadline TEXT NOT NULL,
                    status TEXT DEFAULT 'Jarayonda',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    confirmed_by_admin_id BIGINT,
                    FOREIGN KEY (user_id) REFERENCES Users(telegram_id)
                )
            ''')
            self.conn.commit()
            logger.info("Jadvallar muvaffaqiyatli yaratildi yoki mavjud edi.")
        except sqlite3.Error as e:
            logger.error(f"Jadvallarni yaratishda xato: {e}")
            raise  # Xatolikni yuqori darajaga qaytarish

    def add_user(self, telegram_id, username):
        """Yangi foydalanuvchi qo‘shish"""
        try:
            self.cursor.execute(
                'INSERT OR IGNORE INTO Users (telegram_id, username) VALUES (?, ?)',
                (telegram_id, username)
            )
            self.conn.commit()
            logger.info(f"Foydalanuvchi qo‘shildi: {telegram_id} - @{username}")
            return True
        except sqlite3.Error as e:
            logger.error(f"Foydalanuvchi qo‘shishda xato: {e}")
            return False

    def update_last_active(self, telegram_id):
        """Oxirgi faol vaqtni yangilash"""
        try:
            self.cursor.execute(
                'UPDATE Users SET last_active = ? WHERE telegram_id = ?',
                (datetime.now(), telegram_id)
            )
            self.conn.commit()
            if self.cursor.rowcount > 0:
                logger.info(f"Foydalanuvchi {telegram_id} uchun last_active yangilandi.")
            return self.cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Oxirgi faol vaqtni yangilashda xato: {e}")
            return False

    def select_user(self, telegram_id):
        """Foydalanuvchi ma'lumotlarini olish"""
        try:
            self.cursor.execute('SELECT * FROM Users WHERE telegram_id = ?', (telegram_id,))
            user = self.cursor.fetchone()
            return user
        except sqlite3.Error as e:
            logger.error(f"Foydalanuvchi tanlashda xato: {e}")
            return None

    def count_users(self):
        """Foydalanuvchilar sonini hisoblash"""
        try:
            self.cursor.execute('SELECT COUNT(*) FROM Users')
            count = self.cursor.fetchone()[0]
            return count if count is not None else 0
        except sqlite3.Error as e:
            logger.error(f"Foydalanuvchilar sonini olishda xato: {e}")
            return 0

    def add_order(self, order):
        """Yangi buyurtma qo‘shish"""
        try:
            self.cursor.execute('''
                INSERT INTO Orders (user_id, user, username, phone, service, subject, pages, price, total_price, deadline, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                order['user_id'], order['user'], order['username'], order['phone'],
                order['service'], order['subject'], order['pages'], order['price'],
                order['total_price'], order['deadline'], order['status']
            ))
            self.conn.commit()
            order_id = self.cursor.lastrowid
            logger.info(f"Yangi buyurtma qo‘shildi: #{order_id}")
            return order_id
        except sqlite3.Error as e:
            logger.error(f"Buyurtma qo‘shishda xato: {e}")
            self.conn.rollback()  # Xato bo‘lsa tranzaksiyani bekor qilish
            return None

    def get_orders(self, status=None):
        """Barcha yoki ma'lum holatdagi buyurtmalarni olish"""
        try:
            if status:
                self.cursor.execute('SELECT * FROM Orders WHERE status = ?', (status,))
            else:
                self.cursor.execute('SELECT * FROM Orders')
            orders = self.cursor.fetchall()
            return orders if orders else []
        except sqlite3.Error as e:
            logger.error(f"Buyurtmalarni olishda xato: {e}")
            return []

    def update_order_status(self, order_id, status, confirmed_by_admin_id=None):
        """Buyurtma holatini yangilash"""
        try:
            if confirmed_by_admin_id:
                self.cursor.execute(
                    'UPDATE Orders SET status = ?, confirmed_by_admin_id = ? WHERE order_id = ?',
                    (status, confirmed_by_admin_id, order_id)
                )
            else:
                self.cursor.execute(
                    'UPDATE Orders SET status = ? WHERE order_id = ?',
                    (status, order_id)
                )
            self.conn.commit()
            if self.cursor.rowcount > 0:
                logger.info(f"Buyurtma #{order_id} holati yangilandi: {status}")
            return self.cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Buyurtma holatini yangilashda xato: {e}")
            self.conn.rollback()
            return False

    def delete_order(self, order_id):
        """Buyurtmani o‘chirish"""
        try:
            self.cursor.execute('DELETE FROM Orders WHERE order_id = ?', (order_id,))
            self.conn.commit()
            if self.cursor.rowcount > 0:
                logger.info(f"Buyurtma #{order_id} o‘chirildi")
            return self.cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Buyurtma o‘chirishda xato: {e}")
            self.conn.rollback()
            return False

    def get_order_by_id(self, order_id):
        """Buyurtmani ID bo‘yicha olish"""
        try:
            self.cursor.execute('SELECT * FROM Orders WHERE order_id = ?', (order_id,))
            order = self.cursor.fetchone()
            return order
        except sqlite3.Error as e:
            logger.error(f"Buyurtma #{order_id} ni olishda xato: {e}")
            return None

    def get_latest_confirmed_order_by_user(self, user_id):
        """Oxirgi tasdiqlangan buyurtmani olish"""
        try:
            self.cursor.execute('''
                SELECT * FROM Orders 
                WHERE user_id = ? AND status = 'Qabul qilindi' 
                ORDER BY created_at DESC 
                LIMIT 1
            ''', (user_id,))
            order = self.cursor.fetchone()
            return order
        except sqlite3.Error as e:
            logger.error(f"Foydalanuvchi {user_id} uchun tasdiqlangan buyurtmani olishda xato: {e}")
            return None

    def close(self):
        """Ma'lumotlar bazasini yopish"""
        try:
            if self.conn:
                self.conn.close()
                logger.info("Ma'lumotlar bazasi yopildi.")
        except sqlite3.Error as e:
            logger.error(f"Ma'lumotlar bazasini yopishda xato: {e}")

    def __enter__(self):
        """Context manager bilan ishlatish uchun"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager yopilishi"""
        self.close()
        if exc_type is not None:
            logger.error(f"Kontekst ichida xato: {exc_type}, {exc_val}")
            return False
        return True

# Singleton obyekt yaratish
db = Database()