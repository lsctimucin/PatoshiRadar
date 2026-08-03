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

    # Filtreler
    creator_name = creator_match(creator)
    keyword = keyword_match(name, symbol)

    # Hiçbir eşleşme yoksa çık
    if not creator_name and not keyword:
        return

    # Tek mesaj oluştur
    message = build_message(
        name=name,
        symbol=symbol,
        market_cap=market_cap,
        mint=mint,
        creator=creator,
        creator_name=creator_name,
        keyword=keyword,
    )

    print(message)

    # Telegram başarılıysa kaydet
    if send_message(message):
        mark_sent(
            mint,
            name,
            symbol,
            creator
        )
