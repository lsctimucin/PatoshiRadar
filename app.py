import json
import time

from database import initialize_database
from cache import already_sent, mark_sent

from pump_monitor import PumpMonitor
from telegram_sender import send_message

from filters import keyword_match, creator_match
from notifier import build_message
from creator_tracker import update_creator

import alchemy_activity_watch
from alchemy_activity_watch import add_token, start as start_alchemy_watch, set_result_callback
from transfer_watch import install as install_transfer_watch


def _short(value, length=18):
    if not value:
        return "-"
    value = str(value)
    return value if len(value) <= length else value[:length] + "..."


def _short_wallet(value, length=10):
    if not value:
        return "-"
    value = str(value)
    return value if len(value) <= length * 2 + 3 else value[:length] + "..." + value[-length:]


def on_transfer_event(event):
    if not event:
        return
    try:
        labels = {
            "CREATOR_TRANSFER": "🔴 <b>CREATOR TRANSFER</b>",
            "TREASURY_TRANSFER": "🟣 <b>TREASURY TRANSFER</b>",
            "BULK_DISTRIBUTION": "🟠 <b>BULK / MULTI-WALLET</b>",
            "OFFICIAL_DISTRIBUTION": "🔵 <b>POSSIBLE OFFICIAL DISTRIBUTION</b>",
            "ORDINARY_TRANSFER": "🟢 <b>ORDINARY TRANSFER</b>",
        }
        title = labels.get(event.get("type"), labels["ORDINARY_TRANSFER"])
        senders = list((event.get("senders") or {}).items())[:3]
        recipients = list((event.get("recipients") or {}).items())[:5]
        sender_text = "\n".join(
            f"• <code>{_short_wallet(w)}</code> → {a:g}" for w, a in senders
        ) or "-"
        recipient_text = "\n".join(
            f"• <code>{_short_wallet(w)}</code> ← {a:g}" for w, a in recipients
        ) or "-"
        message = (
            "🔎 <b>PATOSHI RADAR — V5.2 TRANSFER WATCH</b>\n\n"
            f"{title}\n"
            f"🧠 {event.get('reason', '-')}\n\n"
            f"📤 <b>Senders:</b> {event.get('sender_count', 0)}\n{sender_text}\n\n"
            f"📥 <b>Recipients:</b> {event.get('recipient_count', 0)}\n{recipient_text}\n\n"
            f"🪙 <b>Total received:</b> {event.get('total_received', 0):g}\n"
            f"🌐 <code>{event.get('mint', '-')}</code>\n"
            f"🔗 <a href=\"https://solscan.io/tx/{event.get('signature', '')}\">Transaction</a>"
        )
        if send_message(message):
            print(
                f"📨 V5.2 TRANSFER TELEGRAM GÖNDERİLDİ => "
                f"{event.get('mint')} | {event.get('type')}",
                flush=True,
            )
    except Exception as exc:
        print(f"❌ V5.2 Transfer Telegram callback hatası => {exc}", flush=True)


def on_activity_complete(result):
    """Alchemy 60 saniyelik watch tamamlandığında ikinci Telegram mesajı."""
    if not result:
        return
    try:
        name = result.get("name", "Bilinmiyor")
        symbol = result.get("symbol", "-")
        mint = result.get("mint", "")
        lp = bool(result.get("lp_detected"))
        dex = result.get("dex_name") or ("Tespit edildi" if result.get("dex_detected") else "-")
        buy = bool(result.get("buy_detected"))
        elapsed = int(result.get("elapsed_seconds", 60))
        lp_text = "✅ VAR" if lp else "❌ YOK"
        dex_text = f"🏛️ {dex}" if result.get("dex_detected") else "❌ YOK"
        buy_text = "✅ VAR" if buy else "❌ YOK"
        message = (
            "🔬 <b>PATOSHI RADAR — ACTIVITY WATCH</b>\n\n"
            f"🧨 <b>{name}</b> ({symbol})\n\n"
            f"💧 <b>LP:</b> {lp_text}\n"
            f"{dex_text}\n"
            f"🛒 <b>First Buy:</b> {buy_text}\n\n"
            f"⏱️ Watch: {elapsed}s\n\n"
            f"🌐 <code>{_short(mint, 20)}</code>\n\n"
            f'<a href="https://pump.fun/{mint}">Pump.fun</a>'
        )
        if send_message(message):
            print(
                f"📨 V5.1 ALCHEMY TELEGRAM GÖNDERİLDİ => "
                f"{mint} | LP={lp} | DEX={result.get('dex_detected')} | BUY={buy}",
                flush=True,
            )
    except Exception as exc:
        print(f"❌ V5.1 Activity Telegram callback hatası => {exc}", flush=True)


def new_token(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))
    creator = data.get("traderPublicKey", "")
    print(f"CREATOR => {creator}")

    creator_info = update_creator(creator)
    name = data.get("name", "Bilinmiyor")
    symbol = data.get("symbol", "-")
    mint = data.get("mint", "")
    market_cap = data.get("marketCapSol", 0)
    launch_signature = data.get("signature", "")

    if not mint:
        return
    if already_sent(mint):
        print(f"⏩ Daha önce bildirildi: {mint}")
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

    print(message)
    if send_message(message):
        mark_sent(mint, name, symbol, creator)
        print(f"🚀 V5.2 WATCH EKLENİYOR => {name} ({symbol}) | {mint}", flush=True)
        add_token(
            mint=mint,
            name=name,
            symbol=symbol,
            creator=creator,
            launch_signature=launch_signature,
        )


initialize_database()
set_result_callback(on_activity_complete)
install_transfer_watch(alchemy_activity_watch, on_transfer_event)
start_alchemy_watch()

print("🚀 Patoshi Radar V5.2 başlatılıyor...", flush=True)
print("📡 PumpPortal → Telegram → Alchemy 60s Activity Watch + Transfer Watch", flush=True)

monitor = PumpMonitor(new_token)
monitor.start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("🛑 Patoshi Radar durduruldu.")
