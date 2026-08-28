"""Patoshi Radar V5.2 Transfer Watch.

Hooks into the V5.1 Alchemy Activity Watch transaction fetcher so the same
getTransaction RPC response is reused. No second polling loop is created.
"""
import os
from collections import defaultdict

TREASURY_WALLET = os.getenv("PATOSHI_TREASURY_WALLET", "").strip()
BULK_RECIPIENT_THRESHOLD = int(os.getenv("V52_BULK_RECIPIENT_THRESHOLD", "5"))
MIN_TRANSFER_AMOUNT = float(os.getenv("V52_MIN_TRANSFER_AMOUNT", "0"))


def _owner(balance):
    return str((balance or {}).get("owner") or "").strip()


def _amount(balance):
    try:
        ui = (balance or {}).get("uiTokenAmount") or {}
        if ui.get("uiAmountString") is not None:
            return float(ui["uiAmountString"])
        if ui.get("uiAmount") is not None:
            return float(ui["uiAmount"])
        raw = int(ui.get("amount", 0))
        decimals = int(ui.get("decimals", 0))
        return raw / (10 ** decimals)
    except Exception:
        return 0.0


def _aggregate(balances, mint):
    result = defaultdict(float)
    for balance in balances or []:
        if not isinstance(balance, dict) or balance.get("mint") != mint:
            continue
        owner = _owner(balance)
        if owner:
            result[owner] += _amount(balance)
    return result


def classify_transaction(tx, mint, creator="", signature=""):
    if not tx or not mint:
        return None
    meta = tx.get("meta") or {}
    if meta.get("err") is not None:
        return None

    pre = _aggregate(meta.get("preTokenBalances"), mint)
    post = _aggregate(meta.get("postTokenBalances"), mint)
    senders = {}
    recipients = {}

    for owner in set(pre) | set(post):
        delta = post.get(owner, 0.0) - pre.get(owner, 0.0)
        if delta < -MIN_TRANSFER_AMOUNT:
            senders[owner] = abs(delta)
        elif delta > MIN_TRANSFER_AMOUNT:
            recipients[owner] = delta

    if not senders or not recipients:
        return None

    creator = (creator or "").strip()
    if creator and creator in senders:
        kind = "CREATOR_TRANSFER"
        reason = "Creator token transfer"
    elif TREASURY_WALLET and (TREASURY_WALLET in senders or TREASURY_WALLET in recipients):
        kind = "TREASURY_TRANSFER"
        reason = "Tracked Patoshi Treasury transfer"
    elif len(recipients) >= BULK_RECIPIENT_THRESHOLD:
        kind = "BULK_DISTRIBUTION"
        reason = "Multi-wallet / bulk distribution"
    elif creator and creator in recipients:
        kind = "OFFICIAL_DISTRIBUTION"
        reason = "Possible official creator distribution"
    else:
        kind = "ORDINARY_TRANSFER"
        reason = "Ordinary token transfer"

    return {
        "type": kind,
        "reason": reason,
        "mint": mint,
        "signature": signature,
        "senders": senders,
        "recipients": recipients,
        "sender_count": len(senders),
        "recipient_count": len(recipients),
        "total_sent": round(sum(senders.values()), 9),
        "total_received": round(sum(recipients.values()), 9),
        "creator": creator,
        "treasury": TREASURY_WALLET,
    }


def install(activity_module, callback):
    """Monkey-patch V5.1's existing transaction fetcher.

    The original RPC request is performed exactly once; this wrapper only
    analyzes its returned transaction and then gives it back to V5.1.
    """
    original = activity_module._get_transaction
    if getattr(original, "_v52_wrapped", False):
        return

    def wrapped(signature):
        tx = original(signature)
        if tx:
            try:
                mint_events = []
                for mint, item in list(activity_module.watch_tokens.items()):
                    event = classify_transaction(
                        tx,
                        mint,
                        item.get("creator", ""),
                        signature,
                    )
                    if event:
                        mint_events.append(event)
                for event in mint_events:
                    callback(event)
            except Exception as exc:
                print(f"⚠️ V5.2 TRANSFER CLASSIFIER ERROR => {exc}", flush=True)
        return tx

    wrapped._v52_wrapped = True
    activity_module._get_transaction = wrapped
    print("🧩 V5.2 Transfer Watch: V5.1 getTransaction hook aktif.", flush=True)
