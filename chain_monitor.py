import os
import json
import time
import threading
import traceback

import requests
import websocket


# ============================================================
# V5.1 CHAIN MONITOR
# Helius Free Plan Compatible
#
# IMPORTANT:
# - transactionSubscribe KULLANILMIYOR
# - logsSubscribe KULLANILIYOR
# - Pump.fun program logları dinleniyor
# ============================================================


# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------

HELIUS_API_KEY = os.getenv("HELIUS_API_KEY", "").strip()

HELIUS_WS_URL = (
    f"wss://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
)

HELIUS_RPC_URL = (
    f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
)


# Pump.fun main program
PUMP_FUN_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"


# ------------------------------------------------------------
# GLOBAL STATE
# ------------------------------------------------------------

_running = False
_ws = None
_thread = None

_subscription_id = None
_request_id = 1

_lock = threading.Lock()

# Tracked tokens
#
# {
#     mint: {
#         "name": "...",
#         "symbol": "...",
#         "added_at": timestamp,
#         "expires_at": timestamp
#     }
# }
tracked_tokens = {}


# Prevent the same signature from being processed repeatedly
processed_signatures = set()

# Keep this set small
MAX_PROCESSED_SIGNATURES = 5000


# ------------------------------------------------------------
# LOG HELPER
# ------------------------------------------------------------

def _log(message):
    print(message, flush=True)


# ------------------------------------------------------------
# REQUEST ID
# ------------------------------------------------------------

def _next_request_id():
    global _request_id

    with _lock:
        value = _request_id
        _request_id += 1

    return value


# ------------------------------------------------------------
# ADD TOKEN
# ------------------------------------------------------------

def add_token(mint, name=None, symbol=None, duration=60, *args, **kwargs):
    """
    V5.1 Activity Watch'a token ekler.

    Mevcut app.py'nin farklı parametrelerle çağırması durumunda
    mümkün olduğunca geriye uyumlu kalır.
    """

    if not mint:
        return False

    mint = str(mint).strip()

    now = time.time()

    try:
        duration = int(duration)
    except Exception:
        duration = 60

    if duration <= 0:
        duration = 60

    with _lock:
        tracked_tokens[mint] = {
            "name": name or "Unknown",
            "symbol": symbol or "-",
            "added_at": now,
            "expires_at": now + duration,
        }

    _log(
        f"🧪 V5.1 ADD_TOKEN => {mint}"
    )

    _log(
        f"♾️ V5.1 Activity Watch başladı | "
        f"{name or 'Unknown'} ({symbol or '-'}) | "
        f"{duration}s"
    )

    return True


# ------------------------------------------------------------
# REMOVE EXPIRED TOKENS
# ------------------------------------------------------------

def _cleanup_tokens():
    now = time.time()

    expired = []

    with _lock:
        for mint, info in tracked_tokens.items():
            if now >= info["expires_at"]:
                expired.append(
                    (
                        mint,
                        info.get("name", "Unknown"),
                        info.get("symbol", "-"),
                    )
                )

        for mint, _, _ in expired:
            tracked_tokens.pop(mint, None)

    for mint, name, symbol in expired:

        _log(
            f"🛑 V5.1 Activity Watch tamamlandı | "
            f"{name} ({symbol}) | {mint[:8]}... | "
            f"60s"
        )


# ------------------------------------------------------------
# CHECK IF TRANSACTION BELONGS TO TRACKED TOKEN
# ------------------------------------------------------------

def _transaction_contains_mint(transaction, mint):
    """
    getTransaction cevabındaki bütün account adreslerinde
    mint adresini arar.

    Bu yöntem logsSubscribe ile gelen signature sonrasında
    transaction detayını RPC üzerinden kontrol eder.
    """

    if not transaction:
        return False

    mint = str(mint)

    message = (
        transaction
        .get("transaction", {})
        .get("message", {})
    )

    # ----------------------------------------
    # accountKeys
    # ----------------------------------------

    account_keys = message.get("accountKeys", [])

    for account in account_keys:

        if isinstance(account, str):
            address = account

        elif isinstance(account, dict):
            address = account.get("pubkey", "")

        else:
            continue

        if address == mint:
            return True

    # ----------------------------------------
    # loadedAddresses
    # ----------------------------------------

    meta = transaction.get("meta") or {}

    loaded = meta.get("loadedAddresses") or {}

    for section in ("writable", "readonly"):

        for address in loaded.get(section, []):

            if address == mint:
                return True

    # ----------------------------------------
    # token balances
    # ----------------------------------------

    for balance in meta.get("preTokenBalances", []):

        if balance.get("mint") == mint:
            return True

    for balance in meta.get("postTokenBalances", []):

        if balance.get("mint") == mint:
            return True

    return False


# ------------------------------------------------------------
# GET TRANSACTION
# ------------------------------------------------------------

