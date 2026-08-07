import json

from database import initialize_database
from cache import already_sent, mark_sent

from pump_monitor import PumpMonitor
from telegram_sender import send_message

from filters import keyword_match, creator_match
from notifier import build_message

from creator_tracker import update_creator
from lp_monitor import add_token, start as start_lp


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

    # Mesaj oluştur
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

    # Telegram başarılıysa kaydet
    if send_message(message):

        mark_sent(
            mint,
            name,
            symbol,
            creator
        )

        # LP takibine ekle
        add_token(mint)


initialize_database()

# LP Monitor başlat
start_lp()

print("🚀 Patoshi Radar başlatılıyor...")

monitor = PumpMonitor(new_token)

monitor.start()

while True:
    pass
