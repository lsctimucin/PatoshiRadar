import os
import time
from collections import defaultdict

TOKEN_PROGRAM = 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'
TRANSFER_WATCH_SECONDS = int(os.getenv('V52_TRANSFER_WATCH_SECONDS', '60'))
TRANSFER_POLL_SECONDS = int(os.getenv('V52_TRANSFER_POLL_SECONDS', '8'))
MAX_TOKEN_ACCOUNTS = int(os.getenv('V52_MAX_TOKEN_ACCOUNTS', '80'))


def _rpc(rpc, method, params):
    return rpc(method, params)


def token_accounts_for_mint(rpc, mint):
    result = _rpc(rpc, 'getProgramAccounts', [TOKEN_PROGRAM, {
        'encoding': 'jsonParsed',
        'filters': [
            {'dataSize': 165},
            {'memcmp': {'offset': 0, 'bytes': mint}},
        ],
    }])
    accounts = []
    for row in result or []:
        if not isinstance(row, dict):
            continue
        pubkey = row.get('pubkey')
        if pubkey:
            accounts.append(pubkey)
    return accounts[:MAX_TOKEN_ACCOUNTS]


def parse_transfer_balances(tx, mint):
    meta = (tx or {}).get('meta') or {}
    pre = meta.get('preTokenBalances') or []
    post = meta.get('postTokenBalances') or []
    by_idx = {}
    for b in pre:
        if b.get('mint') == mint:
            by_idx.setdefault(b.get('accountIndex'), {})['pre'] = b
    for b in post:
        if b.get('mint') == mint:
            by_idx.setdefault(b.get('accountIndex'), {})['post'] = b

    changes = []
    for idx, pair in by_idx.items():
        a = pair.get('pre', {})
        b = pair.get('post', {})
        pre_amt = int((a.get('uiTokenAmount') or {}).get('amount') or 0)
        post_amt = int((b.get('uiTokenAmount') or {}).get('amount') or 0)
        delta = post_amt - pre_amt
        if delta == 0:
            continue
        owner = (b.get('owner') or a.get('owner') or '').strip()
        changes.append({'account_index': idx, 'owner': owner, 'delta': delta})

    senders = [x for x in changes if x['delta'] < 0]
    receivers = [x for x in changes if x['delta'] > 0]
    transfers = []
    for s in senders:
        remaining = -s['delta']
        for r in receivers:
            if remaining <= 0:
                break
            amount = min(remaining, r['delta'])
            if amount <= 0:
                continue
            transfers.append({'from_owner': s['owner'], 'to_owner': r['owner'], 'amount_raw': amount})
            remaining -= amount
    return transfers


def scan_token(rpc, mint, launch_signature='', seen_signatures=None, token_accounts=None):
    seen_signatures = seen_signatures if seen_signatures is not None else set()
    token_accounts = token_accounts or token_accounts_for_mint(rpc, mint)
    found = []
    for account in token_accounts:
        rows = _rpc(rpc, 'getSignaturesForAddress', [account, {'limit': 10, 'commitment': 'confirmed'}]) or []
        for row in reversed(rows):
            sig = row.get('signature') if isinstance(row, dict) else None
            if not sig or sig in seen_signatures or sig == launch_signature:
                continue
            seen_signatures.add(sig)
            tx = _rpc(rpc, 'getTransaction', [sig, {
                'encoding': 'jsonParsed', 'commitment': 'confirmed', 'maxSupportedTransactionVersion': 0
            }])
            if not tx:
                continue
            transfers = parse_transfer_balances(tx, mint)
            for t in transfers:
                t['signature'] = sig
                found.append(t)
    return found, token_accounts
