from pump_monitor import PumpMonitor
from telegram_sender import send_message


def new_token(data):

    name = data.get("name", "Bilinmiyor")
    symbol = data.get("symbol", "-")
    mint = data.get("mint", "")
    market_cap = data.get("marketCapSol", 0)

    # Sadece "patoshi" geçen coinleri gönder
    search = "patoshi"

    if search not in name.lower() and search not in symbol.lower():
        return

    message = f"""🚀 Yeni Coin!

📛 İsim: {name}
💎 Sembol: {symbol}
💰 Market Cap: {market_cap} SOL

https://pump.fun/{mint}
"""

    print(message)

    send_message(message)


monitor = PumpMonitor(new_token)

monitor.start()

print("Patoshi Radar çalışıyor...")

while True:
    pass
