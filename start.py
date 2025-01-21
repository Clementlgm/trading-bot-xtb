from flask import Flask
import os
from bot_cloud import XTBTradingBot
import threading
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

def run_bot():
    logger.info("Démarrage du bot de trading...")
    try:
        bot = XTBTradingBot(symbol='BITCOIN', timeframe='1h')
        if bot.connect():
            logger.info("Bot connecté avec succès")
            bot.run_strategy()
        else:
            logger.error("Échec de connexion du bot")
    except Exception as e:
        logger.error(f"Erreur dans le bot: {str(e)}")

@app.route('/')
def root():
    return "Trading Bot is running", 200

@app.route('/health')
def health():
    return "OK", 200

if __name__ == "__main__":
    # Démarrage du bot dans un thread séparé
    threading.Thread(target=run_bot, daemon=True).start()
    
    # Démarrage de Flask
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
