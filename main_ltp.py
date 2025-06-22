import os
import json
import asyncio
import logging
from datetime import datetime, time as dt_time
from typing import Optional, Tuple
from threading import Thread
import time as t

import pyotp
import pandas as pd
import requests
from flask import Flask
from SmartApi.smartConnect import SmartConnect
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
API_KEY = os.getenv("API_KEY")
CLIENT_ID = os.getenv("CLIENT_ID")
PIN = os.getenv("PIN")
TOTP_SECRET = os.getenv("TOTP_SECRET")

SYMBOL = os.getenv("SYMBOL", "RELIANCE-EQ")
SYMBOL_TOKEN = os.getenv("SYMBOL_TOKEN", "2885")
EXCHANGE = os.getenv("EXCHANGE", "NSE")
INTERVAL = os.getenv("INTERVAL", "FIFTEEN_MINUTE")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
STATE_FILE = "bot_state.json"

FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("FLASK_PORT", "8080"))

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask app for health check
app = Flask(__name__)

@app.route('/')
def health_check():
    return {
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "bot_active": get_bot_state()
    }

@app.route('/status')
def status_endpoint():
    return {
        "bot_active": get_bot_state(),
        "symbol": SYMBOL,
        "exchange": EXCHANGE,
        "current_time": datetime.now().isoformat()
    }

def run_web_server():
    """Run Flask web server in a separate thread"""
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False)

def keep_alive():
    """Start the web server to keep the app alive"""
    Thread(target=run_web_server, daemon=True).start()

class BotState:
    """Manage bot state with better error handling"""
    
    @staticmethod
    def set_active(active: bool) -> None:
        """Set bot active state"""
        try:
            with open(STATE_FILE, "w") as f:
                json.dump({"active": active}, f)
            logger.info(f"Bot state set to: {active}")
        except Exception as e:
            logger.error(f"Error setting bot state: {e}")
    
    @staticmethod
    def get_active() -> bool:
        """Get bot active state"""
        try:
            if not os.path.exists(STATE_FILE):
                return False
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
            return data.get("active", False)
        except Exception as e:
            logger.error(f"Error getting bot state: {e}")
            return False

def set_bot_state(active: bool) -> None:
    """Legacy function for compatibility"""
    BotState.set_active(active)

def get_bot_state() -> bool:
    """Legacy function for compatibility"""
    return BotState.get_active()

