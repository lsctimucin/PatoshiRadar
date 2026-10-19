"""Standalone two-wallet Solana SOL/SPL movement watcher for Patoshi Radar."""
import os
import json
import time
import html
import logging
from decimal import Decimal
from pathlib import Path
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
WALLETS = {
    'Patoshi Hot Wallet': '2qo8jvuc49pFmTjmUHLiARSV6ppPTaE7gw27ZJ6DnNZy',
    'Patoshi Round-2 Treasury': 'GVyByLjvURtf1wyNkfyJbQGrnjNo8uhAH7J6u197Cpap',
}
BOT = os.getenv('BOT_TOKEN', '').strip()
CHAT = os.getenv('CHAT_ID', '').strip()
KEY = os.getenv('ALCHEMY_API_KEY', '').strip()
RPC = os.getenv('SOLANA_RPC_URL', f'https://solana-mainnet.g.alchemy.com/v2/{KEY}').strip()
INTERVAL = max(3, int(os.getenv('HOT_WALLET_POLL_SECONDS', '10')))
STATE = Path(os.getenv('HOT_WALLET_STATE_FILE', '/tmp/patoshi_dual_wallet_state.json'))
SESSION = requests.Session()


def rpc(method, params):
    response = SESSION.post(RPC, json={'jsonrpc':'2.0','id':1,'method':method,'params':params}, timeout=20)
    response.raise_for_status()
    payload = response.json()
    if payload.get('error'):
        raise RuntimeError(f'{method}: {payload["error"]}')
    return payload.get('result')


def notify(message):
    response = SESSION.post(f'https://api.telegram.org/bot{BOT}/sendMessage', json={
        'chat_id': CHAT, 'text': message, 'parse_mode': 'HTML', 'disable_web_page_preview': True
    }, timeout=15)
    response.raise_for_status()
    if not response.json().get('ok'):
        raise RuntimeError('Telegram did not accept message')


def load():
    try:
        value = json.loads(STATE.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def save(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix('.tmp')
    tmp.write_text(json.dumps(state))
    tmp.replace(STATE)


def changes(tx, wallet):
    meta = tx.get('meta') or {}
    if meta.get('err') is not None:
        return []
    message = (tx.get('transaction') or {}).get('message') or {}
    keys = [k.get('pubkey') if isinstance(k, dict) else k for k in message.get('accountKeys') or []]
    result = []
    if wallet in keys:
        i = keys.index(wallet)
        before, after = meta.get('preBalances') or [], meta.get('postBalances') or []
        if i < len(before) and i < len(after):
            delta = after[i] - before[i]
            if delta:
                result.append(('SOL', Decimal(delta) / Decimal(10**9)))
    tokens = {}
    for field, sign in (('preTokenBalances', -1), ('postTokenBalances', 1)):
        for entry in meta.get(field) or []:
            if entry.get('owner') != wallet:
                continue
            mint = entry.get('mint')
            amount = entry.get('uiTokenAmount') or {}
            if not mint:
                continue
            decimals = int(amount.get('decimals', 0))
            key = (mint, decimals)
            tokens[key] = tokens.get(key, 0) + sign * int(amount.get('amount', '0'))
    for (mint, decimals), delta in tokens.items():
        if delta:
            result.append((mint, Decimal(delta) / (Decimal(10)**decimals)))
    return result


def alert(label, wallet, signature, items):
    lines = ['🔥 <b>PATOSHI WALLET — HAREKET</b>', '',
             f'🏷️ <b>{html.escape(label)}</b>', f'👛 <code>{html.escape(wallet)}</code>', '']
    for mint, delta in items:
        direction = '🟢 GİRİŞ' if delta > 0 else '🔴 ÇIKIŞ'
        asset = 'SOL' if mint == 'SOL' else f'<code>{html.escape(mint)}</code>'
        lines.append(f'{direction}: <b>{format(abs(delta), "f")}</b> {asset}')
