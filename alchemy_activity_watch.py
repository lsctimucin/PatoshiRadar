# ============================================================
# PATOSHI RADAR V5.1
# ALCHEMY ACTIVITY WATCH - HTTP/RPC FINAL
# ============================================================
#
# Akış:
# PumpPortal
#     ↓
# Telegram hemen
#     ↓
# add_token()
#     ↓
# Alchemy HTTP getSignaturesForAddress
#     ↓
# getTransaction
#     ↓
# 60 saniye
#     ↓
# LP / DEX / First Buy
#     ↓
# Telegram ikinci mesaj
#
# ENV:
# ALCHEMY_API_KEY
# ============================================================

import os
import json
import time
import threading
import requests


ALCHEMY_API_KEY = os.getenv("ALCHEMY_API_KEY", "").strip()

RPC_URL = (
    f"https://solana-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
)

WATCH_SECONDS = 60
POLL_SECONDS = 5
MAX_WATCHES = 25
SIGNATURE_LIMIT = 20
HTTP_TIMEOUT = 10

# Bilinen Raydium AMM programı.
RAYDIUM_PROGRAM_ID = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"


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
    "raydium",
    "pumpswap",
    "pump swap",
    "amm",
    "cpmm",
    "swap",
    "route",
]

BUY_KEYWORDS = [
    "buy",
    "swap",
    "exact_tokens_for_sol",
    "exact_sol_for_tokens",
]

watch_tokens = {}
watch_lock = threading.RLock()

running = False
worker_thread = None

_result_callback = None
request_id = 1000
request_lock = threading.Lock()


def log(message):
    print(message, flush=True)


def next_request_id():
    global request_id
    with request_lock:
        request_id += 1
        return request_id


def set_result_callback(callback):
    global _result_callback
    _result_callback = callback
    log("🧩 V5.1 ALCHEMY RESULT CALLBACK HAZIR.")


def _rpc(method, params):
    if not ALCHEMY_API_KEY:
        log("❌ ALCHEMY_API_KEY bulunamadı.")
        return None

    payload = {
        "jsonrpc": "2.0",
        "id": next_request_id(),
        "method": method,
        "params": params,
    }

    try:
        response = requests.post(
            RPC_URL,
            json=payload,
            timeout=HTTP_TIMEOUT,
        )

        if response.status_code == 429:
            log(f"⚠️ ALCHEMY HTTP RATE LIMIT => {method}")
            return None

        response.raise_for_status()

        data = response.json()

        if "error" in data:
            log(
                f"❌ V5.1 ALCHEMY RPC ERROR => "
                f"{data.get('error')}"
            )
            return None

        return data.get("result")

    except requests.RequestException as exc:
        log(
            f"⚠️ V5.1 ALCHEMY HTTP ERROR => "
            f"{method} | {exc}"
        )
        return None
    except Exception as exc:
        log(
            f"⚠️ V5.1 ALCHEMY RPC PARSE ERROR => "
            f"{method} | {exc}"
        )
        return None


def _collect_strings(value, result=None):
    if result is None:
        result = []

    if isinstance(value, str):
        result.append(value.lower())

    elif isinstance(value, dict):
        for item in value.values():
            _collect_strings(item, result)

    elif isinstance(value, list):
        for item in value:
            _collect_strings(item, result)

    return result


def _transaction_text(tx):
    strings = _collect_strings(tx)
    return " ".join(strings)


def _extract_program_ids(tx):
    program_ids = set()

    try:
        message = (
            tx.get("transaction", {})
            .get("message", {})
        )

        for ix in message.get("instructions", []) or []:
            if not isinstance(ix, dict):
                continue

            program_id = ix.get("programId")
            if program_id:
                program_ids.add(str(program_id))

        meta = tx.get("meta") or {}
        inner_groups = meta.get("innerInstructions") or []

        for group in inner_groups:
            for ix in group.get("instructions", []) or []:
                if not isinstance(ix, dict):
                    continue

                program_id = ix.get("programId")
                if program_id:
                    program_ids.add(str(program_id))

    except Exception:
        pass

    return program_ids


def _detect_dex(tx, text):
    text_lower = text.lower()

    if "raydium" in text_lower:
        return "Raydium"

    if RAYDIUM_PROGRAM_ID.lower() in text_lower:
        return "Raydium"

    if "pumpswap" in text_lower or "pump swap" in text_lower:
        return "PumpSwap"

    program_ids = {
        value.lower()
        for value in _extract_program_ids(tx)
    }

    if RAYDIUM_PROGRAM_ID.lower() in program_ids:
        return "Raydium"

    if any(
        keyword in text_lower
        for keyword in ("amm", "cpmm", "route", "swap")
    ):
        return "DEX"

    return None


