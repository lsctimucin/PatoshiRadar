import os
import json
import time
import threading
import traceback

import requests
import websocket


# ============================================================
# V5.1 CHAIN MONITOR
# Helius Free Plan - OPTIMIZED FINAL
#
# IMPORTANT
# ------------------------------------------------------------
# - transactionSubscribe YOK
# - Global Pump.fun logsSubscribe YOK
# - Token-bazlı logsSubscribe VAR
# - Sadece Activity Watch'a alınan tokenlar dinlenir
# - getTransaction sadece ilgili token transaction'larında çağrılır
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


# Pump.fun program
PUMP_FUN_PROGRAM = (
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
)


# Activity Watch default
DEFAULT_DURATION = 60


# Maximum number of remembered signatures
MAX_PROCESSED_SIGNATURES = 5000


# Reconnect
INITIAL_RECONNECT_DELAY = 5
MAX_RECONNECT_DELAY = 60


# Helius quota/rate-limit durumunda uzun bekleme
RATE_LIMIT_BACKOFF = 120


# ------------------------------------------------------------
# GLOBAL STATE
# ------------------------------------------------------------

_running = False
_ws = None
_thread = None

_request_id = 1

_lock = threading.Lock()


# ------------------------------------------------------------
# TRACKED TOKENS
# ------------------------------------------------------------
#
# {
#     mint: {
#         "name": "...",
#         "symbol": "...",
#         "added_at": timestamp,
#         "expires_at": timestamp,
#         "subscription_id": None
#     }
# }
#

tracked_tokens = {}


# ------------------------------------------------------------
# SUBSCRIPTIONS
# ------------------------------------------------------------
#
# Helius:
#
# request id -> mint
# subscription id -> mint
#

pending_subscriptions = {}
active_subscriptions = {}


# ------------------------------------------------------------
# PROCESSED SIGNATURES
# ------------------------------------------------------------

processed_signatures = set()


# ------------------------------------------------------------
# ERROR STATE
# ------------------------------------------------------------

_rate_limit_detected = False
_rate_limit_until = 0


# ------------------------------------------------------------
# LOG
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
# RATE LIMIT
# ------------------------------------------------------------

def _set_rate_limit():
    global _rate_limit_detected
    global _rate_limit_until

    _rate_limit_detected = True
    _rate_limit_until = time.time() + RATE_LIMIT_BACKOFF

    _log(
        "⏸️ V5.1 Helius kullanım/rate limit algılandı. "
        f"{RATE_LIMIT_BACKOFF}s bekleme uygulanacak."
    )


def _rate_limit_active():
    if not _rate_limit_detected:
        return False

    if time.time() >= _rate_limit_until:
        return False

    return True


# ------------------------------------------------------------
# ADD TOKEN
# ------------------------------------------------------------

def add_token(
    mint,
    name=None,
    symbol=None,
    duration=DEFAULT_DURATION,
    *args,
    **kwargs,
):
    """
    V5.1 Activity Watch token ekleme.

    app.py tarafından mevcut kullanım şekilleriyle
    çağrılabilmesi için geriye uyumlu tutulmuştur.
    """

    if not mint:
        return False

    mint = str(mint).strip()

    if not mint:
        return False

    try:
        duration = int(duration)
    except Exception:
        duration = DEFAULT_DURATION

    if duration <= 0:
        duration = DEFAULT_DURATION

    now = time.time()

    with _lock:
        tracked_tokens[mint] = {
            "name": name or "Unknown",
            "symbol": symbol or "-",
            "added_at": now,
            "expires_at": now + duration,
            "subscription_id": None,
        }

    _log(
        f"🧪 V5.1 ADD_TOKEN => {mint}"
    )

    _log(
        f"♾️ V5.1 Activity Watch başladı | "
        f"{name or 'Unknown'} "
        f"({symbol or '-'}) | "
        f"{duration}s"
    )

    # WebSocket zaten açıksa doğrudan token subscription gönder
    if _ws is not None and _ws.sock is not None:
        _subscribe_token(mint)

    return True


