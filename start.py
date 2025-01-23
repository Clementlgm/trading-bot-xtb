from flask import Flask
import os, logging, threading, time
from bot_cloud import XTBTradingBot
from logging_config import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)
bot = None
bot_thread = None

def run_bot():
    global bot
    while True:
        try:
            if bot and bot.connect():
                logger.info("🤖 Bot connected - starting trading strategy")
                bot.run_strategy()
            else:
                logger.error("❌ Bot connection failed - retrying in 60s")
                time.sleep(60)
        except Exception as e:
            logger.error(f"❌ Bot error: {str(e)}")
            time.sleep(60)

def init_bot():
    global bot, bot_thread
    try:
        logger.info("🔄 Initializing trading bot...")
        bot = XTBTradingBot(symbol='EURUSD', timeframe='1h')
        
        if not bot_thread or not bot_thread.is_alive():
            bot_thread = threading.Thread(target=run_bot, daemon=True)
            bot_thread.start()
            logger.info("✅ Bot thread started")
    except Exception as e:
        logger.error(f"❌ Init error: {str(e)}")

@app.route('/')
def home():
    global bot, bot_thread
    status = "running" if bot and bot_thread and bot_thread.is_alive() else "stopped"
    if status == "stopped":
        init_bot()
    logger.info(f"📊 Bot status: {status}")
    return {"status": status}, 200

if __name__ == "__main__":
    init_bot()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
