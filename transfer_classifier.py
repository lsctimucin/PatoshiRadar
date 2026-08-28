"""V5.2 transfer classification. Treasury is optional."""
import os
from collections import defaultdict

TREASURY = os.getenv("PATOSHI_TREASURY_WALLET", "").strip()
BULK_THRESHOLD = int(os.getenv("V52_BULK_RECIPIENT_THRESHOLD", "5"))


def classify_transfers(transfers, creator="", treasury=None):
    treasury = (treasury if treasury is not None else TREASURY).strip()
    creator = (creator or "").strip()
    grouped = defaultdict(list)

    for transfer in transfers or []:
        if not transfer.get("from_owner") or not transfer.get("to_owner"):
            continue
        grouped[transfer.get("signature", "")].append(transfer)

    output = []
    for signature, items in grouped.items():
        recipients = {x["to_owner"] for x in items}
        senders = {x["from_owner"] for x in items}
        label = "🟢 Ordinary Transfer"
        reason = "Normal SPL token movement"

        if creator and creator in senders:
            label, reason = "🔴 Creator Transfer", "Creator wallet sent tokens"
        elif creator and creator in recipients:
            label, reason = "🔵 Possible Official Distribution", "Creator wallet received tokens"

        if treasury and treasury in senders:
            label, reason = "🟣 Treasury Transfer", "Tracked treasury sent tokens"
        elif treasury and treasury in recipients:
            label, reason = "🔵 Possible Official Distribution", "Tracked treasury received tokens"

        if len(recipients) >= BULK_THRESHOLD:
            label, reason = "🟠 Bulk Distribution", f"{len(recipients)} recipient wallets in one transaction"

        output.append(
            {
                "signature": signature,
                "label": label,
                "reason": reason,
                "transfers": items,
            }
        )
    return output