# ------------------------------------------------------------
# SUBSCRIBE TOKEN
# ------------------------------------------------------------

def _subscribe_token(mint):
    global _ws

    if not _running:
        return False

    if _ws is None:
        return False

    if _ws.sock is None:
        return False

    if _rate_limit_active():
        return False

    with _lock:
        info = tracked_tokens.get(mint)

        if not info:
            return False

        # Zaten subscription varsa tekrar gönderme
        if info.get("subscription_id") is not None:
            return True

    request_id = _next_request_id()

    request = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "logsSubscribe",
        "params": [
            {
                "mentions": [
                    mint
                ]
            },
            {
                "commitment": "processed"
            },
        ],
    }

    try:

        with _lock:
            pending_subscriptions[request_id] = mint

        _ws.send(
            json.dumps(request)
        )

        _log(
            f"🧬 V5.1 PUMP.FUN LOG SUBSCRIPTION gönderildi "
            f"| mint={mint[:12]}..."
        )

        return True

    except Exception as exc:

        with _lock:
            pending_subscriptions.pop(
                request_id,
                None,
            )

        _log(
            f"❌ V5.1 logsSubscribe SEND ERROR => "
            f"{exc}"
        )

        return False


# ------------------------------------------------------------
# UNSUBSCRIBE TOKEN
# ------------------------------------------------------------

def _unsubscribe_token(mint):

    global _ws

    if _ws is None:
        return

    if _ws.sock is None:
        return

    with _lock:

        info = tracked_tokens.get(mint)

        if not info:
            return

        subscription_id = info.get(
            "subscription_id"
        )

    if subscription_id is None:
        return

    request_id = _next_request_id()

    request = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "logsUnsubscribe",
        "params": [
            subscription_id
        ],
    }

    try:

        _ws.send(
            json.dumps(request)
        )

        _log(
            f"🧹 V5.1 logsSubscribe kaldırıldı "
            f"| mint={mint[:12]}..."
        )

    except Exception as exc:

        _log(
            f"⚠️ V5.1 logsUnsubscribe ERROR => "
            f"{exc}"
        )

    finally:

        with _lock:

            active_subscriptions.pop(
                subscription_id,
                None,
            )

            if mint in tracked_tokens:
                tracked_tokens[mint][
                    "subscription_id"
                ] = None


# ------------------------------------------------------------
# CLEANUP TOKENS
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
                        info.get(
                            "name",
                            "Unknown",
                        ),
                        info.get(
                            "symbol",
                            "-",
                        ),
                    )
                )

    # Önce subscription kaldır
    for mint, name, symbol in expired:

        _unsubscribe_token(mint)

    # Sonra tokenı sil
    with _lock:

        for mint, _, _ in expired:

            tracked_tokens.pop(
                mint,
                None,
            )

    for mint, name, symbol in expired:

        _log(
            f"🛑 V5.1 Activity Watch tamamlandı | "
            f"{name} ({symbol}) | "
            f"{mint[:8]}... | "
            f"{DEFAULT_DURATION}s"
        )


# ------------------------------------------------------------
# TRANSACTION CONTAINS MINT
# ------------------------------------------------------------

