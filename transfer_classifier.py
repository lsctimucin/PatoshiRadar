import os
from collections import defaultdict

TREASURY = os.getenv('PATOSHI_TREASURY_WALLET', '').strip()
BULK_THRESHOLD = int(os.getenv('V52_BULK_RECIPIENT_THRESHOLD', '5'))


def classify_transfers(transfers, creator='', treasury=None):
    treasury = (treasury or TREASURY).strip()
    if not transfers:
        return []
    creator = (creator or '').strip()
    grouped = defaultdict(list)
    for t in transfers:
        grouped[t.get('signature', '')].append(t)

    out = []
    for sig, items in grouped.items():
        recipients = {x.get('to_owner') for x in items if x.get('to_owner')}
        froms = {x.get('from_owner') for x in items if x.get('from_owner')}
        label = '🟢 Ordinary Transfer'
        reason = 'Normal SPL token movement'
        if creator and (creator in froms or creator in recipients):
            if creator in froms:
                label, reason = '🔴 Creator Transfer', 'Creator wallet sent tokens'
            else:
                label, reason = '🔵 Possible Official Distribution', 'Creator wallet received tokens'
        if treasury and (treasury in froms or treasury in recipients):
            if treasury in froms:
                label, reason = '🟣 Treasury Transfer', 'Tracked treasury sent tokens'
            else:
                label, reason = '🔵 Possible Official Distribution', 'Tracked treasury received tokens'
        if len(recipients) >= BULK_THRESHOLD:
            label, reason = '🟠 Bulk Distribution', f'{len(recipients)} recipient wallets in one transaction'
        out.append({'signature': sig, 'label': label, 'reason': reason, 'transfers': items})
    return out
