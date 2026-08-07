"""
Patoshi Radar
V5.1 - Creator Activity Watch

Helius WebSocket
    ↓
transaction_parser_v5_1
    ↓
tracked mint
    ↓
Activity Watch
    ↓
Transaction Anatomy
"""

import json
import threading
import time

from helius_ws import HeliusWS
from transaction_parser_v5_1 import parse_transaction


WATCH_DURATION = 60


# ============================================================
# WATCH STATE
# ============================================================

watch_tokens = {}

watch_lock = threading.RLock()


# ============================================================
# PROCESSED TRANSACTIONS
# ============================================================

processed_signatures = set()

signature_lock = threading.Lock()

MAX_PROCESSED_SIGNATURES = 10000


# ============================================================
# ADD TOKEN
# ============================================================

def add_token(mint, name="", symbol="", creator=""):
    """
    Token'ı 60 saniyelik Activity Watch'a ekler.
    """

    if not mint:
        return

    with watch_lock:

        if mint in watch_tokens:
            print(
                f"⏩ Zaten Activity Watch'ta: {mint}"
            )
            return

        now = time.time()

        watch_tokens[mint] = {

            "mint": mint,
            "name": name,
            "symbol": symbol,
            "creator": creator,

            "watch_started_at": now,
            "watch_expires_at": now + WATCH_DURATION,

            "event_count": 0,
            "last_event_at": None,

            # Detection
            "lp_found": False,
            "lp_sol": 0.0,

            "dex": None,

            "first_buy": False,
            "first_buy_at": None,

            "holders": 0,

            "whale_buy": False,

            # Event history
            "events": [],

            "activity_update_sent": False,
        }

        print(
            f"👀 V5.1 Activity Watch başladı | "
            f"{name} ({symbol}) | "
            f"{mint} | "
            f"{WATCH_DURATION}s"
        )


# ============================================================
# REMOVE TOKEN
# ============================================================

def remove_token(mint):
    """
    Token'ı Activity Watch listesinden çıkarır.
    """

    with watch_lock:

        token = watch_tokens.pop(mint, None)

    if token is None:
        return

    elapsed = (
        time.time()
        - token["watch_started_at"]
    )

    print(
        f"🛑 Activity Watch tamamlandı | "
        f"{token['name']} ({token['symbol']}) | "
        f"{elapsed:.1f}s | "
        f"Events={token['event_count']} | "
        f"LP={token['lp_found']} | "
        f"FirstBuy={token['first_buy']} | "
        f"DEX={token['dex']}"
    )


# ============================================================
# IS WATCHING
# ============================================================

def is_watching(mint):

    with watch_lock:
        return mint in watch_tokens


# ============================================================
# GET TOKEN
# ============================================================

def get_token(mint):
    """
    Dışarıya token state'inin kopyasını verir.
    """

    with watch_lock:

        token = watch_tokens.get(mint)

        if token is None:
            return None

        return token.copy()


# ============================================================
# SIGNATURE CONTROL
# ============================================================

def _mark_signature_processed(signature):
    """
    Transaction signature daha önce işlendi mi?
    """

    if not signature:
        return False

    with signature_lock:

        if signature in processed_signatures:
            return True

        processed_signatures.add(signature)

        if (
            len(processed_signatures)
            > MAX_PROCESSED_SIGNATURES
        ):

            processed_signatures.clear()

            processed_signatures.add(
                signature
            )

        return False


# ============================================================
# RECORD EVENT
# ============================================================

def _record_event(event):
    """
    Parser'dan gelen gerçek blockchain eventini kaydeder.
    """

    mint = event.get("mint")

    if not mint:
        return

    with watch_lock:

        token = watch_tokens.get(mint)

        if token is None:
            return

        if (
            time.time()
            >= token["watch_expires_at"]
        ):
            return

        token["event_count"] += 1

        token["last_event_at"] = time.time()

        token["events"].append({

            "signature":
                event.get("signature"),

            "slot":
                event.get("slot"),

            "timestamp":
                event.get("timestamp"),

            "type":
                event.get("type"),
        })


        # ====================================================
        # RAW TRANSACTION DEBUG
        # ====================================================

        if token["event_count"] <= 3:

            print("")
            print("=" * 80)

            print(
                "🧪 V5.1 GERÇEK HELIUS TRANSACTION"
            )

            print(
                f"Token : "
                f"{token['name']} "
                f"({token['symbol']})"
            )

            print(
                f"Mint  : {mint}"
            )

            print(
                f"Event : "
                f"#{token['event_count']}"
            )

            print(
                f"Sig   : "
                f"{event.get('signature')}"
            )

            print("=" * 80)

            raw = event.get("raw")

            if raw is not None:

                try:

                    print(
                        json.dumps(
                            raw,
                            ensure_ascii=False,
                            indent=2,
                            default=str
                        )
                    )

                except Exception as e:

                    print(
                        "⚠️ Raw transaction "
                        "JSON yazılamadı:",
                        e
                    )

            print("=" * 80)

            print(
                "🧪 TRANSACTION SONU"
            )

            print("=" * 80)

            print("")


        # ====================================================
        # CURRENT DETECTION FLAGS
        # ====================================================

        if event.get("lp_created"):

            token["lp_found"] = True


        if event.get("dex"):

            token["dex"] = event["dex"]


        if (
            event.get("first_buy")
            and not token["first_buy"]
        ):

            token["first_buy"] = True

            token["first_buy_at"] = (
                time.time()
            )


        if event.get("whale_buy"):

            token["whale_buy"] = True


        amount_sol = (
            event.get("amount_sol")
        )


        if (
            isinstance(
                amount_sol,
                (int, float)
            )
            and amount_sol > 0
        ):

            token["lp_sol"] = max(
                token["lp_sol"],
                float(amount_sol)
            )


        # ====================================================
        # ACTIVITY EVENT
        # ====================================================

        print(
            f"🔎 V5.1 Activity Event | "
            f"{token['name']} "
            f"({token['symbol']}) | "
            f"#{token['event_count']} | "
            f"sig={event.get('signature')}"
        )


        # ====================================================
        # TRANSACTION ANATOMY
        # ====================================================

        print(
            "🧬 V5.1 TRANSACTION ANATOMY"
        )

        print(
            f"   Programs : "
            f"{event.get('program_ids')}"
        )

        print(
            f"   Instructions : "
            f"{event.get('instructions')}"
        )

        print(
            f"   Inner Instructions : "
            f"{len(event.get('inner_instructions') or [])}"
        )

        print(
            f"   SOL Changes : "
            f"{event.get('sol_balance_changes')}"
        )

        print(
            f"   Token Changes : "
            f"{event.get('token_balance_changes')}"
        )

        print(
            f"   Type : "
            f"{event.get('type')}"
        )

        print(
            f"   Buyer : "
            f"{event.get('buyer')}"
        )

        print(
            f"   Amount SOL : "
            f"{event.get('amount_sol')}"
        )

        print(
            f"   DEX : "
            f"{event.get('dex')}"
        )

        print(
            "----------------------------------------"
        )


