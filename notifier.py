def build_message(name, symbol, market_cap, mint, creator, reason):

    return f"""🚀 Yeni Coin!

🎯 Sebep : {reason}

📛 İsim : {name}
💎 Sembol : {symbol}
💰 Market Cap : {market_cap:.2f} SOL

👤 Creator
{creator}

https://pump.fun/{mint}
"""
