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
        reasons.append(
            f"🎯 Creator Match\n{creator_name}"
        )

    if keyword:
        reasons.append(
            f"🔍 Keyword Match\n{keyword}"
        )

    reason_text = "\n\n".join(reasons)

    return f"""🚀 Yeni Coin!

{reason_text}

━━━━━━━━━━━━━━

📛 İsim
{name}

💎 Sembol
{symbol}

💰 Market Cap
{market_cap:.2f} SOL

━━━━━━━━━━━━━━

👤 Creator

{creator}

https://pump.fun/{mint}
"""
