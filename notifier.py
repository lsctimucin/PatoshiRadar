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

    score = calculate_score(
        creator_name,
        keyword,
        market_cap
    )

    # Confidence Emoji
    if score >= 80:
        confidence = "🟢"

    elif score >= 50:
        confidence = "🟡"

    else:
        confidence = "🔴"

    # MarketCap Emoji
    if market_cap >= 100:
        mc = "🟢"

    elif market_cap >= 50:
        mc = "🟡"

    elif market_cap >= 20:
        mc = "🟠"

    else:
        mc = "🔴"

    # Kısa Mint
    short_mint = (
        mint[:6] + "..." + mint[-6:]
        if len(mint) > 12
        else mint
    )

    # Creator Durumu
    if creator_info["is_new"]:
        creator_state = "🆕 İlk Launch"

    elif creator_info["seconds"] < 60:
        creator_state = f"🚨 Launch #{creator_info['count']}"

    elif creator_info["minutes"] < 10:
        creator_state = f"⚠️ Launch #{creator_info['count']}"

    else:
        creator_state = f"✅ Launch #{creator_info['count']}"

    # Bildirim Sebebi
    reasons = []

    if keyword:
        reasons.append(f"🔍 Keyword: <b>{keyword}</b>")

    if creator_name:
        reasons.append(f"🎯 Creator Match: <b>{creator_name}</b>")

    if not reasons:
        reasons.append("❓ Bilinmeyen Eşleşme")

    reason_text = "\n".join(reasons)

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    return f"""🚀 <b>PATOSHI RADAR</b>

📛 <b>{name} ({symbol})</b>

{reason_text}

👤 Creator
{creator_state}

💰 {market_cap:.2f} SOL {mc}
🎯 {score}/100 {confidence}

🪙 <code>{short_mint}</code>

⏰ {now}

🔗 <a href="https://pump.fun/{mint}">Pump.fun</a>
"""
