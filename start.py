from flask import Flask, jsonify
from flask_cors import CORS
from bot_cloud import XTBTradingBot
from threading import Thread, Lock
import logging
import time
import os

app = Flask(__name__)
CORS(app)

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('trading_bot')

# Variables globales avec verrou
bot_lock = Lock()
bot = None
last_check_time = time.time()
CHECK_INTERVAL = 60  # intervalle en secondes

def init_bot_if_needed():
    global bot
    with bot_lock:
        try:
            if bot is None:
                logger.info("Initialisation du bot...")
                user_id = os.getenv('XTB_USER_ID')
                password = os.getenv('XTB_PASSWORD')
                
                if not user_id or not password:
                    logger.error("Identifiants XTB manquants")
                    return False
                    
                bot = XTBTradingBot(symbol='EURUSD', timeframe='1m')
                return bot.connect()
            return True
        except Exception as e:
            logger.error(f"Erreur d'initialisation: {str(e)}")
            return False

def check_and_execute_strategy():
    global last_check_time
    current_time = time.time()
    
    # Vérifier si assez de temps s'est écoulé depuis la dernière vérification
    if current_time - last_check_time < CHECK_INTERVAL:
        return {"status": "waiting", "message": "Attente avant prochaine vérification"}
    
    with bot_lock:
        try:
            if not bot or not bot.check_connection():
                if not init_bot_if_needed():
                    return {"status": "error", "message": "Erreur de connexion"}
            
            # Vérifier les positions existantes
            has_positions = bot.get_active_positions()
            if has_positions:
                return {"status": "waiting", "message": "Positions actives en cours"}
            
            # Obtenir et analyser les données
            df = bot.get_historical_data()
            if df is not None:
                df = bot.calculate_indicators(df)
                if df is not None:
                    signal = bot.check_trading_signals(df)
                    if signal:
                        logger.info(f"Signal détecté: {signal}")
                        bot.execute_trade(signal)
                        return {"status": "success", "message": f"Trade exécuté: {signal}"}
            
            last_check_time = current_time
            return {"status": "no_signal", "message": "Pas de signal détecté"}
            
        except Exception as e:
            logger.error(f"Erreur dans la stratégie: {str(e)}")
            return {"status": "error", "message": str(e)}

@app.route("/execute_strategy", methods=['GET'])
def execute_strategy():
    result = check_and_execute_strategy()
    return jsonify(result)

@app.route("/test_trade", methods=['GET'])
def test_trade():
    if not init_bot_if_needed():
        return jsonify({"status": "error", "message": "Erreur d'initialisation du bot"}), 500
        
    with bot_lock:
        try:
            result = bot.execute_trade("BUY")
            return jsonify({
                "status": "success",
                "message": "Trade test exécuté",
                "result": result
            })
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
