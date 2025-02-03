from flask import Flask, jsonify, request
from flask_cors import CORS
import os, logging, time, jwt
from bot_cloud import XTBTradingBot
from threading import Thread, Lock
import google.cloud.logging
from functools import wraps
from datetime import datetime, timedelta

client = google.cloud.logging.Client()
client.setup_logging()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('trading_bot')

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24))

bot_lock = Lock()
bot = None
bot_status = {
    "is_running": False,
    "last_check": None,
    "last_request_time": 0,
    "request_count": 0
}

RATE_LIMIT = 30
RATE_WINDOW = 60

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('bearer ', '')
        if not token:
            return jsonify({"error": "Token requis"}), 401
        try:
            jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            return f(*args, **kwargs)
        except:
            return jsonify({"error": "Token invalide"}), 401
    return decorated

def rate_limit():
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            current_time = time.time()
            with bot_lock:
                if current_time - bot_status["last_request_time"] > RATE_WINDOW:
                    bot_status["request_count"] = 0
                    bot_status["last_request_time"] = current_time
                
                if bot_status["request_count"] >= RATE_LIMIT:
                    return jsonify({
                        "error": "Limite de taux dépassée",
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
            user_id = os.getenv('XTB_USER_ID')
            password = os.getenv('XTB_PASSWORD')
            
            if not user_id or not password:
                logger.error("Identifiants XTB manquants")
                return False
                
            bot = XTBTradingBot(symbol='BITCOIN', timeframe='1h')
            if not bot.connect():
                return False
            
            bot_status["is_running"] = True
            return True
        return True
    except Exception as e:
        logger.error(f"Erreur d'initialisation: {str(e)}")
        return False

def run_trading():
    global bot
    while True:
        try:
            with bot_lock:
                if bot and bot.check_connection():
                    bot.run_strategy()
                    bot_status["last_check"] = time.time()
                else:
                    if not init_bot_if_needed():
                        time.sleep(30)
            time.sleep(5)
        except Exception as e:
            logger.error(f"Erreur trading: {str(e)}")
            time.sleep(10)

@app.route("/", methods=['GET', 'POST'])
@require_auth
@rate_limit()
def handle_orders():
    if request.method == 'POST':
        try:
            data = request.get_json()
            required = ['symbol', 'type', 'volume']
            if not all(k in data for k in required):
                return jsonify({"error": "Paramètres manquants"}), 400
                
            with bot_lock:
                if not init_bot_if_needed():
                    return jsonify({"error": "Bot non initialisé"}), 500
                    
                success = bot.execute_trade(
                    data['type'].upper(),
                    data['symbol'],
                    float(data['volume'])
                )
                
                if success:
                    return jsonify({"status": "ordre_execute"})
                return jsonify({"error": "Échec exécution"}), 500
                
        except Exception as e:
            logger.error(f"Erreur ordre: {str(e)}")
            return jsonify({"error": str(e)}), 500
            
    return jsonify({"status": "running"})

@app.route("/status")
@require_auth
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
    try:
        if init_bot_if_needed():
            Thread(target=run_trading, daemon=True).start()
    except Exception as e:
        logger.error(f"Erreur démarrage: {str(e)}")

    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
    
