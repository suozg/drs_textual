import os
from sqlcipher3 import dbapi2 as sqlite3 
import config
from settings_db import get_databases_list

def init_db_schema(conn):
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE NOT NULL,
            year INTEGER,
            month INTEGER,
            day INTEGER,
            content TEXT,
            document_number TEXT,
            created_at TEXT,
            content_hash TEXT
        );
    """)

    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts
        USING fts3(
            filename,
            content,
            tokenize=unicode61
        );
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS documents_ai
        AFTER INSERT ON documents
        BEGIN
            INSERT INTO documents_fts(docid, filename, content)
            VALUES (new.id, new.filename, new.content);
        END;
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS documents_ad
        AFTER DELETE ON documents
        BEGIN
            DELETE FROM documents_fts
            WHERE docid = old.id;
        END;
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS documents_au
        AFTER UPDATE ON documents
        BEGIN
            UPDATE documents_fts
            SET filename = new.filename,
                content = new.content
            WHERE docid = old.id;
        END;
    """)

    conn.commit()

def check_patch_db():
    """Перевіряє, чи існує файл поточної бази даних."""
    return os.path.exists(config.db_path)

def create_new_database(db_path, password):
    """Створює нову зашифровану базу даних за вказаним шляхом та ініціалізує її схему."""
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA key = '{password}';")
    cursor.execute("PRAGMA cipher_compatibility = 3;")
    cursor.execute("PRAGMA journal_mode=DELETE;")

    init_db_schema(conn)
    conn.close()

def connect_to_specific_database(db_path, db_password):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA key = '{db_password}';")
        cursor.execute("PRAGMA cipher_compatibility = 3;")
        cursor.execute("PRAGMA temp_store = MEMORY;")
        return conn
    except Exception:
        return None

def connect_to_database(db_password, allow_create=False):
    if not os.path.exists(config.db_path) and not allow_create:
        return None
    try:
        conn = sqlite3.connect(config.db_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA key = '{db_password}';")
        cursor.execute("PRAGMA cipher_compatibility = 3;")
        cursor.execute("PRAGMA journal_mode=DELETE;")
        
        init_db_schema(conn)
        return conn
    except Exception:
        return None

def populate_databases_choice():
    choices = []
    if hasattr(config, 'master_password') and config.master_password:
        databases = get_databases_list(config.master_password)
        for row in databases:
            db_id, db_name, db_path, db_password, is_active = row
            if is_active:
                choices.append((f"{db_name} ({db_path})", (db_path, db_password)))
    return choices
