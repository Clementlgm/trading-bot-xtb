from flask import Flask, jsonify
from flask_cors import CORS
import os
import logging
import time
import json
from xapi.client import Client
from xapi.streaming import Streaming
from threading import Thread, Lock
import google.cloud.logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler

# Configuration du logging
client = google.cloud.logging.Client()
client.setup_logging()

def setup_logger():
    logger = logging.getLogger('trading_bot')
    logger.setLevel(logging.DEBUG)
    
    # Handler pour Cloud Logging
    handler = RotatingFileHandler(
        'trading.log',
        maxBytes=10000000,
        backupCount=5
    )
    
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger

logger = setup_logger()

app = Flask(__name__)
CORS(app)

class XTBTradingBot:
    def __init__(self, symbol='EURUSD', timeframe='1m'):
        self.userId = os.getenv('XTB_USER_ID')
        self.password = os.getenv('XTB_PASSWORD')
        self.symbol = symbol
        self.timeframe = timeframe
        self.client = None
        self.streaming = None
        self.active_positions = set()  # Ensemble pour stocker les IDs des positions actives
        self.last_reconnect = time.time()
        self.reconnect_interval = 60  # Reconnexion toutes les minutes

    def connect(self):
        try:
            logger.info(f"🔄 Tentative de connexion à XTB - UserID: {self.userId}")
            self.client = Client()
            self.client.connect()
            response = self.client.login(self.userId, self.password)
            
            if response.get('status') == True:
                self.streaming = Streaming(self.client)
                logger.info("✅ Connecté à XTB avec succès")
                self.last_reconnect = time.time()
                return True
            else:
                logger.error(f"❌ Échec de connexion: {response.get('errorDescr', 'Erreur inconnue')}")
                return False
        except Exception as e:
            logger.error(f"❌ Erreur de connexion: {str(e)}")
            return False

    def check_connection(self):
        """Vérifie et renouvelle la connexion si nécessaire"""
        current_time = time.time()
        if current_time - self.last_reconnect > self.reconnect_interval:
            logger.info("🔄 Renouvellement de la connexion...")
            try:
                self.disconnect()
            except:
                pass
            return self.connect()
        
        try:
            response = self.client.commandExecute("ping")
            if not response or not response.get('status'):
                logger.warning("Ping échoué, tentative de reconnexion")
                return self.connect()
            return True
        except Exception as e:
            logger.error(f"Erreur de connexion: {str(e)}")
            return self.connect()

    def disconnect(self):
        try:
            if self.streaming:
                self.streaming.disconnect()
            if self.client:
                self.client.disconnect()
        except Exception as e:
            logger.error(f"Erreur lors de la déconnexion: {str(e)}")
        finally:
            self.streaming = None
            self.client = None

    def get_active_positions(self):
        """Récupère toutes les positions actuellement ouvertes"""
        try:
            if not self.check_connection():
                return False

            cmd = {
                "command": "getTrades",
                "arguments": {
                    "openedOnly": True
                }
            }
            response = self.client.commandExecute(cmd["command"], cmd["arguments"])
            
            if response and 'returnData' in response:
                self.active_positions = {
                    str(trade['order']) 
                    for trade in response['returnData'] 
                    if trade.get('symbol') == self.symbol
                }
                
                if self.active_positions:
                    logger.info(f"📊 Positions actives trouvées: {len(self.active_positions)}")
                return len(self.active_positions) > 0
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de la vérification des positions: {str(e)}")
            return False

    def get_historical_data(self, limit=100):
        try:
            if not self.check_connection():
                return None

            end = int(time.time() * 1000)
            start = end - (limit * 3600 * 1000)
            
            command = {
                "command": "getChartRangeRequest",
                "arguments": {
                    "info": {
                        "symbol": self.symbol,
                        "period": 1,
                        "start": start,
                        "end": end
                    }
                }
            }
            
            logger.info(f"Demande données historiques: {json.dumps(command, indent=2)}")
            response = self.client.commandExecute(command["command"], command["arguments"])
            
            if isinstance(response, dict) and 'returnData' in response:
                data = response['returnData']
                if 'rateInfos' in data and len(data['rateInfos']) > 0:
                    df = pd.DataFrame(data['rateInfos'])
                    for col in ['open', 'high', 'low', 'close']:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                    df['timestamp'] = pd.to_datetime(df['ctm'], unit='ms')
                    
                    logger.info(f"Premier prix: {df['close'].iloc[0]}")
                    logger.info(f"Dernier prix: {df['close'].iloc[-1]}")
                    
                    return df.sort_values('timestamp')
            
            logger.error("Pas de données historiques reçues")
            return None
                    
        except Exception as e:
            logger.error(f"❌ Erreur dans get_historical_data: {str(e)}")
            return None

    def calculate_indicators(self, df):
        try:
            df = df.copy()
            df['SMA20'] = df['close'].rolling(window=20).mean()
            df['SMA50'] = df['close'].rolling(window=50).mean()
            
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            return df
        except Exception as e:
            logger.error(f"❌ Erreur lors du calcul des indicateurs: {str(e)}")
            return None

    def check_trading_signals(self, df):
        if len(df) < 50:
            logger.info("⚠️ Pas assez de données pour générer des signaux")
            return None
                
        last_row = df.iloc[-1]
        
        logger.info(f"""
        Conditions actuelles:
        - SMA20: {last_row['SMA20']} > SMA50: {last_row['SMA50']} = {last_row['SMA20'] > last_row['SMA50']}
        - RSI: {last_row['RSI']} < 70 = {last_row['RSI'] < 70}
        - Prix: {last_row['close']} > SMA20: {last_row['SMA20']} = {last_row['close'] > last_row['SMA20']}
        """)
        
        buy_signal = (
            last_row['SMA20'] > last_row['SMA50'] and
            last_row['RSI'] < 70 and
            last_row['close'] > last_row['SMA20']
        )
        
        sell_signal = (
            last_row['SMA20'] < last_row['SMA50'] and
            last_row['RSI'] > 30 and
            last_row['close'] < last_row['SMA20']
        )
        
        if buy_signal:
            logger.info("🔵 SIGNAL ACHAT DÉTECTÉ")
            return "BUY"
        elif sell_signal:
            logger.info("🔴 SIGNAL VENTE DÉTECTÉ")
            return "SELL"
            
        logger.info("Pas de signal")
        return None

    def get_symbol_info(self):
        try:
            cmd = {
                "command": "getSymbol",
                "arguments": {
                    "symbol": self.symbol
                }
            }
            response = self.client.commandExecute(cmd["command"], cmd["arguments"])
            return response.get('returnData', {}) if response else {}
        except Exception as e:
            logger.error(f"❌ Erreur lors de la récupération des infos du symbole: {str(e)}")
            return {}

    def execute_trade(self, signal):
        try:
            # Vérification stricte des positions ouvertes
            if self.get_active_positions():
                logger.info("⚠️ Position déjà ouverte. Pas de nouveau trade.")
                return False

            symbol_info = self.get_symbol_info()
            if not symbol_info:
                logger.error("❌ Impossible d'obtenir les informations du symbole")
                return False

            # Récupération des prix et propriétés du symbole
            ask_price = float(symbol_info.get('ask', 0))
            bid_price = float(symbol_info.get('bid', 0))
            lot_min = float(symbol_info.get('lotMin', 0.01))
            lot_step = float(symbol_info.get('lotStep', 0.01))
        
            if ask_price <= 0 or bid_price <= 0:
                logger.error("❌ Prix invalides reçus du serveur")
                return False

            # Calcul des niveaux
            if signal == "BUY":
                entry_price = ask_price
                sl_price = round(entry_price - 0.00100, 5)  # 10 pips en dessous
                tp_price = round(entry_price + 0.00150, 5)  # 15 pips au-dessus
            else:
                entry_price = bid_price
                sl_price = round(entry_price + 0.00100, 5)  # 10 pips au-dessus
                tp_price = round(entry_price - 0.00150, 5)  # 15 pips en dessous

            # Vérification des distances minimales
            min_distance = float(symbol_info.get('spreadRaw', 0)) * 2
            if abs(entry_price - sl_price) < min_distance:
                sl_price = entry_price - (min_distance * 1.5) if signal == "BUY" else entry_price + (min_distance * 1.5)
            if abs(entry_price - tp_price) < min_distance:
                tp_price = entry_price + (min_distance * 2) if signal == "BUY" else entry_price - (min_distance * 2)

            trade_cmd = {
                "command": "tradeTransaction",
                "arguments": {
                    "tradeTransInfo": {
                        "cmd": 0 if signal == "BUY" else 1,
                        "symbol": self.symbol,
                        "volume": lot_min,
                        "type": 0,
                        "price": entry_price,
                        "sl": sl_price,
                        "tp": tp_price
                    }
                }
            }

            logger.info(f"""🔍 Envoi de l'ordre:
            - Type: {signal}
            - Prix d'entrée: {entry_price}
            - Stop Loss: {sl_price}
            - Take Profit: {tp_price}""")

            response = self.client.commandExecute('tradeTransaction', trade_cmd['arguments'])
            logger.info(f"Réponse trade: {json.dumps(response, indent=2)}")
        
            if response.get('status'):
                new_order_id = str(response.get('returnData', {}).get('order', 0))
                self.active_positions.add(new_order_id)
                logger.info(f"""✅ Ordre exécuté avec succès:
                - Order ID: {new_order_id}
                - Type: {signal}
                - Prix: {entry_price}
                - SL: {sl_price}
                - TP: {tp_price}""")
                return True
            else:
                logger.error(f"❌ Erreur d'exécution: {response.get('errorDescr', 'Erreur inconnue')}")
                return False
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'exécution de l'ordre: {str(e)}")
            return False

    def run_strategy(self):
        logger.info(f"\n🤖 Démarrage du bot de trading sur {self.symbol}")
        
        try:
            # Vérification stricte des positions au début de chaque cycle
            has_positions = self.get_active_positions()
            
            if has_positions:
                logger.info(f"📊 En attente de clôture des positions actives...")
                return
            
            # Si aucune position n'est ouverte, recherche de nouvelles opportunités
            df = self.get_historical_data()
            if df is not None:
                df = self.calculate_indicators(df)
                if df is not None:
                    signal = self.check_trading_signals(df)
                    if signal:
                        logger.info(f"📊 Signal détecté: {signal}")
                        if self.execute_trade(signal):
                            logger.info("✅ Trade exécuté avec succès")
                        else:
                            logger.error("❌ Échec de l'exécution du trade")
                    else:
                        logger.info("⏳ Pas de signal pour le moment")
                else:
                    logger.error("Erreur dans le calcul des indicateurs")
            else:
                logger.error("Erreur dans la récupération des données")
                
        except Exception as e:
            logger.error(f"❌ Erreur dans la boucle de trading: {str(e)}")
            self.connect()

