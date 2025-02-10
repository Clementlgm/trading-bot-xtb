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

def run_trading():
    global bot
    logger.info("Démarrage du thread de trading")
    while True:
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
                        time.sleep(30)
            time.sleep(5)
        except Exception as e:
            logger.error(f"Erreur dans run_trading: {str(e)}")
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

from flask import Flask, jsonify
import json
import logging

@app.route("/test_trade", methods=['GET'])
def test_trade():
    global bot
    if not bot:
        init_bot()
        
    try:
        account_info = bot.check_account_status()
        logger.info(f"État du compte: {json.dumps(account_info, indent=2)}")
        
        symbol_info = bot.get_symbol_info()
        logger.info(f"Info symbole: {json.dumps(symbol_info, indent=2)}")
        
        result = bot.execute_trade("BUY")
        logger.info(f"Résultat trade: {result}")
        
        return jsonify({
            "success": result,
            "account_info": account_info,
            "symbol_info": symbol_info,
            "message": "Trade test exécuté"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/logs", methods=['GET'])
def get_logs():
    verbose = request.args.get('verbose', 'false').lower() == 'true'
    try:
        if not bot:
            return jsonify({"error": "Bot non initialisé"}), 400

        logs = []
        
        # État de la connexion
        connection_status = "connecté" if bot.client else "déconnecté"
        logs.append(f"🔌 État de la connexion : {connection_status}")
        
        # Vérification des positions actives
        has_positions = bot.get_active_positions()
        logs.append(f"📊 Positions actives : {'Oui' if has_positions else 'Non'}")
        
        # Récupération des données de marché
        df = bot.get_historical_data()
        if df is not None:
            df = bot.calculate_indicators(df)
            if df is not None:
                last_row = df.iloc[-1]
                
                # Prix actuels
                logs.append(f"""💰 Données de marché actuelles:
                - Prix de clôture: {last_row['close']}
                - SMA20: {last_row['SMA20']:.5f}
                - SMA50: {last_row['SMA50']:.5f}
                - RSI: {last_row['RSI']:.2f}""")
                
                # Analyse des conditions de trading
                sma_condition = last_row['SMA20'] > last_row['SMA50']
                rsi_buy_condition = last_row['RSI'] < 70
                rsi_sell_condition = last_row['RSI'] > 30
                price_sma_condition = last_row['close'] > last_row['SMA20']
                
                logs.append(f"""🔍 Analyse des conditions:
                Pour un signal BUY:
                - SMA20 > SMA50: {'✅' if sma_condition else '❌'} ({last_row['SMA20']:.5f} vs {last_row['SMA50']:.5f})
                - RSI < 70: {'✅' if rsi_buy_condition else '❌'} ({last_row['RSI']:.2f})
                - Prix > SMA20: {'✅' if price_sma_condition else '❌'} ({last_row['close']} vs {last_row['SMA20']:.5f})
                
                Pour un signal SELL:
                - SMA20 < SMA50: {'✅' if not sma_condition else '❌'} ({last_row['SMA20']:.5f} vs {last_row['SMA50']:.5f})
                - RSI > 30: {'✅' if rsi_sell_condition else '❌'} ({last_row['RSI']:.2f})
                - Prix < SMA20: {'✅' if not price_sma_condition else '❌'} ({last_row['close']} vs {last_row['SMA20']:.5f})""")
                
                # Infos sur les ordres en cours
                if has_positions:
                    cmd = {
                        "command": "getTrades",
                        "arguments": {
                            "openedOnly": True
                        }
                    }
                    trades = bot.client.commandExecute(cmd["command"], cmd["arguments"])
                    if trades and 'returnData' in trades:
                        for trade in trades['returnData']:
                            if trade.get('symbol') == bot.symbol:
                                logs.append(f"""📈 Détails de la position ouverte:
                                - Type: {'ACHAT' if trade.get('cmd') == 0 else 'VENTE'}
                                - Prix d'entrée: {trade.get('open_price')}
                                - Stop Loss: {trade.get('sl')}
                                - Take Profit: {trade.get('tp')}
                                - Volume: {trade.get('volume')}
                                - Profit actuel: {trade.get('profit')}""")
                
                # État du compte
                account_info = bot.client.commandExecute("getMarginLevel")
                if account_info and 'returnData' in account_info:
                    balance = account_info['returnData']
                    logs.append(f"""💳 État du compte:
                    - Balance: {balance.get('balance')}
                    - Equity: {balance.get('equity')}
                    - Margin: {balance.get('margin')}""")
                
            else:
                logs.append("❌ Erreur dans le calcul des indicateurs")
        else:
            logs.append("❌ Erreur dans la récupération des données historiques")
            
        return jsonify({
            "logs": logs,
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
        })
        
    except Exception as e:
        logger.error(f"Erreur dans get_logs: {str(e)}")
        return jsonify({"error": str(e)}), 500
    
    # Démarre le serveur Flask
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
    
