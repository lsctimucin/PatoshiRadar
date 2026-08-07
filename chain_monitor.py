# ============================================================
# PATOSHI RADAR - V5.1
# CHAIN MONITOR
# Helius transactionSubscribe
# Parser + Transaction Anatomy
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


WS_URL = (
    f"wss://mainnet.helius-rpc.com/"
    f"?api-key={HELIUS_API_KEY}"
)


# Pump.fun program
PUMP_FUN_PROGRAM = (
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
)


# ============================================================
# GLOBAL DURUM
# ============================================================

WATCHED_TOKENS = set()

LOCK = threading.Lock()

_RUNNING = False

_SUBSCRIPTION_ID = None

_EVENT_COUNT = 0


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

    if not mint:
        return False

    with LOCK:

        if mint in WATCHED_TOKENS:
            return False

        WATCHED_TOKENS.add(mint)

    print(
        f"🧬 V5.1 ADD_TOKEN => {mint}"
    )

    return True


# ============================================================
# TOKENLARI AL
# ============================================================

def get_tokens():

    with LOCK:
        return list(WATCHED_TOKENS)


# ============================================================
# YARDIMCI FONKSİYONLAR
# ============================================================

def _short(value, length=18):

    if not value:
        return "-"

    value = str(value)

    if len(value) <= length:
        return value

    return value[:length] + "..."


def _collect_strings(obj, result=None):

    if result is None:
        result = []

    if isinstance(obj, str):

        result.append(obj)

    elif isinstance(obj, dict):

        for value in obj.values():
            _collect_strings(value, result)

    elif isinstance(obj, list):

        for value in obj:
            _collect_strings(value, result)

    return result


def _account_key_value(account):

    if isinstance(account, str):
        return account

    if isinstance(account, dict):

        return (
            account.get("pubkey")
            or account.get("address")
        )

    return None


# ============================================================
# TRANSACTION ÇIKAR
# ============================================================

def _extract_transaction(result):

    if not isinstance(result, dict):
        return {}

    tx = result.get("transaction")

    if isinstance(tx, dict):
        return tx

    value = result.get("value")

    if isinstance(value, dict):

        nested = value.get("transaction")

        if isinstance(nested, dict):
            return nested

    return {}


# ============================================================
# SIGNATURE
# ============================================================

def _extract_signature(result, tx):

    return (
        result.get("signature")
        or tx.get("signature")
        or ""
    )


# ============================================================
# SLOT
# ============================================================

def _extract_slot(result):

    return (
        result.get("slot")
        or result.get("context", {}).get("slot")
    )


# ============================================================
# WATCHED TOKEN BUL
# ============================================================

def _find_watched_mint(result, tx):

    watched = get_tokens()

    if not watched:
        return None

    # Önce string alanları tara
    strings = _collect_strings(tx)

    strings.extend(
        _collect_strings(result)
    )

    string_set = set(strings)

    for mint in watched:

        if mint in string_set:
            return mint

    # Son güvenlik kontrolü
    try:

        raw = json.dumps(
            tx,
            ensure_ascii=False
        )

        for mint in watched:

            if mint in raw:
                return mint

    except Exception:
        pass

    return None


# ============================================================
# ACCOUNT KEYS
# ============================================================

def _extract_account_keys(tx):

    message = (
        tx
        .get("transaction", {})
        .get("message", {})
    )

    keys = message.get(
        "accountKeys",
        []
    )

    result = []

    for key in keys:

        value = _account_key_value(key)

        if value:
            result.append(value)

    # Versioned transaction loaded addresses
    meta = tx.get("meta") or {}

    loaded = (
        meta.get("loadedAddresses")
        or {}
    )

    for key in (
        loaded.get("writable", [])
        or []
    ):

        if key not in result:
            result.append(key)

    for key in (
        loaded.get("readonly", [])
        or []
    ):

        if key not in result:
            result.append(key)

    return result


# ============================================================
# INSTRUCTIONS
# ============================================================

def _extract_instructions(tx):

    message = (
        tx
        .get("transaction", {})
        .get("message", {})
    )

    instructions = message.get(
        "instructions",
        []
    )

    result = []

    for ix in instructions:

        if not isinstance(ix, dict):
            continue

        parsed = ix.get("parsed")

        parsed_type = None

        if isinstance(parsed, dict):
            parsed_type = parsed.get("type")

        result.append(
            {
                "program": ix.get("program"),
                "programId": ix.get("programId"),
                "parsed_type": parsed_type,
            }
        )

    return result


