"""
Patoshi Radar
V5.1 - Real Transaction Parser

Görev:
- Helius WebSocket transaction verisini güvenli şekilde ayrıştırır.
- Transaction anatomy çıkarır.
- Takip edilen mint ile transaction bağlantısını belirler.
- Chain Monitor için standart event nesnesi üretir.

NOT:
Bu sürüm gerçek transaction verisini analiz eder.
LP / DEX / First Buy / Whale detection henüz kesin olarak
işaretlenmez. Gerçek transaction örnekleri üzerinden
detection kuralları sonraki aşamada eklenecektir.
"""

from typing import Any, Dict, Optional


# ============================================================
# BASIC HELPERS
# ============================================================

def _get_result(
    data: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Helius subscription mesajından transaction result çıkarır."""

    if not isinstance(data, dict):
        return None

    params = data.get("params")

    if not isinstance(params, dict):
        return None

    result = params.get("result")

    if not isinstance(result, dict):
        return None

    return result


def _get_transaction(
    result: Dict[str, Any]
) -> Dict[str, Any]:
    """Transaction objesini güvenli şekilde döndürür."""

    transaction = result.get("transaction")

    if isinstance(transaction, dict):
        return transaction

    return {}


def _get_message(
    transaction: Dict[str, Any]
) -> Dict[str, Any]:
    """Transaction message objesini güvenli şekilde döndürür."""

    message = transaction.get("message")

    if isinstance(message, dict):
        return message

    return {}


def _get_meta(
    result: Dict[str, Any]
) -> Dict[str, Any]:
    """Transaction meta objesini güvenli şekilde döndürür."""

    meta = result.get("meta")

    if isinstance(meta, dict):
        return meta

    return {}


# ============================================================
# ACCOUNT KEYS
# ============================================================

def _get_account_keys(
    message: Dict[str, Any]
) -> list:
    """
    accountKeys alanını public key listesine dönüştürür.
    """

    keys = []

    account_keys = message.get("accountKeys") or []

    for account in account_keys:

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

def _get_program_ids(
    message: Dict[str, Any]
) -> list:
    """
    Transaction instruction'larından programId listesini çıkarır.
    """

    programs = []

    instructions = message.get("instructions") or []

    for instruction in instructions:

        if not isinstance(instruction, dict):
            continue

        program_id = instruction.get("programId")

        if program_id:
            programs.append(program_id)

    return list(dict.fromkeys(programs))


# ============================================================
# INSTRUCTIONS
# ============================================================

def _get_instructions(
    message: Dict[str, Any]
) -> list:
    """
    Ana instruction'ları sade şekilde döndürür.
    """

    instructions = []

    for instruction in message.get("instructions") or []:

        if not isinstance(instruction, dict):
            continue

        instructions.append(instruction)

    return instructions


# ============================================================
# INNER INSTRUCTIONS
# ============================================================

def _get_inner_instructions(
    meta: Dict[str, Any]
) -> list:
    """
    Meta içerisindeki innerInstructions verisini döndürür.
    """

    inner = meta.get("innerInstructions")

    if not isinstance(inner, list):
        return []

    return inner


# ============================================================
# TOKEN BALANCE CHANGES
# ============================================================

def _get_token_balance_changes(
    meta: Dict[str, Any],
    tracked_mint: Optional[str] = None
) -> list:
    """
    preTokenBalances ve postTokenBalances farklarını çıkarır.

    Çıktı:
    [
        {
            "mint": "...",
            "owner": "...",
            "account_index": 1,
            "pre_amount": 0.0,
            "post_amount": 100.0,
            "change": 100.0
        }
    ]
    """

    pre_balances = meta.get("preTokenBalances") or []
    post_balances = meta.get("postTokenBalances") or []

    changes = {}

    # --------------------------------------------------------
    # PRE
    # --------------------------------------------------------

    for balance in pre_balances:

        if not isinstance(balance, dict):
            continue

        mint = balance.get("mint")

        if tracked_mint and mint != tracked_mint:
            continue

        index = balance.get("accountIndex")

        key = (index, mint)

        ui_amount = 0.0

        token_amount = balance.get("uiTokenAmount")

        if isinstance(token_amount, dict):
            raw = token_amount.get("uiAmount")

            if isinstance(raw, (int, float)):
                ui_amount = float(raw)

        changes[key] = {
            "mint": mint,
            "owner": balance.get("owner"),
            "account_index": index,
            "pre_amount": ui_amount,
            "post_amount": 0.0,
        }

    # --------------------------------------------------------
    # POST
    # --------------------------------------------------------

    for balance in post_balances:

        if not isinstance(balance, dict):
            continue

        mint = balance.get("mint")

        if tracked_mint and mint != tracked_mint:
            continue

        index = balance.get("accountIndex")

        key = (index, mint)

        if key not in changes:

            changes[key] = {
                "mint": mint,
                "owner": balance.get("owner"),
                "account_index": index,
                "pre_amount": 0.0,
                "post_amount": 0.0,
            }

        token_amount = balance.get("uiTokenAmount")

        ui_amount = 0.0

        if isinstance(token_amount, dict):
            raw = token_amount.get("uiAmount")

            if isinstance(raw, (int, float)):
                ui_amount = float(raw)

        changes[key]["post_amount"] = ui_amount

    # --------------------------------------------------------
    # FINAL
    # --------------------------------------------------------

    result = []

    for change in changes.values():

        change["change"] = (
            change["post_amount"]
            - change["pre_amount"]
        )

        result.append(change)

    return result


# ============================================================
# SOL BALANCE CHANGES
# ============================================================

def _get_sol_balance_changes(
    meta: Dict[str, Any],
    account_keys: list
) -> list:
    """
    lamports balance değişimlerini SOL olarak çıkarır.
    """

    pre_balances = meta.get("preBalances") or []
    post_balances = meta.get("postBalances") or []

    changes = []

    count = min(
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

        diff_lamports = post - pre

        if diff_lamports == 0:
            continue

        public_key = None

        if index < len(account_keys):
            public_key = account_keys[index]

        changes.append({
            "account_index": index,
            "account": public_key,
            "pre_lamports": pre,
            "post_lamports": post,
            "change_lamports": diff_lamports,
            "change_sol": diff_lamports / 1_000_000_000,
        })

    return changes


# ============================================================
# MINT DETECTION
# ============================================================

def _mint_in_account_keys(
    account_keys: list,
    mint: str
) -> bool:

    return mint in account_keys


def _mint_in_instructions(
    message: Dict[str, Any],
    mint: str
) -> bool:
    """
    Parsed instruction içerisinde mint arar.
    """

    instructions = message.get("instructions") or []

    for instruction in instructions:

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

        # Bazı instruction formatlarında token alanı
        # source/destination üzerinden gelebilir.

        for key in (
            "source",
            "destination",
            "account",
            "authority",
        ):

            if info.get(key) == mint:
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

        balances = meta.get(field) or []

        for balance in balances:

            if not isinstance(balance, dict):
                continue

            if balance.get("mint") == mint:
                return True

    return False


def _mint_in_logs(
    meta: Dict[str, Any],
    mint: str
) -> bool:

    logs = meta.get("logMessages") or []

    for log in logs:

        if mint in str(log):
            return True

    return False


def transaction_mentions_mint(
    result: Dict[str, Any],
    mint: str
) -> bool:
    """
    Transaction'ın takip edilen mint ile ilişkisini kontrol eder.

    Bu fonksiyon detection değildir.
    Sadece transaction ↔ mint bağlantısını belirler.
    """

    if not mint:
        return False

    transaction = _get_transaction(result)
    message = _get_message(transaction)
    meta = _get_meta(result)

    account_keys = _get_account_keys(message)

    # 1. Account keys
    if _mint_in_account_keys(
        account_keys,
        mint
    ):
        return True

    # 2. Parsed instructions
    if _mint_in_instructions(
        message,
        mint
    ):
        return True

    # 3. Token balances
    if _mint_in_token_balances(
        meta,
        mint
    ):
        return True

    # 4. Logs
    if _mint_in_logs(
        meta,
        mint
    ):
        return True

    return False


# ============================================================
# BUYER CANDIDATE
# ============================================================

def _get_signers(
    message: Dict[str, Any]
) -> list:
    """
    accountKeys içerisinden signer hesaplarını çıkarır.
    """

    signers = []

    account_keys = message.get("accountKeys") or []

    for account in account_keys:

        if isinstance(account, dict):

            if account.get("signer") is True:

                pubkey = account.get("pubkey")

                if pubkey:
                    signers.append(pubkey)

    return signers


# ============================================================
# STATUS
# ============================================================

def _get_status(
    meta: Dict[str, Any]
) -> str:
    """
    Transaction confirmation / execution durumunu belirler.
    """

    err = meta.get("err")

    if err is None:
        return "SUCCESS"

    return "FAILED"


# ============================================================
# AMOUNT EXTRACTION
# ============================================================

def _calculate_token_amount(
    token_changes: list
) -> float:
    """
    Takip edilen mint için toplam pozitif token değişimini bulur.
    """

    total = 0.0

    for change in token_changes:

        amount = change.get("change", 0)

        if isinstance(amount, (int, float)) and amount > 0:
            total += float(amount)

    return total


def _calculate_sol_amount(
    sol_changes: list
) -> float:
    """
    Pozitif SOL değişimini hesaplar.

    Detection aşamasında bunun hangi hesaba ait olduğu ayrıca
    analiz edilecektir.
    """

    total = 0.0

    for change in sol_changes:

        amount = change.get("change_sol", 0)

        if isinstance(amount, (int, float)) and amount > 0:
            total += float(amount)

    return total


# ============================================================
# MAIN PARSER
# ============================================================

def parse_transaction(
    data: Dict[str, Any],
    tracked_mint: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Helius transaction verisini Patoshi Radar V5.1 event nesnesine
    dönüştürür.

    Gerçek transaction anatomy çıkarılır.

    LP / DEX / First Buy / Whale detection burada henüz
    kesinleştirilmez.
    """

    try:

        result = _get_result(data)

        if not result:
            return None

        transaction = _get_transaction(result)

        if not transaction:
            return None

        message = _get_message(transaction)
        meta = _get_meta(result)

        account_keys = _get_account_keys(message)
        program_ids = _get_program_ids(message)
        instructions = _get_instructions(message)
        inner_instructions = _get_inner_instructions(meta)

        token_balance_changes = (
            _get_token_balance_changes(
                meta,
                tracked_mint=tracked_mint
            )
        )

        sol_balance_changes = (
            _get_sol_balance_changes(
                meta,
                account_keys
            )
        )

        tracked = False

        if tracked_mint:

            tracked = transaction_mentions_mint(
                result,
                tracked_mint
            )

        signers = _get_signers(message)

        status = _get_status(meta)

        token_amount = _calculate_token_amount(
            token_balance_changes
        )

        amount_sol = _calculate_sol_amount(
            sol_balance_changes
        )

        # ----------------------------------------------------
        # EVENT
        # ----------------------------------------------------

        event = {

            # Parser
            "version": "5.1",

            # Network
            "network": "mainnet",

            # Event
            "type": "UNKNOWN",
            "status": status,

            # Blockchain
            "signature": result.get("signature"),
            "slot": result.get("slot"),
            "timestamp": result.get("blockTime"),

            # Token
            "mint": tracked_mint,
            "name": None,
            "symbol": None,

            # Wallet
            "buyer": signers[0] if signers else None,
            "seller": None,
            "creator": None,

            # DEX
            "dex": None,

            # Financial
            "amount_sol": amount_sol,
            "token_amount": token_amount,

            # Detection flags
            "lp_created": False,
            "first_buy": False,
            "whale_buy": False,

            # Tracking
            "tracked": tracked,

            # Transaction anatomy
            "program_ids": program_ids,
            "instructions": instructions,
            "inner_instructions": inner_instructions,
            "sol_balance_changes": sol_balance_changes,
            "token_balance_changes": token_balance_changes,
            "signers": signers,

            # Analysis
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

            # Raw data
            "transaction": transaction,

            "message": message,

            "meta": meta,

            "raw": result,
        }

        # ----------------------------------------------------
        # BASIC ANALYSIS INFORMATION
        # ----------------------------------------------------

        if program_ids:

            event["analysis"]["program"] = (
                program_ids[0]
            )

        if instructions:

            first_instruction = instructions[0]

            if isinstance(
                first_instruction,
                dict
            ):

                event["analysis"]["instruction"] = (
                    first_instruction.get("program")
                    or first_instruction.get("type")
                )

        if tracked:

            event["analysis"]["matched"].append(
                "MINT"
            )

            event["analysis"]["reason"].append(
                "Transaction tracked mint ile ilişkili."
            )

        if status == "FAILED":

            event["analysis"]["warnings"].append(
                "Transaction failed."
            )

        if not program_ids:

            event["analysis"]["warnings"].append(
                "Program ID bulunamadı."
            )

        if not instructions:

            event["analysis"]["warnings"].append(
                "Instruction bulunamadı."
            )

        return event

    except Exception as e:

        print("")
        print("❌ V5.1 Transaction Parser Hatası")
        print(f"❌ {type(e).__name__}: {e}")
        print("")

        return None
