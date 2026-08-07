import requests

from config import HELIUS_API_KEY


RPC = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"


def check_lp(mint):

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getAccountInfo",
        "params": [
            mint,
            {
                "encoding": "base64"
            }
        ]
    }

    try:

        r = requests.post(
            RPC,
            json=payload,
            timeout=10
        )

        data = r.json()

        if data.get("result"):
            return False

    except Exception as e:

        print(e)

    return False
