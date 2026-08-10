# ============================================================
# PATOSHI RADAR V5.1
# app.py - FINAL
# ============================================================

from pump_monitor import PumpMonitor
from telegram_sender import TelegramSender
from config import BOT_TOKEN, CHAT_ID

from filters import matches_keyword, matches_creator
from cache import already_sent, mark_sent
from database import initialize_database

from alchemy_activity_watch import start as alchemy_start
from alchemy_activity_watch import add_token as alchemy_add_token


# ============================================================
# TELEGRAM
# ============================================================

telegram = TelegramSender(
    BOT_TOKEN,
    CHAT_ID
)


# ============================================================
# DATABASE
# ============================================================

initialize_database()


# ============================================================
# CREATOR TRACKING
# ============================================================

try:
    from creator_tracker import creator_match
except ImportError:
    creator_match = None


# ============================================================
# TOKEN CALLBACK
# ============================================================

def new_token(data):

    try:

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

        creator = data.get(
            "traderPublicKey",
            data.get(
                "creator",
                ""
            )
        )

        market_cap = data.get(
            "marketCapSol",
            0
        )

        if not mint:
            return


        # ====================================================
        # KEYWORD CHECK
        # ====================================================

        keyword_match = False

        try:

            keyword_match = matches_keyword(
                name,
                symbol
            )

        except TypeError:

            try:
                keyword_match = matches_keyword(
                    name
                )

            except Exception:
                keyword_match = False

        except Exception as e:

            print(
                f"⚠️ Keyword filter ERROR => {e}",
                flush=True
            )


        # ====================================================
        # CREATOR CHECK
        # ====================================================

        creator_match_result = False

        if creator_match is not None:

            try:

                creator_match_result = creator_match(
                    creator
                )

            except Exception as e:

                print(
                    f"⚠️ Creator tracker ERROR => {e}",
                    flush=True
                )

        else:

            try:

                creator_match_result = matches_creator(
                    creator
                )

            except Exception:

                creator_match_result = False


        # ====================================================
        # FILTER
        # ====================================================

        if not keyword_match and not creator_match_result:

            return


        # ====================================================
        # DUPLICATE CHECK
        # ====================================================

        if already_sent(mint):

            return


        # ====================================================
        # MESSAGE
        # ====================================================

        reasons = []

        if keyword_match:
            reasons.append(
                "🔎 Keyword eşleşmesi"
            )

        if creator_match_result:
            reasons.append(
                "👤 Creator eşleşmesi"
            )

        reason_text = "\n".join(
            reasons
        )


        message = (
            "🚨 <b>PATOSHI RADAR V5.1</b>\n\n"
            f"🪙 <b>{name}</b> ({symbol})\n"
            f"💰 Market Cap: {market_cap} SOL\n\n"
            f"{reason_text}\n\n"
            f"🔗 https://pump.fun/coin/{mint}\n"
            f"📌 <code>{mint}</code>"
        )


        # ====================================================
        # TELEGRAM - FIRST ALARM
        # ====================================================

        sent = False

        try:

            sent = telegram.send_message(
                message
            )

        except TypeError:

            try:

                sent = telegram.send(
                    message
                )

            except Exception as e:

                print(
                    f"❌ Telegram ERROR => {e}",
                    flush=True
                )

        except Exception as e:

            print(
                f"❌ Telegram ERROR => {e}",
                flush=True
            )


        # ====================================================
        # TELEGRAM SUCCESS
        # ====================================================

        if not sent:

            print(
                "❌ Telegram gönderilemedi. "
                "Alchemy Activity Watch başlatılmadı.",
                flush=True
            )

            return


        print(
            "✅ V5.1 TELEGRAM ALARM GÖNDERİLDİ => "
            f"{mint}",
            flush=True
        )


        # ====================================================
        # CACHE
        # ====================================================

        try:

            mark_sent(
                mint,
                name,
                symbol,
                creator
            )

        except Exception as e:

            print(
                f"⚠️ Cache mark ERROR => {e}",
                flush=True
            )


        # ====================================================
        # ALCHEMY ACTIVITY WATCH
        # ====================================================

        try:

            alchemy_add_token(
                mint=mint,
                name=name,
                symbol=symbol,
                creator=creator
            )

            print(
                "👁️ V5.1 ALCHEMY ACTIVITY WATCH "
                f"BAŞLADI => {mint}",
                flush=True
            )

        except Exception as e:

            print(
                "❌ V5.1 ALCHEMY WATCH ERROR => "
                f"{e}",
                flush=True
            )


# ============================================================
# START
# ============================================================

def main():

    print(
        "🚀 PATOSHI RADAR V5.1 BAŞLATILIYOR...",
        flush=True
    )


    # ========================================================
    # ALCHEMY
    # ========================================================

    try:

        alchemy_start()

        print(
            "🧬 V5.1 ALCHEMY ACTIVITY WATCH "
            "BAŞLATILDI.",
            flush=True
        )

    except Exception as e:

        print(
            "❌ ALCHEMY START ERROR => "
            f"{e}",
            flush=True
        )


    # ========================================================
    # PUMP MONITOR
    # ========================================================

    print(
        "🚀 PumpPortal monitor başlatılıyor...",
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
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
