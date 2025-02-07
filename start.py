from flask import Flask, jsonify
from flask_cors import CORS
import os
import logging
import time
from bot_cloud import XTBTradingBot
from threading import Thread, Lock
import google.cloud.logging
from functools import wraps

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
bot_status = {
    "is_running": False,
    "last_check": None,
    "last_request_time": 0,
    "request_count": 0
}

def init_bot_if_needed():
    global bot
    try:
        if bot is None:
            logger.info("Initialisation du bot...")
            user_id = os.getenv('XTB_USER_ID')
            password = os.getenv('XTB_PASSWORD')
            
            if not user_id or not password:
                logger.error("Identifiants XTB manquants")
                return False
                
            bot = XTBTradingBot(symbol='BITCOIN', timeframe='1h')
            if not bot.connect():
                logger.error("Échec de la connexion initiale")
                return False
            
            trading_thread = Thread(target=run_trading, daemon=True)
            trading_thread.start()
            bot_status["is_running"] = True
            return True
        return True
    except Exception as e:
        logger.error(f"Erreur d'initialisation: {str(e)}")
        return False

def run_trading():
    global bot
    logger.info("Démarrage du thread de trading")
    while True:
        try:
            with bot_lock:
                if bot and bot.check_connection():
                    bot.run_strategy()
                else:
                    time.sleep(30)
        except Exception as e:
            logger.error(f"Erreur dans run_trading: {str(e)}")
            time.sleep(30)

@app.route("/")
def home():
    return jsonify({
        "status": "running",
        "service": "trading-bot"
    })

@app.route("/status")
def status():
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
