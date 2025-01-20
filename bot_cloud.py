import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import json
import os
from xapi.client import Client
from xapi.streaming import Streaming
import google.cloud.logging
import logging

# Configuration des logs pour Google Cloud
client = google.cloud.logging.Client()
client.setup_logging()

class XTBTradingBot:
    def __init__(self, symbol='BITCOIN', timeframe='1h'):
        self.userId = os.getenv('XTB_USER_ID')
        self.password = os.getenv('XTB_PASSWORD')
        self.symbol = symbol
        self.timeframe = timeframe
        self.client = None
        self.streaming = None
        self.position_open = False
        self.current_order_id = None
        self.last_reconnect = time.time()
        self.reconnect_interval = 60
        self.min_volume = 0.1  # Volume minimum pour Bitcoin
        self.risk_percentage = 0.02  # 2% de risk par trade

    def check_connection(self):
        """Vérifie l'état de la connexion et tente de se reconnecter si nécessaire"""
        try:
            # Vérifie si le client existe et est connecté
            if not self.client:
                logging.info("🔄 Client non initialisé, tentative de connexion...")
                return self.connect()
            
            # Essaie d'exécuter une commande simple pour tester la connexion
            cmd = {
                "command": "ping"
            }
            response = self.client.commandExecute(cmd)
            
            # Si la commande ping échoue, on tente de se reconnecter
            if not response or not response.get('status'):
                logging.warning("⚠️ Connexion perdue, tentative de reconnexion...")
                return self.connect()
            
            # La connexion est bonne
            return True
            
        except Exception as e:
            logging.error(f"❌ Erreur lors de la vérification de la connexion: {str(e)}")
            return self.connect()

    def connect(self):
        """Établit la connexion avec le serveur XTB"""
        try:
            if self.client:
                try:
                    self.client.disconnect()
                except:
                    pass
            
            self.client = Client()
            self.client.connect()
            response = self.client.login(self.userId, self.password)
            
            if response.get('status') == True:
                self.streaming = Streaming(self.client)
                logging.info("✅ Connecté à XTB avec succès")
                self.last_reconnect = time.time()
                # Vérification immédiate du compte après connexion
                self.check_account_status()
                return True
            else:
                logging.error(f"❌ Échec de connexion: {response.get('errorDescr', 'Erreur inconnue')}")
                return False
        except Exception as e:
            logging.error(f"❌ Erreur de connexion: {str(e)}")
            return False

    def check_account_status(self):
        """Vérifie l'état du compte et les paramètres de trading"""
        try:
            if not self.check_connection():
                return None

            cmd = {
                "command": "getMarginLevel"
            }
            response = self.client.commandExecute(cmd)
            if response and 'returnData' in response:
                margin_data = response['returnData']
                logging.info(f"""📊 État du compte:
                - Balance: {margin_data.get('balance', 0)}
                - Equity: {margin_data.get('equity', 0)}
                - Margin Free: {margin_data.get('margin_free', 0)}""")
                return margin_data
            return None
        except Exception as e:
            logging.error(f"❌ Erreur lors de la vérification du compte: {str(e)}")
            return None

    def get_historical_data(self, limit=100):
        """Récupère les données historiques"""
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
            
            if isinstance(response, dict) and 'returnData' in response:
                data = response['returnData']
                if 'rateInfos' in data and len(data['rateInfos']) > 0:
                    df = pd.DataFrame(data['rateInfos'])
                    df['timestamp'] = pd.to_datetime(df['ctm'], unit='ms')
                    df = df.sort_values('timestamp')
                    return df
            return None
                    
        except Exception as e:
            logging.error(f"❌ Erreur dans get_historical_data: {str(e)}")
            return None

    def calculate_indicators(self, df):
        """Calcule les indicateurs techniques"""
        try:
            if df is None or len(df) < 50:
                return None
                
            # Conversion des colonnes en numérique
            for col in ['open', 'high', 'low', 'close']:
                df[col] = pd.to_numeric(df[col])
                
            # Calcul des moyennes mobiles
            df['SMA20'] = df['close'].rolling(window=20).mean()
            df['SMA50'] = df['close'].rolling(window=50).mean()
            
            # Calcul du RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            return df
        except Exception as e:
            logging.error(f"❌ Erreur lors du calcul des indicateurs: {str(e)}")
            return None

    def calculate_atr(self, df, period=14):
        """Calcule l'Average True Range pour la gestion dynamique des SL/TP"""
        try:
            if df is None or len(df) < period:
                return 0.001  # Valeur par défaut si pas assez de données
                
            df = df.copy()
            df['high'] = pd.to_numeric(df['high'])
            df['low'] = pd.to_numeric(df['low'])
            df['close'] = pd.to_numeric(df['close'])
            
            df['tr1'] = abs(df['high'] - df['low'])
            df['tr2'] = abs(df['high'] - df['close'].shift())
            df['tr3'] = abs(df['low'] - df['close'].shift())
            
            df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
            return df['tr'].rolling(period).mean().iloc[-1]
            
        except Exception as e:
            logging.error(f"❌ Erreur dans le calcul de l'ATR: {str(e)}")
            return 0.001

    def calculate_position_size(self, entry_price, stop_loss):
        """Calcule la taille de position basée sur le risk management"""
        try:
            account_info = self.check_account_status()
            if not account_info:
                return self.min_volume
            
            balance = account_info.get('balance', 0)
            risk_amount = balance * self.risk_percentage
            
            # Calcul du risk par pip
            pip_risk = abs(entry_price - stop_loss)
            if pip_risk == 0:
                return self.min_volume
                
            # Calcul du volume basé sur le risk
            position_size = risk_amount / pip_risk
            position_size = max(position_size, self.min_volume)
            position_size = round(position_size, 2)
            
            logging.info(f"""📈 Calcul du volume:
            - Balance: {balance}
            - Risk amount: {risk_amount}
            - Position size: {position_size}""")
            
            return position_size
            
        except Exception as e:
            logging.error(f"❌ Erreur dans le calcul du volume: {str(e)}")
            return self.min_volume

    def check_trade_status(self):
        """Vérifie le statut d'un trade ouvert"""
        try:
            if not self.check_connection() or not self.current_order_id:
                return False

            cmd = {
                "command": "tradeTransactionStatus",
                "arguments": {
                    "order": self.current_order_id
                }
            }
            response = self.client.commandExecute(cmd["command"], cmd["arguments"])
            
            if response and response.get('returnData', {}).get('requestStatus') == 3:
                return True
            return False
            
        except Exception as e:
            logging.error(f"❌ Erreur lors de la vérification du trade: {str(e)}")
            return False

    def check_trading_signals(self, df):
        """Analyse les signaux de trading"""
        try:
            if df is None or len(df) < 50:
                return None
                
            last_row = df.iloc[-1]
            
            # Vérification des conditions d'achat
            buy_signal = (
                last_row['SMA20'] > last_row['SMA50'] and
                last_row['RSI'] < 70 and
                last_row['close'] > last_row['SMA20']
            )
            
            # Vérification des conditions de vente
            sell_signal = (
                last_row['SMA20'] < last_row['SMA50'] and
                last_row['RSI'] > 30 and
                last_row['close'] < last_row['SMA20']
            )
            
            if buy_signal:
                return "BUY"
            elif sell_signal:
                return "SELL"
            return None
            
        except Exception as e:
            logging.error(f"❌ Erreur lors de l'analyse des signaux: {str(e)}")
            return None

    def get_symbol_info(self):
        """Récupère les informations du symbole"""
        try:
            if not self.check_connection():
                return None
                
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
        """Exécute un ordre de trading"""
        try:
            if not signal or not self.check_connection():
                return

            if self.position_open:
                if not self.check_trade_status():
                    self.position_open = False
                    self.current_order_id = None
                else:
                    return

            symbol_info = self.get_symbol_info()
            if not symbol_info:
                return

            ask_price = float(symbol_info.get('ask', 0))
            bid_price = float(symbol_info.get('bid', 0))
            
            if ask_price <= 0 or bid_price <= 0:
                return

            # Calcul dynamique des niveaux de SL et TP basé sur la volatilité
            atr = self.calculate_atr(self.get_historical_data())
            sl_pips = atr * 1.5
            tp_pips = atr * 2.0

            if signal == "BUY":
                entry_price = ask_price
                sl_price = round(entry_price - sl_pips, 5)
                tp_price = round(entry_price + tp_pips, 5)
            else:
                entry_price = bid_price
                sl_price = round(entry_price + sl_pips, 5)
                tp_price = round(entry_price - tp_pips, 5)

            volume = self.calculate_position_size(entry_price, sl_price)

            trade_cmd = {
                "command": "tradeTransaction",
                "arguments": {
                    "tradeTransInfo": {
                        "cmd": 0 if signal == "BUY" else 1,
                        "symbol": self.symbol,
                        "volume": volume,
                        "type": 0,
                        "price": entry_price,
                        "sl": sl_price,
                        "tp": tp_price
                    }
                }
            }

            logging.info(f"""🔍 Envoi de l'ordre:
            - Type: {signal}
            - Volume: {volume}
            - Prix d'entrée: {entry_price}
            - Stop Loss: {sl_price}
            - Take Profit: {tp_price}""")

            response = self.client.commandExecute(trade_cmd["command"], trade_cmd["arguments"])
            
            if response.get('status'):
                self.current_order_id = response.get('returnData', {}).get('order', 0)
                logging.info(f"✅ Ordre exécuté avec succès - Order ID: {self.current_order_id}")
                self.position_open = True
            else:
                logging.error(f"❌ Erreur d'exécution: {response.get('errorDescr', 'Erreur inconnue')}")
                
        except Exception as e:
            logging.error(f"❌ Erreur lors de l'exécution de l'ordre: {str(e)}")

    def run_strategy(self):
        """Exécute la stratégie de trading en continu"""
        logging.info(f"🤖 Démarrage du bot de trading sur {self.symbol}")
        
        while True:
            try:
                if not self.check_connection():
                    time.sleep(30)
                    continue

                # Vérification des positions ouvertes
                if self.position_open:
                    if not self.check_trade_status():
                        logging.info("🔄 Position fermée, recherche de nouvelles opportunités...")
                        self.position_open = False
                        self.current_order_id = None

                # Analyse du marché et trading
                df = self
