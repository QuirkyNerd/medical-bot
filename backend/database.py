import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

# DB file will be stored in persistent volume when using Docker
DB_PATH = os.getenv("DB_PATH", "/data/database.db")

def get_db():
    """Returns a new connection to the SQLite database."""
    # Ensure the directory exists to prevent OperationalError
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    """Initializes the database schema."""
    conn = get_db()
    try:
        with conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    otp_code TEXT NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    is_used BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # ── Persistent chat history ────────────────────────────────────
            conn.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK(role IN ('user','assistant')),
                    content TEXT NOT NULL,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # ── Medication schedules ───────────────────────────────────────
            conn.execute('''
                CREATE TABLE IF NOT EXISTS medication_schedules (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    medication_name TEXT NOT NULL,
                    dosage TEXT NOT NULL,
                    time TEXT NOT NULL,
                    frequency TEXT DEFAULT 'daily',
                    notes TEXT,
                    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','done')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # ── Health Data Tables ───────────────────────────────────────
            conn.execute('''
                CREATE TABLE IF NOT EXISTS health_vitals (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    type TEXT NOT NULL,
                    value TEXT NOT NULL,
                    unit TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS health_records (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    type TEXT NOT NULL,
                    date TIMESTAMP NOT NULL,
                    provider TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS health_medicines (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    dose TEXT NOT NULL,
                    form TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS health_contacts (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    phone TEXT,
                    email TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS ehr_profiles (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS medication_logs (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    medication_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    time TEXT NOT NULL,
                    taken BOOLEAN NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

    finally:
        conn.close()

# Auto-initialize on import
init_db()