def _get_transaction(signature):

    payload = {
        "jsonrpc": "2.0",
        "id": _next_request_id(),
        "method": "getTransaction",
        "params": [
            signature,
            {
                "encoding": "jsonParsed",
                "commitment": "confirmed",
                "maxSupportedTransactionVersion": 0,
            },
        ],
    }

    try:

        response = requests.post(
            HELIUS_RPC_URL,
            json=payload,
            timeout=10,
        )

        if response.status_code != 200:

            _log(
                f"⚠️ V5.1 RPC HTTP ERROR => "
                f"{response.status_code}"
            )

            return None

        data = response.json()

        if "error" in data:

            _log(
                f"⚠️ V5.1 getTransaction ERROR => "
                f"{data['error']}"
            )

            return None

        return data.get("result")

    except Exception as exc:

        _log(
            f"⚠️ V5.1 getTransaction EXCEPTION => "
            f"{exc}"
        )

        return None


# ------------------------------------------------------------
# PARSER
# ------------------------------------------------------------

def _parse_transaction(signature, transaction):
    """
    V5.1 Parser başlangıç noktası.

    Buradaki amaç önce transaction'ın gerçekten
    takip edilen Pump.fun token'ına ait olduğunu
    doğrulamaktır.
    """

    if not transaction:
        return None

    block_time = transaction.get("blockTime")

    slot = transaction.get("slot")

    meta = transaction.get("meta") or {}

    err = meta.get("err")

    message = (
        transaction
        .get("transaction", {})
        .get("message", {})
    )

    instructions = message.get("instructions", [])

    account_keys = message.get("accountKeys", [])

    return {
        "signature": signature,
        "slot": slot,
        "block_time": block_time,
        "error": err,
        "instruction_count": len(instructions),
        "account_count": len(account_keys),
    }


# ------------------------------------------------------------
# TRANSACTION ANATOMY
# ------------------------------------------------------------

def _transaction_anatomy(signature, parsed):

    if not parsed:
        return

    _log(
        f"🧬 V5.1 TRANSACTION ANATOMY | "
        f"signature={signature[:12]}..."
    )

    _log(
        f"🧬 V5.1 TRANSACTION ANATOMY HAZIR | "
        f"slot={parsed.get('slot')} | "
        f"instructions={parsed.get('instruction_count')} | "
        f"accounts={parsed.get('account_count')}"
    )


# ------------------------------------------------------------
# PARSER CHECK
# ------------------------------------------------------------

def _parser_check(signature, mint, parsed):

    if not parsed:
        return

    _log(
        f"⚪ V5.1 PARSER CHECK | "
        f"mint={mint[:8]}... | "
        f"signature={signature[:12]}..."
    )

    if parsed.get("error") is None:

        _log(
            "⚪ V5.1 PARSER CHECK => "
            "transaction başarılı"
        )

    else:

        _log(
            f"⚠️ V5.1 PARSER CHECK => "
            f"transaction error={parsed.get('error')}"
        )


# ------------------------------------------------------------
# PROCESS LOG NOTIFICATION
# ------------------------------------------------------------

def _process_log_notification(data):

    params = data.get("params")

    if not params:
        return

    result = params.get("result")

    if not result:
        return

    value = result.get("value") or {}

    signature = value.get("signature")

    if not signature:
        return

    err = value.get("err")

    logs = value.get("logs") or []

    # ----------------------------------------
    # Duplicate protection
    # ----------------------------------------

    with _lock:

        if signature in processed_signatures:
            return

        processed_signatures.add(signature)

        if len(processed_signatures) > MAX_PROCESSED_SIGNATURES:

            # Remove roughly half
            old_items = list(processed_signatures)[
                :MAX_PROCESSED_SIGNATURES // 2
            ]

            for item in old_items:
                processed_signatures.discard(item)

    # ----------------------------------------
    # Cleanup
    # ----------------------------------------

    _cleanup_tokens()

    # ----------------------------------------
    # Snapshot tracked tokens
    # ----------------------------------------

    with _lock:
        tokens = list(tracked_tokens.items())

    if not tokens:
        return

    # ----------------------------------------
    # Ignore failed transactions
    # ----------------------------------------

    if err is not None:
        return

    # ----------------------------------------
    # Quick log filter
    # ----------------------------------------

    joined_logs = " ".join(logs).lower()

    # Pump.fun transactions generally contain
    # program invocation information.
    #
    # We don't reject here too aggressively because
    # different Pump.fun instructions can have
    # different log strings.
    if "pump" not in joined_logs and "program" not in joined_logs:
        pass

    # ----------------------------------------
    # Fetch transaction
    # ----------------------------------------

    transaction = _get_transaction(signature)

    if not transaction:
        return

    # ----------------------------------------
    # Check every tracked token
    # ----------------------------------------

    for mint, info in tokens:

        if not _transaction_contains_mint(
            transaction,
            mint,
        ):
            continue

        name = info.get("name", "Unknown")
        symbol = info.get("symbol", "-")

        _log(
            f"🔎 V5.1 Helius Event | "
            f"{name} ({symbol}) | "
            f"{signature[:12]}..."
        )

        parsed = _parse_transaction(
            signature,
            transaction,
        )

        _transaction_anatomy(
            signature,
            parsed,
        )

        _parser_check(
            signature,
            mint,
            parsed,
        )

        _log(
            f"🎯 V5.1 ACTIVITY EVENT | "
            f"{name} ({symbol}) | "
            f"{mint[:8]}..."
        )


