from flask import Flask
import threading
import os
import logging
from bot_cloud import XTBTradingBot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
bot = None

def run_bot():
    global bot
    logger.info("Démarrage du bot...")
    try:
        bot = XTBTradingBot(symbol='BITCOIN', timeframe='1h')
        if bot.connect():
            logger.info("Bot connecté avec succès")
            bot.run_strategy()
    except Exception as e:
        logger.error(f"Erreur bot: {str(e)}")

@app.route('/')
def home():
    return "Bot Trading", 200

@app.route('/status')
def status():
    global bot
    if bot and hasattr(bot, 'client'):
        return "Bot connecté", 200
    return "Bot non connecté", 500

# Démarrage du bot dans un thread
bot_thread = threading.Thread(target=run_bot, daemon=True)
bot_thread.start()
