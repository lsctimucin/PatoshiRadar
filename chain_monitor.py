# ============================================================
# PATOSHI RADAR - V5.1
# CHAIN MONITOR
# ============================================================

import os
import json
import time
import threading
import websocket


# ============================================================
# AYARLAR
# ============================================================

HELIUS_API_KEY = os.getenv("HELIUS_API_KEY", "").strip()

if not HELIUS_API_KEY:
    print("⚠️ HELIUS_API_KEY bulunamadı.")


# Helius WebSocket
WS_URL = (
    f"wss://mainnet.helius-rpc.com/"
    f"?api-key={HELIUS_API_KEY}"
)


# İzlenecek tokenlar
WATCHED_TOKENS = set()

# Çift kayıtları engellemek için
LOCK = threading.Lock()

# Thread durumu
_RUNNING = False


# ============================================================
# TOKEN EKLE
# ============================================================

def add_token(mint):
    """
    Activity Watch tarafından izlenecek tokenı ekler.
    """

    if not mint:
        return False

    mint = str(mint).strip()

    with LOCK:
        if mint in WATCHED_TOKENS:
            return False

        WATCHED_TOKENS.add(mint)

    print(f"🧬 V5.1 CHAIN MONITOR ADD_TOKEN => {mint}")

    return True


# ============================================================
# TOKENLARI AL
# ============================================================

def get_tokens():
    with LOCK:
        return list(WATCHED_TOKENS)


# ============================================================
# HELIUS MESAJI
# ============================================================

def on_message(ws, message):

    try:
        data = json.loads(message)

    except Exception:
        return

    # Helius subscription cevabı
    if "result" in data and "id" in data:
        print(f"🛰️ Helius Subscription => {data}")
        return

    # Helius event
    if "method" in data:

        method = data.get("method")

        print(f"🛰️ Helius Event => {method}")

        params = data.get("params", {})

        result = params.get("result")

        if result:
            process_event(result)

        return

    # Normal veri
    process_event(data)


# ============================================================
# EVENT İŞLE
# ============================================================

def process_event(event):

    if not event:
        return

    try:
        value = event.get("value", event)

        if isinstance(value, dict):

            signature = value.get("signature")

            if signature:
                print(
                    f"🧬 V5.1 TRANSACTION => "
                    f"{signature[:16]}..."
                )

    except Exception as e:

        print(
            f"⚠️ V5.1 CHAIN EVENT ERROR => {e}"
        )


# ============================================================
# WEBSOCKET OPEN
# ============================================================

def on_open(ws):

    print("🛰️ Helius WebSocket bağlandı.")

    try:

        # Helius transactionSubscribe
        # Genel transaction akışını dinliyoruz.
        #
        # Filtreleme Activity Watch / Parser tarafında yapılabilir.

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "transactionSubscribe",
            "params": [
                {
                    "accountInclude": []
                },
                {
                    "commitment": "confirmed",
                    "encoding": "jsonParsed",
                    "transactionDetails": "full",
                    "showRewards": False,
                    "maxSupportedTransactionVersion": 0
                }
            ]
        }

        ws.send(json.dumps(payload))

        print(
            "✅ transactionSubscribe gönderildi."
        )

    except Exception as e:

        print(
            f"❌ transactionSubscribe ERROR => {e}"
        )


# ============================================================
# WEBSOCKET ERROR
# ============================================================

def on_error(ws, error):

    print(
        f"❌ Helius WebSocket ERROR => {error}"
    )


# ============================================================
# WEBSOCKET CLOSE
# ============================================================

def on_close(ws, close_status_code, close_msg):

    print(
        f"🔴 Helius WebSocket kapandı. "
        f"code={close_status_code} "
        f"msg={close_msg}"
    )


# ============================================================
# WEBSOCKET ÇALIŞTIR
# ============================================================

def _run_websocket():

    global _RUNNING

    _RUNNING = True

    while True:

        try:

            if not HELIUS_API_KEY:

                print(
                    "❌ HELIUS_API_KEY yok. "
                    "WebSocket başlatılamıyor."
                )

                time.sleep(10)

                continue

            print(
                "🛰️ Helius WebSocket başlatılıyor..."
            )

            ws = websocket.WebSocketApp(
                WS_URL,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )

            ws.run_forever(
                ping_interval=20,
                ping_timeout=10
            )

        except Exception as e:

            print(
                f"❌ Helius WebSocket CRASH => {e}"
            )

        print(
            "🔄 Helius WebSocket yeniden bağlanacak..."
        )

        time.sleep(5)


# ============================================================
# START
# ============================================================

def start():

    """
    app.py tarafından çağrılır.

    ÖNEMLİ:
    app.py şu şekilde kullanıyor:

        from chain_monitor import add_token, start as start_chain

    Bu nedenle start() mutlaka bulunmalıdır.
    """

    global _RUNNING

    if _RUNNING:
        print(
            "⚠️ V5.1 Chain Monitor zaten çalışıyor."
        )
        return

    print(
        "🧬 V5.1 CHAIN MONITOR BAŞLATILIYOR..."
    )

    thread = threading.Thread(
        target=_run_websocket,
        daemon=True
    )

    thread.start()

    print(
        "🧬 V5.1 CHAIN MONITOR AKTİF"
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "🧬 V5.1 CHAIN MONITOR TEST"
    )

    start()

    while True:
        time.sleep(60)
