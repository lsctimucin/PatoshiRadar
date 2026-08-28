PATOSHI RADAR V5.2 - FINAL REPLACE

Replace these files:
1) app.py
2) transfer_watch.py (NEW)

Do NOT replace alchemy_activity_watch.py. V5.2 hooks into its existing
_get_transaction() function and reuses the same RPC response, so it does not
create a second polling/RPC loop.

Railway variables:
Existing:
BOT_TOKEN
CHAT_ID
PUMPPORTAL_API_KEY
ALCHEMY_API_KEY
HELIUS_API_KEY

Recommended V5.2:
PATOSHI_TREASURY_WALLET=<Patoshi Treasury wallet>

Optional:
V52_BULK_RECIPIENT_THRESHOLD=5
V52_MIN_TRANSFER_AMOUNT=0

Classification priority:
1. Creator is sender -> CREATOR_TRANSFER
2. Treasury is sender or recipient -> TREASURY_TRANSFER
3. >= threshold recipients -> BULK_DISTRIBUTION
4. Creator is recipient -> OFFICIAL_DISTRIBUTION
5. Otherwise -> ORDINARY_TRANSFER

Important:
V5.2 analyzes preTokenBalances/postTokenBalances from the transaction that
V5.1 already fetched. Therefore the transfer classifier itself costs no
additional RPC request.
