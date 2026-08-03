import requests
from config import BOT_TOKEN, CHAT_ID


class TelegramSender:

    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id

    def send(self, text):

        try:
            response = requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text
                },
                timeout=10
            )

            print("Telegram:", response.status_code)
            print("Telegram Response:", response.text)

            return response.status_code == 200

        except requests.RequestException as e:
            print("Telegram Hatası:", e)
            return False


sender = TelegramSender(BOT_TOKEN, CHAT_ID)


def send_message(text):
    return sender.send(text)
