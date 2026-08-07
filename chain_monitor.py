# ============================================================
# PATOSHI RADAR - V5.1
# CHAIN MONITOR
# Helius transactionSubscribe + Parser + Transaction Anatomy
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

WS_URL = f"wss://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"

# Pump.fun main program
PUMP_FUN_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"

WATCHED_TOKENS = set()
LOCK = threading.Lock()
_RUNNING = False
_SUBSCRIPTION_ID = None
_EVENT_COUNT = 0


# ============================================================
# TOKEN
# ============================================================

def add_token(mint):
    if not mint:
        return False

    mint = str(mint).strip()

    with LOCK:
        if mint in WATCHED_TOKENS:
            return False
        WATCHED_TOKENS.add(mint)

    print(f"🧬 V5.1 ADD_TOKEN => {mint}")
    return True


def get_tokens():
    with LOCK:
        return list(WATCHED_TOKENS)


# ============================================================
# HELPERS
# ============================================================

def _short(value, length=18):
    if not value:
        return "-"
    value = str(value)
    return value if len(value) <= length else value[:length] + "..."


def _account_key_value(account):
    if isinstance(account, str):
        return account

    if isinstance(account, dict):
        return account.get("pubkey") or account.get("address")

    return None


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


def _extract_signature(result, tx):
    return result.get("signature") or tx.get("signature") or ""


def _extract_slot(result):
    return result.get("slot") or result.get("context", {}).get("slot")


def _find_watched_mint(result, tx):
    watched = get_tokens()

    if not watched:
        return None

    strings = _collect_strings(tx)
    strings.extend(_collect_strings(result))
    string_set = set(strings)

    for mint in watched:
        if mint in string_set:
            return mint

    try:
        raw = json.dumps(tx, ensure_ascii=False)
        for mint in watched:
            if mint in raw:
                return mint
    except Exception:
        pass

    return None


def _extract_account_keys(tx):
    message = tx.get("transaction", {}).get("message", {})
    keys = message.get("accountKeys", [])

    result = []

    for key in keys:
        value = _account_key_value(key)
        if value:
            result.append(value)

    meta = tx.get("meta") or {}
    loaded = meta.get("loadedAddresses") or {}

    for key in loaded.get("writable", []) or []:
        if key not in result:
            result.append(key)

    for key in loaded.get("readonly", []) or []:
        if key not in result:
            result.append(key)

    return result


def _extract_instructions(tx):
    message = tx.get("transaction", {}).get("message", {})
    instructions = message.get("instructions", [])

    result = []

    for ix in instructions:
        if not isinstance(ix, dict):
            continue

        parsed = ix.get("parsed")
        parsed_type = parsed.get("type") if isinstance(parsed, dict) else None

        result.append({
            "program": ix.get("program"),
            "programId": ix.get("programId"),
            "parsed_type": parsed_type,
        })

    return result


def _extract_logs(tx):
    meta = tx.get("meta") or {}
    return [str(x) for x in (meta.get("logMessages") or [])]


def _extract_fee(tx):
    meta = tx.get("meta") or {}
    return meta.get("fee")


def _extract_signers(tx):
    message = tx.get("transaction", {}).get("message", {})
    keys = message.get("accountKeys", [])

    signers = []

    for key in keys:
        if not isinstance(key, dict):
            continue

        if key.get("signer") is True and key.get("pubkey"):
            signers.append(key["pubkey"])

    return signers


# ============================================================
# PARSER
# ============================================================

