"""
Patoshi Radar
Transaction Parser

Görev:

- Helius WebSocket'ten gelen transaction'ları ayrıştırır.
- Standart event nesnesi üretir.
- Tüm analiz modülleri bu event nesnesi üzerinden çalışır.
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

        # null gelebileceği için güvenli kullanım
        meta = result.get("meta") or {}
        message = transaction.get("message") or {}

        event = {

            # Parser Bilgisi
            "version": "4.0",

            # Blockchain Network
            "network": "mainnet",

            # Event Bilgisi
            "type": "UNKNOWN",
            "status": "NEW",

            # Blockchain Bilgileri
            "signature": result.get("signature"),
            "slot": result.get("slot"),
            "timestamp": result.get("blockTime"),

            # Coin Bilgileri
            "mint": None,
            "name": None,
            "symbol": None,

            # Wallet Bilgileri
            "buyer": None,
            "seller": None,
            "creator": None,

            # DEX Bilgileri
            "dex": None,

            # Finansal Bilgiler
            "amount_sol": 0.0,
            "token_amount": 0.0,

            # Event Durumları
            "lp_created": False,
            "first_buy": False,
            "whale_buy": False,

            # Analiz Sonuçları
            "analysis": {

                # Analiz Motoru
                "engine": "Patoshi Radar",

                # Analiz Motoru Versiyonu
                "version": "4.0",

                # Tespit Edilen Program
                "program": None,

                # Tespit Edilen Instruction
                "instruction": None,

                # Analiz Skoru
                "score": 0,

                # Güven Skoru (0-100)
                "confidence": 0,

                # Eşleşen Kurallar
                "matched": [],

                # Analiz Sebepleri
                "reason": [],

                # Uyarılar
                "warnings": [],

                # Parser / Analiz Hataları
                "errors": []
            },

            # Ham Blockchain Verileri
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
