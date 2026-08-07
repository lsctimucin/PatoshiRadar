"""
Patoshi Radar
V5.1 - Creator Activity Watch
REAL HELIUS TRANSACTION DEBUG

Akış:

PumpPortal
    ↓
Telegram alarmı
    ↓
add_token()
    ↓
60 saniyelik Activity Watch
    ↓
Helius WebSocket
    ↓
transaction_parser
    ↓
PARSER MATCH
    ↓
TRANSACTION ANATOMY
    ↓
Gerçek Helius transaction verisi
"""

import json
import threading
import time

from helius_ws import HeliusWS
from transaction_parser import parse_transaction


# ============================================================
# V5.1 AYARLARI
# ============================================================

WATCH_DURATION = 60

# Aynı anda takip edilen tokenlar
watch_tokens = {}

# Thread güvenliği
watch_lock = threading.RLock()

# Aynı transaction'ın tekrar işlenmesini önler
processed_signatures = set()
signature_lock = threading.Lock()

MAX_PROCESSED_SIGNATURES = 10000

# Her token için parser debug sayacı
# Railway logunun sonsuza kadar büyümesini önler.
MAX_PARSER_DEBUG = 10


# ============================================================
# TOKEN WATCH
# ============================================================

def add_token(mint, name="", symbol="", creator=""):
    """
    Token'ı 60 saniyelik Activity Watch'a ekler.

    İlk Telegram alarmından SONRA çağrılır.
    Bu nedenle Activity Watch ilk alarmı geciktirmez.
    """

    if not mint:
        return

    with watch_lock:

        if mint in watch_tokens:
            print(
                f"⏩ V5.1 Zaten Activity Watch'ta | {mint}"
            )
            return

        now = time.time()

        watch_tokens[mint] = {

            # Token bilgileri
            "mint": mint,
            "name": name,
            "symbol": symbol,
            "creator": creator,

            # Watch zaman bilgileri
            "watch_started_at": now,
            "watch_expires_at": now + WATCH_DURATION,

            # Activity
            "event_count": 0,
            "last_event_at": None,

            # Detection state
            "lp_found": False,
            "lp_sol": 0.0,
            "dex": None,

            "first_buy": False,
            "first_buy_at": None,

            "holders": 0,
            "whale_buy": False,

            # Event geçmişi
            "events": [],

            # Debug
            "parser_debug_count": 0,
            "anatomy_count": 0,

            # İleride kullanılacak
            "activity_update_sent": False,
        }

        print("")
        print("=" * 80)
        print("👀 V5.1 ACTIVITY WATCH BAŞLADI")
        print(f"Name    : {name}")
        print(f"Symbol  : {symbol}")
        print(f"Mint    : {mint}")
        print(f"Creator : {creator}")
        print(f"Watch   : {WATCH_DURATION}s")
        print("=" * 80)
        print("")


# ============================================================
# TOKEN REMOVE
# ============================================================

def remove_token(mint):
    """
    Token'ı Activity Watch listesinden çıkarır.
    """

    with watch_lock:
        token = watch_tokens.pop(mint, None)

    if token is None:
        return

    elapsed = time.time() - token["watch_started_at"]

    print("")
    print("=" * 80)
    print("🛑 V5.1 ACTIVITY WATCH TAMAMLANDI")
    print(f"Name    : {token['name']} ({token['symbol']})")
    print(f"Mint    : {mint}")
    print(f"Süre    : {elapsed:.1f}s")
    print(f"Events  : {token['event_count']}")
    print(f"LP      : {token['lp_found']}")
    print(f"FirstBuy: {token['first_buy']}")
    print(f"DEX     : {token['dex']}")
    print("=" * 80)
    print("")


# ============================================================
# PUBLIC HELPERS
# ============================================================

def is_watching(mint):
    """
    Token şu anda Activity Watch içinde mi?
    """

    with watch_lock:
        return mint in watch_tokens


def get_token(mint):
    """
    Token state'inin güvenli kopyasını döndürür.
    """

    with watch_lock:

        token = watch_tokens.get(mint)

        if token is None:
            return None

        return token.copy()


# ============================================================
# SIGNATURE DEDUPLICATION
# ============================================================

def _mark_signature_processed(signature):
    """
    Transaction signature daha önce işlendi mi?

    True  = daha önce işlendi
    False = ilk kez işleniyor
    """

    if not signature:
        return False

    with signature_lock:

        if signature in processed_signatures:
            return True

        processed_signatures.add(signature)

        # Belleğin sınırsız büyümesini engelle
        if len(processed_signatures) > MAX_PROCESSED_SIGNATURES:

            processed_signatures.clear()
            processed_signatures.add(signature)

        return False


# ============================================================
# REAL HELIUS TRANSACTION
# ============================================================

