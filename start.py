from flask import Flask, jsonify
import os, logging, threading, time
from bot_cloud import XTBTradingBot
import google.cloud.logging

# Setup logging
client = google.cloud.logging.Client()
client.setup_logging()
logging.getLogger().setLevel(logging.DEBUG)

app = Flask(__name__)
bot = None
bot_thread = None

def run_bot():
    global bot
    logging.info("🔄 Démarrage thread bot")
    try:
        bot = XTBTradingBot(symbol='EURUSD', timeframe='1h')
        while True:
            try:
                logging.info("🔌 Tentative connexion XTB")
                if bot.connect():
                    logging.info("✅ Connexion réussie")
                    logging.info("🚀 Lancement stratégie")
                    bot.run_strategy()
                else:
                    logging.error("❌ Échec connexion")
                    time.sleep(30)
            except Exception as e:
                logging.error(f"❌ Erreur trading: {str(e)}")
                time.sleep(30)
    except Exception as e:
        logging.error(f"❌ Erreur init bot: {str(e)}")

@app.route('/')
def home():
    global bot_thread
    if not bot_thread or not bot_thread.is_alive():
        logging.info("🔄 Init thread bot")
        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()
    return jsonify({"status": "running"})

@app.route('/status')
def status():
    global bot
    return jsonify({
        "status": "running" if bot else "stopped",
        "thread_alive": bot_thread.is_alive() if bot_thread else False
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
