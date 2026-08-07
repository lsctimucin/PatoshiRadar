"""
Patoshi Radar
V5.1 - Transaction Parser

Gerçek Helius transactionSubscribe verisini analiz eder.

Amaç:
- tracked_mint transaction içinde gerçekten var mı?
- Hangi programlar çalıştı?
- Hangi instruction'lar çalıştı?
- Inner instruction'lar neler?
- SOL balance değişimleri
- Token balance değişimleri
- LP / DEX sinyalleri
- First Buy sinyali
- Whale Buy sinyali
"""

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

def _safe_list(value):
    if isinstance(value, list):
        return value

    return []


def _safe_dict(value):
    if isinstance(value, dict):
        return value

    return {}


def _pubkey(value):
    """
    Solana jsonParsed account key farklı şekillerde gelebilir.

    Örnek:
        {"pubkey": "..."}
        "..."
    """

    if isinstance(value, str):
        return value

    if isinstance(value, dict):
        return value.get("pubkey", "")

    return ""


def _extract_account_keys(message):
    """
    Transaction message içindeki accountKeys listesini çıkarır.
    """

    keys = []

    for account in _safe_list(message.get("accountKeys")):
        key = _pubkey(account)

        if key:
            keys.append(key)

    return keys


def _extract_program_ids(message):
    """
    Transaction instruction'larından program ID'leri çıkarır.
    """

    program_ids = []

    for instruction in _safe_list(
        message.get("instructions")
    ):
        if not isinstance(instruction, dict):
            continue

        program_id = instruction.get("programId")

        if program_id and program_id not in program_ids:
            program_ids.append(program_id)

    return program_ids


def _extract_instructions(message):
    """
    Ana instruction'ları sade formatta çıkarır.
    """

    instructions = []

    for index, instruction in enumerate(
        _safe_list(message.get("instructions"))
    ):
        if not isinstance(instruction, dict):
            continue

        instructions.append({
            "index": index,
            "program": instruction.get("program"),
            "program_id": instruction.get("programId"),
            "accounts": instruction.get("accounts", []),
            "data": instruction.get("data"),
        })

    return instructions


def _extract_inner_instructions(meta):
    """
    Inner instruction listesini çıkarır.
    """

    inner = []

    for group in _safe_list(
        meta.get("innerInstructions")
    ):
        if not isinstance(group, dict):
            continue

        parent_index = group.get("index")

        instructions = group.get(
            "instructions",
            []
        )

        for instruction in _safe_list(instructions):

            if not isinstance(instruction, dict):
                continue

            inner.append({
                "parent_index": parent_index,
                "program": instruction.get("program"),
                "program_id": instruction.get(
                    "programId"
                ),
                "accounts": instruction.get(
                    "accounts",
                    []
                ),
                "data": instruction.get("data"),
            })

    return inner


def _extract_logs(meta):
    """
    Transaction logMessages listesini çıkarır.
    """

    logs = []

    for log in _safe_list(
        meta.get("logMessages")
    ):
        if isinstance(log, str):
            logs.append(log)

    return logs


def _extract_sol_balance_changes(meta):
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
        len(post)
    )

    for index in range(count):

        try:
            before = int(pre[index])
            after = int(post[index])

        except (
            TypeError,
            ValueError
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
            "change_sol": diff_lamports / 1_000_000_000,
        })

    return changes