def _record_event(event):
    """
    Parser tarafından tracked=True dönen gerçek Helius
    transaction eventini Activity Watch state'ine kaydeder.

    İlk 3 gerçek eşleşmede tam raw Helius transaction
    Railway loguna yazılır.
    """

    if not isinstance(event, dict):
        return

    mint = event.get("mint")

    if not mint:
        return

    with watch_lock:

        token = watch_tokens.get(mint)

        if token is None:
            return

        if time.time() >= token["watch_expires_at"]:
            return

        # ----------------------------------------------------
        # EVENT SAYACI
        # ----------------------------------------------------

        token["event_count"] += 1
        token["last_event_at"] = time.time()

        event_summary = {
            "signature": event.get("signature"),
            "slot": event.get("slot"),
            "timestamp": event.get("timestamp"),
            "type": event.get("type"),
        }

        token["events"].append(event_summary)

        # ----------------------------------------------------
        # PARSER MATCH
        # ----------------------------------------------------

        print("")
        print("=" * 80)
        print("🔬 V5.1 PARSER MATCH")
        print(f"Token      : {token['name']} ({token['symbol']})")
        print(f"Mint       : {mint}")
        print(f"Signature  : {event.get('signature')}")
        print(f"Slot       : {event.get('slot')}")
        print(f"Type       : {event.get('type')}")
        print(f"Tracked    : {event.get('tracked')}")
        print("=" * 80)

        # ----------------------------------------------------
        # TRANSACTION ANATOMY
        # ----------------------------------------------------

        token["anatomy_count"] += 1

        print("")
        print("🧬 V5.1 TRANSACTION ANATOMY")
        print("-" * 80)

        anatomy_fields = [
            "signature",
            "slot",
            "timestamp",
            "type",
            "status",
            "network",
            "mint",
            "buyer",
            "seller",
            "creator",
            "dex",
            "amount_sol",
            "token_amount",
            "lp_created",
            "first_buy",
            "whale_buy",
        ]

        for field in anatomy_fields:

            if field in event:
                print(
                    f"{field:<20}: {event.get(field)}"
                )

        # ----------------------------------------------------
        # ANALYSIS
        # ----------------------------------------------------

        analysis = event.get("analysis")

        if isinstance(analysis, dict):

            print("")
            print("🧠 ANALYSIS")
            print("-" * 80)

            for key in (
                "program",
                "instruction",
                "score",
                "confidence",
                "matched",
                "reason",
                "warnings",
                "errors",
            ):

                if key in analysis:
                    print(
                        f"{key:<20}: {analysis.get(key)}"
                    )

        # ----------------------------------------------------
        # GERÇEK BLOCKCHAIN ANATOMİSİ
        # ----------------------------------------------------

        anatomy_fields = [
            "account_keys",
            "program_ids",
            "instructions",
            "inner_instructions",
            "sol_balance_changes",
            "token_balance_changes",
            "log_messages",
        ]

        print("")
        print("🔬 BLOCKCHAIN ANATOMY")
        print("-" * 80)

        for field in anatomy_fields:

            value = event.get(field)

            if value is not None:

                print("")
                print(f"### {field}")

                try:
                    print(
                        json.dumps(
                            value,
                            ensure_ascii=False,
                            indent=2,
                            default=str
                        )
                    )

                except Exception as e:

                    print(
                        f"JSON yazdırılamadı: {e}"
                    )

        # ----------------------------------------------------
        # RAW HELIUS TRANSACTION
        # ----------------------------------------------------

        raw = event.get("raw")

        if raw is not None and token["anatomy_count"] <= 3:

            print("")
            print("=" * 80)
            print("🧪 V5.1 GERÇEK HELIUS TRANSACTION")
            print("=" * 80)

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
                    "⚠️ Raw transaction JSON yazılamadı:",
                    e
                )

            print("=" * 80)
            print("🧪 TRANSACTION SONU")
            print("=" * 80)

        # ----------------------------------------------------
        # STATE UPDATE
        # ----------------------------------------------------

        if event.get("lp_created"):
            token["lp_found"] = True

        if event.get("dex"):
            token["dex"] = event["dex"]

        if event.get("first_buy"):

            if not token["first_buy"]:

                token["first_buy"] = True
                token["first_buy_at"] = time.time()

        if event.get("whale_buy"):
            token["whale_buy"] = True

        amount_sol = event.get("amount_sol")

        if (
            isinstance(amount_sol, (int, float))
            and amount_sol > 0
        ):

            token["lp_sol"] = max(
                token["lp_sol"],
                float(amount_sol)
            )

        print("")
        print(
            f"🔎 V5.1 Activity Event | "
            f"{token['name']} ({token['symbol']}) | "
            f"#{token['event_count']} | "
            f"sig={event.get('signature')}"
        )

        print("")


# ============================================================
# HELIUS EVENT
# ============================================================

