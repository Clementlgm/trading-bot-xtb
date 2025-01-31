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
   def __init__(self, symbol='BITCOIN', timeframe='1h'):
       load_dotenv()
       self.userId = os.getenv('17373384') #XTB_USER_ID
       self.password = os.getenv('Java090214&Clement06032005*') #XTB_PASSWORD
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
       self.risk_percentage = 0.01

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

   def check_connection(self):
    try:
        if self.client is None:
            return self.connect()
        
        response = self.client.commandExecute("ping")
        return response and response.get('status')
    except Exception as e:
        logging.error(f"❌ Erreur de vérification de connexion: {str(e)}")
        return False

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

           period_start = int(time.time()) - (limit * 3600)
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
           
           response = self.client.commandExecute(command["command"], command["arguments"])
           
           if isinstance(response, dict) and 'returnData' in response:
               data = response['returnData']
               if 'rateInfos' in data and len(data['rateInfos']) > 0:
                   df = pd.DataFrame(data['rateInfos'])
                   df['timestamp'] = pd.to_datetime(df['ctm'], unit='ms')
                   return df.sort_values('timestamp')
           return None
       except Exception as e:
           logging.error(f"❌ Erreur dans get_historical_data: {str(e)}")
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
           return None
           
       last_row = df.iloc[-1]
       
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
       
       logging.info(f"🔍 Analyse - SMA20: {last_row['SMA20']}, SMA50: {last_row['SMA50']}, RSI: {last_row['RSI']}, Close: {last_row['close']}")
       
       if buy_signal:
           return "BUY"
       elif sell_signal:
           return "SELL"
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
           logging.error(f"❌ Erreur lors de la récupération des infos du symbole: {str(e)}")
           return {}

   def execute_trade(self, signal):
       if not signal or self.position_open:
           return

       symbol_info = self.get_symbol_info()
       if not symbol_info:
           logging.error("❌ Impossible d'obtenir les informations du symbole")
           return

       ask_price = float(symbol_info.get('ask', 0))
       bid_price = float(symbol_info.get('bid', 0))
       lot_min = float(symbol_info.get('lotMin', 0.01))

       if ask_price <= 0 or bid_price <= 0:
           logging.error("❌ Prix invalides reçus du serveur")
           return

       if signal == "BUY":
        entry_price = ask_price
        sl_price = entry_price - 500  # SL à $500 sous le prix d'entrée
        tp_price = entry_price + 1000  # TP à $1000 au-dessus du prix d'entrée
       else:  # SELL
        entry_price = bid_price
        sl_price = entry_price + 500  # SL à $500 au-dessus du prix d'entrée
        tp_price = entry_price - 1000  # TP à $1000 sous le prix d'entrée 

       trade_cmd = {
           "command": "tradeTransaction",
           "arguments": {
               "tradeTransInfo": {
                   "cmd": 0 if signal == "BUY" else 1,
                   "symbol": self.symbol,
                   "volume": lot_min,
                   "type": 0,
                   "price": entry_price,
                   "sl": round(sl_price, 2),
                   "tp": round(tp_price, 2)
               }
           }
       }

       response = self.client.commandExecute('tradeTransaction', trade_cmd['arguments'])
       if response.get('status'):
           self.current_order_id = response.get('returnData', {}).get('order', 0)
           self.position_open = True
           logging.info(f"✅ Trade exécuté: {signal}, Order ID: {self.current_order_id}")
       else:
           logging.error(f"❌ Échec de l'exécution du trade: {response}")

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
    logging.info(f"🤖 Bot trading {self.symbol}")
    
    while True:
        try:
            if not self.check_connection():
                logging.error("Connexion perdue, tentative de reconnexion...")
                if not self.connect():
                    time.sleep(30)
                    continue
                    
            # Vérifie les positions ouvertes
            if self.position_open:
                if not self.check_trade_status():
                    logging.info("Position fermée")
                    self.position_open = False
                    self.current_order_id = None

            # Analyse du marché
            df = self.get_historical_data()
            if df is not None:
                df = self.calculate_indicators(df)
                if df is not None:
                    signal = self.check_trading_signals(df)
                    if signal:
                        logging.info(f"Signal détecté: {signal}")
                        self.execute_trade(signal)
                        
            # Attente avant prochaine analyse
            time.sleep(60)
            
        except Exception as e:
            logging.error(f"Erreur dans run_strategy: {str(e)}")
            time.sleep(30)

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
        bot = XTBTradingBot(symbol='BITCOIN', timeframe='1h')
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
    init_bot()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))                

if __name__ == "__main__":
   while True:
       try:
           bot = XTBTradingBot(symbol='BITCOIN', timeframe='1h')
           if bot.connect():
               bot.run_strategy()
           else:
               logging.error("Échec de connexion, nouvelle tentative dans 60 secondes...")
               time.sleep(60)
       except Exception as e:
           logging.error(f"Erreur critique: {str(e)}")
           time.sleep(60)
