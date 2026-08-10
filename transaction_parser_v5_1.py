"""
Patoshi Radar
V5.1 - Transaction Parser

Görev:

- Helius logsSubscribe + getTransaction akışıyla uyumlu çalışır.
- Gerçek Solana transaction verisini güvenli şekilde ayrıştırır.
- Chain Monitor için standart event nesnesi üretir.
- tracked_mint transaction içerisinde gerçekten var mı kontrol eder.
- Programları çıkarır.
- Instruction / Inner Instruction çıkarır.
- SOL balance değişimlerini çıkarır.
- Token balance değişimlerini çıkarır.
- LP / DEX sinyallerini çıkarır.
- First Buy sinyalini çıkarır.
- Whale Buy sinyalini çıkarır.

ÖNEMLİ:

Bu parser transactionSubscribe kullanmaz.

Beklenen akış:

logsSubscribe
    ↓
signature
    ↓
getTransaction
    ↓
parse_transaction()
    ↓
V5.1 event
"""

from typing import Any, Dict, List, Optional
import time


# ============================================================
# PROGRAM IDS
# ============================================================

PUMP_PROGRAM_IDS = {
    "6EF8rrecthR5Dkzon8Nwu78HvrfCKubJ14M5uBEwF6P",
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
}

RAYDIUM_PROGRAM_IDS = {
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
}

JUPITER_PROGRAM_IDS = {
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tP7h8tT4jK3tP",
}


# ============================================================
# HELPERS
# ============================================================

def _safe_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value

    return []


def _safe_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value

    return {}


def _pubkey(value: Any) -> str:
    """
    Solana jsonParsed account key farklı şekillerde gelebilir.
    """

    if isinstance(value, str):
        return value

    if isinstance(value, dict):
        return str(value.get("pubkey", "") or "")

    return ""


# ============================================================
# ACCOUNT KEYS
# ============================================================

def _extract_account_keys(message: Dict[str, Any]) -> List[str]:
    keys = []

    for account in _safe_list(
        message.get("accountKeys")
    ):
        key = _pubkey(account)

        if key:
            keys.append(key)

    return keys


# ============================================================
# PROGRAM IDS
# ============================================================

def _extract_program_ids(
    message: Dict[str, Any],
    inner_instructions: Optional[List[Dict[str, Any]]] = None,
) -> List[str]:
    """
    Ana ve inner instruction'lardan program ID'lerini çıkarır.
    """

    program_ids = []

    def add_program(program_id: Any):

        if not program_id:
            return

        program_id = str(program_id)

        if program_id not in program_ids:
            program_ids.append(program_id)

    for instruction in _safe_list(
        message.get("instructions")
    ):

        if not isinstance(instruction, dict):
            continue

        add_program(
            instruction.get("programId")
        )

    for instruction in inner_instructions or []:

        if not isinstance(instruction, dict):
            continue

        add_program(
            instruction.get("program_id")
        )

    return program_ids


# ============================================================
# MAIN INSTRUCTIONS
# ============================================================

def _extract_instructions(
    message: Dict[str, Any]
) -> List[Dict[str, Any]]:

    instructions = []

    for index, instruction in enumerate(
        _safe_list(
            message.get("instructions")
        )
    ):

        if not isinstance(instruction, dict):
            continue

        instructions.append({
            "index": index,
            "program": instruction.get("program"),
            "program_id": instruction.get("programId"),
            "accounts": instruction.get("accounts", []),
            "data": instruction.get("data"),
            "parsed": instruction.get("parsed"),
        })

    return instructions


# ============================================================
# INNER INSTRUCTIONS
# ============================================================

def _extract_inner_instructions(
    meta: Dict[str, Any]
) -> List[Dict[str, Any]]:

    inner = []

    for group in _safe_list(
        meta.get("innerInstructions")
    ):

        if not isinstance(group, dict):
            continue

        parent_index = group.get("index")

        instructions = group.get(
            "instructions",
            [],
        )

        for instruction in _safe_list(
            instructions
        ):

            if not isinstance(instruction, dict):
                continue

            inner.append({
                "parent_index": parent_index,
                "program": instruction.get("program"),
                "program_id": instruction.get("programId"),
                "accounts": instruction.get(
                    "accounts",
                    [],
                ),
                "data": instruction.get("data"),
                "parsed": instruction.get("parsed"),
            })

    return inner


# ============================================================
# LOGS
# ============================================================

def _extract_logs(
    meta: Dict[str, Any]
) -> List[str]:

    logs = []

    for log in _safe_list(
        meta.get("logMessages")
    ):

        if isinstance(log, str):
            logs.append(log)

    return logs


