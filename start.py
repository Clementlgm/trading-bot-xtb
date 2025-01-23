from flask import Flask
import os, logging, threading, time
from bot_cloud import XTBTradingBot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
bot = None
bot_thread = None

def run_bot():
    global bot
    while True:
        try:
            if bot and bot.connect():
                logger.info("Bot connected successfully - starting trading strategy")
                bot.run_strategy()
            else:
                logger.error("Bot connection failed - retrying in 60 seconds")
                time.sleep(60)
        except Exception as e:
            logger.error(f"Bot runtime error: {str(e)}")
            time.sleep(60)

def init_bot():
    global bot, bot_thread
    try:
        logger.info("Initializing trading bot...")
        bot = XTBTradingBot(symbol='EURUSD', timeframe='1h')
        
        # Start bot in a new thread if not already running
        if bot_thread is None or not bot_thread.is_alive():
            bot_thread = threading.Thread(target=run_bot, daemon=True)
            bot_thread.start()
            logger.info("Bot thread started")
    except Exception as e:
        logger.error(f"Bot initialization error: {str(e)}")

@app.route('/')
def home():
    global bot, bot_thread
    if bot and bot_thread and bot_thread.is_alive():
        status = "Bot is running"
    else:
        status = "Bot is not running"
        init_bot()  # Try to reinitialize if not running
    return f"Trading Bot Status: {status}", 200

@app.route('/status')
def status():
    global bot
    if bot:
        account_status = bot.check_account_status()
        return {
            "status": "running" if bot_thread and bot_thread.is_alive() else "stopped",
            "account": account_status if account_status else "unavailable"
        }
    return {"status": "not initialized"}

if __name__ == "__main__":
    threading.Thread(target=init_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
