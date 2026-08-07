import json
import threading
import time

from websocket import WebSocketApp

from config import HELIUS_API_KEY


class HeliusWS:

    def __init__(self, callback=None):

        self.ws = None
        self.thread = None
        self.running = False
        self.callback = callback

    def on_open(self, ws):

        print("🛰 Helius WebSocket bağlandı.")

        subscribe = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "transactionSubscribe",
            "params": [
                {
                    "failed": False,
                    "vote": False,
                    "accountInclude": []
                },
                {
                    "commitment": "confirmed",
                    "encoding": "jsonParsed",
                    "transactionDetails": "full",
                    "maxSupportedTransactionVersion": 0
                }
            ]
        }

        try:

            ws.send(json.dumps(subscribe))

            print("✅ transactionSubscribe gönderildi.")

        except Exception as e:

            print("❌ Subscribe gönderilemedi")
            print(e)

    def on_message(self, ws, message):

        try:

            data = json.loads(message)

            print("🛰 Helius Event")

            if self.callback:

                self.callback(data)

            else:

                print(
                    json.dumps(
                        data,
                        indent=2,
                        ensure_ascii=False
                    )
                )

        except Exception as e:

            print("❌ Helius Parse Hatası")
            print(e)

    def on_error(self, ws, error):

        print("❌ Helius Error")
        print(error)

    def on_close(self, ws, close_status_code, close_msg):

        print("🔌 Helius bağlantısı kapandı.")

        self.ws = None

        if self.running:

            print("♻️ 5 saniye sonra yeniden bağlanılıyor...")

            time.sleep(5)

            self.start()

    def start(self):

        if self.ws is not None:
            return

        self.running = True

        self.ws = WebSocketApp(
            f"wss://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}",
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )

        self.thread = threading.Thread(
            target=self.ws.run_forever,
            daemon=True,
            name="HeliusWS"
        )

        self.thread.start()

    def stop(self):

        self.running = False

        if self.ws:

            self.ws.close()
            self.ws = None

        self.thread = None
