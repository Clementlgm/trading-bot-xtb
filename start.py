from flask import Flask
import threading
from bot_cloud import XTBTradingBot
import os
import logging

app = Flask(__name__)
bot_thread = None
bot = None

logging.basicConfig(level=logging.INFO)

def start_bot():
    global bot
    try:
        bot = XTBTradingBot(symbol='EURUSD', timeframe='1h')
        if bot.connect():
            logging.info("Bot connected successfully")
            bot.run_strategy()
    except Exception as e:
        logging.error(f"Bot error: {e}")

@app.route('/')
def home():
    return "Trading Bot is running", 200

if __name__ == "__main__":
    bot_thread = threading.Thread(target=start_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
