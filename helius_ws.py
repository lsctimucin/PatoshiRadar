import json
import threading
import time

from websocket import WebSocketApp

from config import HELIUS_API_KEY


class HeliusWS:

    def __init__(self, callback=None):

        self.ws = None
        self.running = False
        self.callback = callback

    def on_open(self, ws):

        print("🛰 Helius WebSocket bağlandı.")

        # V4.1
        # Buraya transactionSubscribe isteği eklenecek.

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

            print("Helius Parse Hatası")
            print(e)

    def on_error(self, ws, error):

        print("❌ Helius Error")
        print(error)

    def on_close(self, ws, close_status_code, close_msg):

        print("🔌 Helius bağlantısı kapandı.")

        if self.running:

            print("♻️ 5 saniye sonra yeniden bağlanılıyor...")

            time.sleep(5)

            self.start()

    def start(self):

        self.running = True

        self.ws = WebSocketApp(
            f"wss://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}",
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )

        threading.Thread(
            target=self.ws.run_forever,
            daemon=True
        ).start()

    def stop(self):

        self.running = False

        if self.ws:

            self.ws.close()
