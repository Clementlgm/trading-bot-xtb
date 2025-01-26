from flask import Flask, jsonify
from flask_cors import CORS
import os, logging, time
from bot_cloud import XTBTradingBot
from threading import Thread

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

@app.route("/")
def root():
    return jsonify({"status": "running"})

@app.route("/status")
def get_status():
    global bot
    if not bot:
        init_bot()
    return jsonify({
        "status": "connected" if bot and bot.client else "disconnected",
        "account_info": bot.check_account_status() if bot else None
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    if init_bot():
        Thread(target=run_trading, daemon=True).start()
    app.run(host="0.0.0.0", port=port)
