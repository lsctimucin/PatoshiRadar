import json
from pump_monitor import PumpMonitor
from telegram_sender import send_message


def new_token(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))

    name = data.get("name", "Bilinmiyor")
    symbol = data.get("symbol", "-")
    mint = data.get("mint", "")
    market_cap = data.get("marketCapSol", 0)

    # Aranacak kelimeler
    keywords = [
        "patoshi",
        "pat",
        "turan",
        "pato",
        "patos",
        "enes",
        "parad",
        "paradot",
        "paradotor",
        "patosh",
    ]

    text = f"{name} {symbol}".lower()

    if not any(keyword in text for keyword in keywords):
        return

    message = f"""🚀 Yeni Coin!

📛 İsim: {name}
💎 Sembol: {symbol}
💰 Market Cap: {market_cap:.2f} SOL

https://pump.fun/{mint}
"""

    print(message)
    send_message(message)


monitor = PumpMonitor(new_token)

monitor.start()

print("Patoshi Radar çalışıyor...")

while True:
    pass
