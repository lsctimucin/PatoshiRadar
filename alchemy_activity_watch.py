# ============================================================
# PATOSHI RADAR V5.1
# ALCHEMY ACTIVITY WATCH
# ============================================================
#
# Akış:
# PumpPortal
#     ↓
# Telegram alarmı
#     ↓
# add_token(mint)
#     ↓
# Alchemy logsSubscribe
#     ↓
# 60 saniye Activity Watch
#     ↓
# LP / DEX / SWAP / BUY tespiti
#
# ENV:
# ALCHEMY_API_KEY
#
# ============================================================

import os
import json
import time
import threading
import requests
import websocket


# ============================================================
# CONFIG
# ============================================================

ALCHEMY_API_KEY = os.getenv("ALCHEMY_API_KEY", "").strip()

WS_URL = (
    f"wss://solana-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
)

HTTP_URL = (
    f"https://solana-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
)

WATCH_SECONDS = 60

RECONNECT_SECONDS = 5

MAX_WATCHES = 100

HTTP_TIMEOUT = 10


# ============================================================
# PROGRAM / KEYWORD SIGNATURES
# ============================================================

LP_KEYWORDS = [
    "initialize",
    "initialize2",
    "initialize_pool",
    "create_pool",
    "add_liquidity",
    "liquidity",
    "pool",
]

DEX_KEYWORDS = [
    "swap",
    "route",
    "amm",
    "cpmm",
    "raydium",
    "pumpswap",
    "pump swap",
]

BUY_KEYWORDS = [
    "buy",
    "swap",
    "exact_tokens_for_sol",
    "exact_sol_for_tokens",
]


# ============================================================
# STATE
# ============================================================

watch_tokens = {}

watch_lock = threading.Lock()

subscription_map = {}

subscription_reverse = {}

request_id = 1000

ws_instance = None

ws_lock = threading.Lock()

running = False

worker_thread = None


# ============================================================
# LOG
# ============================================================

def log(message):
    print(message, flush=True)


# ============================================================
# REQUEST ID
# ============================================================

def next_request_id():
    global request_id

    request_id += 1

    return request_id


# ============================================================
# ADD TOKEN
# ============================================================

def add_token(
    mint,
    name="",
    symbol="",
    creator="",
):
    """
    Activity Watch başlatır.

    app.py / notifier tarafından:
        add_token(mint, name, symbol, creator)
    """

    if not mint:
        return False

    now = time.time()

    with watch_lock:

        if len(watch_tokens) >= MAX_WATCHES:
            log(
                "⚠️ ALCHEMY WATCH LIMIT => "
                f"MAX={MAX_WATCHES}"
            )
            return False

        watch_tokens[mint] = {
            "mint": mint,
            "name": name,
            "symbol": symbol,
            "creator": creator,
            "started_at": now,
            "expires_at": now + WATCH_SECONDS,
            "subscription_id": None,
            "lp_detected": False,
            "dex_detected": False,
            "buy_detected": False,
            "first_event_signature": None,
        }

    log(
        "👁️ ALCHEMY ACTIVITY WATCH BAŞLADI => "
        f"{mint} | {WATCH_SECONDS}s"
    )

    subscribe_token(mint)

    return True


# ============================================================
# REMOVE TOKEN
# ============================================================

def remove_token(mint):

    with watch_lock:

        item = watch_tokens.pop(mint, None)

    if not item:
        return

    subscription_id = item.get("subscription_id")

    if subscription_id is not None:
        unsubscribe(subscription_id)

    log(
        "🧹 ALCHEMY WATCH SONLANDI => "
        f"{mint}"
    )


# ============================================================
# SUBSCRIBE TOKEN
# ============================================================

def subscribe_token(mint):

    global ws_instance

    with ws_lock:
        ws = ws_instance

    if ws is None:
        log(
            "⚠️ ALCHEMY WS hazır değil => "
            f"{mint}"
        )
        return False

    try:

        req_id = next_request_id()

        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "logsSubscribe",
            "params": [
                {
                    "mentions": [
                        mint
                    ]
                },
                {
                    "commitment": "confirmed"
                }
            ]
        }

        ws.send(
            json.dumps(payload)
        )

        log(
            "📡 ALCHEMY logsSubscribe gönderildi => "
            f"{mint}"
        )

        return True

    except Exception as e:

        log(
            "❌ ALCHEMY subscribe ERROR => "
            f"{e}"
        )

        return False


# ============================================================
# UNSUBSCRIBE
# ============================================================

