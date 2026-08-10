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


# ============================================================
# ALCHEMY V5.1
# ============================================================

try:
    from alchemy_activity_watch import (
        start as start_alchemy,
        add_token as add_alchemy_token
    )

    ALCHEMY_AVAILABLE = True

    print(
        "🧬 V5.1 ALCHEMY MODULE YÜKLENDİ.",
        flush=True
    )

except Exception as e:

    ALCHEMY_AVAILABLE = False

    start_alchemy = None
    add_alchemy_token = None

    print(
        "⚠️ V5.1 ALCHEMY MODULE YÜKLENEMEDİ => "
        f"{e}",
        flush=True
    )


# ============================================================
# TOKEN CALLBACK
# ============================================================

def new_token(data):

    print(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False
        ),
        flush=True
    )

    creator = data.get(
        "traderPublicKey",
        ""
    )

    print(
        f"CREATOR => {creator}",
        flush=True
    )


    # ========================================================
    # CREATOR
    # ========================================================

    creator_info = update_creator(
        creator
    )


    # ========================================================
    # TOKEN DATA
    # ========================================================

    name = data.get(
        "name",
        "Bilinmiyor"
    )

    symbol = data.get(
        "symbol",
        "-"
    )

    mint = data.get(
        "mint",
        ""
    )

    market_cap = data.get(
        "marketCapSol",
        0
    )


    # ========================================================
    # MINT KONTROL
    # ========================================================

    if not mint:

        return


    # ========================================================
    # DUPLICATE
    # ========================================================

    if already_sent(mint):

        print(
            f"⏩ Daha önce bildirildi: {mint}",
            flush=True
        )

        return


    # ========================================================
    # FILTERS
    # ========================================================

    creator_name = creator_match(
        creator
    )

    keyword = keyword_match(
        name,
        symbol
    )


    # ========================================================
    # NO MATCH
    # ========================================================

    if not creator_name and not keyword:

        return


    # ========================================================
    # TELEGRAM MESSAGE
    # ========================================================

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


    print(
        message,
        flush=True
    )


    # ========================================================
    # TELEGRAM FIRST
    # ========================================================

    telegram_ok = send_message(
        message
    )


    if not telegram_ok:

        print(
            "❌ Telegram gönderilemedi."
            " Activity Watch başlatılmadı.",
            flush=True
        )

        return


    print(
        "✅ V5.1 TELEGRAM ALARMI GÖNDERİLDİ => "
        f"{mint}",
        flush=True
    )


    # ========================================================
    # CACHE
    # ========================================================

    mark_sent(
        mint,
        name,
        symbol,
        creator
    )


    # ========================================================
    # HELIUS / CHAIN MONITOR
    # ========================================================

    try:

        add_token(
            mint=mint,
            name=name,
            symbol=symbol,
            creator=creator
        )

        print(
            "👀 V5.1 CHAIN WATCH ADD_TOKEN => "
            f"{mint}",
            flush=True
        )

    except Exception as e:

        print(
            "⚠️ V5.1 CHAIN MONITOR ADD_TOKEN ERROR => "
            f"{e}",
            flush=True
        )


    # ========================================================
    # ALCHEMY ACTIVITY WATCH
    # ========================================================

    if ALCHEMY_AVAILABLE:

        try:

            result = add_alchemy_token(
                mint=mint,
                name=name,
                symbol=symbol,
                creator=creator
            )

            print(
                "👁️ V5.1 ALCHEMY ACTIVITY WATCH "
                f"ADD_TOKEN => {mint} | result={result}",
                flush=True
            )

        except Exception as e:

            print(
                "⚠️ V5.1 ALCHEMY ADD_TOKEN ERROR => "
                f"{e}",
                flush=True
            )

    else:

        print(
            "⚠️ V5.1 ALCHEMY AKTİF DEĞİL.",
            flush=True
        )


# ============================================================
# DATABASE
# ============================================================

initialize_database()


# ============================================================
# CHAIN MONITOR
# ============================================================

print(
    "🧬 V5.1 CHAIN MONITOR BAŞLATILIYOR...",
    flush=True
)

start_chain()


# ============================================================
# ALCHEMY
# ============================================================

if ALCHEMY_AVAILABLE:

    try:

        print(
            "🧬 V5.1 ALCHEMY ACTIVITY WATCH "
            "BAŞLATILIYOR...",
            flush=True
        )

        start_alchemy()

        print(
            "✅ V5.1 ALCHEMY ACTIVITY WATCH AKTİF",
            flush=True
        )

    except Exception as e:

        print(
            "❌ V5.1 ALCHEMY START ERROR => "
            f"{e}",
            flush=True
        )

else:

    print(
        "⚠️ V5.1 ALCHEMY MODULE YOK / YÜKLENEMEDİ.",
        flush=True
    )


# ============================================================
# PATOSHI RADAR
# ============================================================

print(
    "🚀 Patoshi Radar başlatılıyor...",
    flush=True
)


monitor = PumpMonitor(
    new_token
)


print(
    "🟢 PATOSHI RADAR V5.1 AKTİF",
    flush=True
)


monitor.start()


# ============================================================
# KEEP ALIVE
# ============================================================

try:

    while True:

        time.sleep(1)

except KeyboardInterrupt:

    print(
        "🛑 Patoshi Radar durduruldu.",
        flush=True
    )
