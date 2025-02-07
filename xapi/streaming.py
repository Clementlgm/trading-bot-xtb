import json
import socket
import logging
import time
import os
from threading import Lock
from xapi.client import Client
from xapi.streaming import Streaming

class XTBTradingBot:
    def __init__(self, symbol='BITCOIN', timeframe='1h'):
        self.userId = os.getenv('XTB_USER_ID')
        self.password = os.getenv('XTB_PASSWORD')
        self.symbol = symbol
        self.timeframe = timeframe
        self.client = None
        self.streaming = None
        self.mutex = Lock()
        self.last_check = time.time()
        self.check_interval = 60  # 60 secondes entre chaque vérification
        self.order_in_progress = False

    def connect(self):
        try:
            logging.info(f"🔄 Tentative de connexion à XTB - UserID: {self.userId}")
            
            # Connexion principale
            self.client = Client()
            self.client.connect()
            response = self.client.login(self.userId, self.password)
            
            if not response or not response.get('status'):
                logging.error(f"❌ Échec du login: {response}")
                return False
            
            # Si le login réussit, on initialise le streaming
            try:
                if not self.streaming:
                    self.streaming = Streaming(self.client)
                    self.streaming.connect()
            except Exception as e:
                logging.error(f"❌ Erreur connexion streaming: {str(e)}")
                # Ne pas échouer si le streaming échoue
                
            logging.info("✅ Connecté à XTB avec succès")
            return True
        except Exception as e:
            logging.error(f"❌ Erreur de connexion: {str(e)}")
            return False

    def check_connection(self):
        try:
            with self.mutex:
                current_time = time.time()
                if current_time - self.last_check >= self.check_interval:
                    self.last_check = current_time
                    
                    # Check ping avant déconnexion
                    if not self.client or not self.client.ping():
                        logging.info("Ping échoué, reconnexion nécessaire")
                        if self.streaming:
                            self.streaming.disconnect()
                        if self.client:
                            self.client.disconnect()
                        time.sleep(1)  # Petit délai avant reconnexion
                        return self.connect()
                        
                return self.client is not None
        except Exception as e:
            logging.error(f"❌ Erreur check_connection: {str(e)}")
            return self.connect()

    def check_trade_status(self):
        """Vérifie si un trade est ouvert"""
        try:
            if not self.check_connection():
                return False

            trades = self.client.commandExecute('getTrades', {
                'openedOnly': True
            })
            
            if trades and trades.get('status'):
                return len(trades.get('returnData', [])) > 0
            return False
        except Exception as e:
            logging.error(f"❌ Erreur check_trade_status: {str(e)}")
            return False

    def execute_trade(self, signal):
        """Exécute un trade avec retry et vérifications"""
        if not signal or self.order_in_progress:
            return False
            
        try:
            self.order_in_progress = True
            
            # Vérification de la connexion
            if not self.check_connection():
                logging.error("❌ Pas de connexion pour exécuter le trade")
                return False
                
            # Vérification des positions ouvertes
            if self.check_trade_status():
                logging.info("Position déjà ouverte, pas de nouvel ordre")
                return False

            # Construction de l'ordre
            cmd = 0 if signal == "BUY" else 1
            volume = 0.01  # Volume minimal pour test
            
            order = {
                "command": "tradeTransaction",
                "arguments": {
                    "tradeTransInfo": {
                        "cmd": cmd,
                        "customComment": "CloudRun_Bot",
                        "volume": volume,
                        "symbol": self.symbol,
                        "type": 0  # Ordre marché
                    }
                }
            }

            # Exécution avec retry
            for attempt in range(3):
                try:
                    response = self.client.commandExecute(
                        order["command"], 
                        order["arguments"]
                    )
                    
                    if response and response.get('status'):
                        logging.info(f"✅ Trade exécuté: {signal}")
                        return True
                        
                    logging.error(f"❌ Échec du trade (tentative {attempt+1}): {response}")
                    time.sleep(2)
                except Exception as e:
                    logging.error(f"❌ Erreur d'exécution (tentative {attempt+1}): {str(e)}")
                    if attempt < 2:
                        time.sleep(2)
                        continue
                    
            return False
            
        finally:
            self.order_in_progress = False

    def run_strategy(self):
        """Boucle principale de trading"""
        while True:
            try:
                if not self.check_connection():
                    time.sleep(30)
                    continue

                # Récupération des données et analyse...
                # (Gardez votre logique actuelle)
                
                time.sleep(5)  # Délai entre les itérations
                
            except Exception as e:
                logging.error(f"❌ Erreur dans run_strategy: {str(e)}")
                time.sleep(30)
