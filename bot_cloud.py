from xapi.client import Client
from xapi.streaming import Streaming
from dotenv import load_dotenv
import pandas as pd
import numpy as np
import logging
import time
import json
import os

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading.log'),
        logging.StreamHandler()
    ]
)

# Configuration logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger('trading_bot')

try:
   import google.cloud.logging
   client = google.cloud.logging.Client()
   client.setup_logging()
except:
   pass

load_dotenv()

class XTBTradingBot:
   def __init__(self, symbol='BITCOIN', timeframe='1m'):
       load_dotenv()
       self.userId = os.getenv('XTB_USER_ID') 
       self.password = os.getenv('XTB_PASSWORD') 
       if not self.userId or not self.password:
           raise ValueError("XTB_USER_ID et XTB_PASSWORD doivent être définis dans .env")
       self.symbol = symbol
       self.timeframe = timeframe
       self.client = None
       self.streaming = None
       self.position_open = False
       self.current_order_id = None
       self.last_reconnect = time.time()
       self.reconnect_interval = 60
       self.min_volume = 0.001
       self.risk_percentage = 0.02

   def connect(self):
    try:
        logging.info(f"🔄 Tentative de connexion à XTB - UserID: {self.userId}")
        self.client = Client()
        self.client.connect()
        response = self.client.login(self.userId, self.password)
        
        if response.get('status') == True:
            self.streaming = Streaming(self.client)
            logging.info("✅ Connecté à XTB avec succès")
            return True
        else:
            logging.error(f"❌ Échec de connexion - Détails: {response}")
            return False
    except Exception as e:
        logging.error(f"❌ Erreur de connexion: {str(e)}")
        return False

   #def check_connection(self):
    #try:
        #if self.client is None:
         #   return self.connect()
        
        #response = self.client.commandExecute("ping")
        #return response and response.get('status')
    #except Exception as e:
        #logging.error(f"❌ Erreur de vérification de connexion: {str(e)}")
        #return False

   def check_connection(self):
    try:
        if self.client is None:
            return self.connect()
        
        # Ajout d'un timeout et gestion de la reconnexion
        current_time = time.time()
        if current_time - self.last_reconnect >= self.reconnect_interval:
            logger.info("Renouvellement préventif de la connexion")
            self.disconnect()
            time.sleep(1)
            success = self.connect()
            if success:
                self.last_reconnect = current_time
            return success

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
        
   def check_account_status(self):
    try:
        cmd = {"command": "getMarginLevel"}
        response = self.client.commandExecute(cmd["command"])
        if response and 'returnData' in response:
            margin_data = response['returnData']
            return margin_data
        return None
    except Exception as e:
        logging.error(f"❌ Erreur lors de la vérification du compte: {str(e)}")
        return None

   def get_historical_data(self, limit=100):
    try:
        if not self.check_connection():
            return None

        current_time = int(time.time())
        period_start = current_time - (limit * 3600)
        
        command = {
            'command': 'getChartLastRequest',
            'arguments': {
                'info': {
                    'symbol': self.symbol,
                    'period': 1,
                    'start': period_start * 1000,
                }
            }
        }
        
        response = self.client.commandExecute(command['command'], command['arguments'])
        logger.info(f"Réponse données historiques: {json.dumps(response, indent=2)}")
        
        if isinstance(response, dict) and 'returnData' in response:
            data = response['returnData']
            if 'rateInfos' in data and len(data['rateInfos']) > 0:
                df = pd.DataFrame(data['rateInfos'])
                for col in ['open', 'high', 'low', 'close']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                df['timestamp'] = pd.to_datetime(df['ctm'], unit='ms')
                return df.sort_values('timestamp')
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
           logging.error(f"❌ Erreur lors du calcul des indicateurs: {str(e)}")
           return None

   def check_trading_signals(self, df):
    if len(df) < 50:
        logger.info("⚠️ Pas assez de données")
        return None
            
    last_row = df.iloc[-1]
    
    # Ajout de logging détaillé
    logger.info(f"""
    Analyse des conditions:
    - SMA20 vs SMA50: {last_row['SMA20']} vs {last_row['SMA50']} (SMA20 > SMA50 = {last_row['SMA20'] > last_row['SMA50']})
    - RSI: {last_row['RSI']} (< 70 = {last_row['RSI'] < 70})
    - Prix vs SMA20: {last_row['close']} vs {last_row['SMA20']} (Prix > SMA20 = {last_row['close'] > last_row['SMA20']})
    """)
    
    buy_signal = (
        last_row['SMA20'] > last_row['SMA50'] and  # tendance haussière
        last_row['RSI'] < 70 and                   # pas de surachat
        last_row['close'] > last_row['SMA20']      # prix > SMA20
    )
    
    sell_signal = (
        last_row['SMA20'] < last_row['SMA50'] and  # tendance baissière
        last_row['RSI'] > 30 and                   # pas de survente
        last_row['close'] < last_row['SMA20']      # prix < SMA20
    )
    
    logger.info(f"Signal détecté - Buy: {buy_signal}, Sell: {sell_signal}")
    
    if buy_signal:
        logger.info("🔵 SIGNAL BUY")
        return "BUY"
    elif sell_signal:
        logger.info("🔴 SIGNAL SELL")
        return "SELL"
        
    return None

   def execute_trade(self, signal):
    if not self.check_connection():
        logger.error("Pas de connexion")
        return False
        
    try:
        symbol_info = self.get_symbol_info()
        ask_price = float(symbol_info.get('ask', 0))
        bid_price = float(symbol_info.get('bid', 0))
        lot_min = max(float(symbol_info.get('lotMin', 0.001)), 0.001)

        trade_cmd = {
            "command": "tradeTransaction",
            "arguments": {
                "tradeTransInfo": {
                    "cmd": 0 if signal == "BUY" else 1,
                    "customComment": "Bot Trade",
                    "expiration": 0,
                    "offset": 0,
                    "order": 0,
                    "price": ask_price if signal == "BUY" else bid_price,
                    "sl": round(ask_price * 0.985 if signal == "BUY" else bid_price * 1.01, 2),
                    "tp": round(ask_price * 1.02 if signal == "BUY" else bid_price * 0.985, 2),
                    "symbol": self.symbol,
                    "type": 0,
                    "volume": lot_min
                }
            }
        }

        logger.info(f"Envoi ordre: {json.dumps(trade_cmd, indent=2)}")
        response = self.client.commandExecute('tradeTransaction', trade_cmd['arguments'])
        logger.info(f"Réponse trade: {json.dumps(response, indent=2)}")
        
        if response and response.get('status'):
            self.position_open = True
            self.current_order_id = response.get('returnData', {}).get('order')
            return True
            
        return False
        
    except Exception as e:
        logger.error(f"Erreur execution trade: {str(e)}")
        return False

   def check_trade_status(self):
       try:
           if not self.current_order_id:
               return False
           
           cmd = {
               "command": "getTrades",
               "arguments": {
                   "openedOnly": True
               }
           }
           response = self.client.commandExecute(cmd["command"], cmd["arguments"])
       
           if not response or 'returnData' not in response:
               return False
           
           trades = response['returnData']
           return any(trade.get('order2') == self.current_order_id for trade in trades)
       
       except Exception as e:
           logging.error(f"❌ Erreur lors de la vérification du trade: {str(e)}")
           return False

   def run_strategy(self):
    logging.info(f"🤖 Bot trading {self.symbol} démarré")
    
    try:
        if not self.check_connection():
            logging.error("Connexion perdue, tentative de reconnexion...")
            if not self.connect():
                return
                
        # Récupération des données
        df = self.get_historical_data()
        if df is not None:
            logging.info(f"Données récupérées: {len(df)} périodes")
            
            # Analyse des données
            df = self.calculate_indicators(df)
            if df is not None:
                # Log des dernières valeurs
                last_row = df.iloc[-1]
                logging.info(f"""
                ===== État du marché =====
                Symbole: {self.symbol}
                Dernier prix: {last_row['close']}
                SMA20: {last_row['SMA20']}
                SMA50: {last_row['SMA50']}
                RSI: {last_row['RSI']}
                Position ouverte: {self.position_open}
                """)
                
                # Vérifie les positions ouvertes
                if self.position_open:
                    if not self.check_trade_status():
                        logging.info("🔄 Position fermée, prêt pour nouveau trade")
                        self.position_open = False
                        self.current_order_id = None
                        
                # Recherche de signaux uniquement si aucune position n'est ouverte
                if not self.position_open:
                    signal = self.check_trading_signals(df)
                    if signal:
                        logging.info(f"🎯 Signal détecté: {signal}")
                        if self.execute_trade(signal):
                            logging.info(f"✅ Trade exécuté avec succès: {signal}")
                        else:
                            logging.error("❌ Échec de l'exécution du trade")
                    else:
                        logging.info("⏳ Pas de signal pour le moment")
            else:
                logging.error("Erreur dans le calcul des indicateurs")
        else:
            logging.error("Erreur dans la récupération des données")
            
    except Exception as e:
        logging.error(f"Erreur critique dans run_strategy: {str(e)}")