def _detect_event(tx):
    text = _transaction_text(tx)

    lp_detected = any(
        keyword in text
        for keyword in LP_KEYWORDS
    )

    dex_name = _detect_dex(tx, text)

    dex_detected = dex_name is not None

    buy_detected = any(
        keyword in text
        for keyword in BUY_KEYWORDS
    )

    # Parsed instruction kontrolü.
    try:
        message = (
            tx.get("transaction", {})
            .get("message", {})
        )

        for ix in message.get("instructions", []) or []:
            if not isinstance(ix, dict):
                continue

            parsed = ix.get("parsed")
            if isinstance(parsed, dict):
                ix_type = str(
                    parsed.get("type", "")
                ).lower()

                if ix_type == "swap":
                    buy_detected = True

    except Exception:
        pass

    return {
        "lp_detected": lp_detected,
        "dex_detected": dex_detected,
        "dex_name": dex_name,
        "buy_detected": buy_detected,
    }


def _get_signatures(mint):
    result = _rpc(
        "getSignaturesForAddress",
        [
            mint,
            {
                "limit": SIGNATURE_LIMIT,
                "commitment": "confirmed",
            },
        ],
    )

    if not isinstance(result, list):
        return []

    return result


def _get_transaction(signature):
    return _rpc(
        "getTransaction",
        [
            signature,
            {
                "encoding": "jsonParsed",
                "commitment": "confirmed",
                "maxSupportedTransactionVersion": 0,
            },
        ],
    )


def add_token(
    mint,
    name="",
    symbol="",
    creator="",
    launch_signature="",
):
    if not mint:
        return False

    mint = str(mint).strip()

    with watch_lock:
        if mint in watch_tokens:
            log(
                f"⏩ V5.1 ALCHEMY ZATEN İZLENİYOR => {mint}"
            )
            return False

        if len(watch_tokens) >= MAX_WATCHES:
            log(
                f"⚠️ V5.1 ALCHEMY WATCH LIMIT => "
                f"MAX={MAX_WATCHES}"
            )
            return False

        now = time.time()

        watch_tokens[mint] = {
            "mint": mint,
            "name": name,
            "symbol": symbol,
            "creator": creator,
            "launch_signature": launch_signature,
            "started_at": now,
            "expires_at": now + WATCH_SECONDS,
            "seen_signatures": set(),
            "event_count": 0,
            "lp_detected": False,
            "dex_detected": False,
            "dex_name": None,
            "buy_detected": False,
            "first_buy_signature": None,
            "lp_signature": None,
            "dex_signature": None,
        }

    log(
        f"👁️ ALCHEMY ACTIVITY WATCH BAŞLADI => "
        f"{mint} | {WATCH_SECONDS}s"
    )

    return True


def _process_watch(mint, item):
    signatures = _get_signatures(mint)

    if not signatures:
        return

    for entry in reversed(signatures):
        if not isinstance(entry, dict):
            continue

        signature = entry.get("signature")
        if not signature:
            continue

        with watch_lock:
            current = watch_tokens.get(mint)

            if current is None:
                return

            if time.time() >= current["expires_at"]:
                return

            if signature in current["seen_signatures"]:
                continue

            current["seen_signatures"].add(signature)

            # PumpPortal launch transactionını analiz etmiyoruz.
            if (
                current.get("launch_signature")
                and signature == current["launch_signature"]
            ):
                continue

        tx = _get_transaction(signature)

        if not tx:
            continue

        event = _detect_event(tx)

        if not any(event.values()):
            continue

        with watch_lock:
            current = watch_tokens.get(mint)

            if current is None:
                return

            current["event_count"] += 1

            if event["lp_detected"] and not current["lp_detected"]:
                current["lp_detected"] = True
                current["lp_signature"] = signature

                log(
                    f"💧 V5.1 ALCHEMY LP DETECTED => "
                    f"{mint} | tx={signature}"
                )

            if event["dex_detected"] and not current["dex_detected"]:
                current["dex_detected"] = True
                current["dex_name"] = event["dex_name"]
                current["dex_signature"] = signature

                log(
                    f"🏛️ V5.1 ALCHEMY DEX DETECTED => "
                    f"{mint} | DEX={event['dex_name']} | "
                    f"tx={signature}"
                )

            if event["buy_detected"] and not current["buy_detected"]:
                current["buy_detected"] = True
                current["first_buy_signature"] = signature

                log(
                    f"🛒 V5.1 ALCHEMY FIRST BUY DETECTED => "
                    f"{mint} | tx={signature}"
                )

            log(
                f"⚡ V5.1 ALCHEMY EVENT => {mint} | "
                f"tx={signature} | "
                f"LP={current['lp_detected']} | "
                f"DEX={current['dex_detected']} | "
                f"BUY={current['buy_detected']}"
            )

        # Üçünün de bulunması halinde daha fazla RPC harcamıyoruz.
        with watch_lock:
            current = watch_tokens.get(mint)
            if current is None:
                return

            complete = (
                current["lp_detected"]
                and current["dex_detected"]
                and current["buy_detected"]
            )

        if complete:
            log(
                f"🎯 V5.1 ALCHEMY TÜM SİNYALLER BULUNDU => {mint}"
            )
            _finish_token(mint, early=True)
            return


