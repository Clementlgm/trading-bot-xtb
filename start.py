from flask import Flask, jsonify
from flask_cors import CORS
import os
import logging
import time
from bot_cloud import XTBTradingBot
from threading import Thread, Lock
import google.cloud.logging

# Configuration du logging
client = google.cloud.logging.Client()
client.setup_logging()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('trading_bot')

app = Flask(__name__)
CORS(app)

# Variables globales avec verrou
bot_lock = Lock()
bot = None
trading_thread = None
bot_status = {
    "is_running": False,
    "last_check": None
}

def run_trading():
    while True:
        try:
            with bot_lock:
                if bot and bot.check_connection():
                    bot.run_strategy()
                    bot_status["last_check"] = time.time()
                else:
                    time.sleep(5)
        except Exception as e:
            logger.error(f"Erreur dans run_trading: {str(e)}")
            time.sleep(5)

def init_bot_if_needed():
    global bot, trading_thread
    try:
        with bot_lock:
            if bot is None:
                logger.info("Initialisation du bot...")
                bot = XTBTradingBot(symbol='BITCOIN', timeframe='1h')
                if not bot.connect():
                    logger.error("Échec de la connexion initiale")
                    return False
                
                # Démarrage du thread de trading si non démarré
                if trading_thread is None or not trading_thread.is_alive():
                    trading_thread = Thread(target=run_trading, daemon=True)
                    trading_thread.start()
                    bot_status["is_running"] = True
                    logger.info("Thread de trading démarré")
                
                return True
            return True
    except Exception as e:
        logger.error(f"Erreur d'initialisation: {str(e)}")
        return False

@app.route("/")
def home():
    return jsonify({
        "status": "running",
        "service": "trading-bot"
    })

@app.route("/status")
def status():
    try:
        with bot_lock:
            is_initialized = init_bot_if_needed()
            is_connected = bot and bot.check_connection() if is_initialized else False
            
            return jsonify({
                "status": "connected" if is_connected else "disconnected",
                "bot_initialized": is_initialized,
                "is_running": bot_status["is_running"],
                "last_check": bot_status.get("last_check"),
                "account_info": bot.check_account_status() if is_connected else None
            })
    except Exception as e:
        logger.error(f"Erreur dans /status: {str(e)}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

if __name__ == "__main__":
    try:
        if init_bot_if_needed():
            logger.info("Bot initialisé avec succès")
        else:
            logger.error("Échec de l'initialisation du bot")
            
        # Démarrage du serveur Flask
        port = int(os.environ.get("PORT", 8080))
        app.run(host="0.0.0.0", port=port)
    except Exception as e:
        logger.error(f"Erreur au démarrage: {str(e)}")
