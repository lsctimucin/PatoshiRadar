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

    if score > 100:
        score = 100

    return score


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

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    return f"""🚀 <b>PATOSHI RADAR</b>

{reason_text}

━━━━━━━━━━━━━━

📛 <b>İsim</b>
{name}

💎 <b>Sembol</b>
{symbol}

💰 <b>Market Cap</b>
{market_cap:.2f} SOL

👤 <b>Creator</b>
<code>{creator}</code>

🪙 <b>Mint</b>
<code>{mint}</code>

⏰ <b>Tespit</b>
{now}

━━━━━━━━━━━━━━

🔗 https://pump.fun/{mint}
"""
