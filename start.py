from flask import Flask
import threading
import os
from bot_cloud import XTBTradingBot

app = Flask(__name__)

def run_bot():
    try:
        bot = XTBTradingBot(symbol='BITCOIN', timeframe='1h')
        if bot.connect():
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
    return 'OK', 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
