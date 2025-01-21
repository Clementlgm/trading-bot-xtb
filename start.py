from flask import Flask
import threading
import os
import time
from bot_cloud import XTBTradingBot

app = Flask(__name__)
server_ready = False

def run_bot():
    try:
        global server_ready
        # Attendre que le serveur soit prêt
        time.sleep(10)  # Délai de démarrage
        bot = XTBTradingBot(symbol='BITCOIN', timeframe='1h')
        if bot.connect():
            server_ready = True
            bot.run_strategy()
    except Exception as e:
        app.logger.error(f"Error in bot thread: {str(e)}")

# Démarrer le bot dans un thread séparé
bot_thread = threading.Thread(target=run_bot, daemon=True)
bot_thread.start()

@app.route('/')
def home():
    return 'Bot de trading en cours d\'exécution', 200

@app.route('/health')
def health():
    global server_ready
    if not server_ready:
        time.sleep(2)  # Petit délai pour laisser le temps au bot de démarrer
    return 'OK' if server_ready else 'Starting', 200

if __name__ == '__main__':
    # Définir le port depuis la variable d'environnement
    port = int(os.getenv('PORT', '8080'))
    app.run(host='0.0.0.0', port=port, debug=False)
