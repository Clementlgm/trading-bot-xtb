import logging
from bot_cloud import XTBTradingBot
import time

# Configuration locale simple
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def test_bot():
    bot = XTBTradingBot(symbol='EURUSD', timeframe='1h')
    try:
        if bot.connect():
            margin_cmd = {
                "command": "getMarginLevel",
                "arguments": {}
            }
            margin_response = bot.client.commandExecute(margin_cmd["command"], margin_cmd["arguments"])
            print(f"\nMargin Level Response: {margin_response}")

            chart_cmd = {
                "command": "getChartLastRequest",
                "arguments": {
                    "info": {
                        "period": 1440,
                        "start": int(time.time() - 7 * 24 * 60 * 60) * 1000,
                        "symbol": "BITCOIN"
                    }
                }
            }
            chart_response = bot.client.commandExecute(chart_cmd["command"], chart_cmd["arguments"])
            print(f"\nChart Data Response: {chart_response}")
    finally:
        if bot and bot.client:
            bot.client.disconnect()

if __name__ == "__main__":
    test_bot()