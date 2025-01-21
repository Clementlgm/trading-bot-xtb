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

    def connect(self):
    try:
        logging.info("🔄 Tentative de connexion à XTB...")
        self.client = Client()
        self.client.connect()
        response = self.client.login(self.userId, self.password)
        
        if response.get('status') == True:
            logging.info("✅ Connecté à XTB avec succès")
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
            # Log modifié pour éviter les problèmes de formatage
            log_msg = "📊 État du compte - "
            log_msg += f"Balance: {margin_data.get('balance', 0)}, "
            log_msg += f"Equity: {margin_data.get('equity', 0)}, "
            log_msg += f"Margin Free: {margin_data.get('margin_free', 0)}"
            logging.info(log_msg)
            return margin_data
        return None
    except Exception as e:
        logging.error(f"❌ Erreur lors de la vérification du compte: {str(e)}")
        return None

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
            
            # S'assurer que le volume est au moins le minimum requis
            position_size = max(position_size, self.min_volume)
            position_size = round(position_size, 2)  # Arrondir à 2 décimales
            
            logging.info(f"""📈 Calcul du volume:
            - Balance: {balance}
            - Risk amount: {risk_amount}
            - Position size: {position_size}""")
            
            return position_size
            
        except Exception as e:
            logging.error(f"❌ Erreur dans le calcul du volume: {str(e)}")
            return self.min_volume

    def execute_trade

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

    def check_trade_execution(self, response):
        """Vérifie si l'ordre a été correctement exécuté"""
        try:
            if not response.get('status'):
                return False
                
            order_id = response.get('returnData', {}).get('order')
            if not order_id:
                return False
                
            # Attendre un peu pour être sûr que l'ordre est dans le système
            time.sleep(1)
            
            # Vérifier le statut de l'ordre
            cmd = {
                "command": "tradeTransactionStatus",
                "arguments": {
                    "order": order_id
                }
            }
            status_response = self.client.commandExecute(cmd["command"], cmd["arguments"])
            
            if status_response and status_response.get('returnData', {}).get('requestStatus') == 3:
                return True
                
            return False
            
        except Exception as e:
            logging.error(f"❌ Erreur lors de la vérification de l'exécution: {str(e)}")
            return False

    def get_historical_data(self, limit=100):
        try:
            if not self.check_connection():
                return None

            current_time = int(time.time())
            period_start = current_time - (limit * 3600)
            
            command = {
                'info': {
                    'symbol': self.symbol,
                    'period': 1,
                    'start': period_start * 1000,
                }
            }
            
            response = self.client.commandExecute('getChartLastRequest', command)
            
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
        try:
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

    def check_trading_signals(self, df):
        if len(df) < 50:
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
        else:
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
        try:
            if not signal:
                return

            if self.position_open:
                if not self.check_trade_status():
                    self.position_open = False
                    self.current_order_id = None
                else:
                    return

            symbol_info = self.get_symbol_info()
            if not symbol_info:
                logging.error("❌ Impossible d'obtenir les informations du symbole")
                return

            ask_price = float(symbol_info.get('ask', 0))
            bid_price = float(symbol_info.get('bid', 0))
            
            if ask_price <= 0 or bid_price <= 0:
                logging.error("❌ Prix invalides reçus du serveur")
                return

            # Configuration du trade avec SL et TP
            if signal == "BUY":
                entry_price = ask_price
                sl_price = round(entry_price - 0.00100, 5)  # 10 pips en dessous
                tp_price = round(entry_price + 0.00150, 5)  # 15 pips au-dessus
            else:  # SELL
                entry_price = bid_price
                sl_price = round(entry_price + 0.00100, 5)  # 10 pips au-dessus
                tp_price = round(entry_price - 0.00150, 5)  # 15 pips en dessous

            trade_cmd = {
                "command": "tradeTransaction",
                "arguments": {
                    "tradeTransInfo": {
                        "cmd": 0 if signal == "BUY" else 1,
                        "symbol": self.symbol,
                        "volume": 0.01,
                        "type": 0,
                        "price": entry_price,
                        "sl": sl_price,
                        "tp": tp_price
                    }
                }
            }

            logging.info(f"""🔍 Envoi de l'ordre:
            - Type: {signal}
            - Prix d'entrée: {entry_price}
            - Stop Loss: {sl_price}
            - Take Profit: {tp_price}""")

            response = self.client.commandExecute('tradeTransaction', trade_cmd['arguments'])
            
            if response.get('status'):
                self.current_order_id = response.get('returnData', {}).get('order', 0)
                logging.info(f"""✅ Ordre exécuté avec succès:
                - Order ID: {self.current_order_id}
                - Type: {signal}
                - Prix: {entry_price}
                - SL: {sl_price}
                - TP: {tp_price}""")
                self.position_open = True
            else:
                logging.error(f"❌ Erreur d'exécution: {response.get('errorDescr', 'Erreur inconnue')}")
                
        except Exception as e:
            logging.error(f"❌ Erreur lors de l'exécution de l'ordre: {str(e)}")

    def run_strategy(self):
        logging.info(f"🤖 Démarrage du bot de trading sur {self.symbol}")
        
        while True:
            try:
                # Vérification des positions ouvertes
                if self.position_open:
                    if not self.check_trade_status():
                        logging.info("🔄 Position fermée, recherche de nouvelles opportunités...")
                        self.position_open = False
                        self.current_order_id = None

                # Analyse du marché et trading
                df = self.get_historical_data()
                if df is not None:
                    df = self.calculate_indicators(df)
                    if df is not None:
                        signal = self.check_trading_signals(df)
                        if signal:
                            logging.info(f"📊 Signal détecté: {signal}")
                            self.execute_trade(signal)
                
                time.sleep(60)  # Attente d'1 minute
                
            except Exception as e:
                logging.error(f"❌ Erreur dans la boucle de trading: {str(e)}")
                time.sleep(30)
                self.connect()

if __name__ == "__main__":
    while True:
        try:
            bot = XTBTradingBot(symbol='BITCOIN', timeframe='1h')
            if bot.connect():
                bot.run_strategy()
            else:
                logging.info("⏳ Nouvelle tentative dans 60 secondes...")
                time.sleep(60)
        except KeyboardInterrupt:
            logging.info("⛔ Arrêt du bot demandé par l'utilisateur")
            break
        except Exception as e:
            logging.error(f"❌ Erreur fatale: {str(e)}")
            logging.info("⏳ Redémarrage dans 60 secondes...")
            time.sleep(60)
