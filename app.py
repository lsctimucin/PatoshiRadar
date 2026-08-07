import json
import time

from database import initialize_database
from cache import already_sent, mark_sent

from pump_monitor import PumpMonitor
from telegram_sender import send_message

from filters import keyword_match, creator_match
from notifier import build_message

from creator_tracker import update_creator

from chain_monitor import add_token, start as start_chain


def new_token(data):

    print(json.dumps(data, indent=2, ensure_ascii=False))

    creator = data.get("traderPublicKey", "")
    print(f"CREATOR => {creator}")

    creator_info = update_creator(creator)

    name = data.get("name", "Bilinmiyor")
    symbol = data.get("symbol", "-")
    mint = data.get("mint", "")
    market_cap = data.get("marketCapSol", 0)

    # Mint yoksa geç
    if not mint:
        return

    # Aynı mint ikinci kez gelmesin
    if already_sent(mint):
        print(f"⏩ Daha önce bildirildi: {mint}")
        return

    # Filtreler
    creator_name = creator_match(creator)
    keyword = keyword_match(name, symbol)

    # Hiç eşleşme yoksa çık
    if not creator_name and not keyword:
        return

    # Telegram mesajını oluştur
    message = build_message(
        name=name,
        symbol=symbol,
        market_cap=market_cap,
        mint=mint,
        creator=creator,
        creator_name=creator_name,
        keyword=keyword,
        creator_info=creator_info,
    )

    print(message)

    # Telegram başarılıysa
    if send_message(message):

        # Cache'e kaydet
        mark_sent(
            mint,
            name,
            symbol,
            creator
        )

        # Blockchain takibine ekle
        add_token(
            mint=mint,
            name=name,
            symbol=symbol,
            creator=creator
        )


initialize_database()

# Blockchain takip sistemi
start_chain()

print("🚀 Patoshi Radar başlatılıyor...")

monitor = PumpMonitor(new_token)

monitor.start()

try:

    while True:
        time.sleep(1)

except KeyboardInterrupt:

    print("🛑 Patoshi Radar durduruldu.")