def _transaction_contains_mint(
    transaction,
    mint,
):

    if not transaction:
        return False

    mint = str(mint)

    message = (
        transaction
        .get("transaction", {})
        .get("message", {})
    )

    # --------------------------------------------------------
    # accountKeys
    # --------------------------------------------------------

    account_keys = message.get(
        "accountKeys",
        [],
    )

    for account in account_keys:

        if isinstance(account, str):

            address = account

        elif isinstance(account, dict):

            address = account.get(
                "pubkey",
                "",
            )

        else:

            continue

        if address == mint:
            return True

    # --------------------------------------------------------
    # loadedAddresses
    # --------------------------------------------------------

    meta = transaction.get(
        "meta"
    ) or {}

    loaded = meta.get(
        "loadedAddresses"
    ) or {}

    for section in (
        "writable",
        "readonly",
    ):

        for address in loaded.get(
            section,
            [],
        ):

            if address == mint:
                return True

    # --------------------------------------------------------
    # Token balances
    # --------------------------------------------------------

    for balance in meta.get(
        "preTokenBalances",
        [],
    ):

        if balance.get("mint") == mint:
            return True

    for balance in meta.get(
        "postTokenBalances",
        [],
    ):

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

        # ----------------------------------------------------
        # HTTP ERROR
        # ----------------------------------------------------

        if response.status_code != 200:

            _log(
                f"⚠️ V5.1 RPC HTTP ERROR => "
                f"{response.status_code}"
            )

            if response.status_code in (
                429,
                403,
            ):

                _set_rate_limit()

            return None

        # ----------------------------------------------------
        # JSON
        # ----------------------------------------------------

        data = response.json()

        if "error" in data:

            error = data["error"]

            _log(
                f"⚠️ V5.1 getTransaction ERROR => "
                f"{error}"
            )

            if isinstance(error, dict):

                code = error.get(
                    "code"
                )

                message = str(
                    error.get(
                        "message",
                        "",
                    )
                ).lower()

                if (
                    code == -32429
                    or "max usage" in message
                    or "too many requests" in message
                ):

                    _set_rate_limit()

            return None

        return data.get(
            "result"
        )

    except Exception as exc:

        _log(
            f"⚠️ V5.1 getTransaction EXCEPTION => "
            f"{exc}"
        )

        return None


# ------------------------------------------------------------
# PARSER
# ------------------------------------------------------------

def _parse_transaction(
    signature,
    transaction,
):

    if not transaction:
        return None

    block_time = transaction.get(
        "blockTime"
    )

    slot = transaction.get(
        "slot"
    )

    meta = transaction.get(
        "meta"
    ) or {}

    err = meta.get(
        "err"
    )

    message = (
        transaction
        .get("transaction", {})
        .get("message", {})
    )

    instructions = message.get(
        "instructions",
        [],
    )

    account_keys = message.get(
        "accountKeys",
        [],
    )

    return {
        "signature": signature,
        "slot": slot,
        "block_time": block_time,
        "error": err,
        "instruction_count": len(
            instructions
        ),
        "account_count": len(
            account_keys
        ),
    }


# ------------------------------------------------------------
# TRANSACTION ANATOMY
# ------------------------------------------------------------

def _transaction_anatomy(
    signature,
    parsed,
):

    if not parsed:
        return

    _log(
        f"🧬 V5.1 TRANSACTION ANATOMY | "
        f"signature={signature[:12]}..."
    )

    _log(
        f"🧬 V5.1 TRANSACTION ANATOMY HAZIR | "
        f"slot={parsed.get('slot')} | "
        f"instructions="
        f"{parsed.get('instruction_count')} | "
        f"accounts="
        f"{parsed.get('account_count')}"
    )


# ------------------------------------------------------------
# PARSER CHECK
# ------------------------------------------------------------

def _parser_check(
    signature,
    mint,
    parsed,
):

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
            f"transaction error="
            f"{parsed.get('error')}"
        )


# ------------------------------------------------------------
# PROCESS LOG NOTIFICATION
# ------------------------------------------------------------

