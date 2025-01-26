#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from flask import Flask, jsonify
<<<<<<< HEAD
from flask_cors import CORS
import os, logging
from bot_cloud import XTBTradingBot
from threading import Thread
import time
=======
import os, logging
from bot_cloud import XTBTradingBot
import google.cloud.logging
from threading import Thread
from dotenv import load_dotenv
load_dotenv()

client = google.cloud.logging.Client()
client.setup_logging()
>>>>>>> 32c1e2633458236e86f5a7d9a677bf0f58304d2d

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
<<<<<<< HEAD
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
=======
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
>>>>>>> 32c1e2633458236e86f5a7d9a677bf0f58304d2d