# ============================================================
# PROCESS HELIUS EVENT
# ============================================================

def process_event(data):
    """
    Helius'tan gelen ham mesajı parser'a gönderir.
    """

    if not isinstance(data, dict):
        return


    params = data.get("params")

    if not isinstance(params, dict):
        return


    result = params.get("result")

    if not isinstance(result, dict):
        return


    signature = result.get(
        "signature"
    )


    if _mark_signature_processed(
        signature
    ):
        return


    # ========================================================
    # ACTIVE TOKENS
    # ========================================================

    with watch_lock:

        active_mints = list(
            watch_tokens.keys()
        )


    for mint in active_mints:

        with watch_lock:

            token = watch_tokens.get(
                mint
            )

            if token is None:
                continue

            if (
                time.time()
                >= token["watch_expires_at"]
            ):
                continue


        # ====================================================
        # PARSER
        # ====================================================

        event = parse_transaction(
            data,
            tracked_mint=mint
        )


        if event is None:
            continue


        if not event.get(
            "tracked"
        ):
            continue


        # ====================================================
        # RECORD
        # ====================================================

        _record_event(event)


# ============================================================
# PROCESS TOKEN
# ============================================================

def process_token(mint, token):
    """
    60 saniyelik watch süresi dolan tokenı kapatır.
    """

    if token is None:
        return


    if (
        time.time()
        < token["watch_expires_at"]
    ):
        return


    elapsed = (
        time.time()
        - token["watch_started_at"]
    )


    print("")

    print(
        "⏱️ V5.1 ACTIVITY WATCH SONU"
    )

    print(
        f"Token      : "
        f"{token['name']} "
        f"({token['symbol']})"
    )

    print(
        f"Mint       : "
        f"{mint}"
    )

    print(
        f"Süre       : "
        f"{elapsed:.1f}s"
    )

    print(
        f"Events     : "
        f"{token['event_count']}"
    )

    print(
        f"LP         : "
        f"{token['lp_found']}"
    )

    print(
        f"First Buy  : "
        f"{token['first_buy']}"
    )

    print(
        f"Whale Buy  : "
        f"{token['whale_buy']}"
    )

    print(
        f"DEX        : "
        f"{token['dex']}"
    )

    print("")


    remove_token(mint)


# ============================================================
# WORKER
# ============================================================

def worker():
    """
    Activity Watch timeout worker.
    """

    print(
        f"⚙️ V5.1 Creator Activity Worker "
        f"başlatıldı | Watch={WATCH_DURATION}s"
    )


    while True:

        try:

            with watch_lock:

                snapshot = list(
                    watch_tokens.items()
                )


            for mint, token in snapshot:

                process_token(
                    mint,
                    token
                )


            time.sleep(1)


        except Exception as e:

            print(
                "❌ Creator Activity Worker Hatası"
            )

            print(e)

            time.sleep(3)


# ============================================================
# HELIUS
# ============================================================

helius = HeliusWS(
    callback=process_event
)


# ============================================================
# START
# ============================================================

def start():
    """
    Helius WebSocket ve Activity Worker'ı başlatır.
    """

    print(
        "🛰 V5.1 Chain Monitor çalışıyor..."
    )


    helius.start()


    threading.Thread(
        target=worker,
        daemon=True,
        name="CreatorActivityWatch"
    ).start()


# ============================================================
# STOP
# ============================================================

def stop():
    """
    Activity Watch sistemini durdurur.
    """

    print(
        "🛑 V5.1 Chain Monitor durduruluyor..."
    )


    helius.stop()


    with watch_lock:

        watch_tokens.clear()


    with signature_lock:

        processed_signatures.clear()
