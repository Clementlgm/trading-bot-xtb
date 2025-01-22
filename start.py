from flask import Flask, jsonify
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
        return jsonify({
            "status": "connected",
            "symbol": bot.symbol,
            "position_open": bot.position_open
        })
    return jsonify({"status": "disconnected"}), 503

if __name__ == "__main__":
    bot_thread = threading.Thread(target=start_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
