"""
Patoshi Radar
V5.1 - Creator Activity Watch

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
process_event()
    ↓
transaction_parser
    ↓
PARSER CHECK
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

# Her token için parser debug limiti
MAX_PARSER_DEBUG = 10


# ============================================================
# TOKEN WATCH
# ============================================================

def add_token(
    mint,
    name="",
    symbol="",
    creator=""
):
    """
    Token'ı 60 saniyelik Activity Watch'a ekler.

    İlk Telegram alarmından SONRA çağrılır.
    """

    if not mint:
        print("⚠️ V5.1 add_token: mint boş.")
        return

    with watch_lock:

        if mint in watch_tokens:
            print(
                f"⏩ V5.1 Zaten Activity Watch'ta | "
                f"{mint}"
            )
            return

        now = time.time()

        watch_tokens[mint] = {

            # ------------------------------------------------
            # Token
            # ------------------------------------------------
            "mint": mint,
            "name": name,
            "symbol": symbol,
            "creator": creator,

            # ------------------------------------------------
            # Watch
            # ------------------------------------------------
            "watch_started_at": now,
            "watch_expires_at": (
                now + WATCH_DURATION
            ),

            # ------------------------------------------------
            # Activity
            # ------------------------------------------------
            "event_count": 0,
            "last_event_at": None,

            # ------------------------------------------------
            # Detection state
            # ------------------------------------------------
            "lp_found": False,
            "lp_sol": 0.0,
            "dex": None,

            "first_buy": False,
            "first_buy_at": None,

            "holders": 0,
            "whale_buy": False,

            # ------------------------------------------------
            # Event history
            # ------------------------------------------------
            "events": [],

            # ------------------------------------------------
            # Debug
            # ------------------------------------------------
            "parser_debug_count": 0,
            "anatomy_count": 0,

            # ------------------------------------------------
            # Future
            # ------------------------------------------------
            "activity_update_sent": False,
        }

        print("")
        print("=" * 80)
        print("👀 V5.1 ACTIVITY WATCH BAŞLADI")
        print("=" * 80)
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

        token = watch_tokens.pop(
            mint,
            None
        )

    if token is None:
        return

    elapsed = (
        time.time()
        - token["watch_started_at"]
    )

    print("")
    print("=" * 80)
    print("🛑 V5.1 ACTIVITY WATCH TAMAMLANDI")
    print("=" * 80)

    print(
        f"Name      : "
        f"{token['name']} ({token['symbol']})"
    )

    print(
        f"Mint      : {mint}"
    )

    print(
        f"Süre      : {elapsed:.1f}s"
    )

    print(
        f"Events    : "
        f"{token['event_count']}"
    )

    print(
        f"ParserDbg : "
        f"{token['parser_debug_count']}"
    )

    print(
        f"Anatomy   : "
        f"{token['anatomy_count']}"
    )

    print(
        f"LP        : "
        f"{token['lp_found']}"
    )

    print(
        f"FirstBuy  : "
        f"{token['first_buy']}"
    )

    print(
        f"DEX       : "
        f"{token['dex']}"
    )

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

        token = watch_tokens.get(
            mint
        )

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

        processed_signatures.add(
            signature
        )

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
# HELIUS RESULT NORMALIZER
# ============================================================

def _extract_result(data):
    """
    Helius callback içindeki result nesnesini
    güvenli şekilde çıkarır.

    Beklenen yapı:

    {
        "jsonrpc": "2.0",
        "method": "...",
        "params": {
            "result": {
                ...
            }
        }
    }

    Ayrıca callback doğrudan result gönderirse
    onu da kabul eder.
    """

    if not isinstance(data, dict):
        return None

    # --------------------------------------------------------
    # Normal Helius WebSocket mesajı
    # --------------------------------------------------------

    params = data.get("params")

    if isinstance(params, dict):

        result = params.get(
            "result"
        )

        if isinstance(result, dict):
            return result

    # --------------------------------------------------------
    # Bazı callback yapılarında result doğrudan gelebilir
    # --------------------------------------------------------

    if (
        "transaction" in data
        or "meta" in data
        or "signature" in data
    ):
        return data

    return None


# ============================================================
# REAL HELIUS TRANSACTION
# ============================================================

def _record_event(event):
    """
    Parser tarafından tracked=True dönen
    gerçek Helius transaction eventini kaydeder.
    """

    if not isinstance(event, dict):
        return

    mint = event.get(
        "mint"
    )

    if not mint:
        print(
            "⚠️ V5.1 MATCH eventinde mint yok."
        )
        return

    with watch_lock:

        token = watch_tokens.get(
            mint
        )

        if token is None:
            print(
                f"⚠️ V5.1 Match geldi fakat "
                f"token artık watch listesinde değil | "
                f"{mint}"
            )
            return

        if (
            time.time()
            >= token["watch_expires_at"]
        ):
            print(
                f"⏱️ V5.1 Match geldi fakat "
                f"watch süresi dolmuş | "
                f"{mint}"
            )
            return

        # ----------------------------------------------------
        # EVENT SAYACI
        # ----------------------------------------------------

        token["event_count"] += 1

        token["last_event_at"] = (
            time.time()
        )

        event_summary = {
            "signature": event.get(
                "signature"
            ),
            "slot": event.get(
                "slot"
            ),
            "timestamp": event.get(
                "timestamp"
            ),
            "type": event.get(
                "type"
            ),
        }

        token["events"].append(
            event_summary
        )

        # ----------------------------------------------------
        # PARSER MATCH
        # ----------------------------------------------------

        print("")
        print("=" * 80)
        print("🔬 V5.1 PARSER MATCH")
        print("=" * 80)

        print(
            f"Token      : "
            f"{token['name']} "
            f"({token['symbol']})"
        )

        print(
            f"Mint       : {mint}"
        )

        print(
            f"Signature  : "
            f"{event.get('signature')}"
        )

        print(
            f"Slot       : "
            f"{event.get('slot')}"
        )

        print(
            f"Type       : "
            f"{event.get('type')}"
        )

        print(
            f"Tracked    : "
            f"{event.get('tracked')}"
        )

        print("=" * 80)

        # ----------------------------------------------------
        # TRANSACTION ANATOMY
        # ----------------------------------------------------

        token["anatomy_count"] += 1

        print("")
        print("=" * 80)
        print("🧬 V5.1 TRANSACTION ANATOMY")
        print("=" * 80)

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
                    f"{field:<20}: "
                    f"{event.get(field)}"
                )

        print("=" * 80)

        # ----------------------------------------------------
        # ANALYSIS
        # ----------------------------------------------------

        analysis = event.get(
            "analysis"
        )

        if isinstance(
            analysis,
            dict
        ):

            print("")
            print(
                "🧠 V5.1 ANALYSIS"
            )
            print(
                "-" * 80
            )

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
                        f"{key:<20}: "
                        f"{analysis.get(key)}"
                    )

        # ----------------------------------------------------
        # BLOCKCHAIN ANATOMY
        # ----------------------------------------------------

        blockchain_fields = [

            "account_keys",
            "program_ids",
            "instructions",
            "inner_instructions",
            "sol_balance_changes",
            "token_balance_changes",
            "log_messages",
        ]

        print("")
        print("=" * 80)
        print("🔬 BLOCKCHAIN ANATOMY")
        print("=" * 80)

        for field in blockchain_fields:

            value = event.get(
                field
            )

            if value is None:
                continue

            print("")
            print(
                f"### {field}"
            )

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
                    f"JSON yazdırılamadı: "
                    f"{e}"
                )

        # ----------------------------------------------------
        # RAW HELIUS TRANSACTION
        # ----------------------------------------------------

        raw = event.get(
            "raw"
        )

        if (
            raw is not None
            and token["anatomy_count"] <= 3
        ):

            print("")
            print("=" * 80)
            print(
                "🧪 V5.1 GERÇEK HELIUS TRANSACTION"
            )
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
                    "⚠️ Raw transaction "
                    "JSON yazılamadı:",
                    e
                )

            print("=" * 80)
            print(
                "🧪 TRANSACTION SONU"
            )
            print("=" * 80)

        # ----------------------------------------------------
        # STATE UPDATE
        # ----------------------------------------------------

        if event.get(
            "lp_created"
        ):
            token[
                "lp_found"
            ] = True

        if event.get(
            "dex"
        ):
            token[
                "dex"
            ] = event.get(
                "dex"
            )

        if event.get(
            "first_buy"
        ):

            if not token[
                "first_buy"
            ]:

                token[
                    "first_buy"
                ] = True

                token[
                    "first_buy_at"
                ] = time.time()

        if event.get(
            "whale_buy"
        ):

            token[
                "whale_buy"
            ] = True

        amount_sol = event.get(
            "amount_sol"
        )

        if (
            isinstance(
                amount_sol,
                (int, float)
            )
            and amount_sol > 0
        ):

            token[
                "lp_sol"
            ] = max(
                token["lp_sol"],
                float(amount_sol)
            )

        print("")
        print(
            f"🔎 V5.1 Activity Event | "
            f"{token['name']} "
            f"({token['symbol']}) | "
            f"#{token['event_count']} | "
            f"sig={event.get('signature')}"
        )

        print("")


# ============================================================
# HELIUS EVENT
# ============================================================

def process_event(data):
    """
    Helius WebSocket'ten gelen her mesajı işler.

    Debug akışı:

        Helius Event
            ↓
        RESULT CHECK
            ↓
        ACTIVE TOKEN CHECK
            ↓
        PARSER
            ↓
        PARSER CHECK
            ↓
        PARSER MATCH
            ↓
        TRANSACTION ANATOMY
    """

    # --------------------------------------------------------
    # CALLBACK KONTROL
    # --------------------------------------------------------

    if not isinstance(
        data,
        dict
    ):

        print(
            "⚠️ V5.1 Helius callback "
            "dict değil."
        )

        return

    print("")
    print(
        "🛰 V5.1 HELIUS EVENT ALINDI"
    )

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    result = _extract_result(
        data
    )

    if not isinstance(
        result,
        dict
    ):

        print(
            "⚪ V5.1 HELIUS RESULT YOK "
            "(subscription / system mesajı olabilir)"
        )

        return

    # --------------------------------------------------------
    # TRANSACTION CHECK
    # --------------------------------------------------------

    transaction = result.get(
        "transaction"
    )

    if not isinstance(
        transaction,
        dict
    ):

        print(
            "⚪ V5.1 HELIUS TRANSACTION YOK"
        )

        print(
            f"Result keys: "
            f"{list(result.keys())}"
        )

        return

    # --------------------------------------------------------
    # SIGNATURE
    # --------------------------------------------------------

    signature = result.get(
        "signature"
    )

    print(
        f"📦 V5.1 TRANSACTION ALINDI | "
        f"sig={signature}"
    )

    # --------------------------------------------------------
    # DUPLICATE
    # --------------------------------------------------------

    if _mark_signature_processed(
        signature
    ):

        print(
            f"⏩ V5.1 Duplicate transaction | "
            f"sig={signature}"
        )

        return

    # --------------------------------------------------------
    # ACTIVE TOKENS
    # --------------------------------------------------------

    with watch_lock:

        active_mints = list(
            watch_tokens.keys()
        )

    if not active_mints:

        print(
            "⚪ V5.1 Aktif Activity Watch tokenı yok."
        )

        return

    print(
        f"👀 V5.1 ACTIVE TOKENS | "
        f"{len(active_mints)}"
    )

    # --------------------------------------------------------
    # HER AKTİF MINT İÇİN PARSER
    # --------------------------------------------------------

    for mint in active_mints:

        # ----------------------------------------------------
        # TOKEN KONTROL
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # PARSER CHECK
        # ----------------------------------------------------

        print("")
        print(
            "⚪ V5.1 PARSER CHECK"
        )

        print(
            f"Mint      : {mint}"
        )

        print(
            f"Signature : {signature}"
        )

        # ----------------------------------------------------
        # PARSER ÇAĞRISI
        # ----------------------------------------------------

        try:

            event = parse_transaction(
                data,
                tracked_mint=mint
            )

        except TypeError as e:

            print("")
            print("=" * 80)
            print(
                "❌ V5.1 PARSER SIGNATURE HATASI"
            )
            print("=" * 80)

            print(
                "transaction_parser.py "
                "tracked_mint parametresini "
                "desteklemiyor."
            )

            print(
                f"Hata: {e}"
            )

            print("=" * 80)

            continue

        except Exception as e:

            print("")
            print("=" * 80)
            print(
                "❌ V5.1 PARSER HATASI"
            )
            print("=" * 80)

            print(
                f"Mint : {mint}"
            )

            print(
                f"Hata : {e}"
            )

            print("=" * 80)

            continue

        # ----------------------------------------------------
        # PARSER NONE
        # ----------------------------------------------------

        if event is None:

            with watch_lock:

                token = watch_tokens.get(
                    mint
                )

                if token is not None:

                    if (
                        token[
                            "parser_debug_count"
                        ]
                        < MAX_PARSER_DEBUG
                    ):

                        token[
                            "parser_debug_count"
                        ] += 1

                        print(
                            "⚪ V5.1 PARSER RESULT = NONE"
                        )

            continue

        # ----------------------------------------------------
        # PARSER SONUCU
        # ----------------------------------------------------

        tracked = event.get(
            "tracked",
            False
        )

        print(
            f"⚪ V5.1 PARSER CHECK SONUCU | "
            f"tracked={tracked} | "
            f"mint={mint}"
        )

        # ----------------------------------------------------
        # NOT MATCH
        # ----------------------------------------------------

        if not tracked:

            with watch_lock:

                token = watch_tokens.get(
                    mint
                )

                if token is not None:

                    if (
                        token[
                            "parser_debug_count"
                        ]
                        < MAX_PARSER_DEBUG
                    ):

                        token[
                            "parser_debug_count"
                        ] += 1

                        print(
                            f"⚪ V5.1 PARSER NO MATCH | "
                            f"mint={mint} | "
                            f"sig={signature}"
                        )

            continue

        # ----------------------------------------------------
        #
