import requests
import time
import json
from datetime import datetime

# Configuration - Update these with your actual endpoint
BASE_URL = "https://trading-bot-642630404413.europe-west9.run.app"  # Change to your actual bot URL
ITERATIONS = 5
DELAY = 30  # seconds between checks

def log_with_timestamp(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def check_bot_status():
    """Check if the bot is running and connected"""
    try:
        response = requests.get(f"{BASE_URL}/status", timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            log_with_timestamp(f"Error getting status: {response.status_code}")
            return None
    except Exception as e:
        log_with_timestamp(f"Exception checking status: {str(e)}")
        return None

def get_debug_info():
    """Get detailed debug information from the bot"""
    try:
        response = requests.get(f"{BASE_URL}/debug", timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            log_with_timestamp(f"Error getting debug info: {response.status_code}")
            return None
    except Exception as e:
        log_with_timestamp(f"Exception getting debug info: {str(e)}")
        return None

def get_logs():
    """Get current logs/indicators from the bot"""
    try:
        response = requests.get(f"{BASE_URL}/logs", timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            log_with_timestamp(f"Error getting logs: {response.status_code}")
            return None
    except Exception as e:
        log_with_timestamp(f"Exception getting logs: {str(e)}")
        return None

def sync_status():
    """Sync the bot's position status with actual account status"""
    try:
        response = requests.get(f"{BASE_URL}/sync_status", timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            log_with_timestamp(f"Error syncing status: {response.status_code}")
            return None
    except Exception as e:
        log_with_timestamp(f"Exception syncing status: {str(e)}")
        return None

def check_signal_conditions(debug_info):
    """Analyze if trading signal conditions are being met"""
    if not debug_info or debug_info.get('status') != 'success':
        return "Unknown - couldn't get debug info"
    
    conditions = debug_info.get('trading_conditions', {})
    market_data = debug_info.get('market_data', {})
    
    sma_condition = conditions.get('sma_condition', 'False') == 'True'
    rsi_condition = conditions.get('rsi_condition', 'False') == 'True'
    price_condition = conditions.get('price_condition', 'False') == 'True'
    
    result = {
        "conditions_met": sma_condition and rsi_condition and price_condition,
        "sma_condition": sma_condition,
        "rsi_condition": rsi_condition,
        "price_condition": price_condition,
        "price": market_data.get('last_price'),
        "sma20": market_data.get('sma20'),
        "sma50": market_data.get('sma50'),
        "rsi": market_data.get('rsi')
    }
    
    return result

def run_diagnostics():
    """Run comprehensive diagnostics on the trading bot"""
    log_with_timestamp("Starting trading bot diagnostics...")
    
    # First, check connection and sync status
    status = check_bot_status()
    if not status:
        log_with_timestamp("❌ Cannot connect to the bot API.")
        return
    
    log_with_timestamp(f"✅ Connected to bot. Status: {status.get('status')}")
    
    # Sync position status
    sync_result = sync_status()
    if sync_result:
        log_with_timestamp(f"Position status: {sync_result.get('position_open')} (Previous: {sync_result.get('previous_state')})")
    
    # Initial debug info
    debug_info = get_debug_info()
    if not debug_info:
        log_with_timestamp("❌ Cannot get debug information.")
        return
    
    bot_state = debug_info.get('bot_state', {})
    log_with_timestamp(f"Bot state: Connection={bot_state.get('connection')}, Position open={bot_state.get('position_open')}")
    
    # Begin monitoring over multiple iterations
    log_with_timestamp(f"\n🔄 Starting {ITERATIONS} monitoring iterations with {DELAY}s intervals...")
    
    for i in range(ITERATIONS):
        log_with_timestamp(f"\n--- Iteration {i+1}/{ITERATIONS} ---")
        
        # Get debug info
        debug_info = get_debug_info()
        if not debug_info:
            log_with_timestamp("❌ Cannot get debug information.")
            continue
        
        # Check signal conditions
        signal_check = check_signal_conditions(debug_info)
        log_with_timestamp(f"Signal conditions met: {signal_check.get('conditions_met')}")
        log_with_timestamp(f"  - SMA condition: {signal_check.get('sma_condition')} (SMA20: {signal_check.get('sma20')}, SMA50: {signal_check.get('sma50')})")
        log_with_timestamp(f"  - Price condition: {signal_check.get('price_condition')} (Price: {signal_check.get('price')}, SMA20: {signal_check.get('sma20')})")
        log_with_timestamp(f"  - RSI condition: {signal_check.get('rsi_condition')} (RSI: {signal_check.get('rsi')})")
        
        # Check if a signal is generated
        signal = debug_info.get('trading_conditions', {}).get('signal_type')
        log_with_timestamp(f"Signal generated: {signal}")
        
        # Check position status
        position_status = debug_info.get('position_status')
        log_with_timestamp(f"Position status: {position_status}")
        
        # Wait for next iteration
        if i < ITERATIONS - 1:
            log_with_timestamp(f"Waiting {DELAY} seconds for next check...")
            time.sleep(DELAY)
    
    log_with_timestamp("\n📊 Diagnostic Summary:")
    
    # Final connection check
    status = check_bot_status()
    connection_ok = status and status.get('status') == 'connected'
    log_with_timestamp(f"✅ Connection status: {'Connected' if connection_ok else 'Disconnected'}")
    
    # Check position tracking
    sync_result = sync_status()
    if sync_result:
        position_tracking_ok = sync_result.get('position_open') == sync_result.get('previous_state')
        log_with_timestamp(f"✅ Position tracking: {'Accurate' if position_tracking_ok else 'Inconsistent'}")
    
    # Final signal check
    debug_info = get_debug_info()
    if debug_info:
        signal_check = check_signal_conditions(debug_info)
        signal_conditions_met = signal_check.get('conditions_met')
        log_with_timestamp(f"✅ Signal conditions: {'Met' if signal_conditions_met else 'Not met'}")
        
        if not signal_conditions_met:
            log_with_timestamp("ℹ️ No automatic trade will execute until all signal conditions are met:")
            if not signal_check.get('sma_condition'):
                log_with_timestamp("  - SMA20 must be greater than SMA50")
            if not signal_check.get('price_condition'):
                log_with_timestamp("  - Price must be greater than SMA20")
            if not signal_check.get('rsi_condition'):
                log_with_timestamp("  - RSI must be less than 70")
    
    log_with_timestamp("\n🔍 Diagnostics completed")

if __name__ == "__main__":
    run_diagnostics()
