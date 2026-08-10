# ============================================================
# PATOSHI RADAR V5.1
# ALCHEMY ACTIVITY WATCH
# ============================================================
#
# AKIŞ:
#
# PumpPortal
#     ↓
# Telegram alarmı
#     ↓
# add_token(mint)
#     ↓
# Alchemy HTTP Activity Watch
#     ↓
# 60 saniye izle
#     ↓
# Transaction tespiti
#     ↓
# LP / DEX / SWAP / BUY tespiti
#
# NOT:
# Bu sürüm Alchemy logsSubscribe KULLANMAZ.
# HTTP polling kullanır.
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


# ============================================================
# CONFIG
# ============================================================

ALCHEMY_API_KEY = os.getenv("ALCHEMY_API_KEY", "").strip()

HTTP_URL = (
    f"https://solana-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
)

WATCH_SECONDS = 60

# Her kaç saniyede bir yeni signature kontrol edilecek.
POLL_SECONDS = 3

# Tek token için maksimum incelenecek yeni transaction.
MAX_SIGNATURES_PER_CHECK = 10

# Aynı anda maksimum watch.
MAX_WATCHES = 100

HTTP_TIMEOUT = 10


# ============================================================
# KEYWORDS
# ============================================================

LP_KEYWORDS = [
    "initialize",
    "initialize2",
    "initialize_pool",
    "create_pool",
    "add_liquidity",
    "liquidity",
    "pool",
    "migrate",
    "migration",
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


# ============================================================
# STATE
# ============================================================

watch_tokens = {}

watch_lock = threading.Lock()

running = False

worker_thread = None

cleanup_thread = None


# ============================================================
# LOG
# ============================================================

def log(message):
    print(message, flush=True)


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
    V5.1 Activity Watch başlatır.

    app.py tarafından:

        add_token(
            mint,
            name,
            symbol,
            creator
        )
    """

    if not mint:
        log("⚠️ ALCHEMY ADD_TOKEN => mint boş.")
        return False

    now = time.time()

    with watch_lock:

        if mint in watch_tokens:
            log(
                "⚠️ ALCHEMY WATCH zaten aktif => "
                f"{mint}"
            )
            return True

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

            "seen_signatures": set(),

            "lp_detected": False,
            "dex_detected": False,
            "buy_detected": False,

            "first_event_signature": None,
            "transaction_count": 0,
        }

    log(
        "👁️ ALCHEMY ACTIVITY WATCH BAŞLADI => "
        f"{mint} | {WATCH_SECONDS}s"
    )

    log(
        "🧩 V5.1 ALCHEMY WATCH ADD_TOKEN => "
        f"{mint} | result=True"
    )

    return True


# ============================================================
# REMOVE TOKEN
# ============================================================

def remove_token(mint):

    with watch_lock:

        item = watch_tokens.pop(mint, None)

    if not item:
        return

    log(
        "🧹 ALCHEMY WATCH SONLANDI => "
        f"{mint}"
    )


# ============================================================
# ALCHEMY RPC
# ============================================================

def rpc_request(
    method,
    params,
):

    if not ALCHEMY_API_KEY:

        log(
            "❌ ALCHEMY_API_KEY bulunamadı."
        )

        return None

    payload = {
        "jsonrpc": "2.0",
        "id": int(time.time() * 1000),
        "method": method,
        "params": params,
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
                f"method={method}"
            )

            return None

        response.raise_for_status()

        data = response.json()

        if "error" in data:

            log(
                "❌ V5.1 ALCHEMY RPC ERROR => "
                f"{data['error']}"
            )

            return None

        return data.get("result")

    except Exception as e:

        log(
            "⚠️ V5.1 ALCHEMY RPC REQUEST ERROR => "
            f"{method} | {e}"
        )

        return None


# ============================================================
# GET SIGNATURES
# ============================================================

def get_signatures(mint):

    result = rpc_request(
        "getSignaturesForAddress",
        [
            mint,
            {
                "limit": MAX_SIGNATURES_PER_CHECK,
            },
        ],
    )

    if not result:
        return []

    return result


# ============================================================
# GET TRANSACTION
# ============================================================

def get_transaction(signature):

    if not signature:
        return None

    result = rpc_request(
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

    return result


# ============================================================
# TEXT NORMALIZER
# ============================================================

def normalize_text(value):

    if value is None:
        return ""

    if isinstance(value, str):
        return value.lower()

    try:

        return json.dumps(
            value,
            ensure_ascii=False,
        ).lower()

    except Exception:

        return str(value).lower()


# ============================================================
# TRANSACTION TEXT
# ============================================================

def transaction_text(tx):

    if not tx:
        return ""

    parts = []

    # --------------------------------------------------------
    # LOGS
    # --------------------------------------------------------

    meta = tx.get("meta") or {}

    logs = meta.get("logMessages") or []

    parts.extend(
        str(x)
        for x in logs
    )

    # --------------------------------------------------------
    # TRANSACTION
    # --------------------------------------------------------

    transaction = tx.get(
        "transaction"
    ) or {}

    message = transaction.get(
        "message"
    ) or {}

    instructions = message.get(
        "instructions"
    ) or []

    for instruction in instructions:

        parts.append(
            normalize_text(
                instruction
            )
        )

    # --------------------------------------------------------
    # ACCOUNT KEYS
    # --------------------------------------------------------

    account_keys = message.get(
        "accountKeys"
    ) or []

    for account in account_keys:

        parts.append(
            normalize_text(
                account
            )
        )

    return " ".join(parts).lower()


# ============================================================
# DETECT LP
# ============================================================

def detect_lp(
    mint,
    signature,
    text,
):

    if not text:
        return False

    hit = any(
        keyword in text
        for keyword in LP_KEYWORDS
    )

    if not hit:
        return False

    with watch_lock:

        item = watch_tokens.get(
            mint
        )

        if not item:
            return False

        if item["lp_detected"]:
            return False

        item["lp_detected"] = True

    log(
        "💧 V5.1 ALCHEMY LP DETECTED => "
        f"{mint} | tx={signature}"
    )

    return True


# ============================================================
# DETECT DEX
# ============================================================

def detect_dex(
    mint,
    signature,
    text,
):

    if not text:
        return False

    hit = any(
        keyword in text
        for keyword in DEX_KEYWORDS
    )

    if not hit:
        return False

    with watch_lock:

        item = watch_tokens.get(
            mint
        )

        if not item:
            return False

        if item["dex_detected"]:
            return False

        item["dex_detected"] = True

    log(
        "🏦 V5.1 ALCHEMY DEX DETECTED => "
        f"{mint} | tx={signature}"
    )

    return True


# ============================================================
# DETECT BUY / SWAP
# ============================================================

def detect_buy(
    mint,
    signature,
    text,
):

    if not text:
        return False

    hit = any(
        keyword in text
        for keyword in BUY_KEYWORDS
    )

    if not hit:
        return False

    with watch_lock:

        item = watch_tokens.get(
            mint
        )

        if not item:
            return False

        if item["buy_detected"]:
            return False

        item["buy_detected"] = True

    log(
        "🟢 V5.1 ALCHEMY FIRST BUY/SWAP "
        f"DETECTED => {mint} | tx={signature}"
    )

    return True


# ============================================================
# TRANSACTION ANALYSIS
# ============================================================

def analyze_transaction(
    mint,
    signature,
):

    tx = get_transaction(
        signature
    )

    if not tx:

        return

    with watch_lock:

        item = watch_tokens.get(
            mint
        )

        if not item:
            return

        item["transaction_count"] += 1

        if item["first_event_signature"] is None:

            item[
                "first_event_signature"
            ] = signature

    log(
        "⚡ V5.1 ALCHEMY EVENT => "
        f"{mint} | tx={signature}"
    )

    text = transaction_text(
        tx
    )

    if not text:
        return

    # --------------------------------------------------------
    # LP
    # --------------------------------------------------------

    detect_lp(
        mint,
        signature,
        text,
    )

    # --------------------------------------------------------
    # DEX
    # --------------------------------------------------------

    detect_dex(
        mint,
        signature,
        text,
    )

    # --------------------------------------------------------
    # BUY / SWAP
    # --------------------------------------------------------

    detect_buy(
        mint,
        signature,
        text,
    )

    # --------------------------------------------------------
    # TOKEN BALANCES
    # --------------------------------------------------------

    meta = tx.get(
        "meta"
    ) or {}

    pre_balances = (
        meta.get(
            "preTokenBalances"
        )
        or []
    )

    post_balances = (
        meta.get(
            "postTokenBalances"
        )
        or []
    )

    if (
        pre_balances
        or post_balances
    ):

        log(
            "🪙 V5.1 TOKEN BALANCE DATA => "
            f"{mint}"
        )

    # --------------------------------------------------------
    # ERROR
    # --------------------------------------------------------

    tx_error = meta.get(
        "err"
    )

    if tx_error:

        log(
            "⚠️ V5.1 TRANSACTION ERROR => "
            f"{mint} | tx={signature} | "
            f"err={tx_error}"
        )


# ============================================================
# POLL TOKEN
# ============================================================

def poll_token(mint):

    signatures = get_signatures(
        mint
    )

    if not signatures:
        return

    for signature_data in reversed(
        signatures
    ):

        if not isinstance(
            signature_data,
            dict,
        ):
            continue

        signature = signature_data.get(
            "signature"
        )

        if not signature:
            continue

        with watch_lock:

            item = watch_tokens.get(
                mint
            )

            if not item:
                return

            if signature in item[
                "seen_signatures"
            ]:
                continue

            item[
                "seen_signatures"
            ].add(
                signature
            )

        log(
            "🔎 V5.1 ALCHEMY TX BULUNDU => "
            f"{mint} | tx={signature}"
        )

        analyze_transaction(
            mint,
            signature,
        )


# ============================================================
# ACTIVITY WATCH LOOP
# ============================================================

def activity_watch_loop():

    log(
        "🚀 V5.1 ALCHEMY ACTIVITY WATCH "
        "BAŞLATILIYOR..."
    )

    if not ALCHEMY_API_KEY:

        log(
            "❌ ALCHEMY_API_KEY bulunamadı."
        )

        return

    log(
        "🌐 V5.1 ALCHEMY HTTP ACTIVITY WATCH AKTİF"
    )

    while running:

        with watch_lock:

            active_tokens = list(
                watch_tokens.keys()
            )

        for mint in active_tokens:

            with watch_lock:

                item = watch_tokens.get(
                    mint
                )

                if not item:
                    continue

                if time.time() >= item[
                    "expires_at"
                ]:

                    continue

            try:

                poll_token(
                    mint
                )

            except Exception as e:

                log(
                    "⚠️ V5.1 ALCHEMY WATCH ERROR => "
                    f"{mint} | {e}"
                )

        time.sleep(
            POLL_SECONDS
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

                if now >= item[
                    "expires_at"
                ]:

                    expired.append(
                        mint
                    )

        for mint in expired:

            with watch_lock:

                item = watch_tokens.get(
                    mint
                )

            if item:

                log(
                    "📊 V5.1 ALCHEMY WATCH ÖZET => "
                    f"{mint} | "
                    f"tx={item['transaction_count']} | "
                    f"LP={item['lp_detected']} | "
                    f"DEX={item['dex_detected']} | "
                    f"BUY={item['buy_detected']}"
                )

            remove_token(
                mint
            )

        time.sleep(
            2
        )


# ============================================================
# START
# ============================================================

def start():

    global running
    global worker_thread
    global cleanup_thread

    if running:

        log(
            "⚠️ ALCHEMY ACTIVITY WATCH "
            "zaten aktif."
        )

        return

    running = True

    worker_thread = threading.Thread(
        target=activity_watch_loop,
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

    log(
        "🛑 V5.1 ALCHEMY ACTIVITY WATCH "
        "DURDURULDU."
    )


# ============================================================
# STATUS
# ============================================================

def status():

    with watch_lock:

        result = {}

        for mint, item in watch_tokens.items():

            copy_item = dict(
                item
            )

            copy_item[
                "seen_signatures"
            ] = len(
                item[
                    "seen_signatures"
                ]
            )

            result[mint] = copy_item

        return result


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    start()

    while True:

        time.sleep(
            10
        )
