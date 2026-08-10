"""
Patoshi Radar
V5.1 - Alchemy Transaction Parser

Akış:

PumpPortal
    ↓
Telegram
    ↓
Activity Watch
    ↓
Alchemy logsSubscribe
    ↓
getTransaction
    ↓
Bu parser
    ↓
PARSER CHECK
    ↓
TRANSACTION ANATOMY
"""

import json


# ============================================================
# HELPERS
# ============================================================

def _short(value, length=20):
    if not value:
        return "-"

    value = str(value)

    if len(value) <= length:
        return value

    return value[:length] + "..."


def _account_value(account):
    if isinstance(account, str):
        return account

    if isinstance(account, dict):
        return (
            account.get("pubkey")
            or account.get("address")
        )

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


# ============================================================
# TRANSACTION NORMALIZATION
# ============================================================

def _normalize_transaction(raw):
    """
    Alchemy getTransaction sonucunu normalize eder.
    """

    if not isinstance(raw, dict):
        return None

    # RPC response geldiyse result'ı al
    if "result" in raw and isinstance(
        raw.get("result"),
        dict
    ):
        raw = raw["result"]

    if not isinstance(raw, dict):
        return None

    return raw


# ============================================================
# SIGNATURE
# ============================================================

def _extract_signature(
    transaction,
    signature=None,
):
    if signature:
        return signature

    return (
        transaction.get("signature")
        or transaction.get("transaction", {})
        .get("signature")
        or ""
    )


# ============================================================
# SLOT
# ============================================================

def _extract_slot(transaction):
    return transaction.get("slot")


# ============================================================
# ACCOUNT KEYS
# ============================================================

def _extract_account_keys(transaction):
    message = (
        transaction
        .get("transaction", {})
        .get("message", {})
    )

    keys = message.get(
        "accountKeys",
        [],
    )

    result = []

    for key in keys:
        value = _account_value(key)

        if value and value not in result:
            result.append(value)

    # Versioned transaction
    meta = transaction.get(
        "meta"
    ) or {}

    loaded = meta.get(
        "loadedAddresses"
    ) or {}

    for key in (
        loaded.get("writable")
        or []
    ):
        if key not in result:
            result.append(key)

    for key in (
        loaded.get("readonly")
        or []
    ):
        if key not in result:
            result.append(key)

    return result


# ============================================================
# SIGNERS
# ============================================================

def _extract_signers(transaction):
    message = (
        transaction
        .get("transaction", {})
        .get("message", {})
    )

    keys = message.get(
        "accountKeys",
        [],
    )

    result = []

    for key in keys:

        if not isinstance(key, dict):
            continue

        if (
            key.get("signer") is True
            and key.get("pubkey")
        ):
            result.append(
                key["pubkey"]
            )

    return result


# ============================================================
# INSTRUCTIONS
# ============================================================

def _extract_instructions(transaction):
    message = (
        transaction
        .get("transaction", {})
        .get("message", {})
    )

    instructions = message.get(
        "instructions",
        [],
    )

    result = []

    for ix in instructions:

        if not isinstance(ix, dict):
            continue

        parsed = ix.get(
            "parsed"
        )

        parsed_type = None

        if isinstance(parsed, dict):
            parsed_type = parsed.get(
                "type"
            )

        result.append({
            "program": ix.get(
                "program"
            ),
            "programId": ix.get(
                "programId"
            ),
            "parsed_type": parsed_type,
            "parsed": parsed,
        })

    return result


# ============================================================
# INNER INSTRUCTIONS
# ============================================================

def _extract_inner_instructions(transaction):
    meta = transaction.get(
        "meta"
    ) or {}

    return (
        meta.get(
            "innerInstructions"
        )
        or []
    )


# ============================================================
# LOGS
# ============================================================

def _extract_logs(transaction):
    meta = transaction.get(
        "meta"
    ) or {}

    return [
        str(x)
        for x in (
            meta.get(
                "logMessages"
            )
            or []
        )
    ]


