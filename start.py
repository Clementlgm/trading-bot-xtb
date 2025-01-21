from flask import Flask
import threading
import os
from bot_cloud import XTBTradingBot

app = Flask(__name__)

def run_bot():
    bot = XTBTradingBot(symbol='BITCOIN', timeframe='1h')
    if bot.connect():
        bot.run_strategy()

@app.route('/')
def home():
    return 'Bot de trading en cours d\'exécution', 200

@app.route('/health')
def health():
    return 'OK', 200

if __name__ == '__main__':
    # Démarrage du bot dans un thread séparé
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Définir le port depuis la variable d'environnement
    port = int(os.getenv('PORT', '8080'))
    # Important : démarrage du serveur Flask en dernier
    app.run(host='0.0.0.0', port=port)
