# settings_db.py
import os
from sqlcipher3 import dbapi2 as sqlite3
from config import SETTINGS_DB_PATH

def init_settings_db(master_password):
    """Створює або підключається до зашифрованого файлу налаштувань."""
    conn = sqlite3.connect(SETTINGS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA key = '{master_password}';")
    cursor.execute("PRAGMA cipher_compatibility = 3;")
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS registered_databases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        path TEXT NOT NULL,
        password TEXT,
        is_active INTEGER DEFAULT 1
    );
    """)
    conn.commit()
    return conn

def verify_database_password(path, password):
    """Перевіряє, чи правильний пароль до зашифрованої SQLite (SQLCipher) бази."""
    if not os.path.exists(path):
        return False, "Файл бази даних не знайдено за вказаним шляхом."
    
    try:
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA key = '{password}';")
        cursor.execute("PRAGMA cipher_compatibility = 3;")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        cursor.fetchall()
        
        conn.close()
        return True, "Успішно"
    except Exception as e:
        return False, str(e)

def get_databases_list(master_password):
    """Отримує список усіх зареєстрованих баз даних."""
    if not os.path.exists(SETTINGS_DB_PATH):
        return []
    
    conn = None
    try:
        conn = sqlite3.connect(SETTINGS_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA key = '{master_password}';")
        cursor.execute("PRAGMA cipher_compatibility = 3;")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        cursor.fetchall()
        
        cursor.execute("SELECT id, name, path, password, is_active FROM registered_databases")
        rows = cursor.fetchall()
        return rows
    except Exception as e:
        raise sqlite3.DatabaseError("Невірний пароль або пошкоджений файл налаштувань.")
    finally:
        if conn:
            conn.close()

def add_database_to_settings(master_password, name, path, password):
    """Додає або оновлює базу даних у конфігурації."""
    conn = sqlite3.connect(SETTINGS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA key = '{master_password}';")
    cursor.execute("PRAGMA cipher_compatibility = 3;")
    
    cursor.execute("""
        INSERT OR REPLACE INTO registered_databases (name, path, password, is_active)
        VALUES (?, ?, ?, 1)
    """, (name, path, password))

    conn.commit()
    conn.close()

def remove_database_from_settings(master_password, db_id):
    """Видаляє зареєстровану базу даних за її ID."""
    conn = sqlite3.connect(SETTINGS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA key = '{master_password}';")
    cursor.execute("PRAGMA cipher_compatibility = 3;")
    
    cursor.execute("DELETE FROM registered_databases WHERE id = ?", (db_id,))
    conn.commit()
    conn.close()

def update_database_password(master_password, db_id, new_password):
    conn = sqlite3.connect(SETTINGS_DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA key = '{master_password}';")
        cursor.execute("PRAGMA cipher_compatibility = 3;")

        cursor.execute(
            """
            UPDATE registered_databases
            SET password = ?
            WHERE id = ?
            """,
            (new_password, db_id),
        )

        if cursor.rowcount != 1:
            raise ValueError("Базу даних не знайдено в реєстрі.")

        conn.commit()
    finally:
        conn.close()

def change_master_password(old_password, new_password):
    """Змінює пароль шифрування бази налаштувань (Мастер-пароль)."""

    if not os.path.exists(SETTINGS_DB_PATH):
        return False, "Файл налаштувань не знайдено."

    def quote_pragma(value):
        return "'" + value.replace("'", "''") + "'"

    conn = None

    try:
        conn = sqlite3.connect(SETTINGS_DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            f"PRAGMA key = {quote_pragma(old_password)};"
        )
        cursor.execute("PRAGMA cipher_compatibility = 3;")

        # Перевіряємо старий пароль.
        cursor.execute(
            "SELECT name FROM sqlite_master LIMIT 1;"
        )
        cursor.fetchone()

        # Змінюємо ключ шифрування файлу налаштувань.
        cursor.execute(
            f"PRAGMA rekey = {quote_pragma(new_password)};"
        )

        conn.close()
        conn = None

        # Перевіряємо доступність файлу з новим паролем.
        conn = sqlite3.connect(SETTINGS_DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            f"PRAGMA key = {quote_pragma(new_password)};"
        )
        cursor.execute("PRAGMA cipher_compatibility = 3;")
        cursor.execute(
            "SELECT name FROM sqlite_master LIMIT 1;"
        )
        cursor.fetchone()

        return True, "Майстер-пароль успішно змінено."

    except Exception:
        return False, (
            "Не вдалося змінити майстер-пароль. "
            "Перевірте старий пароль і доступність файлу."
        )

    finally:
        if conn is not None:
            conn.close()


