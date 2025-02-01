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
bot_status = {"is_running": False, "last_check": None}

def ensure_bot_initialized():
    global bot, bot_status
    with bot_lock:
        try:
            if bot is None:
                logger.info("Initialisation du bot...")
                bot = XTBTradingBot(symbol='BITCOIN', timeframe='1h')
                if bot.connect():
                    bot_status["is_running"] = True
                    logger.info("Bot initialisé et connecté avec succès")
                    return True
                else:
                    logger.error("Échec de la connexion du bot")
                    return False
            return True
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation du bot: {str(e)}")
            return False

def run_trading():
    global bot, bot_status
    logger.info("Démarrage du thread de trading")
    while True:
        try:
            with bot_lock:
                if ensure_bot_initialized():
                    if not bot.check_connection():
                        logger.warning("Connexion perdue, tentative de reconnexion...")
                        if bot.connect():
                            logger.info("Reconnecté avec succès")
                            bot_status["is_running"] = True
                        else:
                            logger.error("Échec de la reconnexion")
                            bot_status["is_running"] = False
                    else:
                        bot_status["last_check"] = time.time()
                        bot.run_strategy()
            time.sleep(30)  # Délai réduit pour une meilleure réactivité
        except Exception as e:
            logger.error(f"Erreur dans le thread de trading: {str(e)}")
            time.sleep(10)

@app.route("/")
def home():
    return jsonify({
        "status": "running",
        "bot_initialized": bot is not None,
        "service": "trading-bot"
    })

@app.route("/status")
def status():
    global bot, bot_status
    with bot_lock:
        if not ensure_bot_initialized():
            return jsonify({
                "status": "disconnected",
                "error": "Impossible d'initialiser le bot",
                "last_check": bot_status.get("last_check")
            })

        is_connected = bot and bot.check_connection() and bot_status["is_running"]
        account_info = bot.check_account_status() if is_connected else None

        return jsonify({
            "status": "connected" if is_connected else "disconnected",
            "account_info": account_info,
            "last_check": bot_status.get("last_check"),
            "is_running": bot_status["is_running"]
        })

if __name__ == "__main__":
    try:
        if ensure_bot_initialized():
            trading_thread = Thread(target=run_trading, daemon=True)
            trading_thread.start()
            logger.info("Thread de trading démarré")
        else:
            logger.error("Échec de l'initialisation initiale du bot")
    except Exception as e:
        logger.error(f"Erreur lors du démarrage: {str(e)}")

    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
