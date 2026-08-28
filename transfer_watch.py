"""Patoshi Radar V5.2 - SPL transfer watch.

Treasury is optional. The primary target is always the matched Pump.fun token mint.
"""
import os

TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
MAX_TOKEN_ACCOUNTS = int(os.getenv("V52_MAX_TOKEN_ACCOUNTS", "20"))
SIGNATURE_LIMIT = int(os.getenv("V52_TRANSFER_SIGNATURE_LIMIT", "5"))


def token_accounts_for_mint(rpc, mint):
    result = rpc(
        "getProgramAccounts",
        [
            TOKEN_PROGRAM,
            {
                "encoding": "jsonParsed",
                "commitment": "confirmed",
                "filters": [
                    {"dataSize": 165},
                    {"memcmp": {"offset": 0, "bytes": mint}},
                ],
            },
        ],
    )
    accounts = []
    for row in result or []:
        if isinstance(row, dict) and row.get("pubkey"):
            accounts.append(row["pubkey"])
    return accounts[:MAX_TOKEN_ACCOUNTS]


def parse_transfer_balances(tx, mint):
    """Infer owner-to-owner SPL movements from pre/post token balances.

    Solana exposes mint, owner and raw token amount in pre/postTokenBalances,
    so this avoids relying on instruction text/keyword guesses.
    """
    meta = (tx or {}).get("meta") or {}
    pre = meta.get("preTokenBalances") or []
    post = meta.get("postTokenBalances") or []
    by_idx = {}

    for balance in pre:
        if balance.get("mint") == mint:
            by_idx.setdefault(balance.get("accountIndex"), {})["pre"] = balance
    for balance in post:
        if balance.get("mint") == mint:
            by_idx.setdefault(balance.get("accountIndex"), {})["post"] = balance

    changes = []
    for account_index, pair in by_idx.items():
        before = pair.get("pre") or {}
        after = pair.get("post") or {}
        before_amount = int((before.get("uiTokenAmount") or {}).get("amount") or 0)
        after_amount = int((after.get("uiTokenAmount") or {}).get("amount") or 0)
        delta = after_amount - before_amount
        owner = str(after.get("owner") or before.get("owner") or "").strip()
        if delta and owner:
            changes.append({"account_index": account_index, "owner": owner, "delta": delta})

    senders = [x for x in changes if x["delta"] < 0]
    receivers = [x for x in changes if x["delta"] > 0]
    transfers = []

    # Match debits to credits inside the same transaction. This handles
    # ordinary transfers and multi-recipient distributions without assuming
    # a particular DEX/router program.
    for sender in senders:
        remaining = -sender["delta"]
        for receiver in receivers:
            if remaining <= 0:
                break
            amount = min(remaining, receiver["delta"])
            if amount <= 0 or sender["owner"] == receiver["owner"]:
                continue
            transfers.append(
                {
                    "from_owner": sender["owner"],
                    "to_owner": receiver["owner"],
                    "amount_raw": amount,
                }
            )
            remaining -= amount
    return transfers


def scan_token(rpc, mint, launch_signature="", seen_signatures=None, token_accounts=None):
    seen_signatures = seen_signatures if seen_signatures is not None else set()
    token_accounts = token_accounts or token_accounts_for_mint(rpc, mint)
    found = []

    for account in token_accounts:
        rows = rpc(
            "getSignaturesForAddress",
            [
                account,
                {
                    "limit": SIGNATURE_LIMIT,
                    "commitment": "confirmed",
                },
            ],
        ) or []
        for row in reversed(rows):
            signature = row.get("signature") if isinstance(row, dict) else None
            if not signature or signature in seen_signatures or signature == launch_signature:
                continue
            seen_signatures.add(signature)
            tx = rpc(
                "getTransaction",
                [
                    signature,
                    {
                        "encoding": "jsonParsed",
                        "commitment": "confirmed",
                        "maxSupportedTransactionVersion": 0,
                    },
                ],
            )
            if not tx:
                continue
            for transfer in parse_transfer_balances(tx, mint):
                transfer["signature"] = signature
                found.append(transfer)
    return found, token_accounts