# Variables globales pour Flask
bot_lock = Lock()
bot = None
bot_status = {"is_running": False}

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
                else:
                    if init_bot_if_needed():
                        logger.info("Bot réinitialisé avec succès")
                    else:
                        logger.error("Échec de la réinitialisation")
                        time.sleep(30)
            time.sleep(60)  # Attente d'une minute entre chaque cycle
        except Exception as e:
            logger.error(f"Erreur dans run_trading: {str(e)}")
            time.sleep(30)

# Routes Flask pour l'API
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
        
        try:
            active_positions = bot.get_active_positions() if is_connected else False
            account_info = bot.client.commandExecute("getMarginLevel")['returnData'] if is_connected else None
            
            # Récupération des dernières données de marché
            df = bot.get_historical_data(limit=1) if is_connected else None
            last_price = float(df.iloc[-1]['close']) if df is not None and not df.empty else None
            
            return jsonify({
                "status": "connected" if is_connected else "disconnected",
                "bot_initialized": is_initialized,
                "is_running": bot_status["is_running"],
                "active_positions": active_positions,
                "last_price": last_price,
                "account_info": account_info
            })
        except Exception as e:
            logger.error(f"Erreur dans status: {str(e)}")
            return jsonify({
                "status": "error",
                "error": str(e)
            }), 500