# ============================================================
# FEE
# ============================================================

def _extract_fee(transaction):
    meta = transaction.get(
        "meta"
    ) or {}

    return meta.get(
        "fee"
    )


# ============================================================
# SOL BALANCE CHANGES
# ============================================================

def _extract_sol_balance_changes(transaction):
    meta = transaction.get(
        "meta"
    ) or {}

    pre = meta.get(
        "preBalances"
    ) or []

    post = meta.get(
        "postBalances"
    ) or []

    count = max(
        len(pre),
        len(post),
    )

    changes = []

    for index in range(count):

        before = (
            pre[index]
            if index < len(pre)
            else 0
        )

        after = (
            post[index]
            if index < len(post)
            else 0
        )

        changes.append({
            "index": index,
            "before": before,
            "after": after,
            "change": after - before,
        })

    return changes


# ============================================================
# TOKEN BALANCE CHANGES
# ============================================================

def _extract_token_balance_changes(transaction):
    meta = transaction.get(
        "meta"
    ) or {}

    pre = (
        meta.get(
            "preTokenBalances"
        )
        or []
    )

    post = (
        meta.get(
            "postTokenBalances"
        )
        or []
    )

    return {
        "pre": pre,
        "post": post,
    }


# ============================================================
# PROGRAM IDS
# ============================================================

def _extract_program_ids(
    transaction,
    instructions,
):
    programs = []

    for key in _extract_account_keys(
        transaction
    ):
        # account key değil, burada sadece
        # instruction programlarını topluyoruz
        pass

    for ix in instructions:

        program_id = ix.get(
            "programId"
        )

        program = ix.get(
            "program"
        )

        value = (
            program_id
            or program
        )

        if value and value not in programs:
            programs.append(value)

    return programs


# ============================================================
# MINT MATCH
# ============================================================

def _contains_mint(
    transaction,
    tracked_mint,
):
    if not tracked_mint:
        return False

    strings = _collect_strings(
        transaction
    )

    if tracked_mint in strings:
        return True

    try:
        raw = json.dumps(
            transaction,
            ensure_ascii=False,
            default=str,
        )

        if tracked_mint in raw:
            return True

    except Exception:
        pass

    return False


# ============================================================
# PARSE TRANSACTION
# ============================================================