def parse_transaction(result):
    tx = _extract_transaction(result)

    if not tx:
        return None

    mint = _find_watched_mint(result, tx)

    if not mint:
        return None

    return {
        "signature": _extract_signature(result, tx),
        "slot": _extract_slot(result),
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

    signature = parsed.get("signature")
    mint = parsed.get("mint")
    slot = parsed.get("slot")
    fee = parsed.get("fee")
    signers = parsed.get("signers") or []
    accounts = parsed.get("accounts") or []
    instructions = parsed.get("instructions") or []
    logs = parsed.get("logs") or []

    print("🧬 V5.1 TRANSACTION ANATOMY")
    print(f"   MINT       => {mint}")
    print(f"   SIGNATURE  => {_short(signature, 24)}")
    print(f"   SLOT       => {slot if slot is not None else '-'}")
    print(f"   FEE        => {fee if fee is not None else '-'} lamports")
    print(f"   SIGNERS    => {len(signers)}")

    if signers:
        print(f"   CREATOR    => {signers[0]}")

    print(f"   ACCOUNTS   => {len(accounts)}")
    print(f"   INSTR      => {len(instructions)}")
    print(f"   LOGS       => {len(logs)}")

    for ix in instructions[:8]:
        program = ix.get("programId") or ix.get("program") or "-"
        parsed_type = ix.get("parsed_type") or "-"
        print(f"   IX         => {program} | {parsed_type}")

    print("🧬 V5.1 TRANSACTION ANATOMY END")


# ============================================================
# HELIUS MESSAGE
# ============================================================

def on_message(ws, message):
    global _EVENT_COUNT
    global _SUBSCRIPTION_ID

    try:
        data = json.loads(message)
    except Exception:
        print("⚠️ V5.1 Helius JSON parse edilemedi.")
        return

    # transactionSubscribe success response
    if data.get("id") == 1 and "result" in data:
        _SUBSCRIPTION_ID = data.get("result")
        print(
            f"✅ V5.1 transactionSubscribe AKTİF "
            f"=> subscription={_SUBSCRIPTION_ID}"
        )
        return

    # RPC error
    if "error" in data:
        print(f"❌ V5.1 Helius RPC ERROR => {data.get('error')}")
        return

    # Real transaction notification
    if data.get("method") == "transactionNotification":
        _EVENT_COUNT += 1

        params = data.get("params") or {}
        result = params.get("result")

        if not result:
            return

        signature = result.get("signature") if isinstance(result, dict) else None

        print(
            f"🛰️ Helius Event => transactionNotification "
            f"#{_EVENT_COUNT} | {_short(signature, 18)}"
        )

        parsed = parse_transaction(result)

        if not parsed:
            return

        print(
            f"🔬 V5.1 PARSER CHECK => "
            f"MINT={parsed['mint']} | "
            f"TX={_short(parsed['signature'], 18)}"
        )

        print_transaction_anatomy(parsed)
        return

    if "method" in data:
        print(f"🛰️ Helius Event => {data.get('method')}")


# ============================================================
# WEBSOCKET OPEN
# ============================================================

def on_open(ws):
    print("🛰️ Helius WebSocket bağlandı.")

    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "transactionSubscribe",
            "params": [
                {
                    "failed": False,
                    "vote": False,
                    "accountInclude": [PUMP_FUN_PROGRAM],
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

        ws.send(json.dumps(payload))

        print("🧬 V5.1 PUMP.FUN SUBSCRIPTION gönderildi.")
        print(f"🎯 Pump.fun Program => {PUMP_FUN_PROGRAM}")

    except Exception as e:
        print(f"❌ transactionSubscribe ERROR => {e}")


# ============================================================
# WEBSOCKET ERROR / CLOSE
# ============================================================

def on_error(ws, error):
    print(f"❌ Helius WebSocket ERROR => {error}")


def on_close(ws, close_status_code, close_msg):
    print(
        f"🔴 Helius WebSocket kapandı. "
        f"code={close_status_code} msg={close_msg}"
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

            print("🛰️ Helius WebSocket başlatılıyor...")

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
            print(f"❌ Helius WebSocket CRASH => {e}")

        print("🔄 Helius WebSocket yeniden bağlanacak...")
        time.sleep(5)


# ============================================================
# START
# ============================================================

def start():
    """
    app.py uyumluluğu:

        from chain_monitor import add_token, start as start_chain
    """

    global _RUNNING

    if _RUNNING:
        print("⚠️ V5.1 Chain Monitor zaten çalışıyor.")
        return

    print("🧬 V5.1 CHAIN MONITOR BAŞLATILIYOR...")

    thread = threading.Thread(
        target=_run_websocket,
        daemon=True,
    )

    thread.start()

    print("🧬 V5.1 CHAIN MONITOR AKTİF")


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    print("🧬 V5.1 CHAIN MONITOR TEST")
    start()

    while True:
        time.sleep(60)
