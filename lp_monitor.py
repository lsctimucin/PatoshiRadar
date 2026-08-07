import threading
import time

from solana_rpc import check_lp
from telegram_sender import send_message

watch_list = {}


def add_token(mint):
    if mint not in watch_list:
        watch_list[mint] = {
            "found": False,
            "added": time.time()
        }
        print(f"👀 LP takibine eklendi: {mint}")


def worker():

    while True:

        try:

            for mint in list(watch_list.keys()):

                lp = check_lp(mint)

                if not lp:
                    continue

                print(f"🟢 LP bulundu: {mint}")

                send_message(
                    f"""🟢 <b>LP OLUŞTU</b>

━━━━━━━━━━━━━━

🪙 <b>Mint</b>

<code>{mint}</code>

━━━━━━━━━━━━━━

✅ İlk likidite havuzu tespit edildi.

🚀 Patoshi Radar LP Monitor
"""
                )

                # Artık takip etmeye gerek yok
                del watch_list[mint]

            time.sleep(3)

        except Exception as e:

            print("❌ LP Monitor Hatası")
            print(e)

            time.sleep(5)


def start():

    print("🟢 LP Monitor başlatıldı.")

    threading.Thread(
        target=worker,
        daemon=True
    ).start()
