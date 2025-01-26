from dotenv import load_dotenv
import os
import logging
from xapi.client import Client
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug.log'),
        logging.StreamHandler()
    ]
)

def test_bot():
    try:
        load_dotenv()
        client = Client()
        client.connect()
        
        response = client.login(
            os.getenv('XTB_USER_ID', '17373384'),
            os.getenv('XTB_PASSWORD')
        )
        logging.info(f"Login response: {response}")
        
        if response.get('status'):
            # Test get account info
            account = client.commandExecute("getMarginLevel")
            logging.info(f"Account info: {account}")
            
            # Test get symbol info
            symbol = client.commandExecute("getSymbol", {"symbol": "EURUSD"})
            logging.info(f"Symbol info: {symbol}")
            
            time.sleep(5)
        
    except Exception as e:
        logging.error(f"Error: {str(e)}")

if __name__ == "__main__":
    test_bot()