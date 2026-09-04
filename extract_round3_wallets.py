import os
import requests


# ============================================================
# PATOSHI RADAR - ROUND 3 WALLET EXTRACTOR
# FINAL
#
# Amaç:
# - Round 3 işlem TX'lerini Alchemy üzerinden okumak
# - SPL Transfer / TransferChecked işlemlerini çözmek
# - Token account yerine mümkün olduğunca OWNER wallet çıkarmak
# - Tim / Faik walletlarını isimlendirmek
# - Diğerlerini Round3-01, Round3-02 ... yapmak
#
# Bu dosya Patoshi Radar'ın çalışan sistemini DEĞİŞTİRMEZ.
# Tek seferlik analiz aracıdır.
# ============================================================


# ------------------------------------------------------------
# ALCHEMY
# Ana PatoshiRadar servisindeki aynı environment variable.
# ------------------------------------------------------------

ALCHEMY_API_KEY = os.getenv("ALCHEMY_API_KEY", "").strip()

RPC_URL = (
    f"https://solana-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
    if ALCHEMY_API_KEY
    else ""
)


# ------------------------------------------------------------
# BİLDİĞİMİZ ROUND 3 WALLETLARI
# Burak daha sonra eklenebilir.
# ------------------------------------------------------------

KNOWN_WALLETS = {
    "Tim": "TVWcpT6PUDCVvqRsqkukbTWqih3YdxrEVGAgwvZ1F6z",
    "Faik": "4fqGUHnq7oL94YZ1sVN1PpvNQbHUwZP1GaVyvXt3K5RX",
}


# ------------------------------------------------------------
# ROUND 3 TRANSACTIONS
# ------------------------------------------------------------

TX_SIGNATURES = [
    "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",
]


# ============================================================
# RPC
# ============================================================

