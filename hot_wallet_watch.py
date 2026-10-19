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