# ============================================================
# LOGS
# ============================================================

def _extract_logs(tx):

    meta = tx.get("meta") or {}

    return [
        str(x)
        for x in (
            meta.get("logMessages")
            or []
        )
    ]


# ============================================================
# FEE
# ============================================================

def _extract_fee(tx):

    meta = tx.get("meta") or {}

    return meta.get("fee")


# ============================================================
# SIGNERS
# ============================================================

def _extract_signers(tx):

    message = (
        tx
        .get("transaction", {})
        .get("message", {})
    )

    keys = message.get(
        "accountKeys",
        []
    )

    signers = []

    for key in keys:

        if not isinstance(key, dict):
            continue

        if (
            key.get("signer") is True
            and key.get("pubkey")
        ):

            signers.append(
                key["pubkey"]
            )

    return signers


# ============================================================
# PARSER
# ============================================================

def parse_transaction(result):

    tx = _extract_transaction(result)

    if not tx:

        print(
            "🔬 V5.1 PARSER CHECK => "
            "transaction bulunamadı."
        )

        return None

    signature = _extract_signature(
        result,
        tx
    )

    slot = _extract_slot(result)

    print(
        f"🔬 V5.1 PARSER CHECK => "
        f"TX={_short(signature, 18)} | "
        f"SLOT={slot if slot is not None else '-'}"
    )

    mint = _find_watched_mint(
        result,
        tx
    )

    if not mint:

        print(
            "🔬 V5.1 PARSER CHECK => "
            "WATCHED TOKEN MATCH YOK"
        )

        return None

    print(
        f"🎯 V5.1 PARSER MATCH => "
        f"MINT={mint}"
    )

    return {
        "signature": signature,
        "slot": slot,
        "mint": mint,
        "accounts": _extract_account_keys(tx),
        "instructions": _extract_instructions(tx),
        "logs": _extract_logs(tx),
        "fee": _extract_fee(tx),
        "signers": _extract_signers(tx),
    }


# ============================================================
# TRANSACTION ANATOMY
# ============================================================

def print_transaction_anatomy(parsed):

    if not parsed:
        return

    signature = parsed.get(
        "signature"
    )

    mint = parsed.get(
        "mint"
    )

    slot = parsed.get(
        "slot"
    )

    fee = parsed.get(
        "fee"
    )

    signers = (
        parsed.get("signers")
        or []
    )

    accounts = (
        parsed.get("accounts")
        or []
    )

    instructions = (
        parsed.get("instructions")
        or []
    )

    logs = (
        parsed.get("logs")
        or []
    )

    print(
        "🧬 V5.1 TRANSACTION ANATOMY"
    )

    print(
        f"   MINT       => {mint}"
    )

    print(
        f"   SIGNATURE  => "
        f"{_short(signature, 24)}"
    )

    print(
        f"   SLOT       => "
        f"{slot if slot is not None else '-'}"
    )

    print(
        f"   FEE        => "
        f"{fee if fee is not None else '-'} lamports"
    )

    print(
        f"   SIGNERS    => "
        f"{len(signers)}"
    )

    if signers:

        print(
            f"   CREATOR    => "
            f"{signers[0]}"
        )

    print(
        f"   ACCOUNTS   => "
        f"{len(accounts)}"
    )

    print(
        f"   INSTR      => "
        f"{len(instructions)}"
    )

    print(
        f"   LOGS       => "
        f"{len(logs)}"
    )

    for ix in instructions[:8]:

        program = (
            ix.get("programId")
            or ix.get("program")
            or "-"
        )

        parsed_type = (
            ix.get("parsed_type")
            or "-"
        )

        print(
            f"   IX         => "
            f"{program} | "
            f"{parsed_type}"
        )

    print(
        "🧬 V5.1 TRANSACTION ANATOMY END"
    )


# ============================================================
# HELIUS MESSAGE
# ============================================================

