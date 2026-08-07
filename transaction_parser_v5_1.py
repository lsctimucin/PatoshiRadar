"""
Patoshi Radar
V5.1 - Transaction Parser

GERÇEK BLOCKCHAIN DETECTION

Görev:

- Helius transaction verisini ayrıştırır.
- Takip edilen mint ile transaction bağlantısını bulur.
- Pump.fun BUY işlemlerini tespit eder.
- First Buy tespiti yapar.
- Buyer wallet tespit eder.
- Token miktarını hesaplar.
- SOL değişimini hesaplar.
- Transaction anatomy üretir.

Henüz yapılmayanlar:

- LP detection
- PumpSwap migration detection
- Whale scoring
- DEX scoring

Bunlar sonraki aşamalarda eklenecek.
"""

from typing import Any, Dict, Optional


# ============================================================
# PROGRAM CONSTANTS
# ============================================================

PUMP_PROGRAM_ID = (
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
)

SYSTEM_PROGRAM_ID = (
    "11111111111111111111111111111111"
)

SOL_DECIMALS = 9


# ============================================================
# HELIUS RESULT
# ============================================================

def _get_result(
    data: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Helius subscription mesajından transaction result'ını çıkarır.
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


# ============================================================
# ACCOUNT KEYS
# ============================================================

def _get_account_keys(
    message: Dict[str, Any]
) -> list:
    """
    jsonParsed transaction formatındaki accountKeys
    alanını güvenli şekilde public key listesine dönüştürür.
    """

    keys = []

    for account in (
        message.get("accountKeys") or []
    ):

        if isinstance(account, str):

            keys.append(account)

            continue


        if isinstance(account, dict):

            pubkey = account.get("pubkey")

            if pubkey:

                keys.append(pubkey)


    return keys


# ============================================================
# SIGNER KEYS
# ============================================================

def _get_signer_keys(
    message: Dict[str, Any]
) -> list:
    """
    Transaction içerisindeki signer wallet'ları çıkarır.
    """

    signers = []

    for account in (
        message.get("accountKeys") or []
    ):

        if not isinstance(account, dict):
            continue

        if account.get("signer") is not True:
            continue

        pubkey = account.get("pubkey")

        if pubkey:
            signers.append(pubkey)

    return signers


# ============================================================
# PROGRAM IDS
# ============================================================

def _get_program_ids(
    message: Dict[str, Any]
) -> list:
    """
    Transaction içerisinde görünen program ID'lerini çıkarır.
    """

    programs = []

    for instruction in (
        message.get("instructions") or []
    ):

        if not isinstance(
            instruction,
            dict
        ):
            continue

        program_id = (
            instruction.get("programId")
        )

        if program_id:
            programs.append(
                program_id
            )

        program = instruction.get(
            "program"
        )

        if program:
            programs.append(
                program
            )


    # duplicate temizle

    unique = []

    for program in programs:

        if program not in unique:

            unique.append(program)


    return unique


# ============================================================
# LOG MESSAGES
# ============================================================

def _get_logs(
    meta: Dict[str, Any]
) -> list:
    """
    Transaction logMessages listesini döndürür.
    """

    logs = meta.get(
        "logMessages"
    )

    if not isinstance(
        logs,
        list
    ):
        return []

    return [
        str(log)
        for log in logs
    ]


# ============================================================
# INSTRUCTIONS
# ============================================================

def _get_instructions(
    message: Dict[str, Any],
    meta: Dict[str, Any]
) -> list:
    """
    Ana instruction + inner instruction'ları birleştirir.
    """

    instructions = []

    for instruction in (
        message.get("instructions") or []
    ):

        if isinstance(
            instruction,
            dict
        ):

            instructions.append(
                instruction
            )


    for group in (
        meta.get(
            "innerInstructions"
        ) or []
    ):

        if not isinstance(
            group,
            dict
        ):
            continue

        for instruction in (
            group.get(
                "instructions"
            ) or []
        ):

            if isinstance(
                instruction,
                dict
            ):

                instructions.append(
                    instruction
                )


    return instructions


# ============================================================
# MINT IN ACCOUNT KEYS
# ============================================================

def _mint_in_account_keys(
    message: Dict[str, Any],
    mint: str
) -> bool:
    """
    Mint public key transaction account listesinde var mı?
    """

    if not mint:
        return False

    return (
        mint
        in _get_account_keys(
            message
        )
    )


# ============================================================
# MINT IN INSTRUCTIONS
# ============================================================

def _mint_in_instructions(
    message: Dict[str, Any],
    mint: str
) -> bool:
    """
    Parsed instruction'larda mint alanını kontrol eder.
    """

    if not mint:
        return False


    for instruction in (
        message.get("instructions") or []
    ):

        if not isinstance(
            instruction,
            dict
        ):
            continue


        parsed = instruction.get(
            "parsed"
        )

        if not isinstance(
            parsed,
            dict
        ):
            continue


        info = parsed.get(
            "info"
        )

        if not isinstance(
            info,
            dict
        ):
            continue


        if info.get(
            "mint"
        ) == mint:

            return True


    return False


# ============================================================
# MINT IN TOKEN BALANCES
# ============================================================

def _mint_in_token_balances(
    meta: Dict[str, Any],
    mint: str
) -> bool:
    """
    preTokenBalances / postTokenBalances
    içerisinde takip edilen mint'i arar.
    """

    if not mint:
        return False


    fields = (
        "preTokenBalances",
        "postTokenBalances",
    )


    for field in fields:

        for balance in (
            meta.get(field) or []
        ):

            if not isinstance(
                balance,
                dict
            ):
                continue


            if balance.get(
                "mint"
            ) == mint:

                return True


    return False


# ============================================================
# MINT IN LOGS
# ============================================================

def _mint_in_logs(
    meta: Dict[str, Any],
    mint: str
) -> bool:
    """
    Transaction loglarında mint adresini arar.
    """

    if not mint:
        return False


    for log in _get_logs(meta):

        if mint in log:

            return True


    return False


# ============================================================
# TRANSACTION ↔ MINT
# ============================================================

def transaction_mentions_mint(
    result: Dict[str, Any],
    mint: str
) -> bool:
    """
    Transaction'ın verilen mint ile ilişkisini kontrol eder.

    Bu fonksiyon detection değildir.

    Sadece transaction ↔ mint bağlantısını belirler.
    """

    if not mint:
        return False


    transaction = (
        result.get(
            "transaction"
        ) or {}
    )


    message = (
        transaction.get(
            "message"
        ) or {}
    )


    meta = (
        result.get(
            "meta"
        ) or {}
    )


    # 1
    if _mint_in_account_keys(
        message,
        mint
    ):

        return True


    # 2
    if _mint_in_instructions(
        message,
        mint
    ):

        return True


    # 3
    if _mint_in_token_balances(
        meta,
        mint
    ):

        return True


    # 4
    if _mint_in_logs(
        meta,
        mint
    ):

        return True


    return False


# ============================================================
# TOKEN BALANCE VALUE
# ============================================================

def _token_balance_value(
    balance: Dict[str, Any]
) -> float:
    """
    Token balance değerini UI amount olarak döndürür.
    """

    token_amount = (
        balance.get(
            "uiTokenAmount"
        ) or {}
    )


    ui_amount = token_amount.get(
        "uiAmount"
    )

    if isinstance(
        ui_amount,
        (int, float)
    ):

        return float(
            ui_amount
        )


    ui_string = token_amount.get(
        "uiAmountString"
    )

    if ui_string is not None:

        try:

            return float(
                ui_string
            )

        except (
            TypeError,
            ValueError
        ):

            pass


    raw_amount = token_amount.get(
        "amount"
    )

    decimals = token_amount.get(
        "decimals",
        0
    )


    if raw_amount is not None:

        try:

            return (
                float(raw_amount)
                / (
                    10 ** int(
                        decimals
                    )
                )
            )

        except (
            TypeError,
            ValueError
        ):

            pass


    return 0.0


# ============================================================
# TOKEN BALANCE CHANGES
# ============================================================

def _get_token_balance_changes(
    meta: Dict[str, Any],
    mint: str
) -> list:
    """
    Takip edilen mint için token balance değişimlerini çıkarır.

    Sonuç:

    [
        {
            owner,
            account,
            pre,
            post,
            delta
        }
    ]
    """

    if not mint:
        return []


    pre_balances = {}

    post_balances = {}


    # --------------------------------------------------------
    # PRE
    # --------------------------------------------------------

    for balance in (
        meta.get(
            "preTokenBalances"
        ) or []
    ):

        if not isinstance(
            balance,
            dict
        ):
            continue


        if balance.get(
            "mint"
        ) != mint:

            continue


        account_index = (
            balance.get(
                "accountIndex"
            )
        )


        pre_balances[
            account_index
        ] = balance


    # --------------------------------------------------------
    # POST
    # --------------------------------------------------------

    for balance in (
        meta.get(
            "postTokenBalances"
        ) or []
    ):

        if not isinstance(
            balance,
            dict
        ):
            continue


        if balance.get(
            "mint"
        ) != mint:

            continue


        account_index = (
            balance.get(
                "accountIndex"
            )
        )


        post_balances[
            account_index
        ] = balance


    # --------------------------------------------------------
    # ALL ACCOUNTS
    # --------------------------------------------------------

    indexes = set(
        pre_balances.keys()
    )

    indexes.update(
        post_balances.keys()
    )


    changes = []


    for index in indexes:

        pre = pre_balances.get(
            index
        )

        post = post_balances.get(
            index
        )


        pre_amount = (
            _token_balance_value(
                pre
            )
            if pre
            else 0.0
        )


        post_amount = (
            _token_balance_value(
                post
            )
            if post
            else 0.0
        )


        delta = (
            post_amount
            - pre_amount
        )


        owner = None

        account = None


        if post:

            owner = post.get(
                "owner"
            )


            account = post.get(
                "accountIndex"
            )


        elif pre:

            owner = pre.get(
                "owner"
            )


            account = pre.get(
                "accountIndex"
            )


        changes.append({

            "owner": owner,

            "account_index": account,

            "pre": pre_amount,

            "post": post_amount,

            "delta": delta,
        })


    return changes


# ============================================================
# SOL BALANCE CHANGES
# ============================================================

def _get_sol_balance_changes(
    result: Dict[str, Any],
    message: Dict[str, Any],
    meta: Dict[str, Any]
) -> list:
    """
    Transaction içerisindeki SOL balance değişimlerini çıkarır.
    """

    pre = meta.get(
        "preBalances"
    ) or []


    post = meta.get(
        "postBalances"
    ) or []


    account_keys = (
        message.get(
            "accountKeys"
        ) or []
    )


    changes = []


    count = min(
        len(pre),
        len(post),
        len(account_keys)
    )


    for index in range(
        count
    ):

        account = (
            account_keys[index]
        )


        if isinstance(
            account,
            dict
        ):

            pubkey = account.get(
                "pubkey"
            )

        else:

            pubkey = account


        if not pubkey:
            continue


        pre_sol = (
            float(pre[index])
            / 1_000_000_000
        )


        post_sol = (
            float(post[index])
            / 1_000_000_000
        )


        delta = (
            post_sol
            - pre_sol
        )


        changes.append({

            "wallet": pubkey,

            "account_index": index,

            "pre_sol": pre_sol,

            "post_sol": post_sol,

            "delta_sol": delta,
        })


    return changes


# ============================================================
# BUY INSTRUCTION DETECTION
# ============================================================

def _detect_buy_instruction(
    logs: list
) -> Optional[str]:
    """
    Pump.fun BUY instruction'ını loglardan tespit eder.

    Desteklenen:

    buy
    buy_v2
    buy_exact_quote_in
    buy_exact_quote_in_v2
    """

    buy_names = (
        "buy_exact_quote_in_v2",
        "buy_exact_quote_in",
        "buy_v2",
        "buy",
    )


    for log in logs:

        text = (
            str(log)
            .lower()
        )


        if (
            "instruction:"
            not in text
        ):
            continue


        for name in buy_names:

            if name in text:

                return name


    return None


# ============================================================
# SELL INSTRUCTION DETECTION
# ============================================================

def _detect_sell_instruction(
    logs: list
) -> Optional[str]:
    """
    Pump.fun SELL instruction'ını tespit eder.
    """

    sell_names = (
        "sell_v2",
        "sell",
    )


    for log in logs:

        text = (
            str(log)
            .lower()
        )


        if (
            "instruction:"
            not in text
        ):
            continue


        for name in sell_names:

            if name in text:

                return name


    return None


# ============================================================
# BUYER DETECTION
# ============================================================

def _detect_buyer(
    message: Dict[str, Any],
    token_changes: list
) -> Optional[str]:
    """
    Token miktarı artan wallet'lar arasından
    signer olan wallet'ı buyer olarak seçer.
    """

    signers = set(
        _get_signer_keys(
            message
        )
    )


    candidates = []


    for change in token_changes:

        owner = change.get(
            "owner"
        )


        delta = change.get(
            "delta",
            0
        )


        if not owner:
            continue


        if delta <= 0:
            continue


        candidates.append({
            "owner": owner,
            "delta": delta,
            "signer": owner in signers,
        })


    # Önce signer olan pozitif token değişimini seç

    signer_candidates = [
        item
        for item in candidates
        if item["signer"]
    ]


    if signer_candidates:

        signer_candidates.sort(
            key=lambda x: x["delta"],
            reverse=True
        )


        return signer_candidates[0][
            "owner"
        ]


    # Fallback:
    # En büyük token artışı

    if candidates:

        candidates.sort(
            key=lambda x: x["delta"],
            reverse=True
        )


        return candidates[0][
            "owner"
        ]


    return None


# ============================================================
# BUY AMOUNT
# ============================================================

def _detect_buy_amount(
    token_changes: list,
    buyer: Optional[str]
) -> float:
    """
    Buyer'ın aldığı token miktarını bulur.
    """

    if not buyer:
        return 0.0


    total = 0.0


    for change in token_changes:

        if change.get(
            "owner"
        ) != buyer:

            continue


        delta = change.get(
            "delta",
            0
        )


        if delta > 0:

            total += float(
                delta
            )


    return total


# ============================================================
# BUY SOL AMOUNT
# ============================================================

def _detect_buy_sol(
    result: Dict[str, Any],
    buyer: Optional[str],
    sol_changes: list
) -> float:
    """
    Buyer'ın transaction sırasında kaybettiği SOL'u
    yaklaşık buy amount olarak hesaplar.

    Eğer buyer fee payer ise transaction fee çıkarılır.
    """

    if not buyer:
        return 0.0


    spent = 0.0


    for change in sol_changes:

        if change.get(
            "wallet"
        ) != buyer:

            continue


        delta = change.get(
            "delta_sol",
            0
        )


        if delta < 0:

            spent = abs(
                float(delta)
            )

            break


    if spent <= 0:
        return 0.0


    account_keys = (
        (
            result.get(
                "transaction"
            ) or {}
        )
        .get(
            "message"
        )
        or {}
    ).get(
        "accountKeys"
    ) or []


    fee = (
        result.get(
            "meta"
        ) or {}
    ).get(
        "fee",
        0
    )


    # İlk account genellikle fee payer'dır.

    fee_payer = None


    if account_keys:

        first = account_keys[0]


        if isinstance(
            first,
            dict
        ):

            fee_payer = first.get(
                "pubkey"
            )

        else:

            fee_payer = first


    if buyer == fee_payer:

        spent -= (
            float(fee)
            / 1_000_000_000
        )


    if spent < 0:

        spent = 0.0


    return spent


# ============================================================
# PUMP PROGRAM DETECTION
# ============================================================

def _detect_program(
    program_ids: list
) -> Optional[str]:
    """
    Transaction Pump.fun programını kullanıyor mu?
    """

    if PUMP_PROGRAM_ID in program_ids:

        return "pump"


    return None


# ============================================================
# PARSE TRANSACTION
# ============================================================

def parse_transaction(
    data: Dict[str, Any],
    tracked_mint: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Helius transaction verisini standart
    Patoshi Radar V5.1 event nesnesine dönüştürür.
    """

    try:

        # ====================================================
        # RESULT
        # ====================================================

        result = _get_result(
            data
        )


        if not result:
            return None


        # ====================================================
        # TRANSACTION
        # ====================================================

        transaction = (
            result.get(
                "transaction"
            )
        )


        if not isinstance(
            transaction,
            dict
        ):

            return None


        message = (
            transaction.get(
                "message"
            ) or {}
        )


        meta = (
            result.get(
                "meta"
            ) or {}
        )


        if not isinstance(
            message,
            dict
        ):

            message = {}


        if not isinstance(
            meta,
            dict
        ):

            meta = {}


        # ====================================================
        # BASIC DATA
        # ====================================================

        signature = result.get(
            "signature"
        )


        slot = result.get(
            "slot"
        )


        timestamp = result.get(
            "blockTime"
        )


        # ====================================================
        # PROGRAMS
        # ====================================================

        program_ids = (
            _get_program_ids(
                message
            )
        )


        logs = _get_logs(
            meta
        )


        instructions = (
            _get_instructions(
                message,
                meta
            )
        )


        pump_program = (
            _detect_program(
                program_ids
            )
        )


        # ====================================================
        # MINT MATCH
        # ====================================================

        tracked = False


        if tracked_mint:

            tracked = (
                transaction_mentions_mint(
                    result,
                    tracked_mint
                )
            )


        # ====================================================
        # TOKEN CHANGES
        # ====================================================

        token_balance_changes = []


        if tracked_mint:

            token_balance_changes = (
                _get_token_balance_changes(
                    meta,
                    tracked_mint
                )
            )


        # ====================================================
        # SOL CHANGES
        # ====================================================

        sol_balance_changes = (
            _get_sol_balance_changes(
                result,
                message,
                meta
            )
        )


        # ====================================================
        # BUY / SELL
        # ====================================================

        buy_instruction = (
            _detect_buy_instruction(
                logs
            )
        )


        sell_instruction = (
            _detect_sell_instruction(
                logs
            )
        )


        # ====================================================
        # BUYER
        # ====================================================

        buyer = None

        buy_amount = 0.0

        buy_sol = 0.0

        first_buy = False


        if (
            tracked
            and buy_instruction
            and token_balance_changes
        ):

            buyer = _detect_buyer(
                message,
                token_balance_changes
            )


            buy_amount = (
                _detect_buy_amount(
                    token_balance_changes,
                    buyer
                )
            )


            buy_sol = (
                _detect_buy_sol(
                    result,
                    buyer,
                    sol_balance_changes
                )
            )


            if (
                buyer
                and buy_amount > 0
            ):

                first_buy = True


        # ====================================================
        # EVENT TYPE
        # ====================================================

        event_type = "UNKNOWN"


        if first_buy:

            event_type = "FIRST_BUY"

        elif buy_instruction:

            event_type = "BUY"

        elif sell_instruction:

            event_type = "SELL"


        # ====================================================
        # STANDARD EVENT
        # ====================================================

        event = {

            # Parser
            "version": "5.1",

            # Network
            "network": "mainnet",

            # Event
            "type": event_type,

            "status": (
                "FAILED"
                if meta.get(
                    "err"
                )
                else "CONFIRMED"
            ),

            # Blockchain
            "signature": signature,

            "slot": slot,

            "timestamp": timestamp,

            # Token
            "mint": tracked_mint,

            "name": None,

            "symbol": None,

            # Wallet
            "buyer": buyer,

            "seller": None,

            "creator": None,

            # DEX
            "dex": (
                "pump"
                if pump_program
                else None
            ),

            # Financial
            "amount_sol": buy_sol,

            "token_amount": buy_amount,

            # Detection
            "lp_created": False,

            "first_buy": first_buy,

            "whale_buy": False,

            # Tracking
            "tracked": tracked,

            # =================================================
            # TRANSACTION ANATOMY
            # =================================================

            "program_ids": program_ids,

            "instructions": instructions,

            "inner_instructions": (
                meta.get(
                    "innerInstructions"
                ) or []
            ),

            "sol_balance_changes":
                sol_balance_changes,

            "token_balance_changes":
                token_balance_changes,

            # =================================================
            # PUMP
            # =================================================

            "pump_program":
                pump_program,

            "buy_instruction":
                buy_instruction,

            "sell_instruction":
                sell_instruction,

            # =================================================
            # ANALYSIS
            # =================================================

            "analysis": {

                "engine":
                    "Patoshi Radar",

                "version":
                    "5.1",

                "program":
                    pump_program,

                "instruction":
                    (
                        buy_instruction
                        or sell_instruction
                    ),

                "score": 0,

                "confidence": 0,

                "matched": [],

                "reason": [],

                "warnings": [],

                "errors": [],
            },

            # =================================================
            # RAW DATA
            # =================================================

            "transaction":
                transaction,

            "message":
                message,

            "meta":
                meta,

            "raw":
                result,
        }


        # ====================================================
        # ANALYSIS REASONS
        # ====================================================

        if tracked:

            event["analysis"][
                "matched"
            ].append(
                "tracked_mint"
            )


        if pump_program:

            event["analysis"][
                "matched"
            ].append(
                "pump_program"
            )


        if buy_instruction:

            event["analysis"][
                "matched"
            ].append(
                "buy_instruction"
            )


        if first_buy:

            event["analysis"][
                "matched"
            ].append(
                "first_buy"
            )


            event["analysis"][
                "reason"
            ].append(
                "Positive token balance "
                "change detected for buyer"
            )


        # ====================================================
        # CONFIDENCE
        # ====================================================

        confidence = 0


        if tracked:
            confidence += 30


        if pump_program:
            confidence += 25


        if buy_instruction:
            confidence += 25


        if buyer:
            confidence += 10


        if buy_amount > 0:
            confidence += 10


        event["analysis"][
            "confidence"
        ] = min(
            confidence,
            100
        )


        # ====================================================
        # DEBUG SUMMARY
        # ====================================================

        if tracked:

            print(
                "🧬 V5.1 PARSER"
            )

            print(
                f"   Type       : "
                f"{event['type']}"
            )

            print(
                f"   Mint       : "
                f"{tracked_mint}"
            )

            print(
                f"   Signature  : "
                f"{signature}"
            )

            print(
                f"   Pump       : "
                f"{pump_program}"
            )

            print(
                f"   Instruction: "
                f"{buy_instruction}"
            )

            print(
                f"   Buyer      : "
                f"{buyer}"
            )

            print(
                f"   Token Amt  : "
                f"{buy_amount}"
            )

            print(
                f"   SOL Amount : "
                f"{buy_sol}"
            )

            print(
                f"   First Buy  : "
                f"{first_buy}"
            )

            print(
                f"   Confidence : "
                f"{event['analysis']['confidence']}"
            )


        return event


    except Exception as e:

        print(
            "❌ V5.1 Transaction Parser Hatası"
        )

        print(
            f"   {type(e).__name__}: {e}"
        )

        return None
