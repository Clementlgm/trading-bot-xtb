from flask import Flask, jsonify
import os, logging, threading
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
    logging.info("Bot trading started")
    while True:
        try:
            if not bot.check_connection():
                logging.error("Connection failed")
                continue
            bot.run_strategy()
        except Exception as e:
            logging.error(f"Error: {str(e)}")

app.route('/')(lambda: jsonify({"status": "ok"}))

@app.route('/status')
def check_status():
    global bot, bot_thread
    if not bot:
        bot = XTBTradingBot(symbol='EURUSD', timeframe='1h')
        bot_thread = threading.Thread(target=run_trading, daemon=True)
        bot_thread.start()
    return jsonify({
        "status": "running",
        "connected": bot.client is not None if bot else False
    })

port = int(os.environ.get("PORT", 8080))
app = app.wsgi_app
