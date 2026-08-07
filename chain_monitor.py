import threading
import time

from helius_ws import HeliusWS


# Takip edilen coinler
watch_tokens = {}


def add_token(
    mint,
    name="",
    symbol="",
    creator=""
):
    """
    Yeni coin takip listesine ekler.
    """

    if mint not in watch_tokens:

        watch_tokens[mint] = {
            "name": name,
            "symbol": symbol,
            "creator": creator,
            "created": time.time(),

            # Blockchain olayları
            "lp_found": False,
            "first_buy": False,
            "dex": None,
            "holders": 0,
            "whale_buy": False
        }

        print(f"👀 Takibe eklendi : {name} ({mint})")


def remove_token(mint):

    if mint in watch_tokens:

        del watch_tokens[mint)

        print(f"🗑 Takipten çıkarıldı : {mint}")


def process_event(data):
    """
    Helius WebSocket'ten gelen eventler.
    V4.1'de sadece loglanıyor.
    V4.2'de LP Detection eklenecek.
    """

    print("📦 Blockchain Event")
    print(data)


def process_token(mint, token):
    """
    Gelecekte zaman bazlı kontroller burada yapılacak.
    """
    pass


def worker():

    while True:

        try:

            for mint, token in list(watch_tokens.items()):

                process_token(mint, token)

            time.sleep(1)

        except Exception as e:

            print("❌ Chain Monitor Hatası")
            print(e)

            time.sleep(3)


helius = HeliusWS(
    callback=process_event
)


def start():

    print("🛰 Chain Monitor çalışıyor...")

    helius.start()

    threading.Thread(
        target=worker,
        daemon=True
    ).start()


def stop():

    helius.stop()
