import sqlite3

DB_NAME = "patoshi.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sent_tokens (
            mint TEXT PRIMARY KEY,
            name TEXT,
            symbol TEXT,
            creator TEXT,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
