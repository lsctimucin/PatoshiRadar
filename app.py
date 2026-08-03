from database import initialize_database
from cache import already_sent, mark_sent
import json

from pump_monitor import PumpMonitor
from telegram_sender import send_message

from filters import keyword_match, creator_match
from notifier import build_message


def new_token(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))

    creator = data.get("traderPublicKey", "")
    print(f"CREATOR => {creator}")

    name = data.get("name", "Bilinmiyor")
    symbol = data.get("symbol", "-")
    mint = data.get("mint", "")
    market_cap = data.get("marketCapSol", 0)

    # 1. Creator kontrolü
    if creator_match(creator):
        message = build_message(
            name=name,
            symbol=symbol,
            market_cap=market_cap,
            mint=mint,
            creator=creator,
            reason="🎯 Creator Match"
        )

        print(message)
        send_message(message)
        return

    # 2. Keyword kontrolü
    if keyword_match(name, symbol):
        message = build_message(
            name=name,
            symbol=symbol,
            market_cap=market_cap,
            mint=mint,
            creator=creator,
            reason="🔍 Keyword Match"
        )

        print(message)
        send_message(message)


initialize_database()

monitor = PumpMonitor(new_token)

print("🚀 Patoshi Radar başlatılıyor...")

monitor.start()

while True:
    pass
