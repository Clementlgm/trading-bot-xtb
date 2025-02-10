import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import json
from xapi.client import Client
from xapi.streaming import Streaming

class XTBTradingBot:
    def __init__(self, symbol='EURUSD', timeframe='1m'):
        self.userId = "17498367"
        self.password = "Java090214&Clement06032005*"
        self.symbol = symbol
        self.timeframe = timeframe
        self.client = None
        self.streaming = None
        self.active_positions = set()  # Ensemble pour stocker les IDs des positions actives
        self.last_reconnect = time.time()
        self.reconnect_interval = 60  # Reconnexion toutes les minutes
        
    def connect(self):
        try:
            self.client = Client()
            self.client.connect()
            response = self.client.login(self.userId, self.password)
            
            if response.get('status') == True:
                self.streaming = Streaming(self.client)
                print("✅ Connecté à XTB avec succès")
                self.last_reconnect = time.time()
                return True
            else:
                print(f"❌ Échec de connexion: {response.get('errorDescr', 'Erreur inconnue')}")
                return False
        except Exception as e:
            print(f"❌ Erreur de connexion: {str(e)}")
            return False

    def check_connection(self):
        """Vérifie et renouvelle la connexion si nécessaire"""
        current_time = time.time()
        if current_time - self.last_reconnect > self.reconnect_interval:
            print("🔄 Renouvellement de la connexion...")
            try:
                self.client.disconnect()
            except:
                pass
            return self.connect()
        return True

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
                # Mise à jour de l'ensemble des positions actives
                self.active_positions = {
                    str(trade['order']) 
                    for trade in response['returnData'] 
                    if trade.get('symbol') == self.symbol
                }
                
                if self.active_positions:
                    print(f"📊 Positions actives trouvées: {len(self.active_positions)}")
                return len(self.active_positions) > 0
            
            return False
            
        except Exception as e:
            print(f"❌ Erreur lors de la vérification des positions: {str(e)}")
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
            print(f"❌ Erreur dans get_historical_data: {str(e)}")
            return None

    def calculate_indicators(self, df):
        try:
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
            print(f"❌ Erreur lors du calcul des indicateurs: {str(e)}")
            return None

    def check_trading_signals(self, df):
        if len(df) < 50:
            print("⚠️ Pas assez de données pour générer des signaux")
            return None
            
        last_row = df.iloc[-1]
        
        # Vérification des signaux d'achat/vente
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
            print(f"❌ Erreur lors de la récupération des infos du symbole: {str(e)}")
            return {}

    def execute_trade(self, signal):
        try:
            # Vérification stricte des positions ouvertes
            if self.get_active_positions():
                print("⚠️ Position déjà ouverte. Pas de nouveau trade.")
                return

            symbol_info = self.get_symbol_info()
            if not symbol_info:
                print("❌ Impossible d'obtenir les informations du symbole")
                return

            # Récupération des prix et propriétés du symbole
            ask_price = float(symbol_info.get('ask', 0))
            bid_price = float(symbol_info.get('bid', 0))
            lot_min = float(symbol_info.get('lotMin', 0.01))
            lot_step = float(symbol_info.get('lotStep', 0.01))
        
            if ask_price <= 0 or bid_price <= 0:
                print("❌ Prix invalides reçus du serveur")
                return

            # Calcul de la valeur du pip
            precision = len(str(symbol_info.get('pipsPrecision', 5)))
            pip_value = 1 / (10 ** precision)

            # Configuration des SL et TP
            if signal == "BUY":
                entry_price = ask_price
                sl_price = round(entry_price - 0.00100, 5)  # 10 pips en dessous
                tp_price = round(entry_price + 0.00150, 5)  # 20 pips au-dessus
            else:
                entry_price = bid_price
                sl_price = round(entry_price + 0.00100, 5)  # 10 pips au-dessus
                tp_price = round(entry_price - 0.00150, 5)  # 20 pips en dessous

            # Vérification des distances minimales
            min_distance = float(symbol_info.get('spreadRaw', 0)) * 2
            if abs(entry_price - sl_price) < min_distance:
                sl_price = entry_price - (min_distance * 1.5) if signal == "BUY" else entry_price + (min_distance * 1.5)
            if abs(entry_price - tp_price) < min_distance:
                tp_price = entry_price + (min_distance * 2) if signal == "BUY" else entry_price - (min_distance * 2)

            # Préparation de l'ordre
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

            print(f"""🔍 Envoi de l'ordre:
            - Type: {signal}
            - Prix d'entrée: {entry_price}
            - Stop Loss: {sl_price}
            - Take Profit: {tp_price}""")

            response = self.client.commandExecute('tradeTransaction', trade_cmd['arguments'])
        
            if response.get('status'):
                new_order_id = str(response.get('returnData', {}).get('order', 0))
                self.active_positions.add(new_order_id)
                print(f"""✅ Ordre exécuté avec succès:
                - Order ID: {new_order_id}
                - Type: {signal}
                - Prix: {entry_price}
                - SL: {sl_price}
                - TP: {tp_price}""")
            else:
                print(f"❌ Erreur d'exécution: {response.get('errorDescr', 'Erreur inconnue')}")
            
        except Exception as e:
            print(f"❌ Erreur lors de l'exécution de l'ordre: {str(e)}")

    def run_strategy(self):
        print(f"\n🤖 Démarrage du bot de trading sur {self.symbol}")
        
        while True:
            try:
                # Vérification stricte des positions au début de chaque cycle
                has_positions = self.get_active_positions()
                
                if has_positions:
                    print(f"📊 En attente de clôture des positions actives...")
                    time.sleep(30)  # Attente plus courte quand des positions sont ouvertes
                    continue
                
                # Si aucune position n'est ouverte, recherche de nouvelles opportunités
                df = self.get_historical_data()
                if df is not None:
                    df = self.calculate_indicators(df)
                    if df is not None:
                        signal = self.check_trading_signals(df)
                        if signal:
                            print(f"📊 Signal détecté: {signal}")
                            self.execute_trade(signal)
                
                print("⏳ Attente de 1 minute...")
                time.sleep(60)
                
            except Exception as e:
                print(f"❌ Erreur dans la boucle de trading: {str(e)}")
                print("⏳ Attente de 30 secondes...")
                time.sleep(30)
                self.connect()

if __name__ == "__main__":
    while True:
        try:
            bot = XTBTradingBot(symbol='EURUSD', timeframe='1m')
            if bot.connect():
                bot.run_strategy()
            else:
                print("⏳ Nouvelle tentative dans 60 secondes...")
                time.sleep(60)
        except KeyboardInterrupt:
            print("\n⛔ Arrêt du bot demandé par l'utilisateur")
            break
        except Exception as e:
            print(f"❌ Erreur fatale: {str(e)}")
            print("⏳ Redémarrage dans 60 secondes...")
            time.sleep(60)
