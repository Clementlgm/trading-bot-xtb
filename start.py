from flask import Flask, jsonify
import os, logging, threading, time
from bot_cloud import XTBTradingBot
import google.cloud.logging

client = google.cloud.logging.Client()
client.setup_logging()
logging.getLogger().setLevel(logging.INFO)

app = Flask(__name__)
bot = None
bot_thread = None

def run_trading():
    global bot
    logging.info("Starting trading bot")
    bot = XTBTradingBot(symbol='EURUSD', timeframe='1h')
    while True:
        try:
            if bot.connect():
                logging.info("Connected to XTB")
                bot.run_strategy()
            time.sleep(30)
        except Exception as e:
            logging.error(f"Trading error: {e}")
            time.sleep(30)

@app.route('/')
def home():
    global bot_thread
    if not bot_thread or not bot_thread.is_alive():
        bot_thread = threading.Thread(target=run_trading, daemon=True)
        bot_thread.start()
        logging.info("Started bot thread")
    return "Bot running"

@app.route('/status', methods=['GET'])
def check_status():
    global bot
    if not bot:
        return jsonify({"status": "not running"})
    return jsonify({
        "status": "running",
        "thread_alive": bot_thread.is_alive() if bot_thread else False
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