def parse_transaction(
    raw,
    tracked_mint=None,
    signature=None,
):
    """
    Alchemy getTransaction sonucunu
    V5.1 standard event formatına çevirir.
    """

    transaction = _normalize_transaction(
        raw
    )

    if not transaction:
        print(
            "⚪ V5.1 PARSER CHECK => "
            "transaction bulunamadı."
        )
        return None

    tx_signature = _extract_signature(
        transaction,
        signature,
    )

    slot = _extract_slot(
        transaction
    )

    print(
        f"⚪ V5.1 PARSER CHECK => "
        f"TX={_short(tx_signature, 18)} | "
        f"SLOT={slot if slot is not None else '-'}"
    )

    # --------------------------------------------------------
    # TRACKED TOKEN MATCH
    # --------------------------------------------------------

    if tracked_mint:

        matched = _contains_mint(
            transaction,
            tracked_mint,
        )

        if not matched:

            print(
                f"⚪ V5.1 PARSER CHECK => "
                f"MINT MATCH YOK | "
                f"{tracked_mint[:12]}..."
            )

            return None

    # --------------------------------------------------------
    # EXTRACT
    # --------------------------------------------------------

    instructions = _extract_instructions(
        transaction
    )

    inner_instructions = (
        _extract_inner_instructions(
            transaction
        )
    )

    accounts = _extract_account_keys(
        transaction
    )

    signers = _extract_signers(
        transaction
    )

    logs = _extract_logs(
        transaction
    )

    program_ids = _extract_program_ids(
        transaction,
        instructions,
    )

    sol_changes = (
        _extract_sol_balance_changes(
            transaction
        )
    )

    token_changes = (
        _extract_token_balance_changes(
            transaction
        )
    )

    meta = transaction.get(
        "meta"
    ) or {}

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    event = {
        "tracked": True,
        "mint": tracked_mint,
        "signature": tx_signature,
        "slot": slot,
        "timestamp": transaction.get(
            "blockTime"
        ),
        "status": (
            "success"
            if meta.get("err") is None
            else "failed"
        ),
        "error": meta.get(
            "err"
        ),
        "accounts": accounts,
        "account_keys": accounts,
        "signers": signers,
        "instructions": instructions,
        "inner_instructions": inner_instructions,
        "logs": logs,
        "log_messages": logs,
        "program_ids": program_ids,
        "fee": _extract_fee(
            transaction
        ),
        "sol_balance_changes": sol_changes,
        "token_balance_changes": token_changes,

        # ----------------------------------------------------
        # V5.1 detection placeholders
        # Gerçek transaction görülünce doldurulacak.
        # ----------------------------------------------------

        "lp_created": False,
        "lp_sol": 0.0,
        "dex": None,
        "first_buy": False,
        "amount_sol": 0.0,
        "token_amount": 0.0,
        "buyer": None,
        "seller": None,
        "creator": (
            signers[0]
            if signers
            else None
        ),
        "whale_buy": False,

        # ----------------------------------------------------
        # RAW
        # ----------------------------------------------------

        "raw": transaction,
    }

    print(
        f"🎯 V5.1 PARSER MATCH => "
        f"MINT={tracked_mint} | "
        f"TX={_short(tx_signature, 18)}"
    )

    return event


# ============================================================
# TRANSACTION ANATOMY
# ============================================================

def print_transaction_anatomy(
    event
):
    if not event:
        return

    print("")
    print("=" * 80)
    print(
        "🧬 V5.1 TRANSACTION ANATOMY"
    )
    print("=" * 80)

    print(
        f"MINT       : {event.get('mint')}"
    )

    print(
        f"SIGNATURE  : "
        f"{_short(event.get('signature'), 24)}"
    )

    print(
        f"SLOT       : "
        f"{event.get('slot')}"
    )

    print(
        f"STATUS     : "
        f"{event.get('status')}"
    )

    print(
        f"FEE        : "
        f"{event.get('fee')} lamports"
    )

    print(
        f"CREATOR    : "
        f"{event.get('creator')}"
    )

    print(
        f"ACCOUNTS   : "
        f"{len(event.get('accounts') or [])}"
    )

    print(
        f"SIGNERS    : "
        f"{len(event.get('signers') or [])}"
    )

    print(
        f"PROGRAMS   : "
        f"{event.get('program_ids')}"
    )

    print(
        f"INSTRUCTIONS : "
        f"{len(event.get('instructions') or [])}"
    )

    print(
        f"INNER INSTRUCTIONS : "
        f"{len(event.get('inner_instructions') or [])}"
    )

    print(
        f"LOGS       : "
        f"{len(event.get('logs') or [])}"
    )

    print(
        f"SOL CHANGES : "
        f"{len(event.get('sol_balance_changes') or [])}"
    )

    token_changes = (
        event.get(
            "token_balance_changes"
        )
        or {}
    )

    print(
        f"TOKEN PRE  : "
        f"{len(token_changes.get('pre') or [])}"
    )

    print(
        f"TOKEN POST : "
        f"{len(token_changes.get('post') or [])}"
    )

    print(
        f"LP         : "
        f"{event.get('lp_created')}"
    )

    print(
        f"DEX        : "
        f"{event.get('dex')}"
    )

    print(
        f"FIRST BUY  : "
        f"{event.get('first_buy')}"
    )

    print("=" * 80)
    print(
        "🧬 V5.1 TRANSACTION ANATOMY END"
    )
    print("=" * 80)
    print("")
