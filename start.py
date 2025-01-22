from flask import Flask
import threading
from bot_cloud import XTBTradingBot
import os
import logging

app = Flask(__name__)
bot_thread = None
bot = None

def start_bot():
    global bot
    bot = XTBTradingBot(symbol='EURUSD', timeframe='1h')
    bot.run_strategy()

@app.route('/')
def home():
    return "Trading Bot is running", 200

@app.route('/status')
def status():
    global bot
    if bot and bot.client:
        return "Bot connected and running", 200
    return "Bot not running or disconnected", 503

if __name__ == "__main__":
    # Démarrer le bot dans un thread séparé
    bot_thread = threading.Thread(target=start_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Démarrer le serveur Flask
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
