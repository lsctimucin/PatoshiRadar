"""
Patoshi Radar
V5.1 - Transaction Parser

Görev:

- Helius WebSocket transaction verisini güvenli şekilde ayrıştırır.
- Chain Monitor için standart event nesnesi üretir.
- Takip edilen mint ile transaction arasındaki bağlantıyı belirler.
- Gerçek transaction anatomisini detection katmanına hazırlar.

V5.1 Detection:
- LP / DEX / First Buy henüz kesin olarak doldurulmaz.
- Önce gerçek Helius transaction yapısı gözlemlenir.
"""

from typing import Any, Dict, Optional


def _get_result(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Helius WebSocket subscription mesajından
    transaction result nesnesini çıkarır.
    """

    if not isinstance(data, dict):
        return None

    params = data.get("params")

    if not isinstance(params, dict):
        return None

    result = params.get("result")

    if not isinstance(result, dict):
        return None

    return result


def _get_account_keys(message: Dict[str, Any]) -> list[str]:
    """
    jsonParsed transaction formatındaki accountKeys
    alanını güvenli şekilde public key listesine dönüştürür.
    """

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


def _get_program_ids(message: Dict[str, Any]) -> list[str]:
    """
    Transaction instruction'larından programId listesini çıkarır.
    """

    programs = []

    for instruction in message.get("instructions") or []:

        if not isinstance(instruction, dict):
            continue

        program_id = instruction.get("programId")

        if program_id and program_id not in programs:
            programs.append(program_id)

    return programs


def _get_instructions(message: Dict[str, Any]) -> list[Dict[str, Any]]:
    """
    Top-level instruction'ları standart liste halinde döndürür.
    """

    instructions = []

    for instruction in message.get("instructions") or []:

        if isinstance(instruction, dict):
            instructions.append(instruction)

    return instructions


def _get_inner_instructions(
    meta: Dict[str, Any]
) -> list[Dict[str, Any]]:
    """
    Meta içerisindeki innerInstructions listesini güvenli şekilde döndürür.
    """

    result = []

    for item in meta.get("innerInstructions") or []:

        if isinstance(item, dict):
            result.append(item)

    return result


def _get_sol_balance_changes(
    meta: Dict[str, Any]
) -> list[Dict[str, Any]]:
    """
    preBalances / postBalances farklarını çıkarır.

    Henüz buyer/seller veya LP olarak yorumlanmaz.
    """

    pre = meta.get("preBalances") or []
    post = meta.get("postBalances") or []

    changes = []

    length = min(len(pre), len(post))

    for index in range(length):

        try:
            pre_balance = int(pre[index])
            post_balance = int(post[index])

            delta_lamports = post_balance - pre_balance

            if delta_lamports != 0:
                changes.append({
                    "account_index": index,
                    "pre_lamports": pre_balance,
                    "post_lamports": post_balance,
                    "delta_lamports": delta_lamports,
                    "delta_sol": delta_lamports / 1_000_000_000,
                })

        except (TypeError, ValueError):
            continue

    return changes


def _get_token_balance_changes(
    meta: Dict[str, Any],
    tracked_mint: Optional[str] = None
) -> list[Dict[str, Any]]:
    """
    preTokenBalances / postTokenBalances farklarını çıkarır.

    tracked_mint verilirse özellikle o mint'in değişimleri
    ayrıca yakalanır.
    """

    pre_balances = meta.get("preTokenBalances") or []
    post_balances = meta.get("postTokenBalances") or []

    changes = []

    pre_map = {}
    post_map = {}

    for balance in pre_balances:

        if not isinstance(balance, dict):
            continue

        key = (
            balance.get("accountIndex"),
            balance.get("mint"),
            balance.get("owner"),
        )

        pre_map[key] = balance

    for balance in post_balances:

        if not isinstance(balance, dict):
            continue

        key = (
            balance.get("accountIndex"),
            balance.get("mint"),
            balance.get("owner"),
        )

        post_map[key] = balance

    all_keys = set(pre_map.keys()) | set(post_map.keys())

    for key in all_keys:

        pre = pre_map.get(key) or {}
        post = post_map.get(key) or {}

        mint = post.get("mint") or pre.get("mint")

        if tracked_mint and mint != tracked_mint:
            continue

        pre_ui = (
            (pre.get("uiTokenAmount") or {}).get("uiAmount")
        )

        post_ui = (
            (post.get("uiTokenAmount") or {}).get("uiAmount")
        )

        try:
            pre_amount = float(pre_ui or 0)
            post_amount = float(post_ui or 0)
        except (TypeError, ValueError):
            continue

        delta = post_amount - pre_amount

        if delta == 0:
            continue

        changes.append({
            "account_index": key[0],
            "mint": mint,
            "owner": key[2],
            "pre_amount": pre_amount,
            "post_amount": post_amount,
            "delta": delta,
        })

    return changes


def _mint_in_instructions(
    message: Dict[str, Any],
    mint: str
) -> bool:
    """
    Parsed instruction'larda takip edilen mint'i arar.
    """

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


def _mint_in_token_balances(
    meta: Dict[str, Any],
    mint: str
) -> bool:
    """
    preTokenBalances / postTokenBalances içerisinde
    takip edilen mint'i arar.
    """

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
    """
    Transaction loglarında mint adresini arar.
    """

    for log in meta.get("logMessages") or []:

        if mint in str(log):
            return True

    return False


def transaction_mentions_mint(
    result: Dict[str, Any],
    mint: str
) -> bool:
    """
    Transaction ile takip edilen mint arasındaki bağlantıyı belirler.

    Bu fonksiyon LP / DEX / Swap detection değildir.

    Yalnızca:

    - accountKeys
    - parsed instructions
    - token balances
    - logMessages

    üzerinden bağlantı arar.
    """

    if not mint:
        return False

    transaction = result.get("transaction") or {}

    message = transaction.get("message") or {}

    meta = result.get("meta") or {}

    if not isinstance(message, dict):
        message = {}

    if not isinstance(meta, dict):
        meta = {}

    # 1. Account keys
    if mint in _get_account_keys(message):
        return True

    # 2. Parsed instructions
    if _mint_in_instructions(message, mint):
        return True

    # 3. Token balances
    if _mint_in_token_balances(meta, mint):
        return True

    # 4. Logs
    if _mint_in_logs(meta, mint):
        return True

    return False


def parse_transaction(
    data: Dict[str, Any],
    tracked_mint: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Helius transaction verisini Patoshi Radar V5.1
    standart event nesnesine dönüştürür.
    """

    try:

        result = _get_result(data)

        if not result:
            return None

        transaction = result.get("transaction")

        if not isinstance(transaction, dict):
            return None

        message = transaction.get("message") or {}
        meta = result.get("meta") or {}

        if not isinstance(message, dict):
            message = {}

        if not isinstance(meta, dict):
            meta = {}

        # ---------------------------------------------------------
        # Temel blockchain anatomisi
        # ---------------------------------------------------------

        account_keys = _get_account_keys(message)
        program_ids = _get_program_ids(message)
        instructions = _get_instructions(message)
        inner_instructions = _get_inner_instructions(meta)

        sol_balance_changes = _get_sol_balance_changes(meta)

        token_balance_changes = _get_token_balance_changes(
            meta,
            tracked_mint=tracked_mint
        )

        # ---------------------------------------------------------
        # Event
        # ---------------------------------------------------------

        event = {

            # Parser
            "version": "5.1",

            # Network
            "network": "mainnet",

            # Event
            "type": "UNKNOWN",
            "status": "CONFIRMED",

            # Blockchain
            "signature": result.get("signature"),
            "slot": result.get("slot"),
            "timestamp": result.get("blockTime"),

            # Token
            "mint": tracked_mint,
            "name": None,
            "symbol": None,

            # Wallet
            "buyer": None,
            "seller": None,
            "creator": None,

            # DEX
            "dex": None,

            # Financial
            "amount_sol": 0.0,
            "token_amount": 0.0,

            # Activity flags
            "lp_created": False,
            "first_buy": False,
            "whale_buy": False,

            # Tracking
            "tracked": False,

            # -----------------------------------------------------
            # REAL TRANSACTION ANATOMY
            # -----------------------------------------------------

            "account_keys": account_keys,

            "program_ids": program_ids,

            "instructions": instructions,

            "inner_instructions": inner_instructions,

            "sol_balance_changes": sol_balance_changes,

            "token_balance_changes": token_balance_changes,

            "log_messages": meta.get("logMessages") or [],

            # -----------------------------------------------------
            # Analysis
            # -----------------------------------------------------

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

            # -----------------------------------------------------
            # Raw transaction
            # -----------------------------------------------------

            "transaction": transaction,

            "message": message,

            "meta": meta,

            "raw": result,
        }

        # ---------------------------------------------------------
        # Mint tracking
        # ---------------------------------------------------------

        if tracked_mint:

            event["tracked"] = transaction_mentions_mint(
                result,
                tracked_mint
            )

        # ---------------------------------------------------------
        # Parser debug
        #
        # SADECE takip edilen mint bulunduğunda çalışır.
        # Böylece Railway logları gereksiz yere şişmez.
        # ---------------------------------------------------------

        if event["tracked"]:

            print(
                f"🔬 V5.1 PARSER MATCH | "
                f"mint={tracked_mint} | "
                f"sig={event.get('signature')}"
            )

            print(
                f"   Programs      : "
                f"{len(program_ids)}"
            )

            print(
                f"   Instructions  : "
                f"{len(instructions)}"
            )

            print(
                f"   Inner         : "
                f"{len(inner_instructions)}"
            )

            print(
                f"   SOL Changes   : "
                f"{len(sol_balance_changes)}"
            )

            print(
                f"   Token Changes : "
                f"{len(token_balance_changes)}"
            )

            print(
                f"   Logs          : "
                f"{len(event['log_messages'])}"
            )

            print(
                f"🧬 V5.1 TRANSACTION ANATOMY | "
                f"{tracked_mint}"
            )

            print(
                f"   Program IDs = "
                f"{program_ids}"
            )

            print(
                f"   Instructions = "
                f"{instructions}"
            )

            print(
                f"   SOL Changes = "
                f"{sol_balance_changes}"
            )

            print(
                f"   Token Changes = "
                f"{token_balance_changes}"
            )

        return event

    except Exception as e:

        print("❌ V5.1 Transaction Parser Hatası")
        print(e)

        return None
