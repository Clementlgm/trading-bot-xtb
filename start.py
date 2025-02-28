from flask import Flask, jsonify
from flask_cors import CORS
import os
import logging
import time
from bot_cloud import XTBTradingBot
from threading import Thread, Lock
import google.cloud.logging
from functools import wraps
from apscheduler.schedulers.background import BackgroundScheduler
import datetime

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

def sync_position_status():
    """Synchronise l'état interne du bot avec l'état réel du compte"""
    global bot
    with bot_lock:
        if bot and bot.check_connection():
            logger.info("Exécution de la synchronisation programmée du statut des positions...")
            actual_status = bot.check_trade_status()
            if actual_status != bot.position_open:
                logger.warning(f"Incohérence de statut de position détectée et corrigée. Réel: {actual_status}, Interne au bot: {bot.position_open}")
                bot.position_open = actual_status

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
                
            bot = XTBTradingBot(symbol='EURUSD', timeframe='1h')
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
    first_run = True
    while True:
        try:
            with bot_lock:
                if bot and bot.check_connection():
                    # Force un ordre uniquement au premier passage pour tester
                    if first_run:
                        logger.info("⚠️ ORDRE DE TEST FORCÉ")
                        bot.execute_trade("BUY")
                        first_run = False
                    else:
                        success = bot.run_strategy()
                        if not success:
                            logger.warning("Échec de l'exécution de la stratégie")
                else:
                    if init_bot_if_needed():
                        logger.info("Bot réinitialisé avec succès")
                    else:
                        logger.error("Échec de la réinitialisation")
                        time.sleep(30)
            time.sleep(60)
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

from flask import Flask, jsonify
import json
import logging

@app.route("/test_trade", methods=['GET'])
def test_trade():
    global bot
    if not bot:
        init_bot_if_needed()
        
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
    logs = []
    try:
        if bot:
            logs.append(f"État du bot : {'connecté' if bot.client else 'déconnecté'}")
            logs.append(f"Position ouverte : {bot.position_open}")
            df = bot.get_historical_data()
            if df is not None:
                df = bot.calculate_indicators(df)  # Calcul des indicateurs
                if df is not None:
                    last_row = df.iloc[-1]
                    logs.append(f"""
                    Dernières valeurs:
                    - Prix: {last_row['close']}
                    - SMA20: {last_row['SMA20']}
                    - SMA50: {last_row['SMA50']}
                    - RSI: {last_row['RSI']}
                    """)
        return jsonify({"logs": logs})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/debug", methods=['GET'])
def debug_bot():
    try:
        if not bot:
            return jsonify({
                "status": "error",
                "message": "Bot non initialisé"
            }), 500

        # Vérification de la connexion
        connection_status = bot.check_connection()
        
        # Récupération des données historiques
        df = bot.get_historical_data()
        
        if df is None:
            return jsonify({
                "status": "error",
                "message": "Impossible de récupérer les données historiques",
                "connection_status": connection_status
            }), 500
            
        # Calcul des indicateurs
        df_with_indicators = bot.calculate_indicators(df)
        
        if df_with_indicators is None:
            return jsonify({
                "status": "error",
                "message": "Erreur dans le calcul des indicateurs",
                "data_shape": df.shape if df is not None else None
            }), 500
            
        # Dernières valeurs des indicateurs
        last_row = df_with_indicators.iloc[-1]
        
        # Vérification des conditions de trading
        sma_condition = last_row['SMA20'] > last_row['SMA50']
        rsi_condition = last_row['RSI'] < 70
        price_condition = last_row['close'] > last_row['SMA20']
        
        # Vérification du signal
        signal = bot.check_trading_signals(df_with_indicators)
        
        # État du compte
        account_info = bot.check_account_status()
        
        # Vérification des positions ouvertes
        position_status = bot.check_trade_status()

        return jsonify({
            "status": "success",
            "bot_state": {
                "connection": connection_status,
                "symbol": bot.symbol,
                "timeframe": bot.timeframe,
                "position_open": bot.position_open,
                "current_order_id": bot.current_order_id
            },
            "market_data": {
                "last_price": float(last_row['close']),
                "sma20": float(last_row['SMA20']),
                "sma50": float(last_row['SMA50']),
                "rsi": float(last_row['RSI'])
            },
            "trading_conditions": {
                "sma_condition": str(sma_condition),  # Conversion en string
                "rsi_condition": str(rsi_condition),  # Conversion en string
                "price_condition": str(price_condition),  # Conversion en string
                "signal_generated": str(signal is not None),  # Conversion en string
                "signal_type": signal
            },
            "account_status": account_info,
            "position_status": position_status,
            "data_info": {
                "total_periods": len(df),
                "last_update": df.index[-1].strftime('%Y-%m-%d %H:%M:%S') if not df.empty else None
            }
        })
        
    except Exception as e:
        logger.error(f"Erreur dans debug_bot: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route("/force_trade", methods=['GET'])
def force_trade():
    global bot
    if not bot:
        init_bot_if_needed()
        
    try:
        logger.info("🔥 FORÇAGE D'ORDRE MANUEL VIA /force_trade")
        # Vérification explicite de la connexion
        if not bot.check_connection():
            return jsonify({"error": "Bot non connecté"}), 500
            
        # Vérifie s'il y a des positions ouvertes
        if bot.check_trade_status():
            return jsonify({"error": "Position déjà ouverte"}), 400
            
        # Force un ordre d'achat
        result = bot.execute_trade("BUY")
        logger.info(f"Résultat de l'ordre forcé via API: {result}")
        
        return jsonify({
            "success": result,
            "message": "Ordre forcé exécuté"
        })
    except Exception as e:
        logger.error(f"Exception lors du forçage d'ordre: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/sync_status", methods=['GET'])
def sync_status():
    global bot
    if not bot:
        init_bot_if_needed()
        
    try:
        has_positions = bot.check_trade_status()
        return jsonify({
            "success": True,
            "position_open": has_positions,
            "message": "État synchronisé",
            "previous_state": bot.position_open
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    try:
        if init_bot_if_needed():
            logger.info("Bot initialisé avec succès, démarrage du thread de trading...")
            trading_thread = Thread(target=run_trading_thread, daemon=True)
            trading_thread.start()
            logger.info("Thread de trading démarré avec succès")
        else:
            logger.error("Échec de l'initialisation du bot")
    except Exception as e:
        logger.error(f"Erreur lors du démarrage: {str(e)}")
        
    # Démarre le serveur Flask
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
