import json
import time

from database import initialize_database
from cache import already_sent, mark_sent
from pump_monitor import PumpMonitor
from telegram_sender import send_message
from filters import keyword_match, creator_match
from notifier import build_message
from creator_tracker import update_creator
from alchemy_activity_watch import add_token, start as start_alchemy_watch, set_result_callback


def _short(value, length=18):
    if not value:
        return "-"
    value = str(value)
    return value if len(value) <= length else value[:length] + "..."


def on_activity_complete(result):
    if not result:
        return
    try:
        mint = result.get("mint", "")
        summaries = result.get("transfer_summary") or []
        lines = [f"{x['label']} — {x['reason']}" for x in summaries[:6]]
        transfer_text = "\n".join(lines) if lines else "🟢 Kayda değer SPL transferi tespit edilmedi."
        message = (
            "🔬 <b>PATOSHI RADAR — V5.2 WATCH</b>\n\n"
            f"🧨 <b>{result.get('name', 'Bilinmiyor')}</b> ({result.get('symbol', '-')})\n\n"
            f"💧 <b>LP:</b> {'✅ VAR' if result.get('lp_detected') else '❌ YOK'}\n"
            f"🏛️ <b>DEX:</b> {result.get('dex_name') or ('Tespit edildi' if result.get('dex_detected') else '❌ YOK')}\n"
            f"🛒 <b>First Buy:</b> {'✅ VAR' if result.get('buy_detected') else '❌ YOK'}\n\n"
            f"<b>Transfer Watch</b>\n{transfer_text}\n\n"
            f"🌐 <code>{_short(mint, 20)}</code>\n"
            f'<a href="https://pump.fun/{mint}">Pump.fun</a>'
        )
        send_message(message)
    except Exception as exc:
        print(f"❌ V5.2 callback hatası => {exc}", flush=True)


def new_token(data):
    print(json.dumps(data, indent=2, ensure_ascii=False), flush=True)
    creator = data.get("traderPublicKey", "")
    creator_info = update_creator(creator)
    name = data.get("name", "Bilinmiyor")
    symbol = data.get("symbol", "-")
    mint = data.get("mint", "")
    market_cap = data.get("marketCapSol", 0)
    launch_signature = data.get("signature", "")

    if not mint or already_sent(mint):
        return

    creator_name = creator_match(creator)
    keyword = keyword_match(name, symbol)
    if not creator_name and not keyword:
        return

    message = build_message(
        name=name,
        symbol=symbol,
        market_cap=market_cap,
        mint=mint,
        creator=creator,
        creator_name=creator_name,
        keyword=keyword,
        creator_info=creator_info,
    )

    # First alert stays immediate. V5.2 starts only after Telegram succeeds.
    if send_message(message):
        mark_sent(mint, name, symbol, creator)
        add_token(
            mint=mint,
            name=name,
            symbol=symbol,
            creator=creator,
            launch_signature=launch_signature,
        )
        print(f"🚀 V5.2 WATCH EKLENDİ => {name} ({symbol}) | {mint}", flush=True)


initialize_database()
set_result_callback(on_activity_complete)
start_alchemy_watch()

print("🚀 Patoshi Radar V5.2 başlatılıyor...", flush=True)
print("📡 PumpPortal → Keywords → Telegram → Activity + SPL Transfer Watch", flush=True)
print("ℹ️ PATOSHI_TREASURY_WALLET opsiyoneldir; boş olsa da V5.2 çalışır.", flush=True)

monitor = PumpMonitor(new_token)
monitor.start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("🛑 Patoshi Radar durduruldu.", flush=True)
