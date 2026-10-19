"""Patoshi dual-wallet SOL/SPL monitor. Standalone Railway service."""
import os
import json
import time
import html
import logging
from decimal import Decimal
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("patoshi-wallet-watch")

WALLETS = {
    "Patoshi Hot Wallet": "2qo8jvuc49pFmTjmUHLiARSV6ppPTaE7gw27ZJ6DnNZy",
    "Patoshi Round-2 Treasury": "GVyByLjvURtf1wyNkfyJbQGrnjNo8uhAH7J6u197Cpap",
}
BOT = os.getenv("BOT_TOKEN", "").strip()
CHAT = os.getenv("CHAT_ID", "").strip()
KEY = os.getenv("ALCHEMY_API_KEY", "").strip()
RPC = os.getenv("SOLANA_RPC_URL", "").strip() or (
    f"https://solana-mainnet.g.alchemy.com/v2/{KEY}" if KEY else ""
)
INTERVAL = max(5, int(os.getenv("HOT_WALLET_POLL_SECONDS", "10")))
STATE = Path(os.getenv("HOT_WALLET_STATE_FILE", "/tmp/patoshi_dual_wallet_state.json"))
SESSION = requests.Session()


def rpc(method, params):
    response = SESSION.post(
        RPC, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise RuntimeError(f"{method}: {payload['error']}")
    return payload.get("result")


def notify(message):
    response = SESSION.post(
        f"https://api.telegram.org/bot{BOT}/sendMessage",
        json={
            "chat_id": CHAT, "text": message,
            "parse_mode": "HTML", "disable_web_page_preview": True,
        },
        timeout=15,
    )
    response.raise_for_status()
    if not response.json().get("ok"):
        raise RuntimeError(f"Telegram rejected message: {response.text[:200]}")


def load():
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state), encoding="utf-8")
    tmp.replace(STATE)


def changes(tx, wallet):
    meta = tx.get("meta") or {}
    if meta.get("err") is not None:
        return []
    message = (tx.get("transaction") or {}).get("message") or {}
    keys = [x.get("pubkey") if isinstance(x, dict) else x
            for x in message.get("accountKeys") or []]
    results = []
    if wallet in keys:
        i = keys.index(wallet)
        before, after = meta.get("preBalances") or [], meta.get("postBalances") or []
        if i < len(before) and i < len(after):
            delta = after[i] - before[i]
            if delta:
                results.append(("SOL", Decimal(delta) / Decimal(10**9)))
    tokens = {}
    for field, sign in (("preTokenBalances", -1), ("postTokenBalances", 1)):
        for item in meta.get(field) or []:
            if item.get("owner") != wallet or not item.get("mint"):
                continue
            value = item.get("uiTokenAmount") or {}
            decimals = int(value.get("decimals", 0))
            key = (item["mint"], decimals)
            tokens[key] = tokens.get(key, 0) + sign * int(value.get("amount", "0"))
    for (mint, decimals), delta in tokens.items():
        if delta:
            results.append((mint, Decimal(delta) / Decimal(10**decimals)))
    return results


def alert(label, wallet, signature, movements):
    lines = [
        "🔥 <b>PATOSHI WALLET — HAREKET</b>", "",
        f"🏷️ <b>{html.escape(label)}</b>",
        f"👛 <code>{html.escape(wallet)}</code>", "",
    ]
    for mint, delta in movements:
        direction = "🟢 GİRİŞ" if delta > 0 else "🔴 ÇIKIŞ"
        asset = "SOL" if mint == "SOL" else f"<code>{html.escape(mint)}</code>"
        lines.append(f"{direction}: <b>{format(abs(delta), 'f')}</b> {asset}")
    lines += ["", f"🔗 https://solscan.io/tx/{signature}"]
    notify("\n".join(lines))


def signatures(wallet, **opts):
    params = {"limit": 100, "commitment": "confirmed"}
    params.update(opts)
    result = rpc("getSignaturesForAddress", [wallet, params])
    if result is None:
        raise RuntimeError("getSignaturesForAddress returned null")
    return result


def pending_signatures(wallet, cursor):
    """Collect new signatures back to the saved cursor, including pagination."""
    if not cursor:
        return []
    found = False
    pending = []
    before = None
    for _ in range(25):
        rows = signatures(wallet, **({"before": before} if before else {}))
        if not rows:
            # Cursor might be older than retention; do not silently skip.
            raise RuntimeError(f"Saved cursor not found for {wallet}; manual recovery needed")
        for row in rows:
            sig = row.get("signature")
            if sig == cursor:
                found = True
                break
            if sig:
                pending.append(sig)
        if found:
            return list(reversed(pending))
        if len(rows) < 100:
            raise RuntimeError(f"Saved cursor missing for {wallet}; refusing to skip transactions")
        before = rows[-1]["signature"]
    raise RuntimeError(f"Backlog over 2500 transactions for {wallet}; retry/review")


def process_wallet(label, wallet, state):
    cursor = state.get(wallet)
    if not cursor:
        rows = signatures(wallet, limit=1)
        if rows:
            state[wallet] = rows[0]["signature"]
            save(state)
        LOG.info("Initialized %s; historical transactions not notified", label)
        return
    pending = pending_signatures(wallet, cursor)
    for sig in pending:
        tx = rpc("getTransaction", [
            sig,
            {"encoding": "jsonParsed", "commitment": "confirmed",
             "maxSupportedTransactionVersion": 0},
        ])
        if tx is None:
            raise RuntimeError(f"Transaction not yet available: {sig}")
        movements = changes(tx, wallet)
        if movements:
            # Cursor is only advanced after Telegram accepts the notification.
            alert(label, wallet, sig, movements)
            LOG.info("%s movement notified: %s", label, sig)
        state[wallet] = sig
        save(state)


def run():
    if not BOT or not CHAT or not RPC:
        raise RuntimeError("BOT_TOKEN, CHAT_ID and ALCHEMY_API_KEY or SOLANA_RPC_URL required")
    LOG.info("Starting Patoshi Wallet Watch | wallets=%s | interval=%ss",
             len(WALLETS), INTERVAL)
    state = load()
    # Test RPC and Telegram before entering the long-running loop.
    rpc("getHealth", [])
    notify(
        "🛰️ <b>PATOSHI WALLET WATCH AKTİF</b>\n"
        "👛 Hot Wallet + Round-2 Treasury\n"
        "🟢 SOL / SPL giriş-çıkış takibi başlatıldı."
    )
    LOG.info("Telegram startup notification sent")
    while True:
        for label, wallet in WALLETS.items():
            try:
                process_wallet(label, wallet, state)
            except Exception:
                LOG.exception("Wallet scan failed: %s", label)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    run()