# ============================================================
# SOL BALANCE CHANGES
# ============================================================

def _extract_sol_balance_changes(
    meta: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    preBalances / postBalances farklarını çıkarır.

    Lamports -> SOL
    """

    pre = _safe_list(
        meta.get("preBalances")
    )

    post = _safe_list(
        meta.get("postBalances")
    )

    changes = []

    count = min(
        len(pre),
        len(post),
    )

    for index in range(count):

        try:

            before = int(pre[index])
            after = int(post[index])

        except (
            TypeError,
            ValueError,
        ):

            continue

        diff_lamports = after - before

        if diff_lamports == 0:
            continue

        changes.append({
            "account_index": index,
            "before_lamports": before,
            "after_lamports": after,
            "change_lamports": diff_lamports,
            "change_sol": (
                diff_lamports / 1_000_000_000
            ),
        })

    return changes


# ============================================================
# TOKEN BALANCE CHANGES
# ============================================================

def _extract_token_balance_changes(
    meta: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    preTokenBalances / postTokenBalances farklarını çıkarır.
    """

    pre = _safe_list(
        meta.get("preTokenBalances")
    )

    post = _safe_list(
        meta.get("postTokenBalances")
    )

    changes = []

    pre_map = {}

    for item in pre:

        if not isinstance(item, dict):
            continue

        account_index = item.get(
            "accountIndex"
        )

        pre_map[account_index] = item

    post_map = {}

    for item in post:

        if not isinstance(item, dict):
            continue

        account_index = item.get(
            "accountIndex"
        )

        post_map[account_index] = item

    all_indexes = set(
        pre_map.keys()
    ) | set(
        post_map.keys()
    )

    for account_index in all_indexes:

        before_item = pre_map.get(
            account_index,
            {},
        )

        after_item = post_map.get(
            account_index,
            {},
        )

        mint = (
            after_item.get("mint")
            or before_item.get("mint")
        )

        owner = (
            after_item.get("owner")
            or before_item.get("owner")
        )

        before_amount = (
            before_item
            .get("uiTokenAmount", {})
            .get("uiAmount")
        )

        after_amount = (
            after_item
            .get("uiTokenAmount", {})
            .get("uiAmount")
        )

        if before_amount is None:
            before_amount = 0

        if after_amount is None:
            after_amount = 0

        try:

            change = (
                float(after_amount)
                - float(before_amount)
            )

        except (
            TypeError,
            ValueError,
        ):

            continue

        if change == 0:
            continue

        changes.append({
            "account_index": account_index,
            "mint": mint,
            "owner": owner,
            "before": before_amount,
            "after": after_amount,
            "change": change,
        })

    return changes


# ============================================================
# MINT MATCH
# ============================================================

def _mint_present(
    tracked_mint: Optional[str],
    account_keys: List[str],
    token_changes: List[Dict[str, Any]],
    instructions: List[Dict[str, Any]],
    inner_instructions: List[Dict[str, Any]],
    logs: Optional[List[str]] = None,
) -> bool:
    """
    tracked_mint transaction içerisinde gerçekten geçiyor mu?
    """

    if not tracked_mint:
        return False

    # --------------------------------------------------------
    # Account keys
    # --------------------------------------------------------

    if tracked_mint in account_keys:
        return True

    # --------------------------------------------------------
    # Token balances
    # --------------------------------------------------------

    for item in token_changes:

        if item.get("mint") == tracked_mint:
            return True

    # --------------------------------------------------------
    # Main instructions
    # --------------------------------------------------------

    for instruction in instructions:

        accounts = instruction.get(
            "accounts",
            [],
        )

        if tracked_mint in accounts:
            return True

        parsed = instruction.get(
            "parsed"
        )

        if isinstance(parsed, dict):

            info = parsed.get(
                "info"
            )

            if isinstance(info, dict):

                if (
                    info.get("mint")
                    == tracked_mint
                ):
                    return True

    # --------------------------------------------------------
    # Inner instructions
    # --------------------------------------------------------

    for instruction in inner_instructions:

        accounts = instruction.get(
            "accounts",
            [],
        )

        if tracked_mint in accounts:
            return True

        parsed = instruction.get(
            "parsed"
        )

        if isinstance(parsed, dict):

            info = parsed.get(
                "info"
            )

            if isinstance(info, dict):

                if (
                    info.get("mint")
                    == tracked_mint
                ):
                    return True

    # --------------------------------------------------------
    # Logs
    # --------------------------------------------------------

    for log in logs or []:

        if tracked_mint in str(log):
            return True

    return False


# ============================================================
# DEX DETECTION
# ============================================================

def _detect_dex(
    program_ids: List[str],
    logs: List[str],
) -> Optional[str]:
    """
    DEX tespiti.

    Öncelik:
    1. Program ID
    2. Log metni
    """

    text = " ".join(
        logs
    ).lower()

    # Raydium
    for program_id in program_ids:

        if program_id in RAYDIUM_PROGRAM_IDS:
            return "Raydium"

    if "raydium" in text:
        return "Raydium"

    # Jupiter
    for program_id in program_ids:

        if program_id in JUPITER_PROGRAM_IDS:
            return "Jupiter"

    if "jupiter" in text:
        return "Jupiter"

    # Orca
    if "orca" in text:
        return "Orca"

    # Meteora
    if "meteora" in text:
        return "Meteora"

    return None


# ============================================================
# LP DETECTION
# ============================================================

def _detect_lp(
    program_ids: List[str],
    logs: List[str],
) -> bool:
    """
    LP / liquidity sinyali.

    Conservative detection.
    """

    text = " ".join(
        logs
    ).lower()

    lp_words = [
        "initialize pool",
        "initialize2",
        "initialize pool2",
        "add liquidity",
        "addliquidity",
        "liquidity",
        "pool initialized",
        "poolinitialize",
        "create pool",
        "create_pool",
    ]

    for word in lp_words:

        if word in text:
            return True

    for program_id in program_ids:

        if program_id in RAYDIUM_PROGRAM_IDS:
            return True

    return False


# ============================================================
# BUY / SELL LOG DETECTION
# ============================================================

def _detect_trade_type(
    logs: List[str],
    instructions: List[Dict[str, Any]],
    inner_instructions: List[Dict[str, Any]],
) -> str:
    """
    Transaction'ın temel trade tipini belirler.

    Şimdilik conservative:
    BUY / SELL / SWAP / UNKNOWN
    """

    text = " ".join(
        logs
    ).lower()

    # SELL önce kontrol edilir.
    # Çünkü bazı transaction'larda swap kelimesi
    # birlikte bulunabilir.

    sell_words = [
        "sell",
        "sell_exact",
        "selling",
    ]

    for word in sell_words:

        if word in text:
            return "SELL"

    buy_words = [
        "buy",
        "buy_exact",
        "purchase",
        "purchasing",
    ]

    for word in buy_words:

        if word in text:
            return "BUY"

    if "swap" in text:
        return "SWAP"

    # Parsed instruction kontrolü
    all_instructions = (
        instructions
        + inner_instructions
    )

    for instruction in all_instructions:

        parsed = instruction.get(
            "parsed"
        )

        if not isinstance(parsed, dict):
            continue

        instruction_type = str(
            parsed.get(
                "type",
                "",
            )
        ).lower()

        if "sell" in instruction_type:
            return "SELL"

        if "buy" in instruction_type:
            return "BUY"

        if "swap" in instruction_type:
            return "SWAP"

    return "UNKNOWN"


# ============================================================
# FIRST BUY
# ============================================================

def _detect_first_buy(
    trade_type: str,
    token_changes: List[Dict[str, Any]],
) -> bool:
    """
    İlk buy için temel sinyal.

    Gerçek first-buy sıralaması Chain Monitor tarafında
    Activity Watch içerisinde takip edilecektir.

    Parser burada transaction'ın BUY olduğunu
    ve token girişini kontrol eder.
    """

    if trade_type != "BUY":
        return False

    for change in token_changes:

        try:

            amount = float(
                change.get(
                    "change",
                    0,
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            continue

        if amount > 0:
            return True

    return False


# ============================================================
# WHALE BUY
# ============================================================

def _detect_whale_buy(
    trade_type: str,
    sol_changes: List[Dict[str, Any]],
) -> bool:
    """
    Conservative whale buy sinyali.

    Şimdilik 5 SOL eşik kullanılır.
    """

    if trade_type != "BUY":
        return False

    WHALE_SOL_THRESHOLD = 5.0

    for change in sol_changes:

        try:

            sol_change = float(
                change.get(
                    "change_sol",
                    0,
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            continue

        # Buyer tarafında SOL azalması
        if sol_change <= -WHALE_SOL_THRESHOLD:
            return True

    return False


# ============================================================
# AMOUNT SOL
# ============================================================

def _estimate_amount_sol(
    sol_changes: List[Dict[str, Any]]
) -> float:
    """
    Transaction'daki en büyük SOL hareketini
    yaklaşık amount olarak döndürür.

    Bu kesin swap amount değildir.
    """

    largest = 0.0

    for change in sol_changes:

        try:

            value = abs(
                float(
                    change.get(
                        "change_sol",
                        0,
                    )
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            continue

        if value > largest:
            largest = value

    return largest


# ============================================================
# TOKEN AMOUNT
# ============================================================

def _estimate_token_amount(
    tracked_mint: Optional[str],
    token_changes: List[Dict[str, Any]],
) -> float:
    """
    Takip edilen mint için toplam pozitif token
    hareketini hesaplar.
    """

    if not tracked_mint:
        return 0.0

    largest_positive = 0.0

    for change in token_changes:

        if change.get(
            "mint"
        ) != tracked_mint:
            continue

        try:

            amount = float(
                change.get(
                    "change",
                    0,
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            continue

        if amount > largest_positive:
            largest_positive = amount

    return largest_positive


# ============================================================
# PROGRAM CLASSIFICATION
# ============================================================

def _classify_program(
    program_ids: List[str]
) -> Optional[str]:

    for program_id in program_ids:

        if program_id in PUMP_PROGRAM_IDS:
            return "pump.fun"

        if program_id in RAYDIUM_PROGRAM_IDS:
            return "Raydium"

        if program_id in JUPITER_PROGRAM_IDS:
            return "Jupiter"

    return None


# ============================================================
# MAIN PARSER
# ============================================================

def parse_transaction(
    data: Dict[str, Any],
    tracked_mint: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    logsSubscribe + getTransaction uyumlu parser.

    Beklenen data:

    {
        "params": {
            "result": {
                "signature": "...",
                "transaction": {
                    "transaction": {...},
                    "meta": {...}
                }
            }
        }
    }

    Ayrıca doğrudan getTransaction sonucu verilmesini
    de destekler.
    """

    try:

        if not isinstance(data, dict):
            return None

        # ====================================================
        # INPUT NORMALIZATION
        # ====================================================

        params = data.get(
            "params"
        )

        # ----------------------------------------------------
        # logsSubscribe / wrapper format
        # ----------------------------------------------------

        if isinstance(params, dict):

            result = params.get(
                "result"
            )

            if not isinstance(result, dict):
                return None

            # logsNotification formatında:
            #
            # result
            #   └── value
            #        └── signature
            #
            # Burada transaction henüz yoktur.
            #
            # Bu parser getTransaction verisi bekler.

            if "value" in result:
                return None

        else:

            result = data.get(
                "result"
            )

            if not isinstance(result, dict):
                result = data

        # ====================================================
        # TRANSACTION OBJECT
        # ====================================================

        tx_container = result.get(
            "transaction"
        )

        # ----------------------------------------------------
        # Helius getTransaction / transactionSubscribe
        # ----------------------------------------------------

        if isinstance(
            tx_container,
            dict,
        ):

            # Helius transactionSubscribe formatı
            if isinstance(
                tx_container.get("transaction"),
                dict,
            ):

                transaction = (
                    tx_container
                    .get("transaction")
                )

                meta = (
                    tx_container
                    .get("meta")
                )

            # Standart getTransaction formatı
            elif isinstance(
                tx_container.get("message"),
                dict,
            ):

                transaction = tx_container
                meta = result.get(
                    "meta"
                )

            else:

                return None

        else:

            # Doğrudan transaction object
            if isinstance(
                result.get("message"),
                dict,
            ):

                transaction = result
                meta = result.get(
                    "meta"
                )

            else:

                return None

        if not isinstance(
            transaction,
            dict,
        ):
            return None

        if not isinstance(
            meta,
            dict,
        ):
            meta = {}

        message = transaction.get(
            "message"
        )

        if not isinstance(
            message,
            dict,
        ):
            return None

        # ====================================================
        # BASIC INFO
        # ====================================================

        signature = result.get(
            "signature"
        )

        slot = result.get(
            "slot"
        )

        block_time = result.get(
            "blockTime"
        )

        if block_time is None:

            block_time = result.get(
                "block_time"
            )

        timestamp = (
            block_time
            if block_time is not None
            else time.time()
        )

        # ====================================================
        # ACCOUNT KEYS
        # ====================================================

        account_keys = (
            _extract_account_keys(
                message
            )
        )

        # ====================================================
        # INNER INSTRUCTIONS
        # ====================================================

        inner_instructions = (
            _extract_inner_instructions(
                meta
            )
        )

        # ====================================================
        # PROGRAMS
        # ====================================================

        program_ids = (
            _extract_program_ids(
                message,
                inner_instructions,
            )
        )

        # ====================================================
        # INSTRUCTIONS
        # ====================================================

        instructions = (
            _extract_instructions(
                message
            )
        )

        # ====================================================
        # LOGS
        # ====================================================

        logs = _extract_logs(
            meta
        )

        # ====================================================
        # BALANCE CHANGES
        # ====================================================

        sol_balance_changes = (
            _extract_sol_balance_changes(
                meta
            )
        )

        token_balance_changes = (
            _extract_token_balance_changes(
                meta
            )
        )

        # ====================================================
        # MINT MATCH
        # ====================================================

        tracked = _mint_present(
            tracked_mint=tracked_mint,
            account_keys=account_keys,
            token_changes=token_balance_changes,
            instructions=instructions,
            inner_instructions=inner_instructions,
            logs=logs,
        )

        if tracked_mint and not tracked:
            return None

        # ====================================================
        # DETECTIONS
        # ====================================================

        dex = _detect_dex(
            program_ids,
            logs,
        )

        lp_created = _detect_lp(
            program_ids,
            logs,
        )

        trade_type = _detect_trade_type(
            logs,
            instructions,
            inner_instructions,
        )

        first_buy = _detect_first_buy(
            trade_type,
            token_balance_changes,
        )

        whale_buy = _detect_whale_buy(
            trade_type,
            sol_balance_changes,
        )

        amount_sol = _estimate_amount_sol(
            sol_balance_changes
        )

        token_amount = _estimate_token_amount(
            tracked_mint,
            token_balance_changes,
        )

        program = _classify_program(
            program_ids
        )

        # ====================================================
        # PARSER MATCH LOG
        # ====================================================

        print("")
        print("=" * 80)
        print("🔬 V5.1 PARSER MATCH")
        print("=" * 80)

        print(
            f"Mint              : {tracked_mint}"
        )

        print(
            f"Signature         : {signature}"
        )

        print(
            f"Slot              : {slot}"
        )

        print(
            f"Program           : {program}"
        )

        print(
            f"Programs          : {len(program_ids)}"
        )

        print(
            f"Instructions      : "
            f"{len(instructions)}"
        )

        print(
            f"Inner Instructions: "
            f"{len(inner_instructions)}"
        )

        print(
            f"Trade Type        : "
            f"{trade_type}"
        )

        print(
            f"LP                : "
            f"{lp_created}"
        )

        print(
            f"DEX               : "
            f"{dex}"
        )

        print(
            f"First Buy         : "
            f"{first_buy}"
        )

        print(
            f"Whale Buy         : "
            f"{whale_buy}"
        )

        print(
            f"Amount SOL        : "
            f"{amount_sol}"
        )

        print(
            f"Token Amount      : "
            f"{token_amount}"
        )

        print("=" * 80)

        # ====================================================
        # TRANSACTION ANATOMY
        # ====================================================

        print("")
        print("🧬 V5.1 TRANSACTION ANATOMY")
        print("-" * 80)

        print(
            f"Programs : {program_ids}"
        )

        print(
            f"Instructions : {instructions}"
        )

        print(
            f"Inner Instructions : "
            f"{len(inner_instructions)}"
        )

        print(
            f"SOL Changes : "
            f"{sol_balance_changes}"
        )

        print(
            f"Token Changes : "
            f"{token_balance_changes}"
        )

        print(
            f"Logs : {logs}"
        )

        print("-" * 80)

        # ====================================================
        # FINAL EVENT
        # ====================================================

        event = {
            "version": "5.1",

            "network": "mainnet",

            "tracked": tracked,

            "mint": tracked_mint,

            "signature": signature,

            "slot": slot,

            "timestamp": timestamp,

            "type": trade_type,

            "status": (
                "FAILED"
                if meta.get("err")
                else "CONFIRMED"
            ),

            "program": program,

            "program_ids": program_ids,

            "instructions": instructions,

            "inner_instructions": (
                inner_instructions
            ),

            "sol_balance_changes": (
                sol_balance_changes
            ),

            "token_balance_changes": (
                token_balance_changes
            ),

            "logs": logs,

            "dex": dex,

            "lp_created": lp_created,

            "first_buy": first_buy,

            "whale_buy": whale_buy,

            "amount_sol": amount_sol,

            "token_amount": token_amount,

            "buyer": None,

            "seller": None,

            "creator": None,

            "analysis": {
                "engine": "Patoshi Radar",
                "version": "5.1",
                "program": program,
                "instruction": trade_type,
                "score": 0,
                "confidence": 0,
                "matched": [],
                "reason": [],
                "warnings": [],
                "errors": [],
            },

            "raw": data,
        }

        return event

    except Exception as exc:

        print(
            "❌ V5.1 Transaction Parser Hatası"
        )

        print(
            f"Type: {type(exc).__name__}"
        )

        print(
            f"Error: {exc}"
        )

        return None