def process_event(data):
    """
    Helius WebSocket'ten gelen ham transaction'ı parser'a gönderir.

    Akış:

        Helius
          ↓
        process_event
          ↓
        signature kontrolü
          ↓
        aktif mint listesi
          ↓
        transaction_parser
          ↓
        tracked=True ?
          ↓
        _record_event()
    """

    if not isinstance(data, dict):
        return

    # --------------------------------------------------------
    # PARAMS
    # --------------------------------------------------------

    params = data.get("params")

    if not isinstance(params, dict):
        return

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    result = params.get("result")

    if not isinstance(result, dict):
        return

    # --------------------------------------------------------
    # SIGNATURE
    # --------------------------------------------------------

    signature = result.get("signature")

    if _mark_signature_processed(signature):
        return

    # --------------------------------------------------------
    # AKTİF TOKENLAR
    # --------------------------------------------------------

    with watch_lock:

        active_mints = list(
            watch_tokens.keys()
        )

    if not active_mints:
        return

    # --------------------------------------------------------
    # PARSER
    # --------------------------------------------------------

    for mint in active_mints:

        with watch_lock:

            token = watch_tokens.get(mint)

            if token is None:
                continue

            if time.time() >= token["watch_expires_at"]:
                continue

        # ----------------------------------------------------
        # PARSER ÇAĞRISI
        # ----------------------------------------------------

        try:

            event = parse_transaction(
                data,
                tracked_mint=mint
            )

        except TypeError as e:

            # transaction_parser.py eski V4 ise burada anlaşılır.
            print("")
            print("=" * 80)
            print("❌ V5.1 PARSER SIGNATURE HATASI")
            print(
                "transaction_parser.py "
                "tracked_mint desteklemiyor."
            )
            print(f"Hata: {e}")
            print("=" * 80)
            print("")

            continue

        except Exception as e:

            print("")
            print("=" * 80)
            print("❌ V5.1 PARSER HATASI")
            print(f"Mint : {mint}")
            print(f"Hata : {e}")
            print("=" * 80)
            print("")

            continue

        # ----------------------------------------------------
        # PARSER NONE
        # ----------------------------------------------------

        if event is None:

            with watch_lock:

                token = watch_tokens.get(mint)

                if token is not None:

                    if (
                        token["parser_debug_count"]
                        < MAX_PARSER_DEBUG
                    ):

                        token[
                            "parser_debug_count"
                        ] += 1

                        print(
                            f"⚪ V5.1 PARSER SKIP | "
                            f"mint={mint} | "
                            f"sig={signature}"
                        )

            continue

        # ----------------------------------------------------
        # TRACKED KONTROLÜ
        # ----------------------------------------------------

        tracked = event.get("tracked", False)

        if not tracked:

            with watch_lock:

                token = watch_tokens.get(mint)

                if token is not None:

                    if (
                        token["parser_debug_count"]
                        < MAX_PARSER_DEBUG
                    ):

                        token[
                            "parser_debug_count"
                        ] += 1

                        print(
                            f"⚪ V5.1 PARSER CHECK | "
                            f"tracked=False | "
                            f"mint={mint} | "
                            f"sig={signature}"
                        )

            continue

        # ----------------------------------------------------
        # GERÇEK MATCH
        # ----------------------------------------------------

        _record_event(event)


# ============================================================
# 60 SECOND WATCH WORKER
# ============================================================

def process_token(mint, token):
    """
    60 saniyelik watch süresi dolan tokenı kapatır.
    """

    if token is None:
        return

    if time.time() < token["watch_expires_at"]:
        return

    elapsed = (
        time.time()
        - token["watch_started_at"]
    )

    print("")
    print("=" * 80)
    print("⏱️ V5.1 60 SANİYE TAMAMLANDI")
    print(f"Token     : {token['name']} ({token['symbol']})")
    print(f"Mint      : {mint}")
    print(f"Süre      : {elapsed:.1f}s")
    print(f"Events    : {token['event_count']}")
    print(f"LP        : {token['lp_found']}")
    print(f"First Buy : {token['first_buy']}")
    print(f"DEX       : {token['dex']}")
    print(
        f"ParserDbg : "
        f"{token['parser_debug_count']}"
    )
    print(
        f"Anatomy   : "
        f"{token['anatomy_count']}"
    )
    print("=" * 80)
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
        f"⚙️ V5.1 Creator Activity Worker başlatıldı | "
        f"Watch={WATCH_DURATION}s"
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
# HELIUS INSTANCE
# ============================================================

helius = HeliusWS(
    callback=process_event
)


# ============================================================
# START
# ============================================================

def start():
    """
    Helius WebSocket ve Activity Worker başlatılır.
    """

    print("")
    print("=" * 80)
    print("🛰 V5.1 CHAIN MONITOR BAŞLIYOR")
    print("=" * 80)
    print("🔗 Helius WebSocket")
    print("🧬 Transaction Parser")
    print("🔬 Parser Match")
    print("🧬 Transaction Anatomy")
    print("🧪 Real Helius Transaction")
    print("👀 60s Activity Watch")
    print("=" * 80)
    print("")

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
