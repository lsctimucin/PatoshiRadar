import requests

class TelegramSender:

    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id

    def send(self, text):

        requests.post(
            f"https://api.telegram.org/bot{self.token}/sendMessage",
            json={
                "chat_id": self.chat_id,
                "text": text
            },
            timeout=10
        )
