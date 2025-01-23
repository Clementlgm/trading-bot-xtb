from flask import Flask
import os, logging, threading
from bot_cloud import XTBTradingBot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
bot = None

def init_bot():
    global bot
    try:
        logger.info("Initializing trading bot...")
        bot = XTBTradingBot(symbol='EURUSD', timeframe='1h')
        logger.info("Bot initialized")
    except Exception as e:
        logger.error(f"Bot initialization error: {str(e)}")

@app.route('/')
def home():
    global bot
    status = "Bot initialized" if bot else "Bot not initialized"
    logger.info(f"Home endpoint - {status}")
    return f"Trading Bot is running - {status}", 200

if __name__ == "__main__":
    threading.Thread(target=init_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
