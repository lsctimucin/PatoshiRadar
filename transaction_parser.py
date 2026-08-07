"""
Patoshi Radar
Transaction Parser

Görev:
- Helius WebSocket'ten gelen transaction'ları yorumlar.
- Standart event nesneleri üretir.
"""


def parse_transaction(data):
    """
    Helius transaction verisini ayrıştırır.

    Döndürür:
        None veya event dict
    """

    try:

        params = data.get("params")
        if not params:
            return None

        result = params.get("result")
        if not result:
            return None

        transaction = result.get("transaction")
        if not transaction:
            return None

        meta = result.get("meta", {})
        message = transaction.get("message", {})

        event = {
            # Event bilgisi
            "type": "UNKNOWN",

            # Blockchain bilgileri
            "signature": result.get("signature"),
            "slot": result.get("slot"),
            "timestamp": result.get("blockTime"),

            # İleride doldurulacak alanlar
            "mint": None,
            "dex": None,
            "buyer": None,
            "creator": None,
            "amount_sol": 0.0,
            "lp_created": False,

            # Ham veriler
            "transaction": transaction,
            "message": message,
            "meta": meta,
            "raw": result
        }

        return event

    except Exception as e:

        print("❌ Transaction Parser Hatası")
        print(e)

        return None
