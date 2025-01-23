from flask import Flask, jsonify
import os, logging, threading, time
from bot_cloud import XTBTradingBot
import google.cloud.logging

client = google.cloud.logging.Client()
client.setup_logging()

app = Flask(__name__)
bot = None
bot_thread = None

def run_bot():
    global bot
    while True:
        try:
            logging.info("Starting trading bot...")
            if not bot.check_connection():
                logging.error("Connection failed")
                time.sleep(30)
                continue
            bot.run_strategy()
        except Exception as e:
            logging.error(f"Bot error: {str(e)}")
            time.sleep(30)

@app.route('/')
def home():
    global bot, bot_thread
    try:
        if not bot:
            bot = XTBTradingBot(symbol='EURUSD', timeframe='1h')
        if not bot_thread or not bot_thread.is_alive():
            bot_thread = threading.Thread(target=run_bot, daemon=True)
            bot_thread.start()
        return jsonify({"status": "running"})
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)})

@app.route('/status')
def status():
    global bot
    return jsonify({
        "status": "running" if bot and bot_thread and bot_thread.is_alive() else "stopped",
        "connected": bool(bot and bot.client is not None) if bot else False
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
