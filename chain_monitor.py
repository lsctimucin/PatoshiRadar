import threading
import time

# Takip edilen coinler
watch_tokens = {}


def add_token(
    mint,
    name="",
    symbol="",
    creator=""
):
    """
    Yeni coin takip listesine eklenir.
    """

    if mint not in watch_tokens:

        watch_tokens[mint] = {
            "name": name,
            "symbol": symbol,
            "creator": creator,
            "created": time.time(),

            # Durumlar
            "lp_found": False,
            "first_buy": False,
            "dex": None
        }

        print(f"👀 Takibe eklendi : {name} ({mint})")


def remove_token(mint):

    if mint in watch_tokens:

        del watch_tokens[mint]


def process_token(mint, token):

    """
    V4'te burası boş.
    V5'te Helius transaction burada analiz edilecek.
    """

    pass


def worker():

    print("🛰 Chain Monitor çalışıyor...")

    while True:

        try:

            for mint, token in list(watch_tokens.items()):

                process_token(mint, token)

            time.sleep(1)

        except Exception as e:

            print("Chain Monitor:", e)

            time.sleep(3)


def start():

    threading.Thread(
        target=worker,
        daemon=True
    ).start()
