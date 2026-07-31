import requests

class TelegramSender:

    def __init__(self, bot_token, chat_id):
        self.bot_token = bot_token
        self.chat_id = chat_id

    def send(self, text):
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

        data = {
            "chat_id": self.chat_id,
            "text": text,
            "disable_web_page_preview": True
        }

        try:
            r = requests.post(url, json=data, timeout=15)

            if r.status_code == 200:
                print("Telegram bildirimi gönderildi.")
            else:
                print("Telegram Hatası")
                print(r.text)

        except Exception as e:
            print(e)
