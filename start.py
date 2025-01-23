from flask import Flask, jsonify
import os, logging, threading, time
from bot_cloud import XTBTradingBot
import google.cloud.logging

client = google.cloud.logging.Client()
client.setup_logging()

app = Flask(__name__)
bot = None
bot_thread = None

def run_bot():
    global bot
    while True:
        try:
            if bot and bot.connect():
                logging.info("🤖 Bot connecté - démarrage trading")
                bot.run_strategy()
            else:
                logging.error("❌ Échec connexion - retry dans 60s")
                time.sleep(60)
        except Exception as e:
            logging.error(f"❌ Erreur bot: {str(e)}")
            time.sleep(60)

@app.route('/')
def home():
    global bot, bot_thread
    if not bot or not bot_thread or not bot_thread.is_alive():
        try:
            logging.info("🔄 Initialisation bot...")
            bot = XTBTradingBot(symbol='EURUSD', timeframe='1h')
            bot_thread = threading.Thread(target=run_bot, daemon=True)
            bot_thread.start()
            logging.info("✅ Bot démarré")
        except Exception as e:
            logging.error(f"❌ Erreur initialisation: {str(e)}")
    return jsonify({"status": "running" if bot_thread and bot_thread.is_alive() else "stopped"})

@app.route('/status')
def status():
    global bot
    if bot:
        try:
            account_info = bot.check_account_status()
            return jsonify({
                "status": "running",
                "account": account_info,
                "connected": bot.client is not None
            })
        except Exception as e:
            logging.error(f"❌ Erreur status: {str(e)}")
            return jsonify({"status": "error", "message": str(e)})
    return jsonify({"status": "not_initialized"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
