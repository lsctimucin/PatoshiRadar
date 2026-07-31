import json
import threading
import time

from websocket import WebSocketApp
from config import PUMPPORTAL_API_KEY


class PumpMonitor:

    def __init__(self, callback):
        self.callback = callback
        self.ws = None
        self.running = False

    def on_open(self, ws):
        print("PumpPortal bağlantısı başarılı.")

        ws.send(json.dumps({
            "method": "subscribeNewToken"
        }))

        print("Yeni coin aboneliği gönderildi.")

    def on_message(self, ws, message):

        print("GELEN VERİ:")
        print(message)

        try:
            data = json.loads(message)
            self.callback(data)

        except Exception as e:
            print(e)

    def on_error(self, ws, error):
        print("WebSocket Hatası")
        print(error)

    def on_close(self, ws, close_status_code, close_msg):
        print("Bağlantı kapandı.")

        if self.running:
            time.sleep(5)
            self.start()

    def start(self):

        self.running = True

        self.ws = WebSocketApp(
            f"wss://pumpportal.fun/api/data?api-key={PUMPPORTAL_API_KEY}",
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