def on_message(ws, message):

    global _EVENT_COUNT
    global _SUBSCRIPTION_ID

    try:

        data = json.loads(
            message
        )

    except Exception as e:

        print(
            f"⚠️ V5.1 Helius JSON "
            f"parse edilemedi => {e}"
        )

        return

    # ========================================================
    # SUBSCRIPTION RESPONSE
    # ========================================================

    if (
        data.get("id") == 1
        and "result" in data
    ):

        _SUBSCRIPTION_ID = (
            data.get("result")
        )

        print(
            "✅ V5.1 "
            "transactionSubscribe AKTİF "
            f"=> subscription="
            f"{_SUBSCRIPTION_ID}"
        )

        return

    # ========================================================
    # RPC ERROR
    # ========================================================

    if "error" in data:

        print(
            "🛰️ Helius Event => RPC_ERROR"
        )

        print(
            "❌ V5.1 Helius RPC ERROR => "
            f"{data.get('error')}"
        )

        return

    # ========================================================
    # TRANSACTION NOTIFICATION
    # ========================================================

    if (
        data.get("method")
        == "transactionNotification"
    ):

        _EVENT_COUNT += 1

        params = (
            data.get("params")
            or {}
        )

        result = params.get(
            "result"
        )

        if not result:
            return

        signature = ""

        if isinstance(result, dict):

            signature = result.get(
                "signature"
            )

        # ----------------------------------------------------
        # HELIUS EVENT
        # ----------------------------------------------------

        print(
            f"🛰️ Helius Event => "
            f"transactionNotification "
            f"#{_EVENT_COUNT} | "
            f"{_short(signature, 18)}"
        )

        # ----------------------------------------------------
        # PARSER
        # ----------------------------------------------------

        parsed = parse_transaction(
            result
        )

        if not parsed:
            return

        # ----------------------------------------------------
        # PARSER MATCH
        # ----------------------------------------------------

        print(
            f"🔬 V5.1 PARSER MATCH => "
            f"MINT={parsed['mint']} | "
            f"TX={_short(parsed['signature'], 18)}"
        )

        # ----------------------------------------------------
        # TRANSACTION ANATOMY
        # ----------------------------------------------------

        print_transaction_anatomy(
            parsed
        )

        return

    # ========================================================
    # OTHER HELIUS EVENTS
    # ========================================================

    if "method" in data:

        print(
            f"🛰️ Helius Event => "
            f"{data.get('method')}"
        )


# ============================================================
# WEBSOCKET OPEN
# ============================================================

def on_open(ws):

    print(
        "🛰️ Helius WebSocket bağlandı."
    )

    try:

        payload = {

            "jsonrpc": "2.0",

            "id": 1,

            "method": "transactionSubscribe",

            "params": [

                {
                    "failed": False,
                    "vote": False,
                    "accountInclude": [
                        PUMP_FUN_PROGRAM
                    ],
                },

                {
                    "commitment": "confirmed",

                    "encoding": "jsonParsed",

                    "transactionDetails": "full",

                    "showRewards": False,

                    "maxSupportedTransactionVersion": 0,
                },
            ],
        }

        ws.send(
            json.dumps(payload)
        )

        print(
            "🧬 V5.1 PUMP.FUN "
            "SUBSCRIPTION gönderildi."
        )

        print(
            f"🎯 Pump.fun Program => "
            f"{PUMP_FUN_PROGRAM}"
        )

        print(
            "🔬 V5.1 PARSER CHECK => HAZIR"
        )

        print(
            "🧬 V5.1 TRANSACTION "
            "ANATOMY HAZIR"
        )

    except Exception as e:

        print(
            "❌ transactionSubscribe "
            f"ERROR => {e}"
        )


# ============================================================
# WEBSOCKET ERROR
# ============================================================

def on_error(ws, error):

    print(
        f"❌ Helius WebSocket ERROR "
        f"=> {error}"
    )


# ============================================================
# WEBSOCKET CLOSE
# ============================================================

def on_close(
    ws,
    close_status_code,
    close_msg
):

    print(
        "🔴 Helius WebSocket kapandı. "
        f"code={close_status_code} "
        f"msg={close_msg}"
    )


# ============================================================
# WEBSOCKET RUNNER
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
                "🛰️ Helius WebSocket "
                "başlatılıyor..."
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

                ping_timeout=10
            )

        except Exception as e:

            print(
                "❌ Helius WebSocket "
                f"CRASH => {e}"
            )

        print(
            "🔄 Helius WebSocket "
            "yeniden bağlanacak..."
        )

        time.sleep(5)


# ============================================================
# START
# ============================================================

def start():

    """
    app.py uyumluluğu.

    app.py:

        from chain_monitor import add_token, start as start_chain

    Bu nedenle start() mutlaka mevcut.
    """

    global _RUNNING

    if _RUNNING:

        print(
            "⚠️ V5.1 Chain Monitor "
            "zaten çalışıyor."
        )

        return

    print(
        "🧬 V5.1 CHAIN MONITOR "
        "BAŞLATILIYOR..."
    )

    thread = threading.Thread(

        target=_run_websocket,

        daemon=True,

        name="V5.1-ChainMonitor"
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
