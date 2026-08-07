import threading
import time

from solana_rpc import check_lp
from telegram_sender import send_message

watch_list = {}


def add_token(mint):
    if mint not in watch_list:
        watch_list[mint] = False


def worker():

    while True:

        try:

            for mint in list(watch_list.keys()):

                # Daha önce bulunduysa tekrar kontrol etme
                if watch_list[mint]:
                    continue

                lp = check_lp(mint)

                if lp:

                    watch_list[mint] = True

                    print(f"🟢 LP bulundu: {mint}")

                    send_message(
                        f"""🟢 <b>LP OLUŞTU</b>

🪙 Mint
<code>{mint}</code>

Likidite havuzu tespit edildi.
"""
                    )

            time.sleep(3)

        except Exception as e:

            print("LP Monitor Hatası:", e)
            time.sleep(5)


def start():

    threading.Thread(
        target=worker,
        daemon=True
    ).start()