def _process_log_notification(data):

    params = data.get(
        "params"
    )

    if not params:
        return

    result = params.get(
        "result"
    )

    if not result:
        return

    # --------------------------------------------------------
    # Subscription ID
    # --------------------------------------------------------

    subscription_id = result.get(
        "subscription"
    )

    value = result.get(
        "value"
    ) or {}

    signature = value.get(
        "signature"
    )

    if not signature:
        return

    # --------------------------------------------------------
    # Find token belonging to subscription
    # --------------------------------------------------------

    with _lock:

        mint = active_subscriptions.get(
            subscription_id
        )

        if not mint:
            return

        info = tracked_tokens.get(
            mint
        )

    if not info:
        return

    name = info.get(
        "name",
        "Unknown",
    )

    symbol = info.get(
        "symbol",
        "-",
    )

    # --------------------------------------------------------
    # Duplicate protection
    # --------------------------------------------------------

    with _lock:

        if signature in processed_signatures:
            return

        processed_signatures.add(
            signature
        )

        if (
            len(processed_signatures)
            > MAX_PROCESSED_SIGNATURES
        ):

            old_items = list(
                processed_signatures
            )[
                :MAX_PROCESSED_SIGNATURES // 2
            ]

            for item in old_items:

                processed_signatures.discard(
                    item
                )

    # --------------------------------------------------------
    # Failed transaction
    # --------------------------------------------------------

    err = value.get(
        "err"
    )

    if err is not None:

        _log(
            f"⚠️ V5.1 Helius Event FAILED | "
            f"{name} ({symbol}) | "
            f"{signature[:12]}..."
        )

        return

    # --------------------------------------------------------
    # Helius Event
    # --------------------------------------------------------

    _log(
        f"🔎 V5.1 Helius Event | "
        f"{name} ({symbol}) | "
        f"{signature[:12]}..."
    )

    # --------------------------------------------------------
    # Get transaction
    # --------------------------------------------------------

    transaction = _get_transaction(
        signature
    )

    if not transaction:
        return

    # --------------------------------------------------------
    # Validate mint
    # --------------------------------------------------------

    if not _transaction_contains_mint(
        transaction,
        mint,
    ):

        _log(
            f"⚠️ V5.1 Helius Event | "
            f"mint doğrulanamadı | "
            f"{mint[:12]}..."
        )

        return

    # --------------------------------------------------------
    # Parser
    # --------------------------------------------------------

    parsed = _parse_transaction(
        signature,
        transaction,
    )

    # --------------------------------------------------------
    # Anatomy
    # --------------------------------------------------------

    _transaction_anatomy(
        signature,
        parsed,
    )

    # --------------------------------------------------------
    # Parser Check
    # --------------------------------------------------------

    _parser_check(
        signature,
        mint,
        parsed,
    )

    # --------------------------------------------------------
    # Activity Event
    # --------------------------------------------------------

    _log(
        f"🎯 V5.1 ACTIVITY EVENT | "
        f"{name} ({symbol}) | "
        f"{mint[:8]}..."
    )


# ------------------------------------------------------------
# WEBSOCKET CALLBACK - OPEN
# ------------------------------------------------------------

def _on_open(ws):

    global _rate_limit_detected

    _rate_limit_detected = False

    _log(
        "🔌 Helius WebSocket bağlandı."
    )

    _log(
        "🧬 V5.1 TOKEN-BASED LOG MONITOR AKTİF"
    )

    _log(
        "🧬 V5.1 PUMP.FUN LOG SUBSCRIPTION "
        "hazır | token-bazlı"
    )

    # --------------------------------------------------------
    # Existing tracked tokens
    # --------------------------------------------------------

    with _lock:

        tokens = list(
            tracked_tokens.keys()
        )

    for mint in tokens:

        time.sleep(0.05)

        _subscribe_token(
            mint
        )


# ------------------------------------------------------------
# WEBSOCKET CALLBACK - MESSAGE
# ------------------------------------------------------------

