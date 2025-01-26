from flask import Flask, jsonify
from flask_cors import CORS
import os, logging
from bot_cloud import XTBTradingBot
from threading import Thread
import time

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
CORS(app)
bot = None

def init_bot():
    global bot
    if not bot:
        bot = XTBTradingBot(symbol='BITCOIN', timeframe='1h')
        return bot.connect()
    return True

def run_trading():
    while True:
        try:
            if bot and bot.client:
                bot.run_strategy()
            time.sleep(60)
        except Exception as e:
            logging.error(f"Error: {str(e)}")
            time.sleep(30)

@app.route("/trades")
def get_trades():
    global bot
    if not bot:
        return "Bot not initialized", 500
    cmd = {
        "command": "getTrades",
        "arguments": {
            "openedOnly": True
        }
    }
    return bot.client.commandExecute(cmd["command"], cmd["arguments"])

@app.route("/status")
def status():
    global bot
    return jsonify({
        "status": "connected" if bot and bot.client else "disconnected"
    })

@app.route("/")
def home():
    return jsonify({"status": "running"})

if __name__ == "__main__":
    if init_bot():
        Thread(target=run_trading, daemon=True).start()
        app.run(port=8080)