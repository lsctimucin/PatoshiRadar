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

# Helius transactionSubscribe için Pump.fun programı
PUMP_FUN_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"

WS_URL = (
    f"wss://mainnet.helius-rpc.com/"
    f"?api-key={HELIUS_API_KEY}"
)


# ============================================================
# GLOBAL DURUM
# ============================================================

WATCHED_TOKENS = set()
LOCK = threading.Lock()

_RUNNING = False
_WS = None
_SUBSCRIPTION_ID = None


# ============================================================
# TOKEN EKLE
# ============================================================

def add_token(mint):
    """
    Activity Watch tarafından izlenecek tokenı ekler.
    Helius subscription Pump.fun programını dinlediği için
    yeni tokenlar WebSocket subscription'ına tekrar eklenmez.
    Burada sadece lokal eşleştirme listesine alınırlar.
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

    print(f"🧪 V5.1 ADD_TOKEN => {mint}")
    return True


# ============================================================
# TOKENLARI AL
# ============================================================

def get_tokens():
    with LOCK:
        return list(WATCHED_TOKENS)


# ============================================================
# TOKEN EŞLEŞTİRME
# ============================================================

def _token_is_watched(token):
    if not token:
        return False

    with LOCK:
        return token in WATCHED_TOKENS


def _extract_pubkey(account):
    """
    jsonParsed accountKeys içindeki pubkey'i güvenli şekilde alır.
    """

    if isinstance(account, str):
        return account

    if isinstance(account, dict):
        return account.get("pubkey", "")

    return ""


def _extract_accounts(transaction):
    """
    Transaction message.accountKeys içinden tüm pubkey'leri çıkarır.
    """

    try:
        message = transaction["transaction"]["message"]
        account_keys = message.get("accountKeys", [])

        result = []

        for account in account_keys:
            pubkey = _extract_pubkey(account)

            if pubkey:
                result.append(pubkey)

        return result

    except Exception:
        return []


def _extract_mint_candidates(transaction):
    """
    Transaction içindeki token mint adreslerini bulmaya çalışır.

    Öncelik:
    1. Account keys
    2. Parsed token instruction içindeki mint alanları
    """

    candidates = set()

    # Account keys
    for pubkey in _extract_accounts(transaction):
        candidates.add(pubkey)

    try:
        message = transaction["transaction"]["message"]

        for instruction in message.get("instructions", []):
            parsed = instruction.get("parsed")

            if isinstance(parsed, dict):
                info = parsed.get("info", {})

                if isinstance(info, dict):
                    mint = info.get("mint")

                    if mint:
                        candidates.add(str(mint))

    except Exception:
        pass

    return candidates


# ============================================================
# PARSER
# ============================================================

def _parse_transaction(event):
    """
    Helius transactionNotification payload'ını V5.1
    parser formatına çevirir.
    """

    if not isinstance(event, dict):
        return None

    transaction = event.get("transaction")

    if not isinstance(transaction, dict):
        return None

    meta = transaction.get("meta") or {}
    tx_body = transaction.get("transaction") or {}

    message = tx_body.get("message") or {}

    account_keys = message.get("accountKeys") or []
    instructions = message.get("instructions") or []
    log_messages = meta.get("logMessages") or []

    signature = event.get("signature", "")

    slot = event.get("slot")

    fee = meta.get("fee", 0)

    err = meta.get("err")

    accounts = _extract_accounts(transaction)

    # İlk signer creator/trader adayıdır.
    signer = ""

    for account in account_keys:
        if isinstance(account, dict) and account.get("signer"):
            signer = account.get("pubkey", "")
            break

    if not signer and account_keys:
        signer = _extract_pubkey(account_keys[0])

    watched_token = ""

    candidates = _extract_mint_candidates(transaction)

    with LOCK:
        for mint in WATCHED_TOKENS:
            if mint in candidates:
                watched_token = mint
                break

    if not watched_token:
        return None

    return {
        "signature": signature,
        "slot": slot,
        "token": watched_token,
        "signer": signer,
        "fee": fee,
        "err": err,
        "account_count": len(accounts),
        "instruction_count": len(instructions),
        "log_count": len(log_messages),
        "logs": log_messages,
        "accounts": accounts,
    }


# ============================================================
# TRANSACTION ANATOMY
# ============================================================

def _print_transaction_anatomy(parsed):
    """
    Eşleşen transaction için V5.1 Transaction Anatomy çıktısı.
    """

    if not parsed:
        return

    signature = parsed["signature"]
    token = parsed["token"]
    signer = parsed["signer"]

    print("🔬 V5.1 PARSER CHECK")
    print(f"   Token      => {token}")
    print(f"   Signature  => {signature}")
    print(f"   Slot       => {parsed['slot']}")
    print(f"   Signer     => {signer}")
    print(f"   Fee        => {parsed['fee']} lamports")
    print(f"   Accounts   => {parsed['account_count']}")
    print(f"   Instructions=> {parsed['instruction_count']}")
    print(f"   Logs       => {parsed['log_count']}")
    print(f"   Error      => {parsed['err']}")

    print("🧬 V5.1 TRANSACTION ANATOMY")
    print(f"   MINT       => {token}")
    print(f"   CREATOR    => {signer}")
    print(f"   SIGNATURE  => {signature}")
    print(f"   SLOT       => {parsed['slot']}")
    print(f"   FEE        => {parsed['fee']} lamports")

    # İlk birkaç log satırını göster.
    logs = parsed.get("logs") or []

    for log in logs[:8]:
        print(f"   LOG        => {log}")


# ============================================================
# HELIUS MESAJI
# ============================================================

def on_message(ws, message):

    try:
        data = json.loads(message)

    except Exception as e:
        print(f"⚠️ V5.1 JSON PARSE ERROR => {e}")
        return

    # Helius subscription cevabı
    if data.get("id") == 1 and "result" in data:
        global _SUBSCRIPTION_ID

        _SUBSCRIPTION_ID = data.get("result")

        print(
            f"✅ V5.1 transactionSubscribe AKTİF "
            f"=> subscription={_SUBSCRIPTION_ID}"
        )

        return

    # Helius RPC error
    if "error" in data:
        print(f"❌ Helius RPC ERROR => {data['error']}")
        return

    # Transaction notification
    if data.get("method") == "transactionNotification":

        params = data.get("params") or {}
        event = params.get("result")

        if not event:
            return

        parsed = _parse_transaction(event)

        if parsed:
            _print_transaction_anatomy(parsed)

        return


# ============================================================
# WEBSOCKET OPEN
# ============================================================

def on_open(ws):

    print("🛰️ Helius WebSocket bağlandı.")

    try:

        # Pump.fun programının transactionlarını dinliyoruz.
        #
        # Böylece ADD_TOKEN sonradan geldiğinde subscription
        # değiştirmeye gerek kalmaz. Parser, gelen Pump.fun
        # transactionlarında WATCHED_TOKENS eşleşmesini yapar.

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "transactionSubscribe",
            "params": [
                {
                    "accountInclude": [PUMP_FUN_PROGRAM],
                    "failed": False,
                    "vote": False
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

        print("✅ transactionSubscribe gönderildi.")

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

    global _SUBSCRIPTION_ID

    _SUBSCRIPTION_ID = None

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
    global _WS

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
                "🧬 V5.1 CHAIN MONITOR AKTİF"
            )

            _WS = websocket.WebSocketApp(
                WS_URL,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )

            _WS.run_forever(
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

    app.py:
        from chain_monitor import add_token, start as start_chain
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
