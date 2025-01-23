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

@app.route('/')
def home():
    return jsonify({"status": "ok"})

@app.route('/status')
def status():
    global bot, bot_thread
    try:
        if not bot:
            bot = XTBTradingBot(symbol='EURUSD', timeframe='1h')
            bot_thread = threading.Thread(target=bot.run_strategy, daemon=True)
            bot_thread.start()
        return jsonify({
            "status": "running",
            "connected": bot.client is not None
        })
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
