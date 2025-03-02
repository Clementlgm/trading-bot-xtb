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
   def __init__(self, symbol='ETHEREUM', timeframe='1h'):
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
            logger.info("Client est None, connexion en cours...")
            return self.connect()
        
        # Reconnexion plus agressive
        current_time = time.time()
        if current_time - self.last_reconnect >= 30:  # Réduit de 60 à 30 secondes
            logger.info("Reconnexion préventive en cours")
            self.disconnect()
            time.sleep(2)  # Augmenté de 1 à 2 secondes
            success = self.connect()
            if success:
                self.last_reconnect = current_time
            return success

        try:
            # Ajout d'un timeout à la commande ping
            response = self.client.commandExecute("ping")
            if not response or not response.get('status'):
                logger.warning("Échec du ping, reconnexion...")
                self.disconnect()
                time.sleep(2)
                return self.connect()
        except Exception as e:
            logger.error(f"Erreur pendant le ping: {str(e)}")
            return self.connect()
            
        return True
    except Exception as e:
        logger.error(f"Erreur de vérification de connexion: {str(e)}")
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
                    if self.symbol == 'ETHEREUM':
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
        logger.info("⚠️ Pas assez de données pour générer un signal (minimum 50 périodes)")
        return None
            
    last_row = df.iloc[-1]
    previous_row = df.iloc[-2] if len(df) > 1 else last_row
    
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
    
    # Ajout de détection de tendance
    sma20_trend = "HAUSSE" if last_row['SMA20'] > previous_row['SMA20'] else "BAISSE"
    sma50_trend = "HAUSSE" if last_row['SMA50'] > previous_row['SMA50'] else "BAISSE"
    
    signal_type = None
    if buy_signal:
        signal_type = "BUY"
    elif sell_signal:
        signal_type = "SELL"
    
    # Logging détaillé pour l'analyse des signaux
    logger.info(f"""
    =================================
    ANALYSE DE SIGNAL DE TRADING:
    ---------------------------------
    CONDITIONS ACTUELLES:
    - Prix: {last_row['close']:.5f}
    - SMA20: {last_row['SMA20']:.5f} (Tendance: {sma20_trend})
    - SMA50: {last_row['SMA50']:.5f} (Tendance: {sma50_trend})
    - RSI: {last_row['RSI']:.2f}
    
    ANALYSE SIGNAL ACHAT:
    - Condition SMA (SMA20 > SMA50): {buy_sma_condition} ({last_row['SMA20']:.5f} {'>' if buy_sma_condition else '<='} {last_row['SMA50']:.5f})
    - Condition Prix (Prix > SMA20): {buy_price_condition} ({last_row['close']:.5f} {'>' if buy_price_condition else '<='} {last_row['SMA20']:.5f})
    - Condition RSI (RSI < 70): {buy_rsi_condition} ({last_row['RSI']:.2f} {'<' if buy_rsi_condition else '>='} 70)
    - Signal ACHAT généré: {buy_signal}
    
    ANALYSE SIGNAL VENTE:
    - Condition SMA (SMA20 < SMA50): {sell_sma_condition} ({last_row['SMA20']:.5f} {'<' if sell_sma_condition else '>='} {last_row['SMA50']:.5f})
    - Condition Prix (Prix < SMA20): {sell_price_condition} ({last_row['close']:.5f} {'<' if sell_price_condition else '>='} {last_row['SMA20']:.5f})
    - Condition RSI (RSI > 30): {sell_rsi_condition} ({last_row['RSI']:.2f} {'>' if sell_rsi_condition else '<='} 30)
    - Signal VENTE généré: {sell_signal}
    
    DÉCISION: {signal_type if signal_type else "AUCUN SIGNAL"}
    =================================
    """)
    
    return signal_type

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
    
   def run_strategy(self):
    try:
        logger.info("=== Exécution de la stratégie de trading ===")
        
        if not self.check_connection():
            logger.error("Pas de connexion à XTB")
            return False
        
        # Vérification du statut des positions au début de chaque cycle
        has_positions = self.check_trade_status()
        logger.info(f"Statut actuel des positions: {has_positions}")
        
        if has_positions:
            logger.info("Position déjà ouverte. En attente de clôture.")
            return True
        
        # Si aucune position n'est ouverte, recherche d'opportunités
        logger.info("Récupération des données historiques...")
        df = self.get_historical_data()
        
        if df is None:
            logger.error("Échec de récupération des données historiques")
            return False
            
        if len(df) < 50:
            logger.warning(f"Données insuffisantes pour l'analyse: {len(df)} périodes (minimum 50 requis)")
            return True
        
        logger.info("Calcul des indicateurs techniques...")
        df = self.calculate_indicators(df)
        
        if df is None:
            logger.error("Échec du calcul des indicateurs")
            return False
        
        # Vérification des signaux de trading
        logger.info("Recherche de signaux de trading...")
        signal = self.check_trading_signals(df)
        
        if signal:
            logger.info(f"📈 Signal détecté: {signal}")
            
            # Double vérification du statut des positions avant exécution
            if self.check_trade_status():
                logger.warning("Position détectée lors de la vérification finale, abandon du nouveau trade")
                return True
            
            # Exécution du trade
            logger.info(f"Exécution du trade {signal}...")
            result = self.execute_trade(signal)
            logger.info(f"Résultat de l'exécution du trade: {'Succès' if result else 'Échec'}")
            
            # Vérification que le trade a été exécuté
            time.sleep(1)
            actual_status = self.check_trade_status()
            logger.info(f"Statut des positions après trade: {actual_status}")
            
            if result and not actual_status:
                logger.warning("L'exécution du trade a signalé un succès mais aucune position n'est détectée")
            
            return result
        else:
            logger.info("Aucun signal de trading détecté")
            return True
            
    except Exception as e:
        logger.error(f"Erreur critique dans run_strategy: {str(e)}")
        return False