@app.route("/trades")
def get_trades():
    with bot_lock:
        if not bot or not bot.check_connection():
            return jsonify({"error": "Bot non connecté"}), 400
            
        try:
            cmd = {
                "command": "getTrades",
                "arguments": {
                    "openedOnly": True
                }
            }
            response = bot.client.commandExecute(cmd["command"], cmd["arguments"])
            return jsonify(response.get('returnData', []))
        except Exception as e:
            logger.error(f"Erreur dans get_trades: {str(e)}")
            return jsonify({"error": str(e)}), 500

@app.route("/market_data")
def get_market_data():
    with bot_lock:
        if not bot or not bot.check_connection():
            return jsonify({"error": "Bot non connecté"}), 400
            
        try:
            df = bot.get_historical_data(limit=100)
            if df is not None:
                df = bot.calculate_indicators(df)
                if df is not None:
                    # Conversion du DataFrame en format JSON
                    data = df.tail(100).to_dict(orient='records')
                    return jsonify({
                        "data": data,
                        "last_update": time.strftime('%Y-%m-%d %H:%M:%S')
                    })
            return jsonify({"error": "Impossible de récupérer les données"}), 500
        except Exception as e:
            logger.error(f"Erreur dans get_market_data: {str(e)}")
            return jsonify({"error": str(e)}), 500

@app.route("/test_trade", methods=['GET'])
def test_trade():
    with bot_lock:
        if not bot or not bot.check_connection():
            return jsonify({"error": "Bot non connecté"}), 400
            
        try:
            # Vérification des positions ouvertes
            if bot.get_active_positions():
                return jsonify({
                    "success": False,
                    "message": "Une position est déjà ouverte"
                }), 400

            # Récupération des données de marché
            df = bot.get_historical_data()
            if df is not None:
                df = bot.calculate_indicators(df)
                if df is not None:
                    signal = bot.check_trading_signals(df)
                    if signal:
                        success = bot.execute_trade(signal)
                        return jsonify({
                            "success": success,
                            "signal": signal,
                            "message": "Trade test exécuté" if success else "Échec de l'exécution"
                        })
                    else:
                        return jsonify({
                            "success": False,
                            "message": "Pas de signal de trading détecté"
                        })
            return jsonify({
                "success": False,
                "message": "Impossible de récupérer les données de marché"
            }), 500
        except Exception as e:
            logger.error(f"Erreur dans test_trade: {str(e)}")
            return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Démarre le thread de trading
    try:
        if init_bot_if_needed():
            trading_thread = Thread(target=run_trading, daemon=True)
            trading_thread.start()
            logger.info("Thread de trading démarré")
    except Exception as e:
        logger.error(f"Erreur au démarrage: {str(e)}")

    # Démarre le serveur Flask
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
