from flask import Flask
import threading
from bot_cloud import XTBTradingBot

app = Flask(__name__)

def run_bot():
    bot = XTBTradingBot(symbol='BITCOIN', timeframe='1h')
    if bot.connect():
        bot.run_strategy()

# Démarrer le bot dans un thread séparé
bot_thread = threading.Thread(target=run_bot, daemon=True)
bot_thread.start()

@app.route('/')
def home():
    return 'Bot de trading en cours d\'exécution', 200

@app.route('/health')
def health():
    return 'OK', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)