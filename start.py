from flask import Flask
import os
import logging
import threading
import sys
from bot_cloud import XTBTradingBot
import traceback

# Configuration du logging plus détaillée
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout  # Important pour Cloud Run
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
bot = None
bot_thread_running = False

def run_bot():
    global bot, bot_thread_running
    try:
        logger.info("🚀 Démarrage du thread du bot de trading")
        bot_thread_running = True
        
        logger.info("🔄 Initialisation du bot XTB")
        bot = XTBTradingBot(symbol='BITCOIN', timeframe='1h')
        
        logger.info("🔌 Tentative de connexion à XTB")
        if bot.connect():
            logger.info("✅ Bot connecté à XTB avec succès")
            logger.info("📈 Démarrage de la stratégie de trading")
            bot.run_strategy()
        else:
            logger.error("❌ Échec de connexion à XTB")
    except Exception as e:
        logger.error(f"❌ Erreur dans le thread du bot: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
    finally:
        bot_thread_running = False
        logger.info("⚠️ Thread du bot terminé")

@app.route('/')
def root():
    global bot_thread_running
    status = "Bot thread en cours" if bot_thread_running else "Bot thread arrêté"
    return f"État du bot de trading: {status}", 200

@app.route('/health')
def health():
    return "OK", 200

@app.route('/status')
def status():
    global bot, bot_thread_running
    if not bot_thread_running:
        return "Bot thread non démarré", 500
    if not bot or not bot.client:
        return "Bot non initialisé", 500
    return "Bot actif et connecté", 200

if __name__ == "__main__":
    logger.info("🌟 Démarrage de l'application")
    
    # Démarrage du bot dans un thread séparé
    trading_thread = threading.Thread(target=run_bot, daemon=True)
    trading_thread.start()
    logger.info("✅ Thread du bot démarré")
    
    # Démarrage de Flask
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"🚀 Démarrage du serveur Flask sur le port {port}")
    app.run(host="0.0.0.0", port=port)
