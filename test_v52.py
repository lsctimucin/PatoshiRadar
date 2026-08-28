from transfer_classifier import classify_transfers


creator = "CREATOR_WALLET_TEST"

tests = [
    {
        "signature": "tx_creator",
        "from_owner": creator,
        "to_owner": "wallet_A",
        "amount_raw": 1000,
    },
    {
        "signature": "tx_normal",
        "from_owner": "wallet_B",
        "to_owner": "wallet_C",
        "amount_raw": 500,
    },
]

result = classify_transfers(
    tests,
    creator=creator,
)

for item in result:
    print(item["signature"])
    print(item["label"])
    print(item["reason"])
    print("-" * 40)