from flask import Flask, jsonify
import os, logging
from bot_cloud import XTBTradingBot
from threading import Thread
import time

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
bot = None
trade_thread = None

def run_trading():
    while True:
        try:
            if bot and bot.client:
                bot.run_strategy()
            time.sleep(60)
        except Exception as e:
            logging.error(f"Error: {str(e)}")
            time.sleep(30)

def init_bot():
    global bot, trade_thread
    if not bot:
        bot = XTBTradingBot(symbol='BITCOIN', timeframe='1m')
        bot.connect()
        trade_thread = Thread(target=run_trading, daemon=True)
        trade_thread.start()

@app.route("/status", methods=['GET'])
def status():
    global bot
    if not bot:
        init_bot()
    return jsonify({
        "status": "connected" if bot and bot.client else "disconnected",
        "account_info": bot.check_account_status() if bot else None
    })

if __name__ == "__main__":
    bot = None
    while True:
        try:
            if bot is None or not bot.check_connection():
                bot = XTBTradingBot(symbol='BITCOIN', timeframe='1m')
                if not bot.connect():
                    logging.error("Échec de connexion, nouvelle tentative dans 60 secondes...")
                    time.sleep(60)
                    continue
            
            bot.run_strategy()
            # Attente avant la prochaine itération
            time.sleep(60)
            
        except Exception as e:
            logging.error(f"Erreur critique: {str(e)}")
            if bot:
                try:
                    bot.disconnect()
                except:
                    pass
                bot = None
            time.sleep(60)
