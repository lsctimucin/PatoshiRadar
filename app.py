from config import BOT_TOKEN, CHAT_ID
from telegram_sender import TelegramSender

print("Patoshi Radar Başlıyor...")

bot = TelegramSender(BOT_TOKEN, CHAT_ID)

bot.send("🚀 Patoshi Radar Railway üzerinde çalışıyor.")
