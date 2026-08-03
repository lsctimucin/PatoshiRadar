from database import get_connection


def already_sent(mint):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT 1 FROM sent_tokens WHERE mint = ?",
        (mint,)
    )

    result = cursor.fetchone()

    conn.close()

    return result is not None


def mark_sent(mint, name, symbol, creator):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO sent_tokens
        (mint, name, symbol, creator)
        VALUES (?, ?, ?, ?)
    """, (
        mint,
        name,
        symbol,
        creator
    ))

    conn.commit()
    conn.close()
