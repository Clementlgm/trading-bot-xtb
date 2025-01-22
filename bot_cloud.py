requirements.txt
xapi-python>=2.5.0
google-cloud-storage>=2.5.0
pandas>=1.5.0
numpy>=1.21.0
python-dotenv>=0.19.0

main.py
import os
from google.cloud import storage
import pandas as pd
import numpy as np
from datetime import datetime
import time
import json
from xapi.client import Client
from xapi.streaming import Streaming
from dotenv import load_dotenv

load_dotenv()

def initialize_storage_client():
    return storage.Client()

def save_state(bucket_name, data):
    client = initialize_storage_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob('trading_state.json')
    blob.upload_from_string(json.dumps(data))

def load_state(bucket_name):
    client = initialize_storage_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob('trading_state.json')
    
    try:
        return json.loads(blob.download_as_string())
    except:
        return {'position_open': False, 'current_order_id': None}

class CloudTradingBot:
    def __init__(self, bucket_name):
        self.userId = os.getenv('XTB_USER_ID')
        self.password = os.getenv('XTB_PASSWORD')
        self.symbol = 'BITCOIN'
        self.client = None
        self.bucket_name = bucket_name
        self.state = load_state(bucket_name)
        self.position_open = self.state['position_open']
        self.current_order_id = self.state['current_order_id']

    def connect(self):
        try:
            self.client = Client()
            self.client.connect()
            response = self.client.login(self.userId, self.password)
            
            if response.get('status'):
                print("✅ Connected to XTB")
                return True
            return False
        except Exception as e:
            print(f"❌ Connection error: {str(e)}")
            return False

    def get_historical_data(self):
        try:
            current_time = int(time.time())
            period_start = current_time - (100 * 3600)
            
            command = {
                'info': {
                    'symbol': self.symbol,
                    'period': 1,
                    'start': period_start * 1000,
                }
            }
            
            response = self.client.commandExecute('getChartLastRequest', command)
            
            if isinstance(response, dict) and 'returnData' in response:
                data = response['returnData']
                if 'rateInfos' in data and data['rateInfos']:
                    df = pd.DataFrame(data['rateInfos'])
                    df['timestamp'] = pd.to_datetime(df['ctm'], unit='ms')
                    return df.sort_values('timestamp')
            return None
                    
        except Exception as e:
            print(f"❌ Error in get_historical_data: {str(e)}")
            return None

    def calculate_indicators(self, df):
        try:
            df['SMA20'] = df['close'].rolling(window=20).mean()
            df['SMA50'] = df['close'].rolling(window=50).mean()
            
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            return df
        except Exception as e:
            print(f"❌ Error calculating indicators: {str(e)}")
            return None

    def check_trading_signals(self, df):
        if len(df) < 50:
            return None
            
        last_row = df.iloc[-1]
        
        buy_signal = (
            last_row['SMA20'] > last_row['SMA50'] and
            last_row['RSI'] < 70 and
            last_row['close'] > last_row['SMA20']
        )
        
        sell_signal = (
            last_row['SMA20'] < last_row['SMA50'] and
            last_row['RSI'] > 30 and
            last_row['close'] < last_row['SMA20']
        )
        
        return "BUY" if buy_signal else "SELL" if sell_signal else None

    def execute_trade(self, signal):
        try:
            if not signal:
                return False

            symbol_info = self.client.commandExecute('getSymbol', {'symbol': self.symbol})
            if not symbol_info or 'returnData' not in symbol_info:
                return False

            symbol_data = symbol_info['returnData']
            ask_price = float(symbol_data.get('ask', 0))
            bid_price = float(symbol_data.get('bid', 0))
            precision = len(str(symbol_data.get('pipsPrecision', 5)))
            pip_value = 1 / (10 ** precision)

            if signal == "BUY":
                entry_price = ask_price
                sl_price = round(entry_price - (100 * pip_value), precision)
                tp_price = round(entry_price + (200 * pip_value), precision)
            else:
                entry_price = bid_price
                sl_price = round(entry_price + (100 * pip_value), precision)
                tp_price = round(entry_price - (200 * pip_value), precision)

            trade_cmd = {
                "tradeTransInfo": {
                    "cmd": 0 if signal == "BUY" else 1,
                    "symbol": self.symbol,
                    "volume": 0.01,
                    "type": 0,
                    "price": entry_price,
                    "sl": sl_price,
                    "tp": tp_price
                }
            }

            response = self.client.commandExecute('tradeTransaction', trade_cmd)
            
            if response.get('status'):
                self.current_order_id = response['returnData']['order']
                self.position_open = True
                self.save_state()
                return True
                
            return False
            
        except Exception as e:
            print(f"❌ Error executing trade: {str(e)}")
            return False

    def save_state(self):
        state = {
            'position_open': self.position_open,
            'current_order_id': self.current_order_id
        }
        save_state(self.bucket_name, state)

    def check_position(self):
        try:
            if not self.position_open:
                return False

            response = self.client.commandExecute('getTrades', {'openedOnly': True})
            
            if response and 'returnData' in response:
                trades = response['returnData']
                current_trade = next((t for t in trades if str(t.get('order', 0)) == str(self.current_order_id)), None)
                
                if not current_trade:
                    self.position_open = False
                    self.current_order_id = None
                    self.save_state()
                    return False
                    
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ Error checking position: {str(e)}")
            return False

def trading_function(event, context):
    """Cloud Function entry point"""
    bucket_name = os.getenv('BUCKET_NAME')
    bot = CloudTradingBot(bucket_name)
    
    if not bot.connect():
        return 'Failed to connect'

    if bot.position_open:
        if not bot.check_position():
            bot.position_open = False
            bot.current_order_id = None
            bot.save_state()

    if not bot.position_open:
        df = bot.get_historical_data()
        if df is not None:
            df = bot.calculate_indicators(df)
            if df is not None:
                signal = bot.check_trading_signals(df)
                if signal:
                    bot.execute_trade(signal)

    return 'Trading cycle completed'

.env
XTB_USER_ID=your_user_id
XTB_PASSWORD=your_password
BUCKET_NAME=your_bucket_name
