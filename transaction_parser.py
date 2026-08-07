"""
Patoshi Radar
V5.1 - Transaction Parser / Blockchain Anatomy

Görev:

- Helius WebSocket transaction verisini ayrıştırır.
- Takip edilen mint ile transaction bağlantısını bulur.
- Instruction / Inner Instruction bilgilerini çıkarır.
- Program ID'lerini çıkarır.
- SOL balance değişimlerini çıkarır.
- Token balance değişimlerini çıkarır.
- Logları çıkarır.

ÖNEMLİ:

Bu sürüm henüz LP / DEX / First Swap sonucunu tahmin etmez.

Amaç:
Gerçek blockchain transaction yapısını çıkarmak ve
sonraki detection motorlarına temiz veri sağlamaktır.
"""

from typing import Any, Dict, Optional


# ============================================================
# HELIUS RESULT
# ============================================================

def _get_result(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Helius subscription mesajından transaction result'ını çıkarır."""

    if not isinstance(data, dict):
        return None

    params = data.get("params")

    if not isinstance(params, dict):
        return None

    result = params.get("result")

    if not isinstance(result, dict):
        return None

    return result


# ============================================================
# ACCOUNT KEYS
# ============================================================

def _get_account_keys(message: Dict[str, Any]) -> list[str]:
    """Transaction account key listesini çıkarır."""

    keys = []

    for account in message.get("accountKeys") or []:

        if isinstance(account, str):
            keys.append(account)
            continue

        if isinstance(account, dict):

            pubkey = account.get("pubkey")

            if pubkey:
                keys.append(pubkey)

    return keys


# ============================================================
# PROGRAM IDS
# ============================================================

def _extract_program_ids(message: Dict[str, Any]) -> list[str]:
    """
    Transaction instruction'larından program ID'lerini çıkarır.
    """

    programs = []

    for instruction in message.get("instructions") or []:

        if not isinstance(instruction, dict):
            continue

        program_id = instruction.get("programId")

        if program_id and program_id not in programs:
            programs.append(program_id)

        # Bazı jsonParsed yapılarda program alanı bulunabilir.
        program = instruction.get("program")

        if program and program not in programs:
            programs.append(program)

    return programs


# ============================================================
# INSTRUCTIONS
# ============================================================

def _extract_instructions(message: Dict[str, Any]) -> list[dict]:
    """
    Top-level instruction'ları sadeleştirerek çıkarır.
    """

    instructions = []

    for instruction in message.get("instructions") or []:

        if not isinstance(instruction, dict):
            continue

        parsed = instruction.get("parsed")

        item = {
            "program": instruction.get("program"),
            "programId": instruction.get("programId"),
            "parsed_type": None,
            "parsed_info": None,
        }

        if isinstance(parsed, dict):

            item["parsed_type"] = parsed.get("type")
            item["parsed_info"] = parsed.get("info")

        instructions.append(item)

    return instructions


# ============================================================
# INNER INSTRUCTIONS
# ============================================================

def _extract_inner_instructions(
    meta: Dict[str, Any]
) -> list[dict]:
    """
    Meta içerisindeki innerInstructions alanını çıkarır.

    LP ve swap detection için özellikle önemlidir.
    """

    result = []

    for group in meta.get("innerInstructions") or []:

        if not isinstance(group, dict):
            continue

        parent_index = group.get("index")

        for instruction in group.get("instructions") or []:

            if not isinstance(instruction, dict):
                continue

            parsed = instruction.get("parsed")

            item = {
                "parent_index": parent_index,
                "program": instruction.get("program"),
                "programId": instruction.get("programId"),
                "parsed_type": None,
                "parsed_info": None,
            }

            if isinstance(parsed, dict):

                item["parsed_type"] = parsed.get("type")
                item["parsed_info"] = parsed.get("info")

            result.append(item)

    return result


# ============================================================
# MINT CONNECTION
# ============================================================

def _mint_in_instructions(
    message: Dict[str, Any],
    mint: str
) -> bool:

    for instruction in message.get("instructions") or []:

        if not isinstance(instruction, dict):
            continue

        parsed = instruction.get("parsed")

        if not isinstance(parsed, dict):
            continue

        info = parsed.get("info")

        if not isinstance(info, dict):
            continue

        if info.get("mint") == mint:
            return True

    return False


def _mint_in_inner_instructions(
    meta: Dict[str, Any],
    mint: str
) -> bool:

    for group in meta.get("innerInstructions") or []:

        if not isinstance(group, dict):
            continue

        for instruction in group.get("instructions") or []:

            if not isinstance(instruction, dict):
                continue

            parsed = instruction.get("parsed")

            if not isinstance(parsed, dict):
                continue

            info = parsed.get("info")

            if not isinstance(info, dict):
                continue

            if info.get("mint") == mint:
                return True

    return False


def _mint_in_token_balances(
    meta: Dict[str, Any],
    mint: str
) -> bool:

    for field in (
        "preTokenBalances",
        "postTokenBalances",
    ):

        for balance in meta.get(field) or []:

            if not isinstance(balance, dict):
                continue

            if balance.get("mint") == mint:
                return True

    return False


def _mint_in_logs(
    meta: Dict[str, Any],
    mint: str
) -> bool:

    for log in meta.get("logMessages") or []:

        if mint in str(log):
            return True

    return False


def transaction_mentions_mint(
    result: Dict[str, Any],
    mint: str
) -> bool:

    if not mint:
        return False

    transaction = result.get("transaction") or {}
    message = transaction.get("message") or {}
    meta = result.get("meta") or {}

    if mint in _get_account_keys(message):
        return True

    if _mint_in_instructions(message, mint):
        return True

    if _mint_in_inner_instructions(meta, mint):
        return True

    if _mint_in_token_balances(meta, mint):
        return True

    if _mint_in_logs(meta, mint):
        return True

    return False


# ============================================================
# SOL BALANCE DELTAS
# ============================================================

def _extract_sol_balance_changes(
    message: Dict[str, Any],
    meta: Dict[str, Any]
) -> list[dict]:

    account_keys = _get_account_keys(message)

    pre_balances = meta.get("preBalances") or []
    post_balances = meta.get("postBalances") or []

    changes = []

    count = min(
        len(account_keys),
        len(pre_balances),
        len(post_balances)
    )

    for index in range(count):

        pre = pre_balances[index]
        post = post_balances[index]

        if not isinstance(pre, (int, float)):
            continue

        if not isinstance(post, (int, float)):
            continue

        delta_lamports = post - pre

        if delta_lamports == 0:
            continue

        changes.append({
            "account": account_keys[index],
            "pre_lamports": pre,
            "post_lamports": post,
            "delta_lamports": delta_lamports,
            "delta_sol": delta_lamports / 1_000_000_000,
        })

    return changes


# ============================================================
# TOKEN BALANCE CHANGES
# ============================================================

def _extract_token_balance_changes(
    meta: Dict[str, Any]
) -> list[dict]:

    pre_balances = {}

    for balance in meta.get("preTokenBalances") or []:

        if not isinstance(balance, dict):
            continue

        key = (
            balance.get("accountIndex"),
            balance.get("mint"),
        )

        pre_balances[key] = balance

    changes = []

    for balance in meta.get("postTokenBalances") or []:

        if not isinstance(balance, dict):
            continue

        account_index = balance.get("accountIndex")
        mint = balance.get("mint")

        key = (
            account_index,
            mint,
        )

        pre = pre_balances.get(key)

        pre_amount = 0.0
        post_amount = 0.0

        if isinstance(pre, dict):

            ui = pre.get("uiTokenAmount") or {}

            try:
                pre_amount = float(
                    ui.get("uiAmount") or 0
                )
            except (TypeError, ValueError):
                pre_amount = 0.0

        ui = balance.get("uiTokenAmount") or {}

        try:
            post_amount = float(
                ui.get("uiAmount") or 0
            )
        except (TypeError, ValueError):
            post_amount = 0.0

        delta = post_amount - pre_amount

        if delta == 0:
            continue

        changes.append({
            "account_index": account_index,
            "mint": mint,
            "owner": balance.get("owner"),
            "pre_amount": pre_amount,
            "post_amount": post_amount,
            "delta": delta,
        })

    return changes


# ============================================================
# LOGS
# ============================================================

def _extract_logs(meta: Dict[str, Any]) -> list[str]:

    logs = meta.get("logMessages") or []

    return [
        str(log)
        for log in logs
    ]


# ============================================================
# PARSER
# ============================================================

def parse_transaction(
    data: Dict[str, Any],
    tracked_mint: Optional[str] = None
) -> Optional[Dict[str, Any]]:

    try:

        result = _get_result(data)

        if not result:
            return None

        transaction = result.get("transaction")

        if not isinstance(transaction, dict):
            return None

        meta = result.get("meta") or {}
        message = transaction.get("message") or {}

        if not isinstance(meta, dict):
            meta = {}

        if not isinstance(message, dict):
            message = {}

        tracked = False

        if tracked_mint:

            tracked = transaction_mentions_mint(
                result,
                tracked_mint
            )

        if not tracked_mint:

            tracked = True

        event = {

            # ====================================================
            # VERSION
            # ====================================================

            "version": "5.1",

            # ====================================================
            # BLOCKCHAIN
            # ====================================================

            "network": "mainnet",

            "signature": result.get("signature"),

            "slot": result.get("slot"),

            "timestamp": result.get("blockTime"),

            # ====================================================
            # TOKEN
            # ====================================================

            "mint": tracked_mint,

            # ====================================================
            # TRACKING
            # ====================================================

            "tracked": tracked,

            # ====================================================
            # RAW TRANSACTION
            # ====================================================

            "transaction": transaction,

            "message": message,

            "meta": meta,

            "raw": result,

            # ====================================================
            # TRANSACTION ANATOMY
            # ====================================================

            "account_keys": _get_account_keys(
                message
            ),

            "program_ids": _extract_program_ids(
                message
            ),

            "instructions": _extract_instructions(
                message
            ),

            "inner_instructions": _extract_inner_instructions(
                meta
            ),

            "sol_balance_changes": _extract_sol_balance_changes(
                message,
                meta
            ),

            "token_balance_changes": _extract_token_balance_changes(
                meta
            ),

            "logs": _extract_logs(
                meta
            ),

            # ====================================================
            # DETECTION PLACEHOLDERS
            # ====================================================

            "type": "UNKNOWN",

            "dex": None,

            "lp_created": False,

            "lp_sol": 0.0,

            "first_buy": False,

            "first_buy_at": None,

            "buyer": None,

            "creator": None,

            "whale_buy": False,

            "amount_sol": 0.0,

            "token_amount": 0.0,

            # ====================================================
            # ANALYSIS
            # ====================================================

            "analysis": {

                "engine": "Patoshi Radar",

                "version": "5.1",

                "program": None,

                "instruction": None,

                "score": 0,

                "confidence": 0,

                "matched": [],

                "reason": [],

                "warnings": [],

                "errors": [],
            },
        }

        return event

    except Exception as e:

        print("❌ V5.1 Transaction Parser Hatası")
        print(e)

        return None
