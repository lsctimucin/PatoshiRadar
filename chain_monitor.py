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

    if mint in watch_tokens:
        return

    watch_tokens[mint] = {
        "name": name,
        "symbol": symbol,
        "creator": creator,
        "created": time.time(),

        # Blockchain durumları
        "lp_found": False,
        "first_buy": False,
        "dex": None,
        "holders": 0,
        "whale_buy": False
    }

    print(
        f"👀 Takibe eklendi: {name} ({mint}) | Toplam Takip: {len(watch_tokens)}"
    )


def remove_token(mint):
    """
    Coini takip listesinden kaldırır.
    """

    if mint not in watch_tokens:
        return

    del watch_tokens[mint]

    print(
        f"🗑 Takipten çıkarıldı: {mint} | Kalan Takip: {len(watch_tokens)}"
    )


def process_event(data):
    """
    Helius WebSocket'ten gelen blockchain eventleri.

    V4.0
        Sadece loglanıyor.

    V4.1
        LP Detection

    V4.2
        First Buy Detection

    V4.3
        Whale Detection

    V4.4
        Holder Tracking
    """

    print("📦 Blockchain Event")
    print(data)


def process_token(mint, token):
    """
    İleride timeout, süre ve diğer kontroller burada yapılacak.
    """

    pass


def worker():

    print("⚙️ Chain Worker başlatıldı.")

    while True:

        try:

            for mint, token in list(watch_tokens.items()):

                process_token(
                    mint,
                    token
                )

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
        daemon=True,
        name="ChainMonitor"
    ).start()


def stop():

    print("🛑 Chain Monitor durduruluyor...")

    helius.stop()
