"""Patoshi dual-wallet monitor; 1 SOL equivalent alert threshold."""
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
RPC = os.getenv("SOLANA_RPC_URL", "").strip() or (f"https://solana-mainnet.g.alchemy.com/v2/{KEY}" if KEY else "")
INTERVAL = max(10, int(os.getenv("HOT_WALLET_POLL_SECONDS", "60")))
THRESHOLD = Decimal(os.getenv("HOT_WALLET_MIN_SOL", "1"))
STATE = Path(os.getenv("HOT_WALLET_STATE_FILE", "/tmp/patoshi_dual_wallet_state.json"))
SESSION = requests.Session()
SOL_MINT = "So11111111111111111111111111111111111111112"
USDT_MINT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
PRICE_CACHE = {}
PRICE_TTL = 120


def rpc(method, params):
    response = SESSION.post(RPC, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=20)
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise RuntimeError(f"{method}: {payload['error']}")
    return payload.get("result")


def notify(message):
    response = SESSION.post(
        f"https://api.telegram.org/bot{BOT}/sendMessage",
        json={"chat_id": CHAT, "text": message, "parse_mode": "HTML", "disable_web_page_preview": True},
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
    keys = [x.get("pubkey") if isinstance(x, dict) else x for x in message.get("accountKeys") or []]
    results = []
    if wallet in keys:
        i = keys.index(wallet)
        before, after = meta.get("preBalances") or [], meta.get("postBalances") or []
        if i < len(before) and i < len(after):
            delta = after[i] - before[i]
            # Transaction fee is not a SOL transfer; exclude it from net balance change.
            if keys and keys[0] == wallet:
                delta += int(meta.get("fee") or 0)
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
            for mint in batch:
                PRICE_CACHE[mint] = (now, None)
    return {mint: PRICE_CACHE.get(mint, (0, None))[1] for mint in set(mints)}


def filter_movements(movements):
    """SOL >= threshold; other tokens >= SOL equivalent; unknown price => notify."""
    if not movements:
        return []
    mints = [mint for mint, _ in movements if mint != "SOL"]
    prices = prices_usd([SOL_MINT] + mints) if mints else {}
    sol_usd = prices.get(SOL_MINT)
    selected = []
    for mint, delta in movements:
        if mint == "SOL":
            if abs(delta) >= THRESHOLD:
                selected.append((mint, delta, abs(delta)))
            continue
        token_usd = prices.get(mint)
        if token_usd is None or sol_usd is None or sol_usd <= 0:
            selected.append((mint, delta, None))
            continue
        equivalent = abs(delta) * token_usd / sol_usd
        if equivalent >= THRESHOLD:
            selected.append((mint, delta, equivalent))
    return selected


def alert(label, wallet, signature, movements):
    lines = ["🔥 <b>PATOSHI WALLET — ÖNEMLİ HAREKET</b>", "", f"🏷️ <b>{html.escape(label)}</b>", f"👛 <code>{html.escape(wallet)}</code>", ""]
    for mint, delta, equivalent in movements:
        direction = "🟢 GİRİŞ" if delta > 0 else "🔴 ÇIKIŞ"
        asset = "SOL" if mint == "SOL" else ("USDT" if mint == USDT_MINT else "USDC" if mint == USDC_MINT else f"<code>{html.escape(mint)}</code>")
        detail = "" if mint == "SOL" else (" (SOL değeri bilinmiyor)" if equivalent is None else f" (~{equivalent:.3f} SOL)")
        lines.append(f"{direction}: <b>{format(abs(delta), 'f')}</b> {asset}{detail}")
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
    if not cursor:
        return []
    pending = []
    before = None
    for _ in range(25):
        rows = signatures(wallet, **({"before": before} if before else {}))
        if not rows:
            raise RuntimeError(f"Saved cursor not found for {wallet}; manual recovery needed")
        for row in rows:
            sig = row.get("signature")
            if sig == cursor:
                return list(reversed(pending))
            if sig:
                pending.append(sig)
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
    for sig in pending_signatures(wallet, cursor):
        tx = rpc("getTransaction", [sig, {"encoding": "jsonParsed", "commitment": "confirmed", "maxSupportedTransactionVersion": 0}])
        if tx is None:
            raise RuntimeError(f"Transaction not yet available: {sig}")
        movements = filter_movements(changes(tx, wallet))
        if movements:
            alert(label, wallet, sig, movements)
            LOG.info("%s threshold movement notified: %s", label, sig)
        state[wallet] = sig
        save(state)


def run():
    if not BOT or not CHAT or not RPC:
        raise RuntimeError("BOT_TOKEN, CHAT_ID and ALCHEMY_API_KEY or SOLANA_RPC_URL required")
    if THRESHOLD <= 0:
        raise RuntimeError("HOT_WALLET_MIN_SOL must be positive")
    LOG.info("Starting Patoshi Wallet Watch | wallets=%s | interval=%ss | min=%s SOL", len(WALLETS), INTERVAL, THRESHOLD)
    state = load()
    rpc("getHealth", [])
    notify("🛰️ <b>PATOSHI WALLET WATCH AKTİF</b>\n👛 Hot Wallet + Round-2 Treasury\n🔔 Minimum alarm: 1 SOL karşılığı\n❔ Fiyatı bulunamayan tokenlar da bildirilir.")
    while True:
        for label, wallet in WALLETS.items():
            try:
                process_wallet(label, wallet, state)
            except Exception:
                LOG.exception("Wallet scan failed: %s", label)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    run()
