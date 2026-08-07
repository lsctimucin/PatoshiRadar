from datetime import datetime


def calculate_score(
    creator_name,
    keyword,
    market_cap
):
    score = 0

    if creator_name:
        score += 60

    if keyword:
        score += 25

    if market_cap >= 20:
        score += 15

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
):

    reasons = []

    if creator_name:
        reasons.append(f"🎯 Creator Match\n{creator_name}")

    if keyword:
        reasons.append(f"🔍 Keyword Match\n{keyword}")

    if not reasons:
        reasons.append("❓ Bilinmeyen Eşleşme")

    reason_text = "\n\n".join(reasons)

    score = calculate_score(
        creator_name,
        keyword,
        market_cap
    )

    mc_status = marketcap_status(market_cap)

    if score >= 80:
        status = "🟢 YÜKSEK"
    elif score >= 50:
        status = "🟡 ORTA"
    else:
        status = "🔴 DÜŞÜK"

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

👤 <b>Creator</b>

{short_creator}

🪙 <b>Mint</b>

{short_mint}

⏰ <b>Tespit</b>

{now}

━━━━━━━━━━━━━━

🔗 https://pump.fun/{mint}
"""