def rpc_call(method, params):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }

    response = requests.post(
        RPC_URL,
        json=payload,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    if "error" in data:
        raise RuntimeError(data["error"])

    return data.get("result")


def get_transaction(signature):
    return rpc_call(
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


# ============================================================
# HELPERS
# ============================================================

def unique_preserve_order(values):
    seen = set()
    output = []

    for value in values:
        if not value:
            continue

        if value in seen:
            continue

        seen.add(value)
        output.append(value)

    return output


def known_label(wallet):
    for label, address in KNOWN_WALLETS.items():
        if address == wallet:
            return label

    return None


def get_account_keys(tx):
    message = tx.get("transaction", {}).get("message", {})

    result = []

    for item in message.get("accountKeys", []):
        if isinstance(item, str):
            result.append(
                {
                    "pubkey": item,
                    "signer": False,
                    "writable": False,
                }
            )

        elif isinstance(item, dict):
            result.append(
                {
                    "pubkey": item.get("pubkey"),
                    "signer": bool(item.get("signer")),
                    "writable": bool(item.get("writable")),
                }
            )

    return result


def get_signers(tx):
    return [
        item["pubkey"]
        for item in get_account_keys(tx)
        if item.get("signer") and item.get("pubkey")
    ]


def get_token_owners(tx):
    """
    accountIndex -> token account owner wallet
    """

    result = {}

    meta = tx.get("meta") or {}

    balances = (
        (meta.get("preTokenBalances") or [])
        + (meta.get("postTokenBalances") or [])
    )

    for balance in balances:
        index = balance.get("accountIndex")
        owner = balance.get("owner")
        mint = balance.get("mint")

        if index is None or not owner:
            continue

        result[index] = {
            "owner": owner,
            "mint": mint,
        }

    return result


def walk_instructions(tx):
    """
    Top-level + inner instructions
    """

    output = []

    message = tx.get("transaction", {}).get("message", {})

    for instruction in message.get("instructions", []):
        output.append(instruction)

    meta = tx.get("meta") or {}

    for group in meta.get("innerInstructions", []) or []:
        for instruction in group.get("instructions", []):
            output.append(instruction)

    return output


# ============================================================
# TRANSFER PARSER
# ============================================================

def extract_transfer_candidates(tx):
    account_keys = get_account_keys(tx)
    token_owners = get_token_owners(tx)

    candidates = []

    for instruction in walk_instructions(tx):
        parsed = instruction.get("parsed")

        if not isinstance(parsed, dict):
            continue

        instruction_type = str(
            parsed.get("type", "")
        ).lower()

        if instruction_type not in (
            "transfer",
            "transferchecked",
        ):
            continue

        info = parsed.get("info") or {}

        source = info.get("source")
        destination = info.get("destination")

        authority = (
            info.get("authority")
            or info.get("owner")
            or info.get("multisigAuthority")
        )

        destination_owner = None
        source_owner = None

        # Token account -> Owner wallet çözümleme
        for index, key in enumerate(account_keys):
            pubkey = key.get("pubkey")

            if (
                pubkey == destination
                and index in token_owners
            ):
                destination_owner = token_owners[index]["owner"]

            if (
                pubkey == source
                and index in token_owners
            ):
                source_owner = token_owners[index]["owner"]

        destination_owner = (
            info.get("destinationOwner")
            or destination_owner
        )

        source_owner = (
            info.get("sourceOwner")
            or source_owner
            or authority
        )

        token_amount = info.get("tokenAmount") or {}

        amount = (
            token_amount.get("uiAmountString")
            or token_amount.get("uiAmount")
            or info.get("amount")
        )

        mint = info.get("mint")

        candidates.append(
            {
                "type": instruction_type,
                "source_token_account": source,
                "destination_token_account": destination,
                "source_owner": source_owner,
                "destination_owner": destination_owner,
                "mint": mint,
                "amount": amount,
            }
        )

    return candidates


# ============================================================
# MAIN
# ============================================================

def main():
    print("")
    print("=" * 76)
    print("PATOSHI RADAR - ROUND 3 WALLET EXTRACTOR")
    print("=" * 76)

    if not RPC_URL:
        print("")
        print("❌ ALCHEMY_API_KEY bulunamadı.")
        print("")
        print(
            "victorious-smile -> Variables içine "
            "ALCHEMY_API_KEY ekle."
        )
        print("")
        return

    # Aynı TX iki kez varsa tek RPC isteği
    signatures = unique_preserve_order(TX_SIGNATURES)

    print("")
    print(f"Input TX  : {len(TX_SIGNATURES)}")
    print(f"Unique TX : {len(signatures)}")
    print("")

    confirmed_destination_owners = []

    ambiguous_transactions = []
    failed_transactions = []

    for number, signature in enumerate(
        signatures,
        start=1,
    ):
        print("-" * 76)

        print(
            f"[{number}/{len(signatures)}] "
            f"{signature}"
        )

        try:
            tx = get_transaction(signature)

            if not tx:
                print("⚠️ Transaction bulunamadı.")

                failed_transactions.append(signature)
                continue

            signers = get_signers(tx)

            if signers:
                print("")
                print("Signer(s):")

                for signer in signers:
                    label = known_label(signer)

                    if label:
                        print(
                            f"  {signer} [{label}]"
                        )
                    else:
                        print(f"  {signer}")

            transfers = extract_transfer_candidates(tx)

            if not transfers:
                print("")
                print(
                    "⚠️ Parsed SPL Transfer / "
                    "TransferChecked bulunamadı."
                )

                ambiguous_transactions.append(signature)
                continue

            destination_owners_this_tx = []

            for index, transfer in enumerate(
                transfers,
                start=1,
            ):
                print("")
                print(f"Transfer #{index}")

                print(
                    f"  Type        : "
                    f"{transfer['type']}"
                )

                print(
                    f"  Amount      : "
                    f"{transfer['amount']}"
                )

                print(
                    f"  Mint        : "
                    f"{transfer['mint'] or '-'}"
                )

                print(
                    f"  SourceOwner : "
                    f"{transfer['source_owner'] or '-'}"
                )

                print(
                    f"  DestOwner   : "
                    f"{transfer['destination_owner'] or '-'}"
                )

                print(
                    f"  DestToken   : "
                    f"{transfer['destination_token_account'] or '-'}"
                )

                if transfer["destination_owner"]:
                    destination_owners_this_tx.append(
                        transfer["destination_owner"]
                    )

            destination_owners_this_tx = (
                unique_preserve_order(
                    destination_owners_this_tx
                )
            )

            # -----------------------------------------------
            # Tek recipient owner -> otomatik güvenli liste
            # -----------------------------------------------

            if len(destination_owners_this_tx) == 1:
                wallet = destination_owners_this_tx[0]

                confirmed_destination_owners.append(wallet)

                label = known_label(wallet)

                print("")

                if label:
                    print(
                        f"✅ Tek recipient owner: "
                        f"{wallet} [{label}]"
                    )
                else:
                    print(
                        f"✅ Tek recipient owner: "
                        f"{wallet}"
                    )

            # -----------------------------------------------
            # Bir TX içinde birden fazla recipient
            # Tahmin yapmıyoruz.
            # -----------------------------------------------

            elif len(destination_owners_this_tx) > 1:
                print("")
                print(
                    "⚠️ MULTIPLE DESTINATION OWNERS"
                )

                print(
                    "Bu TX otomatik olarak tek "
                    "Round 3 wallet'a atanmadı."
                )

                for wallet in destination_owners_this_tx:
                    label = known_label(wallet)

                    if label:
                        print(
                            f"  → {wallet} [{label}]"
                        )
                    else:
                        print(
                            f"  → {wallet}"
                        )

                ambiguous_transactions.append(signature)

            else:
                print("")
                print(
                    "⚠️ Destination owner çözülemedi."
                )

                ambiguous_transactions.append(signature)

        except Exception as exc:
            print("")
            print(f"❌ ERROR: {exc}")

            failed_transactions.append(signature)

    # ========================================================
    # FINAL LIST
    # ========================================================

    unique_wallets = unique_preserve_order(
        confirmed_destination_owners
    )

    final_entries = []

    # Tim / Faik daima başta
    for label, wallet in KNOWN_WALLETS.items():
        final_entries.append(
            (label, wallet)
        )

    known_addresses = set(
        KNOWN_WALLETS.values()
    )

    anonymous_counter = 1

    for wallet in unique_wallets:
        if wallet in known_addresses:
            continue

        label = (
            f"Round3-{anonymous_counter:02d}"
        )

        anonymous_counter += 1

        final_entries.append(
            (label, wallet)
        )

    # ========================================================
    # OUTPUT
    # ========================================================

    print("")
    print("")
    print("=" * 76)
    print(
        "FINAL - AUTO CONFIRMED ROUND 3 WALLET LIST"
    )
    print("=" * 76)
    print("")

    for label, wallet in final_entries:
        print(
            f"{label}={wallet}"
        )

    railway_value = ",".join(
        f"{label}={wallet}"
        for label, wallet in final_entries
    )

    print("")
    print("=" * 76)
    print("RAILWAY VALUE")
    print("=" * 76)
    print("")

    print(
        "ROUND3_WALLETS="
        + railway_value
    )

    # ========================================================
    # MANUAL REVIEW
    # ========================================================

    print("")
    print("")
    print("=" * 76)
    print("MANUAL REVIEW")
    print("=" * 76)

    if ambiguous_transactions:
        print("")
        print(
            f"⚠️ {len(ambiguous_transactions)} TX "
            "tek recipient wallet'a "
            "otomatik indirgenemedi."
        )

        print("")

        for signature in ambiguous_transactions:
            print(
                f"https://solscan.io/tx/{signature}"
            )

    else:
        print("")
        print(
            "✅ Manual review gereken TX yok."
        )

    if failed_transactions:
        print("")
        print(
            f"❌ {len(failed_transactions)} TX "
            "RPC üzerinden okunamadı."
        )

        print("")

        for signature in failed_transactions:
            print(signature)

    print("")
    print("=" * 76)
    print("BİTTİ")
    print("=" * 76)

    print("")
    print(
        "Bu script Patoshi Radar'ın çalışan "
        "V5.2 sistemini değiştirmedi."
    )
    print("")


if __name__ == "__main__":
    main()