def unsubscribe(subscription_id):

    global ws_instance

    if subscription_id is None:
        return

    with ws_lock:
        ws = ws_instance

    if ws is None:
        return

    try:

        req_id = next_request_id()

        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "logsUnsubscribe",
            "params": [
                subscription_id
            ]
        }

        ws.send(
            json.dumps(payload)
        )

        log(
            "📴 ALCHEMY logsUnsubscribe => "
            f"{subscription_id}"
        )

    except Exception as e:

        log(
            "⚠️ unsubscribe ERROR => "
            f"{e}"
        )


# ============================================================
# GET TRANSACTION
# ============================================================

def get_transaction(signature):

    if not signature:
        return None

    payload = {
        "jsonrpc": "2.0",
        "id": next_request_id(),
        "method": "getTransaction",
        "params": [
            signature,
            {
                "encoding": "jsonParsed",
                "commitment": "confirmed",
                "maxSupportedTransactionVersion": 0,
            }
        ]
    }

    try:

        response = requests.post(
            HTTP_URL,
            json=payload,
            timeout=HTTP_TIMEOUT,
        )

        if response.status_code == 429:

            log(
                "⚠️ ALCHEMY HTTP RATE LIMIT => "
                f"signature={signature}"
            )

            return None

        response.raise_for_status()

        data = response.json()

        return data.get("result")

    except Exception as e:

        log(
            "⚠️ getTransaction ERROR => "
            f"{e}"
        )

        return None


# ============================================================
# TEXT NORMALIZER
# ============================================================

def normalize_logs(logs):

    if not logs:
        return ""

    return " ".join(
        str(x).lower()
        for x in logs
    )


# ============================================================
# EVENT ANALYSIS
# ============================================================

def analyze_event(
    mint,
    signature,
    logs,
):

    text = normalize_logs(logs)

    if not text:
        return

    with watch_lock:

        item = watch_tokens.get(mint)

        if not item:
            return

        if item["first_event_signature"] is None:
            item["first_event_signature"] = signature

    # --------------------------------------------------------
    # LP
    # --------------------------------------------------------

    lp_hit = any(
        keyword in text
        for keyword in LP_KEYWORDS
    )

    if lp_hit:

        with watch_lock:

            item = watch_tokens.get(mint)

            if item and not item["lp_detected"]:

                item["lp_detected"] = True

                log(
                    "💧 V5.1 ALCHEMY LP DETECTED => "
                    f"{mint} | tx={signature}"
                )

    # --------------------------------------------------------
    # DEX
    # --------------------------------------------------------

    dex_hit = any(
        keyword in text
        for keyword in DEX_KEYWORDS
    )

    if dex_hit:

        with watch_lock:

            item = watch_tokens.get(mint)

            if item and not item["dex_detected"]:

                item["dex_detected"] = True

                log(
                    "🏦 V5.1 ALCHEMY DEX DETECTED => "
                    f"{mint} | tx={signature}"
                )

    # --------------------------------------------------------
    # BUY / SWAP
    # --------------------------------------------------------

    buy_hit = any(
        keyword in text
        for keyword in BUY_KEYWORDS
    )

    if buy_hit:

        with watch_lock:

            item = watch_tokens.get(mint)

            if item and not item["buy_detected"]:

                item["buy_detected"] = True

                log(
                    "🟢 V5.1 ALCHEMY FIRST BUY/SWAP "
                    f"DETECTED => {mint} | tx={signature}"
                )

    # --------------------------------------------------------
    # TRANSACTION ANALYSIS
    # --------------------------------------------------------

    tx = get_transaction(signature)

    if tx:

        log(
            "🔬 V5.1 ALCHEMY TRANSACTION ANALYSIS => "
            f"{mint} | tx={signature}"
        )

        meta = tx.get("meta") or {}

        pre_balances = meta.get(
            "preTokenBalances"
        ) or []

        post_balances = meta.get(
            "postTokenBalances"
        ) or []

        if pre_balances or post_balances:

            log(
                "🪙 V5.1 TOKEN BALANCE DATA => "
                f"{mint}"
            )


# ============================================================
# WEBSOCKET MESSAGE
# ============================================================

