import os
import threading

_raw = os.getenv("ROUND3_WALLETS", "").strip()
_lock = threading.RLock()
_received_by_mint = {}

def _load_wallets():
    by_address = {}
    auto_no = 1
    for part in _raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            label, address = part.split("=", 1)
            label, address = label.strip(), address.strip()
        else:
            address = part
            label = f"Round3-{auto_no:02d}"
            auto_no += 1
        if address:
            by_address.setdefault(address, label or f"Round3-{auto_no:02d}")
    return by_address

ROUND3_BY_ADDRESS = _load_wallets()

def wallet_count():
    return len(ROUND3_BY_ADDRESS)

def check_transfers(mint, transfers):
    if not mint or not ROUND3_BY_ADDRESS or not transfers:
        return None
    matches = []
    for transfer in transfers:
        to_owner = str(transfer.get("to_owner") or "").strip()
        if to_owner in ROUND3_BY_ADDRESS:
            matches.append({
                "label": ROUND3_BY_ADDRESS[to_owner],
                "wallet": to_owner,
                "signature": transfer.get("signature", ""),
                "transfer": transfer,
            })
    if not matches:
        return None
    with _lock:
        received = _received_by_mint.setdefault(mint, {})
        new_matches = []
        for match in matches:
            if match["wallet"] not in received:
                received[match["wallet"]] = {
                    "label": match["label"],
                    "wallet": match["wallet"],
                    "signature": match["signature"],
                }
                new_matches.append(match)
        if not new_matches:
            return None
        all_matches = list(received.values())
    total = len(all_matches)
    new_wallets = {x["wallet"] for x in new_matches}
    return {
        "signature": next((x["signature"] for x in new_matches if x["signature"]), ""),
        "label": (
            "🔥🔥🔥 ROUND 3 MULTI-WALLET CONFIRMATION"
            if total >= 2 else
            "🔥 ROUND 3 WALLET CONFIRMATION"
        ),
        "reason": (
            f"{total} known Round 3 wallets received the SAME candidate token."
            if total >= 2 else
            "A known Round 3 wallet received the candidate token."
        ),
        "transfers": [x["transfer"] for x in matches if x["wallet"] in new_wallets],
        "round3_new_matches": new_matches,
        "round3_matches": all_matches,
        "round3_total": total,
    }

def clear_mint(mint):
    with _lock:
        _received_by_mint.pop(mint, None)