class TelegramNotifier:
    """Handle Telegram notifications"""
    
    @staticmethod
    async def send_message(message: str) -> bool:
        """Send message to Telegram"""
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            logger.info(f"Message sent: {message[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False

def send_telegram(message: str) -> None:
    """Legacy function for compatibility"""
    asyncio.create_task(TelegramNotifier.send_message(message))

class AngelOneAPI:
    """Handle Angel One API operations"""
    
    def __init__(self):
        self.obj = None
        self.login_time = None
    
    def login(self) -> SmartConnect:
        """Login to Angel One API with session management"""
        try:
            # Check if we need to re-login (every 8 hours)
            if (self.obj is None or 
                self.login_time is None or 
                (datetime.now() - self.login_time).seconds > 28800):
                
                totp = pyotp.TOTP(TOTP_SECRET).now()
                self.obj = SmartConnect(api_key=API_KEY)
                response = self.obj.generateSession(CLIENT_ID, PIN, totp)
                
                if response.get('status'):
                    self.login_time = datetime.now()
                    logger.info("Successfully logged in to Angel One API")
                else:
                    logger.error(f"Login failed: {response}")
                    raise Exception("Login failed")
            
            return self.obj
        except Exception as e:
            logger.error(f"Login error: {e}")
            raise
    
    def get_opening_range(self) -> Tuple[float, float, int]:
        """Get opening range breakout levels"""
        try:
            obj = self.login()
            today = datetime.now().strftime('%Y-%m-%d')
            from_time = f"{today} 09:15"
            to_time = f"{today} 09:30"
            
            params = {
                "exchange": EXCHANGE,
                "symboltoken": SYMBOL_TOKEN,
                "interval": INTERVAL,
                "tradingsymbol": SYMBOL,
                "fromdate": from_time,
                "todate": to_time
            }
            
            response = obj.getCandleData(params)
            if not response.get('data'):
                raise Exception("No candle data received")
            
            df = pd.DataFrame(
                response['data'], 
                columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
            )
            
            high = df['High'].max()
            low = df['Low'].min()
            volume = df['Volume'].sum()
            
            logger.info(f"ORB calculated - High: {high}, Low: {low}, Volume: {volume}")
            return high, low, volume
            
        except Exception as e:
            logger.error(f"Error getting opening range: {e}")
            raise
    
    def get_ltp(self) -> Optional[float]:
        """Get Last Traded Price"""
        try:
            obj = self.login()
            data = obj.ltpData(
                exchange=EXCHANGE, 
                tradingsymbol=SYMBOL, 
                symboltoken=SYMBOL_TOKEN
            )
            
            if data.get('status') and data.get('data'):
                ltp = float(data['data']['ltp'])
                return ltp
            else:
                logger.warning("No LTP data received")
                return None
                
        except Exception as e:
            logger.error(f"Error getting LTP: {e}")
            return None

class ORBTrader:
    """Opening Range Breakout trading logic"""
    
    def __init__(self):
        self.api = AngelOneAPI()
        self.signal_sent = False
        self.orb_high = None
        self.orb_low = None
        self.orb_volume = None
    
    async def run_orb_strategy(self):
        """Main ORB trading loop"""
        try:
            # Wait until market opens
            while datetime.now().time() < dt_time(9, 30):
                await asyncio.sleep(10)
            
            # Calculate opening range
            self.orb_high, self.orb_low, self.orb_volume = self.api.get_opening_range()
            
            message = (
                f"📌 <b>Opening Range Breakout</b>\n"
                f"🔺 High: ₹{self.orb_high:.2f}\n"
                f"🔻 Low: ₹{self.orb_low:.2f}\n"
                f"📊 Volume: {self.orb_volume:,}\n"
                f"📈 Symbol: {SYMBOL}"
            )
            await TelegramNotifier.send_message(message)
            
            # Monitor for breakouts
            while datetime.now().time() < dt_time(15, 15):
                if not get_bot_state():
                    await asyncio.sleep(30)
                    continue
                
                ltp = self.api.get_ltp()
                if ltp and not self.signal_sent:
                    await self.check_breakout(ltp)
                
                await asyncio.sleep(60)
                
        except Exception as e:
            logger.error(f"Error in ORB strategy: {e}")
            await TelegramNotifier.send_message(f"❌ ORB Strategy Error: {str(e)}")
    
    async def check_breakout(self, ltp: float):
        """Check for breakout signals"""
        try:
            if ltp > self.orb_high:
                message = (
                    f"🚀 <b>BUY SIGNAL</b>\n"
                    f"💰 LTP: ₹{ltp:.2f}\n"
                    f"📊 Breakout above: ₹{self.orb_high:.2f}\n"
                    f"📈 Symbol: {SYMBOL}"
                )
                await TelegramNotifier.send_message(message)
                self.signal_sent = True
                logger.info(f"BUY signal sent at {ltp}")
                
            elif ltp < self.orb_low:
                message = (
                    f"📉 <b>SELL SIGNAL</b>\n"
                    f"💰 LTP: ₹{ltp:.2f}\n"
                    f"📊 Breakdown below: ₹{self.orb_low:.2f}\n"
                    f"📈 Symbol: {SYMBOL}"
                )
                await TelegramNotifier.send_message(message)
                self.signal_sent = True
                logger.info(f"SELL signal sent at {ltp}")
                
        except Exception as e:
            logger.error(f"Error checking breakout: {e}")

# Telegram bot command handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start bot command"""
    BotState.set_active(True)
    await update.message.reply_text("✅ <b>Bot Activated</b>", parse_mode="HTML")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop bot command"""
    BotState.set_active(False)
    await update.message.reply_text("⛔ <b>Bot Deactivated</b>", parse_mode="HTML")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Status command"""
    now = datetime.now().strftime('%H:%M:%S')
    state = BotState.get_active()
    
    message = (
        f"📊 <b>Bot Status</b>\n"
        f"🔘 Status: {'🟢 ACTIVE' if state else '🔴 INACTIVE'}\n"
        f"⏰ Time: {now}\n"
        f"📈 Symbol: {SYMBOL}\n"
        f"🏢 Exchange: {EXCHANGE}"
    )
    await update.message.reply_text(message, parse_mode="HTML")

async def holiday_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Holiday check command"""
    today = datetime.today().weekday()
    if today in [5, 6]:  # Saturday, Sunday
        message = "📅 <b>Market CLOSED</b> (Weekend)"
    else:
        message = "📅 <b>Market is OPEN</b>"
    
    await update.message.reply_text(message, parse_mode="HTML")

async def ltp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get LTP command"""
    try:
        api = AngelOneAPI()
        ltp = api.get_ltp()
        
        if ltp:
            message = f"📊 <b>{SYMBOL} LTP:</b> ₹{ltp:.2f}"
        else:
            message = "❌ Unable to fetch LTP"
            
    except Exception as e:
        message = f"❌ Error fetching LTP: {str(e)}"
        logger.error(f"LTP command error: {e}")
    
    await update.message.reply_text(message, parse_mode="HTML")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    message = (
        f"🤖 <b>ORB Trading Bot Commands</b>\n\n"
        f"/startbot - Activate the bot\n"
        f"/stopbot - Deactivate the bot\n"
        f"/status - Check bot status\n"
        f"/ltp - Get current LTP\n"
        f"/holidaycheck - Check if market is open\n"
        f"/help - Show this help message\n\n"
        f"📈 <b>Current Symbol:</b> {SYMBOL}\n"
        f"🏢 <b>Exchange:</b> {EXCHANGE}"
    )
    await update.message.reply_text(message, parse_mode="HTML")

def main():
    """Main function"""
    # Validate environment variables
    required_vars = [API_KEY, CLIENT_ID, PIN, TOTP_SECRET, TELEGRAM_TOKEN, CHAT_ID]
    if not all(required_vars):
        logger.error("Missing required environment variables")
        return
    
    # Start web server
    keep_alive()
    
    # Initialize bot state
    BotState.set_active(False)
    
    # Create Telegram application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("startbot", start_command))
    application.add_handler(CommandHandler("stopbot", stop_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("holidaycheck", holiday_command))
    application.add_handler(CommandHandler("ltp", ltp_command))
    application.add_handler(CommandHandler("help", help_command))
    
    # Start the bot
    logger.info("Starting Telegram bot...")
    
    # Run both the bot and ORB strategy
    async def run_bot():
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        
        # Start ORB strategy
        trader = ORBTrader()
        await trader.run_orb_strategy()
    
    # Run the async main loop
    asyncio.run(run_bot())

if __name__ == "__main__":
    main()
