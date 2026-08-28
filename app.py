import json
import time

from database import initialize_database
from cache import already_sent, mark_sent
from pump_monitor import PumpMonitor
from telegram_sender import send_message
from filters import keyword_match, creator_match
from notifier import build_message
from creator_tracker import update_creator
from alchemy_activity_watch import (
    add_token,
    start as start_alchemy_watch,
    set_result_callback,
)
from long_transfer_watch import (
    add_token as add_long_transfer_token,
    start as start_long_transfer_watch,
    set_alert_callback as set_long_transfer_callback,
)


def _short(value, length=18):
    if not value:
        return "-"
    value = str(value)
    return value if len(value) <= length else value[:length] + "..."


def _format_elapsed(seconds):
    seconds = max(0, int(seconds or 0))
    minutes, seconds = divmod(seconds, 60)
    if minutes:
        return f"{minutes} dk {seconds} sn"
    return f"{seconds} sn"


def on_long_transfer_alert(result):
    if not result:
        return

    try:
        mint = result.get("mint", "")
        transfers = result.get("transfers") or []
        recipients = {
            item.get("to_owner")
            for item in transfers
            if item.get("to_owner")
        }
        amount_count = len(transfers)

        detail_lines = []
        if recipients:
            detail_lines.append(
                f"👥 <b>Alıcı wallet:</b> {len(recipients)}"
            )
        if amount_count:
            detail_lines.append(
                f"🔁 <b>Transfer kaydı:</b> {amount_count}"
            )

        details = "\n".join(detail_lines)
        if details:
            details += "\n\n"

        message = (
            "🚨 <b>PATOSHI RADAR — LONG TRANSFER ALERT</b>\n\n"
            f"🧨 <b>{result.get('name', 'Bilinmiyor')}</b> "
            f"({result.get('symbol', '-')})\n\n"
            f"{result.get('label', '⚠️ Transfer Signal')}\n"
            f"{result.get('reason', '')}\n\n"
            f"{details}"
            f"⏱️ <b>Long Watch:</b> "
            f"{_format_elapsed(result.get('elapsed_seconds'))}\n\n"
            f"🌐 <code>{mint}</code>\n"
            f'<a href="https://pump.fun/{mint}">Pump.fun</a>'
        )

        if send_message(message):
            print(
                f"📨 V5.2 LONG TRANSFER ALERT GÖNDERİLDİ => "
                f"{mint} | {result.get('label')} | "
                f"{result.get('signature')}"
            , flush=True)
        else:
            print(
                f"❌ V5.2 LONG TRANSFER ALERT GÖNDERİLEMEDİ => {mint}",
                flush=True,
            )

    except Exception as exc:
        print(f"❌ V5.2 Long Transfer Telegram callback hatası => {exc}", flush=True)


def on_activity_complete(result):
    if not result:
        return

    mint = result.get("mint", "")
    summaries = result.get("transfer_summary") or []

    try:
        lines = [
            f"{item['label']} — {item['reason']}"
            for item in summaries[:6]
        ]
        transfer_text = (
            "\n".join(lines)
            if lines
            else "🟢 Kayda değer SPL transferi tespit edilmedi."
        )

        dex_text = result.get("dex_name") or (
            "Tespit edildi"
            if result.get("dex_detected")
            else "❌ YOK"
        )

        message = (
            "🔬 <b>PATOSHI RADAR — V5.2 WATCH</b>\n\n"
            f"🧨 <b>{result.get('name', 'Bilinmiyor')}</b> "
            f"({result.get('symbol', '-')})\n\n"
            f"💧 <b>LP:</b> "
            f"{'✅ VAR' if result.get('lp_detected') else '❌ YOK'}\n"
            f"🏛️ <b>DEX:</b> {dex_text}\n"
            f"🛒 <b>First Buy:</b> "
            f"{'✅ VAR' if result.get('buy_detected') else '❌ YOK'}\n\n"
            f"<b>Transfer Watch</b>\n{transfer_text}\n\n"
            f"🌐 <code>{_short(mint, 20)}</code>\n"
            f'<a href="https://pump.fun/{mint}">Pump.fun</a>'
        )

        send_message(message)

    except Exception as exc:
        print(f"❌ V5.2 callback hatası => {exc}", flush=True)

    # The normal 60-second V5.2 report is now complete. Start a separate
    # 75-minute transfer-only watch. Signatures already covered by the first
    # report are preloaded so Long Watch does not send duplicate alerts.
    try:
        initial_seen_signatures = [
            item.get("signature")
            for item in summaries
            if item.get("signature")
        ]

        added = add_long_transfer_token(
            mint=mint,
            name=result.get("name", "Bilinmiyor"),
            symbol=result.get("symbol", "-"),
            creator=result.get("creator", ""),
            initial_seen_signatures=initial_seen_signatures,
        )

        if added:
            print(
                f"🛰️ V5.2 75 DK LONG TRANSFER WATCH EKLENDİ => {mint}",
                flush=True,
            )

    except Exception as exc:
        print(f"❌ V5.2 Long Watch başlatma hatası => {exc}", flush=True)


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

    # First alert stays immediate. The existing 60-second V5.2 watch starts
    # only after Telegram succeeds.
    if send_message(message):
        mark_sent(mint, name, symbol, creator)
        add_token(
            mint=mint,
            name=name,
            symbol=symbol,
            creator=creator,
            launch_signature=launch_signature,
        )
        print(
            f"🚀 V5.2 WATCH EKLENDİ => {name} ({symbol}) | {mint}",
            flush=True,
        )


initialize_database()
set_result_callback(on_activity_complete)
set_long_transfer_callback(on_long_transfer_alert)
start_alchemy_watch()
start_long_transfer_watch()

print("🚀 Patoshi Radar V5.2 FINAL başlatılıyor...", flush=True)
print(
    "📡 PumpPortal → Keywords/Wallet → Telegram → "
    "60s V5.2 → 75dk Long Transfer Watch",
    flush=True,
)
print("ℹ️ Long Transfer Watch treasury kullanmaz.", flush=True)

monitor = PumpMonitor(new_token)
monitor.start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("🛑 Patoshi Radar durduruldu.", flush=True)
