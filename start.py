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

# Configuration des limites de taux
RATE_LIMIT = 30  # requêtes par minute
RATE_WINDOW = 60  # fenêtre de 60 secondes

def rate_limit():
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            current_time = time.time()
            with bot_lock:
                # Réinitialise le compteur si la fenêtre est passée
                if current_time - bot_status["last_request_time"] > RATE_WINDOW:
                    bot_status["request_count"] = 0
                    bot_status["last_request_time"] = current_time
                
                # Vérifie la limite de taux
                if bot_status["request_count"] >= RATE_LIMIT:
                    logger.warning("Limite de taux dépassée")
                    return jsonify({
                        "error": "Rate limit exceeded",
                        "retry_after": RATE_WINDOW - (current_time - bot_status["last_request_time"])
                    }), 429
                
                bot_status["request_count"] += 1
            return f(*args, **kwargs)
        return wrapped
    return decorator

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
                
            bot = XTBTradingBot(symbol='EURUSD', timeframe='1m')
            if not bot.connect():
                logger.error("Échec de la connexion initiale")
                return False
            
            bot_status["is_running"] = True
            return True
        return True
    except Exception as e:
        logger.error(f"Erreur d'initialisation: {str(e)}")
        return False

def run_trading_thread():
    logger.info("Démarrage du thread de trading")
    while True:
        try:
            with bot_lock:
                if bot and bot.check_connection():
                    success = bot.run_strategy()
                    if not success:
                        logger.warning("Échec de l'exécution de la stratégie")
                else:
                    if init_bot_if_needed():
                        logger.info("Bot réinitialisé avec succès")
                    else:
                        logger.error("Échec de la réinitialisation")
                        time.sleep(30)
            # Attente avant la prochaine itération
            time.sleep(60)  # Vérifie toutes les minutes
        except Exception as e:
            logger.error(f"Erreur dans le thread de trading: {str(e)}")
            time.sleep(10)

@app.route("/")
@rate_limit()
def home():
    return jsonify({
        "status": "running",
        "service": "trading-bot"
    })

@app.route("/status")
@rate_limit()
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
    # Démarre le thread de trading
    try:
        if init_bot_if_needed():
            trading_thread = Thread(target=run_trading_thread, daemon=True)
            trading_thread.start()
            logger.info("Thread de trading démarré")
    except Exception as e:
        logger.error(f"Erreur au démarrage: {str(e)}")

    # Démarre le serveur Flask
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
    

    


    
