from datetime import datetime


def calculate_score(
    creator_name,
    keyword,
    market_cap
):
    score = 0

    # Creator Match
    if creator_name:
        score += 70

    # Keyword Match
    if keyword:
        score += 20

    # MarketCap Bonus
    if market_cap >= 50:
        score += 10

    return min(score, 100)


def marketcap_status(market_cap):

    if market_cap >= 100:
        return "🟢 ÇOK GÜÇLÜ"

    elif market_cap >= 50:
        return "🟡 GÜÇLÜ"

    elif market_cap >= 20:
        return "🟠 ORTA"

    else:
        return "🔴 DÜŞÜK"


def build_message(
    name,
    symbol,
    market_cap,
    mint,
    creator,
    creator_name,
    keyword,
    creator_info,
):

    reasons = []

    if creator_name:
        reasons.append(f"🎯 <b>Creator Match</b>\n{creator_name}")

    if keyword:
        reasons.append(f"🔍 <b>Keyword Match</b>\n{keyword}")

    if not reasons:
        reasons.append("❓ <b>Bilinmeyen Eşleşme</b>")

    reason_text = "\n\n".join(reasons)

    score = calculate_score(
        creator_name,
        keyword,
        market_cap
    )

    if score >= 80:
        status = "🟢 YÜKSEK"
    elif score >= 50:
        status = "🟡 ORTA"
    else:
        status = "🔴 DÜŞÜK"

    mc_status = marketcap_status(market_cap)

    short_creator = (
        creator[:6] + "..." + creator[-6:]
        if len(creator) > 12
        else creator
    )

    short_mint = (
        mint[:6] + "..." + mint[-6:]
        if len(mint) > 12
        else mint
    )

    if creator_info["is_new"]:
        creator_state = "🆕 İlk kez görüldü"

    elif creator_info["seconds"] < 60:
        creator_state = "🚨 Çok kısa sürede tekrar coin bastı"

    elif creator_info["minutes"] < 10:
        creator_state = "⚠️ Yakın zamanda tekrar coin bastı"

    else:
        creator_state = "✅ Normal"

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    return f"""🚀 <b>PATOSHI RADAR</b>

{reason_text}

━━━━━━━━━━━━━━

🎯 <b>Confidence</b>

{score}/100

{status}

━━━━━━━━━━━━━━

📛 <b>İsim</b>

{name}

💎 <b>Sembol</b>

{symbol}

💰 <b>Market Cap</b>

{market_cap:.2f} SOL

{mc_status}

━━━━━━━━━━━━━━

👤 <b>Creator</b>

{short_creator}

<code>{creator}</code>

📊 <b>Creator Analizi</b>

Toplam Launch : {creator_info["count"]}

Durum : {creator_state}

━━━━━━━━━━━━━━

🪙 <b>Mint</b>

{short_mint}

<code>{mint}</code>

━━━━━━━━━━━━━━

⏰ <b>Tespit</b>

{now}

━━━━━━━━━━━━━━

🔗 <b>Pump.fun</b>

https://pump.fun/{mint}
"""
