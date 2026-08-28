import html
from datetime import datetime, timezone


def _creator_label(creator_name, creator_info):
    if creator_name:
        return str(creator_name)

    if isinstance(creator_info, dict):
        label = (
            creator_info.get("name")
            or creator_info.get("label")
            or creator_info.get("title")
        )
        if label:
            return str(label)

    if isinstance(creator_info, str) and creator_info.strip():
        return creator_info.strip()

    return "Creator"


def build_message(
    name,
    symbol,
    market_cap,
    mint,
    creator,
    creator_name=None,
    keyword=None,
    creator_info=None,
):
    safe_name = html.escape(str(name or "Bilinmiyor"))
    safe_symbol = html.escape(str(symbol or "-"))
    safe_mint = html.escape(str(mint or ""))
    safe_keyword = html.escape(str(keyword or "-"))

    creator_label = html.escape(
        _creator_label(
            creator_name,
            creator_info,
        )
    )

    try:
        sol_value = float(market_cap or 0)
    except (TypeError, ValueError):
        sol_value = 0.0

    now_utc = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d %H:%M UTC")

    message = (
        "🚀 <b>PATOSHI RADAR</b>\n\n"
        f"🧨 <b>{safe_name}</b> ({safe_symbol})\n\n"
        f"🔍 Keyword: {safe_keyword}\n\n"
        f"👤 {creator_label}\n"
        "🆕 İlk Launch\n\n"
        f"💰 {sol_value:.2f} SOL 🟠\n"
        "🎯 20/100 🔴\n\n"
        f"🌐 <code>{safe_mint}</code>\n\n"
        f"⏰ {now_utc}\n\n"
        f'🔗 <a href="https://pump.fun/{safe_mint}">Pump.fun</a>'
    )

    return message