def _extract_token_balance_changes(meta):
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

    for item in post:

        if not isinstance(item, dict):
            continue

        account_index = item.get(
            "accountIndex"
        )

        before_item = pre_map.get(
            account_index,
            {}
        )

        mint = item.get(
            "mint"
        )

        owner = item.get(
            "owner"
        )

        before_amount = (
            before_item
            .get("uiTokenAmount", {})
            .get("uiAmount")
        )

        after_amount = (
            item
            .get("uiTokenAmount", {})
            .get("uiAmount")
        )

        if before_amount is None:
            before_amount = 0

        if after_amount is None:
            after_amount = 0

        try:
            change = float(after_amount) - float(
                before_amount
            )

        except (
            TypeError,
            ValueError
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


def _mint_present(
    tracked_mint,
    account_keys,
    token_changes,
    instructions,
    inner_instructions,
):
    """
    tracked_mint transaction içerisinde gerçekten
    geçiyor mu kontrol eder.
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
            []
        )

        if tracked_mint in accounts:
            return True

    # --------------------------------------------------------
    # Inner instructions
    # --------------------------------------------------------

    for instruction in inner_instructions:

        accounts = instruction.get(
            "accounts",
            []
        )

        if tracked_mint in accounts:
            return True

    return False


def _detect_dex(program_ids, logs):
    """
    DEX tespiti.
    """

    text = " ".join(logs).lower()

    for program_id in program_ids:

        if program_id in RAYDIUM_PROGRAM_IDS:
            return "Raydium"

    if "raydium" in text:
        return "Raydium"

    if "orca" in text:
        return "Orca"

    if "meteora" in text:
        return "Meteora"

    if "jupiter" in text:
        return "Jupiter"

    return None


def _detect_lp(program_ids, logs):
    """
    LP / liquidity sinyali.
    """

    text = " ".join(logs).lower()

    lp_words = [
        "initialize pool",
        "initialize2",
        "add liquidity",
        "addliquidity",
        "liquidity",
        "pool initialized",
        "poolinitialize",
    ]

    for word in lp_words:

        if word in text:
            return True

    for program_id in program_ids:

        if program_id in RAYDIUM_PROGRAM_IDS:
            return True

    return False


def _detect_first_buy(
    logs,
    token_changes,
):
    """
    İlk buy için temel sinyal.

    Bu V5.1 parser seviyesinde conservative tutulur.
    Daha ileri aşamada pump.fun instruction decoding
    ile kesinleştirilebilir.
    """

    text = " ".join(logs).lower()

    buy_words = [
        "buy",
        "buy_exact",
        "swap",
        "purchase",
    ]

    has_buy_log = any(
        word in text
        for word in buy_words
    )

    if has_buy_log:
        return True

    # Token balance artışı varsa potansiyel buy
    for change in token_changes:

        try:
            amount = float(
                change.get("change", 0)
            )

        except (
            TypeError,
            ValueError
        ):
            continue

        if amount > 0:
            return True

    return False


def _detect_whale_buy(
    token_changes,
    sol_changes,
):
    """
    Basit whale sinyali.

    Şimdilik yüksek değerli token girişleri
    veya SOL çıkışları üzerinden conservative
    bir sinyal üretir.

    Eşik ileride config'e taşınabilir.
    """

    WHALE_SOL_THRESHOLD = 5.0

    # SOL hareketi
    for change in sol_changes:

        try:
            sol_change = float(
                change.get("change_sol", 0)
            )

        except (
            TypeError,
            ValueError
        ):
            continue

        if sol_change <= -WHALE_SOL_THRESHOLD:
            return True

    return False


def _estimate_amount_sol(sol_changes):
    """
    Transaction'daki en büyük SOL çıkışını
    yaklaşık işlem miktarı olarak döndürür.

    Bu kesin swap amount değildir.
    """

    largest = 0.0

    for change in sol_changes:

        try:
            value = abs(
                float(
                    change.get(
                        "change_sol",
                        0
                    )
                )
            )

        except (
            TypeError,
            ValueError
        ):
            continue

        if value > largest:
            largest = value

    return largest


# ============================================================
# MAIN PARSER
# ============================================================

def parse_transaction(
    data,
    tracked_mint=None,
):
    """
    Helius WebSocket transactionSubscribe
    mesajını parse eder.

    Beklenen yapı:

    data
      └── params
           └── result
                ├── signature
                ├── slot
                └── transaction
                     ├── transaction
                     │    └── message
                     └── meta
    """

    # ========================================================
    # BASIC VALIDATION
    # ========================================================

    if not isinstance(data, dict):
        return None

    params = data.get("params")

    if not isinstance(params, dict):
        return None

    result = params.get("result")

    if not isinstance(result, dict):
        return None

    # ========================================================
    # HELIUS TRANSACTION OBJECT
    # ========================================================

    tx_container = result.get(
        "transaction"
    )

    if not isinstance(tx_container, dict):
        return None

    transaction = tx_container.get(
        "transaction"
    )

    meta = tx_container.get(
        "meta"
    )

    if not isinstance(transaction, dict):
        return None

    if not isinstance(meta, dict):
        meta = {}

    message = transaction.get(
        "message"
    )

    if not isinstance(message, dict):
        return None

    # ========================================================
    # BASIC INFO
    # ========================================================

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

    timestamp = block_time

    if timestamp is None:
        timestamp = time.time()

    # ========================================================
    # ACCOUNT KEYS
    # ========================================================

    account_keys = _extract_account_keys(
        message
    )

    # ========================================================
    # PROGRAMS
    # ========================================================

    program_ids = _extract_program_ids(
        message
    )

    # ========================================================
    # INSTRUCTIONS
    # ========================================================

    instructions = _extract_instructions(
        message
    )

    # ========================================================
    # INNER INSTRUCTIONS
    # ========================================================

    inner_instructions = (
        _extract_inner_instructions(
            meta
        )
    )

    # ========================================================
    # LOGS
    # ========================================================

    logs = _extract_logs(
        meta
    )

    # ========================================================
    # BALANCE CHANGES
    # ========================================================

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

    # ========================================================
    # MINT MATCH
    # ========================================================

    tracked = _mint_present(
        tracked_mint=tracked_mint,
        account_keys=account_keys,
        token_changes=token_balance_changes,
        instructions=instructions,
        inner_instructions=inner_instructions,
    )

    if not tracked:
        return None

    # ========================================================
    # DETECTIONS
    # ========================================================

    dex = _detect_dex(
        program_ids,
        logs
    )

    lp_created = _detect_lp(
        program_ids,
        logs
    )

    first_buy = _detect_first_buy(
        logs,
        token_balance_changes
    )

    whale_buy = _detect_whale_buy(
        token_balance_changes,
        sol_balance_changes
    )

    amount_sol = _estimate_amount_sol(
        sol_balance_changes
    )

    # ========================================================
    # PARSER MATCH LOG
    # ========================================================

    print("")
    print("🔬 V5.1 PARSER MATCH")
    print("-" * 70)
    print(
        f"Mint       : {tracked_mint}"
    )
    print(
        f"Signature  : {signature}"
    )
    print(
        f"Slot       : {slot}"
    )
    print(
        f"Programs   : {len(program_ids)}"
    )
    print(
        f"Instructions : {len(instructions)}"
    )
    print(
        f"Inner Instructions : "
        f"{len(inner_instructions)}"
    )
    print(
        f"LP         : {lp_created}"
    )
    print(
        f"DEX        : {dex}"
    )
    print(
        f"First Buy  : {first_buy}"
    )
    print(
        f"Whale Buy  : {whale_buy}"
    )
    print(
        f"Amount SOL : {amount_sol}"
    )
    print("-" * 70)

    # ========================================================
    # TRANSACTION ANATOMY LOG
    # ========================================================

    print("")
    print("🧬 V5.1 TRANSACTION ANATOMY")
    print("-" * 70)

    print(
        f"Programs : {program_ids}"
    )

    print(
        f"Instructions : "
        f"{instructions}"
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
        f"Logs : "
        f"{logs}"
    )

    print("-" * 70)

    # ========================================================
    # FINAL EVENT
    # ========================================================

    event = {
        "tracked": True,

        "mint": tracked_mint,

        "signature": signature,

        "slot": slot,

        "timestamp": timestamp,

        "program_ids": program_ids,

        "instructions": instructions,

        "inner_instructions": inner_instructions,

        "sol_balance_changes":
            sol_balance_changes,

        "token_balance_changes":
            token_balance_changes,

        "logs": logs,

        "lp_created": lp_created,

        "dex": dex,

        "first_buy": first_buy,

        "whale_buy": whale_buy,

        "amount_sol": amount_sol,

        "raw": data,
    }

    return event
