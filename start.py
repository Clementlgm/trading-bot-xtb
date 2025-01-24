from flask import Flask, jsonify
import os, logging
from bot_cloud import XTBTradingBot
import google.cloud.logging
from threading import Thread

client = google.cloud.logging.Client()
client.setup_logging()

app = Flask(__name__)
bot = None
trade_thread = None

def run_trading():
    global bot
    if bot and bot.connect():
        bot.run_strategy()

@app.route("/", methods=['GET'])
def home():
    return jsonify({"status": "running"})

@app.route("/status", methods=['GET'])
def status():
    global bot, trade_thread
    if not bot:
        bot = XTBTradingBot(symbol='EURUSD', timeframe='1h')
        trade_thread = Thread(target=run_trading, daemon=True)
        trade_thread.start()
    
    return jsonify({
        "status": "active",
        "connected": bool(bot and bot.client)
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