def on_message(ws, message):

    try:

        data = json.loads(message)

    except Exception:

        return

    # --------------------------------------------------------
    # SUBSCRIPTION RESPONSE
    # --------------------------------------------------------

    if "result" in data and "id" in data:

        result = data.get("result")

        request_identifier = data.get("id")

        if isinstance(result, int):

            log(
                "✅ ALCHEMY logsSubscribe AKTİF => "
                f"subscription={result}"
            )

            # En son subscribe edilen tokenı bulmak için
            # aktif ve subscription_id boş tokenları kontrol ediyoruz.

            with watch_lock:

                candidates = [
                    item
                    for item in watch_tokens.values()
                    if item.get("subscription_id") is None
                ]

                if candidates:

                    item = candidates[-1]

                    item["subscription_id"] = result

                    mint = item["mint"]

                    subscription_map[
                        result
                    ] = mint

                    subscription_reverse[
                        mint
                    ] = result

        return

    # --------------------------------------------------------
    # ERROR
    # --------------------------------------------------------

    if "error" in data:

        error = data.get("error")

        log(
            "❌ V5.1 ALCHEMY RPC ERROR => "
            f"{error}"
        )

        return

    # --------------------------------------------------------
    # LOG NOTIFICATION
    # --------------------------------------------------------

    if data.get("method") != "logsNotification":
        return

    params = data.get("params") or {}

    subscription_id = params.get(
        "subscription"
    )

    result = (
        params.get("result")
        or {}
    )

    value = (
        result.get("value")
        or {}
    )

    signature = value.get(
        "signature"
    )

    logs = value.get(
        "logs"
    ) or []

    if not signature:
        return

    with watch_lock:

        mint = subscription_map.get(
            subscription_id
        )

    if not mint:
        return

    log(
        "⚡ V5.1 ALCHEMY EVENT => "
        f"{mint} | tx={signature}"
    )

    analyze_event(
        mint,
        signature,
        logs,
    )


# ============================================================
# WEBSOCKET OPEN
# ============================================================

def on_open(ws):

    global ws_instance

    with ws_lock:
        ws_instance = ws

    log(
        "🔌 Alchemy WebSocket bağlandı."
    )

    log(
        "🧬 V5.1 ALCHEMY ACTIVITY WATCH AKTİF"
    )

    # --------------------------------------------------------
    # ACTIVE WATCHES RE-SUBSCRIBE
    # --------------------------------------------------------

    with watch_lock:

        active_tokens = list(
            watch_tokens.keys()
        )

    for mint in active_tokens:

        subscribe_token(
            mint
        )


# ============================================================
# WEBSOCKET ERROR
# ============================================================

def on_error(ws, error):

    log(
        "❌ V5.1 Alchemy WebSocket ERROR => "
        f"{error}"
    )


# ============================================================
# WEBSOCKET CLOSE
# ============================================================

def on_close(
    ws,
    close_status_code,
    close_msg,
):

    global ws_instance

    with ws_lock:

        ws_instance = None

    log(
        "🔌 V5.1 Alchemy WebSocket kapandı "
        f"| code={close_status_code} "
        f"| msg={close_msg}"
    )


# ============================================================
# CLEANUP LOOP
# ============================================================

def cleanup_loop():

    while running:

        now = time.time()

        expired = []

        with watch_lock:

            for mint, item in list(
                watch_tokens.items()
            ):

                if now >= item["expires_at"]:

                    expired.append(
                        mint
                    )

        for mint in expired:

            remove_token(
                mint
            )

        time.sleep(2)


# ============================================================
# WEBSOCKET LOOP
# ============================================================

def websocket_loop():

    global running

    if not ALCHEMY_API_KEY:

        log(
            "❌ ALCHEMY_API_KEY bulunamadı."
        )

        return

    log(
        "🚀 V5.1 ALCHEMY ACTIVITY WATCH "
        "BAŞLATILIYOR..."
    )

    while running:

        try:

            log(
                "🔌 Alchemy WebSocket bağlanıyor..."
            )

            ws = websocket.WebSocketApp(
                WS_URL,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
            )

            ws.run_forever(
                ping_interval=20,
                ping_timeout=10,
            )

        except Exception as e:

            log(
                "❌ V5.1 ALCHEMY WS CRASH => "
                f"{e}"
            )

        if running:

            log(
                f"🔄 V5.1 Alchemy yeniden bağlanacak... "
                f"{RECONNECT_SECONDS}s"
            )

            time.sleep(
                RECONNECT_SECONDS
            )


# ============================================================
# START
# ============================================================

def start():

    global running
    global worker_thread

    if running:
        log(
            "⚠️ ALCHEMY ACTIVITY WATCH zaten aktif."
        )
        return

    running = True

    worker_thread = threading.Thread(
        target=websocket_loop,
        daemon=True,
        name="AlchemyActivityWatch",
    )

    worker_thread.start()

    cleanup_thread = threading.Thread(
        target=cleanup_loop,
        daemon=True,
        name="AlchemyActivityCleanup",
    )

    cleanup_thread.start()


# ============================================================
# STOP
# ============================================================

def stop():

    global running

    running = False

    with ws_lock:

        ws = ws_instance

    if ws:

        try:
            ws.close()

        except Exception:
            pass

    log(
        "🛑 V5.1 ALCHEMY ACTIVITY WATCH DURDURULDU."
    )


# ============================================================
# STATUS
# ============================================================

def status():

    with watch_lock:

        return {
            mint: dict(item)
            for mint, item
            in watch_tokens.items()
        }


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    start()

    while True:

        time.sleep(10)
