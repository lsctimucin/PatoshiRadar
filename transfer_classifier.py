"""Patoshi Radar V5.2 - transfer classification.

Treasury is optional.
"""

import os
from collections import defaultdict


TREASURY = os.getenv(
    "PATOSHI_TREASURY_WALLET",
    "",
).strip()

BULK_THRESHOLD = int(
    os.getenv(
        "V52_BULK_RECIPIENT_THRESHOLD",
        "5",
    )
)


def classify_transfers(
    transfers,
    creator="",
    treasury=None,
):
    treasury = (
        treasury
        if treasury is not None
        else TREASURY
    ).strip()

    creator = (creator or "").strip()

    grouped = defaultdict(list)

    for transfer in transfers or []:
        from_owner = transfer.get("from_owner")
        to_owner = transfer.get("to_owner")

        if not from_owner or not to_owner:
            continue

        signature = transfer.get("signature", "")

        grouped[signature].append(transfer)

    output = []

    for signature, items in grouped.items():
        recipients = {
            item["to_owner"]
            for item in items
        }

        senders = {
            item["from_owner"]
            for item in items
        }

        # --------------------------------------------------
        # V5.2 classification priority
        # --------------------------------------------------

        if creator and creator in senders:
            label = "🔴 Creator Transfer"
            reason = "Creator wallet sent tokens"

        elif treasury and (
            treasury in senders
            or treasury in recipients
        ):
            label = "🟣 Treasury Transfer"

            if treasury in senders:
                reason = "Tracked treasury sent tokens"
            else:
                reason = "Tracked treasury received tokens"

        elif len(recipients) >= BULK_THRESHOLD:
            label = "🟠 Bulk Distribution"
            reason = (
                f"{len(recipients)} recipient wallets "
                "in one transaction"
            )

        elif creator and creator in recipients:
            label = "🔵 Possible Official Distribution"
            reason = "Creator wallet received tokens"

        else:
            label = "🟢 Ordinary Transfer"
            reason = "Normal SPL token movement"

        output.append(
            {
                "signature": signature,
                "label": label,
                "reason": reason,
                "transfers": items,
            }
        )

    return output
