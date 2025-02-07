from flask import Flask, jsonify
from flask_cors import CORS
import os
import logging
import time
from bot_cloud import XTBTradingBot
from threading import Thread, Lock, Event
import google.cloud.logging
from functools import wraps
import signal

client = google.cloud.logging.Client()
client.setup_logging()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('trading_bot')

app = Flask(__name__)
CORS(app)

bot_lock = Lock()
shutdown_event = Event()
bot = None
trading_thread = None
bot_status = {
    "is_running": False,
    "last_check": None
}

def rate_limit():
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            with bot_lock:
                return f(*args, **kwargs)
        return wrapped
    return decorator

def signal_handler(signum, frame):
    logger.info(f"Signal reçu : {signum}")
    if bot:
        try:
            with bot_lock:
                if bot.streaming:
                    bot.streaming.disconnect()
                if bot.client:
                    bot.client.disconnect()
        except Exception as e:
            logger.error(f"Erreur lors de la déconnexion: {e}")
    shutdown_event.set()

def init_bot_if_needed():
    global bot, trading_thread
    try:
        if bot is None:
            with bot_lock:
                logger.info("Initialisation du bot...")
                user_id = os.getenv('XTB_USER_ID')
                password = os.getenv('XTB_PASSWORD')
                
                if not user_id or not password:
                    logger.error("Identifiants XTB manquants")
                    return False
                    
                bot = XTBTradingBot(symbol='BITCOIN')
                if not bot.connect():
                    logger.error("Échec de la connexion initiale")
                    return False
                
                if not trading_thread or not trading_thread.is_alive():
                    trading_thread = Thread(target=run_trading, daemon=True)
                    trading_thread.start()
                    logger.info("Thread de trading démarré")
                
                bot_status["is_running"] = True
                return True
        return True
    except Exception as e:
        logger.error(f"Erreur d'initialisation: {str(e)}")
        return False

def run_trading():
    logger.info("Démarrage du thread de trading")
    while not shutdown_event.is_set():
        try:
            with bot_lock:
                if bot and bot.check_connection():
                    bot.run_strategy()
                    bot_status["last_check"] = time.time()
                else:
                    if init_bot_if_needed():
                        logger.info("Bot réinitialisé avec succès")
                    else:
                        logger.error("Échec de la réinitialisation")
                        time.sleep(5)
            if not shutdown_event.is_set():
                time.sleep(5)
        except Exception as e:
            logger.error(f"Erreur dans run_trading: {str(e)}")
            if not shutdown_event.is_set():
                time.sleep(5)

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
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        if init_bot_if_needed():
            logger.info("Bot initialisé avec succès")
        else:
            logger.error("Échec de l'initialisation du bot")
    except Exception as e:
        logger.error(f"Erreur au démarrage: {str(e)}")

    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
