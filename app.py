def new_token(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))

    creator = data.get("traderPublicKey", "")
    print(f"CREATOR => {creator}")

    name = data.get("name", "Bilinmiyor")
    symbol = data.get("symbol", "-")
    mint = data.get("mint", "")
    market_cap = data.get("marketCapSol", 0)

    # Aynı mint daha önce gönderildiyse çık
    if already_sent(mint):
        print(f"⏩ Daha önce bildirildi: {mint}")
        return

    # 1. Creator kontrolü
    if creator_match(creator):
        message = build_message(
            name=name,
            symbol=symbol,
            market_cap=market_cap,
            mint=mint,
            creator=creator,
            reason="🎯 Creator Match"
        )

        print(message)
        send_message(message)

        mark_sent(
            mint,
            name,
            symbol,
            creator
        )

        return

    # 2. Keyword kontrolü
    if keyword_match(name, symbol):
        message = build_message(
            name=name,
            symbol=symbol,
            market_cap=market_cap,
            mint=mint,
            creator=creator,
            reason="🔍 Keyword Match"
        )

        print(message)
        send_message(message)

        mark_sent(
            mint,
            name,
            symbol,
            creator
        )
