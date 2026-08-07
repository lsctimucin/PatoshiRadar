"""
Patoshi Radar
V5.1 - Transaction Parser

Görev:
- Helius WebSocket'ten gelen transaction'ları güvenli şekilde ayrıştırır.
- Chain Monitor için standart bir event nesnesi üretir.
- Takip edilen mint ile transaction arasındaki bağlantıyı belirler.

ÖNEMLİ:
Bu sürüm henüz LP / DEX / First Swap tespiti yapmaz.
Bu alanlar gerçek Helius transaction örnekleri incelendikten sonra
ayrı detection kurallarıyla doldurulacaktır.
"""

from typing import Any, Dict, Optional


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


def _get_account_keys(message: Dict[str, Any]) -> list[str]:
    """
    jsonParsed transaction formatındaki accountKeys alanını güvenli
    şekilde string public key listesine dönüştürür.
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


def _mint_in_instructions(message: Dict[str, Any], mint: str) -> bool:
    """Parsed instruction'larda mint alanını kontrol eder."""

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


def _mint_in_token_balances(meta: Dict[str, Any], mint: str) -> bool:
    """
    preTokenBalances / postTokenBalances içerisinde takip edilen mint'i
    kontrol eder.
    """

    balance_fields = (
        "preTokenBalances",
        "postTokenBalances",
    )

    for field in balance_fields:

        for balance in meta.get(field) or []:

            if not isinstance(balance, dict):
                continue

            if balance.get("mint") == mint:
                return True

    return False


def _mint_in_logs(meta: Dict[str, Any], mint: str) -> bool:
    """Transaction loglarında mint adresini kontrol eder."""

    for log in meta.get("logMessages") or []:

        if mint in str(log):
            return True

    return False


def transaction_mentions_mint(
    result: Dict[str, Any],
    mint: str
) -> bool:
    """
    Transaction'ın verilen mint ile ilişkisini kontrol eder.

    Bu fonksiyon LP veya swap tespiti değildir.

    Yalnızca:
    - accountKeys
    - parsed instructions
    - token balances
    - logMessages

    üzerinden transaction ↔ mint bağlantısı arar.
    """

    if not mint:
        return False

    transaction = result.get("transaction") or {}
    message = transaction.get("message") or {}
    meta = result.get("meta") or {}

    # 1. Account keys
    if mint in _get_account_keys(message):
        return True

    # 2. Parsed instructions
    if _mint_in_instructions(message, mint):
        return True

    # 3. Token balances
    if _mint_in_token_balances(meta, mint):
        return True

    # 4. Log messages
    if _mint_in_logs(meta, mint):
        return True

    return False


def parse_transaction(
    data: Dict[str, Any],
    tracked_mint: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Helius transaction verisini standart Patoshi Radar event nesnesine
    dönüştürür.

    tracked_mint verilirse event['tracked'] alanı ile transaction'ın
    o mint'e ait olup olmadığı belirtilir.
    """

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

            # V5.1 tracking
            "tracked": False,

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

            # Raw data retained for later detection development
            "transaction": transaction,
            "message": message,
            "meta": meta,
            "raw": result,
        }

        if tracked_mint:
            event["tracked"] = transaction_mentions_mint(
                result,
                tracked_mint
            )

        return event

    except Exception as e:

        print("❌ V5.1 Transaction Parser Hatası")
        print(e)

        return None
