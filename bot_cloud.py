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
   def __init__(self, symbol='EURUSD', timeframe='1h'):
       load_dotenv()
       self.userId = os.getenv('XTB_USER_ID') 
       self.password = os.getenv('XTB_PASSWORD') 
       if not self.userId or not self.password:
           raise ValueError("XTB_USER_ID et XTB_PASSWORD doivent être définis dans .env")
       self.symbol = symbol
       self.timeframe = timeframe
       self.client = None
       self.streaming = None
       self.active_positions = set()
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

        end = int(time.time() * 1000)
        start = end - (limit * 3600 * 1000)  # Convertir les heures en millisecondes
        
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
        logger.info(f"Réponse données historiques: {json.dumps(response, indent=2)}")
        
        if isinstance(response, dict) and 'returnData' in response:
            data = response['returnData']
            if 'rateInfos' in data and len(data['rateInfos']) > 0:
                df = pd.DataFrame(data['rateInfos'])
                
                # Convertir les données brutes en prix réels
                for col in ['close', 'open', 'high', 'low']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                    # Conversion spécifique pour EURUSD
                    if self.symbol == 'EURUSD':
                        df[col] = (df[col] + 10000) / 100000  # Correction pour les valeurs négatives
                    else:
                        df[col] = df[col] / 10000
                
                # Conversion des timestamps
                df['timestamp'] = pd.to_datetime(df['ctm'], unit='ms')
                df = df.set_index('timestamp').sort_index()
                
                # Log des valeurs pour debugging
                logger.info(f"""
                Données traitées:
                - Premier prix: {df['close'].iloc[0]}
                - Dernier prix: {df['close'].iloc[-1]}
                - Min prix: {df['close'].min()}
                - Max prix: {df['close'].max()}
                - Nombre de périodes: {len(df)}
                """)
                
                return df
                
        logger.error("Pas de données historiques reçues")
        return None
        
    except Exception as e:
        logger.error(f"❌ Erreur dans get_historical_data: {str(e)}")
        return None

   def calculate_indicators(self, df):
    try:
        df = df.copy()
        # Assurez-vous que 'close' est numérique
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        
        # Recalcul des SMA en utilisant uniquement les valeurs valides
        df['SMA20'] = df['close'].rolling(window=20, min_periods=1).mean()
        df['SMA50'] = df['close'].rolling(window=50, min_periods=1).mean()
        
        # Calcul du RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # Remplacer les valeurs NaN par des valeurs appropriées
        df['SMA20'].fillna(df['close'], inplace=True)
        df['SMA50'].fillna(df['close'], inplace=True)
        df['RSI'].fillna(50, inplace=True)
        
        return df
    except Exception as e:
        logging.error(f"❌ Erreur lors du calcul des indicateurs: {str(e)}")
        return None

   def check_trading_signals(self, df):
    if len(df) < 50:
        logger.info("⚠️ Pas assez de données")
        return None
            
    last_row = df.iloc[-1]
    
    # Conditions pour l'achat
    buy_sma_condition = last_row['SMA20'] > last_row['SMA50']
    buy_price_condition = last_row['close'] > last_row['SMA20']
    buy_rsi_condition = last_row['RSI'] < 70
    
    # Conditions pour la vente
    sell_sma_condition = last_row['SMA20'] < last_row['SMA50']
    sell_price_condition = last_row['close'] < last_row['SMA20']
    sell_rsi_condition = last_row['RSI'] > 30
    
    buy_signal = buy_sma_condition and buy_price_condition and buy_rsi_condition
    sell_signal = sell_sma_condition and sell_price_condition and sell_rsi_condition
    
    signal_type = None
    if buy_signal:
        signal_type = "BUY"
        conditions = {
            "sma_condition": str(buy_sma_condition),
            "price_condition": str(buy_price_condition),
            "rsi_condition": str(buy_rsi_condition)
        }
    elif sell_signal:
        signal_type = "SELL"
        conditions = {
            "sma_condition": str(sell_sma_condition),
            "price_condition": str(sell_price_condition),
            "rsi_condition": str(sell_rsi_condition)
        }
    
    logger.info(f"""
    Conditions actuelles pour {signal_type if signal_type else 'aucun signal'}:
    - SMA20: {last_row['SMA20']} {'>' if signal_type == 'BUY' else '<'} SMA50: {last_row['SMA50']}
    - Prix: {last_row['close']} {'>' if signal_type == 'BUY' else '<'} SMA20: {last_row['SMA20']}
    - RSI: {last_row['RSI']} {'<' if signal_type == 'BUY' else '>'} {70 if signal_type == 'BUY' else 30}
    """)
    
    return signal_type

    
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
    if self.check_trade_status():
        logger.info("Position déjà ouverte. Pas de nouveau trade.")
        return False
    if not self.check_connection():
        logger.error("Pas de connexion")
        return False
        
    try:
        symbol_info = self.get_symbol_info()
        ask_price = float(symbol_info.get('ask', 0))
        bid_price = float(symbol_info.get('bid', 0))
        lot_min = max(float(symbol_info.get('lotMin', 0.01)), 0.01)
        
        logger.info(f"Prix demandé: {ask_price}, Prix offert: {bid_price}, Volume min: {lot_min}")

        # Vérification des valeurs
        if ask_price <= 0 or bid_price <= 0 or lot_min <= 0:
            logger.error(f"Valeurs invalides pour le trade: ask={ask_price}, bid={bid_price}, lot_min={lot_min}")
            return False

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
                    "sl": round(ask_price * 0.985 if signal == "BUY" else bid_price * 1.015, 5),
                    "tp": round(ask_price * 1.02 if signal == "BUY" else bid_price * 0.98, 5),
                    "symbol": self.symbol,
                    "type": 0,
                    "volume": lot_min
                }
            }
        }

        logger.info(f"Envoi ordre: {json.dumps(trade_cmd, indent=2)}")
        response = self.client.commandExecute('tradeTransaction', trade_cmd['arguments'])
        logger.info(f"Réponse trade complète: {json.dumps(response, indent=2)}")
        
        if response and response.get('status'):
            order_id = response.get('returnData', {}).get('order')
            logger.info(f"Trade exécuté avec succès, order_id: {order_id}")
            self.position_open = True
            self.current_order_id = order_id
            return True
            
        error_msg = response.get('errorDescr', 'Erreur inconnue') if response else 'Pas de réponse'
        logger.error(f"Échec du trade: {error_msg}")
        return False

        if response and response.get('status'):
            order_id = response.get('returnData', {}).get('order')
            logger.info(f"Trade exécuté avec succès, order_id: {order_id}")
    
            # Vérification immédiate pour confirmer l'état
            time.sleep(1)  # Attente courte pour que l'ordre soit traité
            has_positions = self.check_trade_status()
            logger.info(f"Vérification après trade: position_open={has_positions}")
    
            self.position_open = True
            self.current_order_id = order_id
            return True
       
    except Exception as e:
        logger.error(f"Exception lors de l'exécution du trade: {str(e)}")
        return False

   def check_trade_status(self):
    try:
        cmd = {
            "command": "getTrades",
            "arguments": {
                "openedOnly": True
            }
        }
        response = self.client.commandExecute(cmd["command"], cmd["arguments"])
    
        if response and 'returnData' in response:
            trades = response['returnData']
            has_positions = len(trades) > 0
            # Très important: mettre à jour l'état interne
            self.position_open = has_positions
            return has_positions
        self.position_open = False
        return False
    
    except Exception as e:
        logging.error(f"❌ Erreur lors de la vérification du trade: {str(e)}")
        self.position_open = False
        return False

   def execute_trade_simulation(self, signal):
    """Version simulation de execute_trade qui ne passe pas d'ordre réel"""
    logger.info(f"SIMULATION: Exécution d'un ordre {signal}")
    self.position_open = True
    self.current_order_id = f"sim_{int(time.time())}"
    return True
    
   def check_trade_status_simulation(self):
    """Version simulation de check_trade_status"""
    return self.position_open 
    
   def run_strategy(self):
    try:
        if not self.check_connection():
            logger.error("Pas de connexion à XTB")
            return False
        
        # Vérification stricte des positions au début de chaque cycle
        has_positions = self.check_trade_status()
        
        if has_positions:
            logger.info("📊 En attente de clôture des positions actives...")
            return True  # Indique que tout va bien, mais on attend
        
        # Si aucune position n'est ouverte, recherche de nouvelles opportunités
        df = self.get_historical_data()
        if df is not None:
            df = self.calculate_indicators(df)
            if df is not None:
                # Loggez toutes les valeurs importantes
                last_row = df.iloc[-1]
                logger.info(f"""
                Analyse pour décision de trading:
                - Prix actuel: {last_row['close']}
                - SMA20: {last_row['SMA20']}
                - SMA50: {last_row['SMA50']}
                - RSI: {last_row['RSI']}
                """)
                
                signal = self.check_trading_signals(df)
                
                if signal:
                    logger.info(f"🎯 Signal détecté: {signal}")
            
                    # SIMULATION: Utiliser la version simulation pour tester
                    result = self.execute_trade_simulation(signal)
                    logger.info(f"Résultat de l'ordre SIMULÉ: {result}")
                    return result
                    
                    # Double vérification des positions
                    if self.check_trade_status():
                        logger.info("Position détectée après vérification, pas de nouveau trade")
                        return True
                    
                    # Exécution du trade
                    result = self.execute_trade(signal)
                    logger.info(f"Résultat de l'ordre automatique: {result}")
                    return result
        
        return True
    except Exception as e:
        logger.error(f"Erreur critique dans run_strategy: {str(e)}")
        return False
