"""Patoshi Radar V5.2 - 75 minute Long Transfer Watch.

Starts after the normal 60-second V5.2 report. Treasury is intentionally
ignored here: long-watch decisions are based on the matched token mint and
its creator/tracked wallet context only.
"""

import os
import threading
import time

import requests

from transfer_classifier import classify_transfers
from transfer_watch import scan_token


ALCHEMY_API_KEY = os.getenv("ALCHEMY_API_KEY", "").strip()
RPC_URL = f"https://solana-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}"

LONG_WATCH_SECONDS = int(os.getenv("V52_LONG_WATCH_SECONDS", "4500"))
LONG_POLL_SECONDS = int(os.getenv("V52_LONG_POLL_SECONDS", "30"))
MAX_LONG_WATCHES = int(os.getenv("V52_MAX_LONG_WATCHES", "5"))
TOKEN_ACCOUNT_REFRESH_EVERY = int(
    os.getenv("V52_LONG_TOKEN_ACCOUNT_REFRESH_EVERY", "4")
)
HTTP_TIMEOUT = int(os.getenv("V52_LONG_HTTP_TIMEOUT", "10"))

SIGNIFICANT_LABELS = {
    "🔴 Creator Transfer",
    "🟠 Bulk Distribution",
    "🔵 Possible Official Distribution",
}

_watch_tokens = {}
_lock = threading.RLock()
_running = False
_worker_thread = None
_alert_callback = None
_request_id = 50000
_request_lock = threading.Lock()


def log(message):
    print(message, flush=True)


def _next_request_id():
    global _request_id
    with _request_lock:
        _request_id += 1
        return _request_id


def _rpc(method, params):
    if not ALCHEMY_API_KEY:
        return None

    payload = {
        "jsonrpc": "2.0",
        "id": _next_request_id(),
        "method": method,
        "params": params,
    }

    try:
        response = requests.post(
            RPC_URL,
            json=payload,
            timeout=HTTP_TIMEOUT,
        )

        if response.status_code == 429:
            log(f"⚠️ V5.2 LONG WATCH ALCHEMY RATE LIMIT => {method}")
            return None

        response.raise_for_status()
        data = response.json()

        if "error" in data:
            log(f"❌ V5.2 LONG WATCH RPC => {data.get('error')}")
            return None

        return data.get("result")

    except requests.RequestException as exc:
        log(f"⚠️ V5.2 LONG WATCH HTTP => {method} | {exc}")
        return None
    except Exception as exc:
        log(f"⚠️ V5.2 LONG WATCH RPC PARSE => {method} | {exc}")
        return None


def set_alert_callback(callback):
    global _alert_callback
    _alert_callback = callback
    log("🧩 V5.2 LONG TRANSFER CALLBACK HAZIR")


def add_token(
    mint,
    name="",
    symbol="",
    creator="",
    initial_seen_signatures=None,
):
    """Add a token to the 75-minute transfer-only watch.

    initial_seen_signatures should contain signatures already covered by the
    first 60-second V5.2 report, preventing duplicate long-watch alerts.
    """
    if not mint:
        return False

    initial_seen = {
        signature
        for signature in (initial_seen_signatures or [])
        if signature
    }

    with _lock:
        if mint in _watch_tokens:
            return False

        if len(_watch_tokens) >= MAX_LONG_WATCHES:
            log(
                f"⚠️ V5.2 LONG WATCH LIMIT => {mint} | "
                f"max={MAX_LONG_WATCHES}"
            )
            return False

        _watch_tokens[mint] = {
            "mint": mint,
            "name": name or "Bilinmiyor",
            "symbol": symbol or "-",
            "creator": creator or "",
            "started": time.time(),
            "seen_signatures": set(initial_seen),
            "notified_signatures": set(initial_seen),
            "token_accounts": [],
            "scan_count": 0,
        }

    log(
        f"🛰️ V5.2 LONG TRANSFER WATCH BAŞLADI => {mint} | "
        f"{LONG_WATCH_SECONDS}s"
    )
    return True


def _emit_alert(item, event):
    signature = event.get("signature", "")
    if not signature:
        return

    with _lock:
        if signature in item["notified_signatures"]:
            return
        item["notified_signatures"].add(signature)

    if _alert_callback is None:
        return

    payload = {
        "mint": item["mint"],
        "name": item["name"],
        "symbol": item["symbol"],
        "creator": item["creator"],
        "signature": signature,
        "label": event.get("label", ""),
        "reason": event.get("reason", ""),
        "transfers": event.get("transfers") or [],
        "elapsed_seconds": int(time.time() - item["started"]),
    }

    try:
        _alert_callback(payload)
    except Exception as exc:
        log(f"❌ V5.2 LONG TRANSFER CALLBACK => {exc}")


def _process_token(mint):
    with _lock:
        item = _watch_tokens.get(mint)
        if not item:
            return
        item["scan_count"] += 1
        scan_count = item["scan_count"]
        cached_accounts = list(item.get("token_accounts") or [])

    # Refresh token-account discovery periodically so accounts created later
    # during the 75-minute window can also be observed.
    if (
        not cached_accounts
        or TOKEN_ACCOUNT_REFRESH_EVERY <= 1
        or scan_count % TOKEN_ACCOUNT_REFRESH_EVERY == 0
    ):
        token_accounts = None
    else:
        token_accounts = cached_accounts

    try:
        transfers, discovered_accounts = scan_token(
            _rpc,
            item["mint"],
            "",
            item["seen_signatures"],
            token_accounts,
        )

        with _lock:
            current = _watch_tokens.get(mint)
            if current is not None:
                current["token_accounts"] = discovered_accounts or []

        if not transfers:
            return

        # Treasury is deliberately disabled for Long Watch.
        classified = classify_transfers(
            transfers,
            creator=item["creator"],
            treasury="",
        )

        for event in classified:
            if event.get("label") in SIGNIFICANT_LABELS:
                _emit_alert(item, event)

    except Exception as exc:
        log(f"⚠️ V5.2 LONG TRANSFER WATCH => {mint} | {exc}")


def _finish_token(mint):
    with _lock:
        item = _watch_tokens.pop(mint, None)

    if item:
        elapsed = int(time.time() - item["started"])
        log(f"✅ V5.2 LONG TRANSFER WATCH BİTTİ => {mint} | {elapsed}s")


def _worker():
    global _running

    while _running:
        try:
            for mint in list(_watch_tokens):
                with _lock:
                    item = _watch_tokens.get(mint)
                    if not item:
                        continue
                    expired = (
                        time.time() - item["started"] >= LONG_WATCH_SECONDS
                    )

                if expired:
                    _finish_token(mint)
                    continue

                _process_token(mint)

            time.sleep(max(1, LONG_POLL_SECONDS))

        except Exception as exc:
            log(f"❌ V5.2 LONG WATCH WORKER => {exc}")
            time.sleep(2)


def start():
    global _running, _worker_thread

    if _running:
        return

    if not ALCHEMY_API_KEY:
        log("❌ ALCHEMY_API_KEY yok; Long Transfer Watch başlatılmadı.")
        return

    _running = True
    _worker_thread = threading.Thread(
        target=_worker,
        daemon=True,
        name="PatoshiV52LongTransferWatch",
    )
    _worker_thread.start()

    log(
        "📡 V5.2 LONG TRANSFER WATCH AKTİF | "
        f"{LONG_WATCH_SECONDS}s / poll={LONG_POLL_SECONDS}s"
    )
