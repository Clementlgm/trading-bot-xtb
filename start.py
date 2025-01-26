from flask import Flask, jsonify
from flask_cors import CORS
import os, logging
from bot_cloud import XTBTradingBot
from threading import Thread
import google.cloud.logging

# Configure Google Cloud Logging
try:
    client = google.cloud.logging.Client()
    client.setup_logging()
except Exception as e:
    logging.error(f"Failed to setup Google Cloud Logging: {e}")

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Global variables
bot = None
trade_thread = None

def init_bot():
    """Initialize the trading bot"""
    global bot
    if not bot:
        try:
            bot = XTBTradingBot(symbol='BITCOIN', timeframe='1h')
            return bot.connect()
        except Exception as e:
            logging.error(f"Failed to initialize bot: {e}")
            return False
    return True

def run_trading():
    """Run the trading bot strategy"""
    while True:
        try:
            if bot and bot.client:
                bot.run_strategy()
            else:
                logging.warning("Bot not initialized or client not connected")
            logging.info("Trading cycle completed, waiting for next cycle")
        except Exception as e:
            logging.error(f"Error in trading thread: {e}")
        finally:
            time.sleep(60)

@app.route("/status")
def status():
    """Get bot status"""
    global bot
    try:
        is_connected = bool(bot and bot.client)
        account_info = bot.check_account_status() if is_connected else None
        return jsonify({
            "status": "connected" if is_connected else "disconnected",
            "account_info": account_info
        })
    except Exception as e:
        logging.error(f"Error checking status: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/trades")
def get_trades():
    """Get current trades"""
    global bot
    try:
        if not bot:
            return jsonify({"error": "Bot not initialized"}), 500
        trades = bot.client.commandExecute("getTrades", {"openedOnly": True})
        return jsonify(trades)
    except Exception as e:
        logging.error(f"Error getting trades: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/")
def home():
    """Home endpoint"""
    return jsonify({"status": "running"})

if __name__ == "__main__":
    # Get port from environment variable
    port = int(os.environ.get("PORT", 8080))
    
    # Initialize bot and start trading thread
    if init_bot():
        trading_thread = Thread(target=run_trading, daemon=True)
        trading_thread.start()
        logging.info("Trading thread started")
    
    # Start Flask app
    app.run(host="0.0.0.0", port=port)