def _finish_token(mint, early=False):
    with watch_lock:
        item = watch_tokens.pop(mint, None)

    if item is None:
        return

    elapsed = max(
        0,
        int(time.time() - item["started_at"])
    )

    result = {
        "mint": item["mint"],
        "name": item["name"],
        "symbol": item["symbol"],
        "creator": item["creator"],
        "lp_detected": item["lp_detected"],
        "dex_detected": item["dex_detected"],
        "dex_name": item["dex_name"],
        "buy_detected": item["buy_detected"],
        "first_buy_signature": item["first_buy_signature"],
        "lp_signature": item["lp_signature"],
        "dex_signature": item["dex_signature"],
        "event_count": item["event_count"],
        "elapsed_seconds": elapsed,
        "early": early,
    }

    log(
        f"📊 V5.1 ALCHEMY WATCH ÖZET => "
        f"{mint} | "
        f"LP={result['lp_detected']} | "
        f"DEX={result['dex_detected']} | "
        f"BUY={result['buy_detected']} | "
        f"events={result['event_count']}"
    )

    callback = _result_callback

    if callback:
        try:
            callback(result)
        except Exception as exc:
            log(
                f"❌ V5.1 ALCHEMY RESULT CALLBACK ERROR => {exc}"
            )


def cleanup_loop():
    while running:
        try:
            now = time.time()
            expired = []

            with watch_lock:
                for mint, item in list(
                    watch_tokens.items()
                ):
                    if now >= item["expires_at"]:
                        expired.append(mint)

            for mint in expired:
                _finish_token(mint, early=False)

            time.sleep(1)

        except Exception as exc:
            log(
                f"❌ V5.1 ALCHEMY CLEANUP ERROR => {exc}"
            )
            time.sleep(2)


def worker_loop():
    log(
        "🚀 V5.1 ALCHEMY HTTP ACTIVITY WATCH BAŞLATILIYOR..."
    )

    while running:
        try:
            with watch_lock:
                snapshot = list(
                    watch_tokens.items()
                )

            for mint, item in snapshot:
                if time.time() >= item["expires_at"]:
                    _finish_token(mint, early=False)
                    continue

                _process_watch(mint, item)

            time.sleep(POLL_SECONDS)

        except Exception as exc:
            log(
                f"❌ V5.1 ALCHEMY WORKER ERROR => {exc}"
            )
            time.sleep(2)


def start():
    global running
    global worker_thread

    if running:
        log(
            "⚠️ V5.1 ALCHEMY ACTIVITY WATCH zaten aktif."
        )
        return

    if not ALCHEMY_API_KEY:
        log(
            "❌ ALCHEMY_API_KEY bulunamadı. "
            "Activity Watch başlatılmadı."
        )
        return

    running = True

    log(
        "📡 V5.1 ALCHEMY HTTP ACTIVITY WATCH AKTİF"
    )

    worker_thread = threading.Thread(
        target=worker_loop,
        daemon=True,
        name="AlchemyActivityWatch",
    )
    worker_thread.start()

    threading.Thread(
        target=cleanup_loop,
        daemon=True,
        name="AlchemyActivityCleanup",
    ).start()


def stop():
    global running
    running = False

    log(
        "🛑 V5.1 ALCHEMY ACTIVITY WATCH DURDURULDU."
    )


def status():
    with watch_lock:
        result = {}

        for mint, item in watch_tokens.items():
            copied = dict(item)
            copied["seen_signatures"] = len(
                item["seen_signatures"]
            )
            result[mint] = copied

        return result


if __name__ == "__main__":
    start()

    while True:
        time.sleep(10)
