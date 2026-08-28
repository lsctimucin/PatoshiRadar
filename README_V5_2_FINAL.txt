PATOSHI RADAR V5.2 FINAL

Purpose
- PumpPortal detects new Pump.fun tokens.
- Existing keyword/creator filters decide whether the token is relevant.
- Telegram alert is sent immediately.
- Only then does the 60-second V5.2 watch start.
- Activity Watch checks LP / DEX / first-buy signals.
- SPL Transfer Watch checks token-account transactions and derives owner-to-owner movements from pre/postTokenBalances.

Treasury
PATOSHI_TREASURY_WALLET IS OPTIONAL.
Do NOT add it to Railway unless you have a verified treasury address.
If it is missing, Creator / Ordinary / Bulk / Possible Official Distribution logic still works.

Railway required variables remain the existing ones:
BOT_TOKEN
CHAT_ID
PUMPPORTAL_API_KEY
ALCHEMY_API_KEY

Optional variables:
PATOSHI_TREASURY_WALLET
V52_BULK_RECIPIENT_THRESHOLD=5
V52_MAX_TOKEN_ACCOUNTS=20
V52_TRANSFER_SIGNATURE_LIMIT=5
WATCH_SECONDS=60
POLL_SECONDS=5
MAX_WATCHES=25

Replace these files in the existing repo:
app.py
alchemy_activity_watch.py
transfer_watch.py
transfer_classifier.py

Do not upload __pycache__ files.