# ------------------------------------------------------------
# WEBSOCKET CALLBACKS
# ------------------------------------------------------------

def _on_open(ws):

    global _subscription_id

    _subscription_id = None

    _log(
        "🧬 V5.1 PUMP.FUN LOG SUBSCRIPTION gönderildi."
    )

    request = {
        "jsonrpc": "2.0",
        "id": _next_request_id(),
        "method": "logsSubscribe",
        "params": [
            {
                "mentions": [
                    PUMP_FUN_PROGRAM
                ]
            },
            {
                "commitment": "processed"
            },
        ],
    }

    try:

        ws.send(
            json.dumps(request)
        )

    except Exception as exc:

        _log(
            f"❌ V5.1 logsSubscribe SEND ERROR => "
            f"{exc}"
        )


def _on_message(ws, message):

    global _subscription_id

    try:

        data = json.loads(message)

    except Exception:

        _log(
            "⚠️ V5.1 WebSocket JSON parse edilemedi."
        )

        return

    # ----------------------------------------
    # RPC error
    # ----------------------------------------

    if "error" in data:

        _log(
            f"❌ V5.1 Helius RPC ERROR => "
            f"{data['error']}"
        )

        return

    # ----------------------------------------
    # Subscription confirmation
    # ----------------------------------------

    if (
        data.get("jsonrpc") == "2.0"
        and "result" in data
        and "id" in data
        and data.get("id") is not None
    ):

        result = data.get("result")

        if isinstance(result, int):

            _subscription_id = result

            _log(
                f"✅ V5.1 logsSubscribe AKTİF => "
                f"subscription={result}"
            )

            return

    # ----------------------------------------
    # logsNotification
    # ----------------------------------------

    if data.get("method") == "logsNotification":

        _process_log_notification(data)

        return


def _on_error(ws, error):

    _log(
        f"❌ V5.1 Helius WebSocket ERROR => "
        f"{error}"
    )


def _on_close(ws, close_status_code, close_msg):

    _log(
        f"🔌 V5.1 Helius WebSocket kapandı | "
        f"code={close_status_code} | "
        f"msg={close_msg}"
    )


# ------------------------------------------------------------
# WEBSOCKET LOOP
# ------------------------------------------------------------

def _websocket_loop():

    global _ws

    if not HELIUS_API_KEY:

        _log(
            "❌ V5.1 HELIUS_API_KEY bulunamadı."
        )

        return

    reconnect_delay = 3

    while _running:

        try:

            _log(
                "🔌 Helius WebSocket başlatılıyor..."
                "🧬 V5.1 CHAIN MONITOR AKTİF"
            )

            _ws = websocket.WebSocketApp(
                HELIUS_WS_URL,
                on_open=_on_open,
                on_message=_on_message,
                on_error=_on_error,
                on_close=_on_close,
            )

            _ws.run_forever(
                ping_interval=20,
                ping_timeout=10,
            )

        except Exception as exc:

            _log(
                f"❌ V5.1 WebSocket LOOP ERROR => "
                f"{exc}"
            )

            traceback.print_exc()

        finally:

            _ws = None

        if not _running:
            break

        _log(
            f"🔄 V5.1 Helius yeniden bağlanacak... "
            f"{reconnect_delay}s"
        )

        time.sleep(reconnect_delay)

        reconnect_delay = min(
            reconnect_delay * 2,
            30,
        )


# ------------------------------------------------------------
# START
# ------------------------------------------------------------

def start(*args, **kwargs):

    global _running
    global _thread

    if _running:

        _log(
            "⚠️ V5.1 CHAIN MONITOR zaten aktif."
        )

        return

    _running = True

    _log(
        "🧬 V5.1 CHAIN MONITOR BAŞLATILIYOR..."
    )

    _thread = threading.Thread(
        target=_websocket_loop,
        daemon=True,
        name="V5.1-ChainMonitor",
    )

    _thread.start()

    return _thread


# ------------------------------------------------------------
# STOP
# ------------------------------------------------------------

def stop(*args, **kwargs):

    global _running
    global _ws

    _running = False

    try:

        if _ws is not None:
            _ws.close()

    except Exception:
        pass

    _log(
        "🛑 V5.1 CHAIN MONITOR DURDURULDU."
    )


# ------------------------------------------------------------
# STATUS
# ------------------------------------------------------------

def is_running():

    return _running


# ------------------------------------------------------------
# OPTIONAL DIRECT RUN
# ------------------------------------------------------------

if __name__ == "__main__":

    start()

    try:

        while True:

            time.sleep(10)

    except KeyboardInterrupt:

        stop()