def _on_message(
    ws,
    message,
):

    global _rate_limit_detected

    try:

        data = json.loads(
            message
        )

    except Exception:

        _log(
            "⚠️ V5.1 WebSocket JSON "
            "parse edilemedi."
        )

        return

    # --------------------------------------------------------
    # RPC ERROR
    # --------------------------------------------------------

    if "error" in data:

        error = data.get(
            "error"
        )

        _log(
            f"❌ V5.1 Helius RPC ERROR => "
            f"{error}"
        )

        if isinstance(error, dict):

            code = error.get(
                "code"
            )

            msg = str(
                error.get(
                    "message",
                    "",
                )
            ).lower()

            if (
                code == -32429
                or "max usage" in msg
                or "too many requests" in msg
            ):

                _set_rate_limit()

        return

    # --------------------------------------------------------
    # SUBSCRIPTION CONFIRMATION
    # --------------------------------------------------------

    if (
        data.get("jsonrpc") == "2.0"
        and "result" in data
        and "id" in data
        and data.get("id") is not None
    ):

        request_id = data.get(
            "id"
        )

        result = data.get(
            "result"
        )

        if isinstance(result, int):

            with _lock:

                mint = pending_subscriptions.pop(
                    request_id,
                    None
                )

                if mint:

                    active_subscriptions[
                        result
                    ] = mint

                    if mint in tracked_tokens:

                        tracked_tokens[mint][
                            "subscription_id"
                        ] = result

            if mint:

                _log(
                    f"✅ V5.1 logsSubscribe AKTİF => "
                    f"subscription={result} | "
                    f"mint={mint[:12]}..."
                )

            else:

                _log(
                    f"✅ V5.1 logsSubscribe AKTİF => "
                    f"subscription={result}"
                )

            return

    # --------------------------------------------------------
    # logsNotification
    # --------------------------------------------------------

    if (
        data.get("method")
        == "logsNotification"
    ):

        _process_log_notification(
            data
        )

        return


# ------------------------------------------------------------
# WEBSOCKET CALLBACK - ERROR
# ------------------------------------------------------------

def _on_error(
    ws,
    error,
):

    _log(
        f"❌ V5.1 Helius WebSocket ERROR => "
        f"{error}"
    )

    error_text = str(
        error
    ).lower()

    if (
        "429" in error_text
        or "too many requests" in error_text
        or "max usage" in error_text
    ):

        _set_rate_limit()


# ------------------------------------------------------------
# WEBSOCKET CALLBACK - CLOSE
# ------------------------------------------------------------

def _on_close(
    ws,
    close_status_code,
    close_msg,
):

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

    reconnect_delay = INITIAL_RECONNECT_DELAY

    while _running:

        # ----------------------------------------------------
        # Rate limit pause
        # ----------------------------------------------------

        if _rate_limit_active():

            remaining = int(
                max(
                    1,
                    _rate_limit_until
                    - time.time(),
                )
            )

            _log(
                f"⏸️ V5.1 Helius rate-limit bekleme "
                f"| {remaining}s"
            )

            time.sleep(
                min(
                    remaining,
                    10,
                )
            )

            continue

        try:

            _log(
                "🧬 V5.1 CHAIN MONITOR BAŞLATILIYOR..."
            )

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

            # WebSocket kapanınca eski subscription
            # ID'leri geçersizdir.
            with _lock:

                active_subscriptions.clear()
                pending_subscriptions.clear()

                for mint in tracked_tokens:

                    tracked_tokens[mint][
                        "subscription_id"
                    ] = None

        if not _running:
            break

        # ----------------------------------------------------
        # Rate limit varsa uzun bekle
        # ----------------------------------------------------

        if _rate_limit_active():

            _log(
                "⏸️ V5.1 Helius rate-limit nedeniyle "
                "reconnect beklemesi uygulanıyor."
            )

            time.sleep(
                min(
                    RATE_LIMIT_BACKOFF,
                    30,
                )
            )

            continue

        # ----------------------------------------------------
        # Normal reconnect
        # ----------------------------------------------------

        _log(
            f"🔄 V5.1 Helius yeniden bağlanacak... "
            f"{reconnect_delay}s"
        )

        time.sleep(
            reconnect_delay
        )

        reconnect_delay = min(
            reconnect_delay * 2,
            MAX_RECONNECT_DELAY,
        )


# ------------------------------------------------------------
# START
# ------------------------------------------------------------

def start(
    *args,
    **kwargs,
):

    global _running
    global _thread

    if _running:

        _log(
            "⚠️ V5.1 CHAIN MONITOR zaten aktif."
        )

        return _thread

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

def stop(
    *args,
    **kwargs,
):

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
