from config import BOT_TOKEN, CHAT_ID
from telegram_sender import TelegramSender

print("Patoshi Radar Başlatılıyor...")

bot = TelegramSender(BOT_TOKEN, CHAT_ID)

bot.send("✅ Patoshi Radar çalışmaya başladı.")
