# main.py
import os
import json
import time
import logging
from datetime import datetime, time as dt_time, timedelta
from typing import Optional, Tuple

import pandas as pd
import pyotp
import requests
from dotenv import load_dotenv
from flask import Flask
from SmartApi.smartConnect import SmartConnect
from telegram import Update
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackContext,
    Application,
    ContextTypes,
)
from threading import Thread

# Load environment variables
load_dotenv()

# Constants
SYMBOL = "RELIANCE-EQ"
SYMBOL_TOKEN = "2885"
EXCHANGE = "NSE"
INTERVAL = "FIFTEEN_MINUTE"
MIN_VOLUME = 50000
STATE_FILE = "bot_state.json"
OPENING_RANGE_START = dt_time(9, 15)
OPENING_RANGE_END = dt_time(9, 30)
MARKET_CLOSE = dt_time(15, 15)

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TradingBot:
    def __init__(self):
        self.api_key = os.getenv("API_KEY")
        self.client_id = os.getenv("CLIENT_ID")
        self.pin = os.getenv("PIN")
        self.totp_secret = os.getenv("TOTP_SECRET")
        self.telegram_token = os.getenv("TELEGRAM_TOKEN")
        self.chat_id = os.getenv("CHAT_ID")
        self.session = None

    def set_bot_state(self, active: bool) -> None:
        """Save bot state to file."""
        with open(STATE_FILE, "w") as f:
            json.dump({"active": active}, f)

    def get_bot_state(self) -> bool:
        """Get bot state from file."""
        if not os.path.exists(STATE_FILE):
            return False
        with open(STATE_FILE) as f:
            return json.load(f).get("active", False)

    async def send_telegram(self, message: str) -> None:
        """Send message to Telegram."""
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        try:
            response = requests.post(
                url,
                data={"chat_id": self.chat_id, "text": message},
                timeout=10
            )
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Failed to send Telegram message: {e}")

    def login(self) -> SmartConnect:
        """Login to Angel One Smart API."""
        totp = pyotp.TOTP(self.totp_secret).now()
        obj = SmartConnect(api_key=self.api_key)
        data = obj.generateSession(self.client_id, self.pin, totp)
        
        if data.get("status") and "jwtToken" in data["data"]:
            self.session = obj
            logger.info("Login successful")
            return obj
        else:
            logger.error("Login failed")
            raise ConnectionError("Failed to login to Angel One API")

    def get_opening_range(self) -> Tuple[float, float, float]:
        """Get opening range high, low and volume."""
        today = datetime.now().strftime('%Y-%m-%d')
        from_time = f"{today} 09:15"
        to_time = f"{today} 09:30"
        
        try:
            candles = self.session.getCandleData({
                "exchange": EXCHANGE,
                "symboltoken": SYMBOL_TOKEN,
                "interval": INTERVAL,
                "tradingsymbol": SYMBOL,
                "fromdate": from_time,
                "todate": to_time
            })['data']
            
            df = pd.DataFrame(candles, columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume'])
            return df['High'].max(), df['Low'].min(), df['Volume'].sum()
        except Exception as e:
            logger.error(f"Error getting opening range: {e}")
            raise

    def get_ltp(self) -> Optional[float]:
        """Get last traded price."""
        try:
            data = self.session.ltpData(
                exchange=EXCHANGE,
                tradingsymbol=SYMBOL,
                symboltoken=SYMBOL_TOKEN
            )
            return float(data['data']['ltp'])
        except Exception as e:
            logger.error(f"Error getting LTP: {e}")
            return None

    async def run_orb_loop(self) -> None:
        """Main trading loop."""
        self.session = self.login()
        
        # Wait for opening range to complete
        while datetime.now().time() < OPENING_RANGE_END:
            time.sleep(10)
        
        high, low, vol = self.get_opening_range()
        await self.send_telegram(
            f"📌 ORB:\nHigh: ₹{high:.2f}\nLow: ₹{low:.2f}\nVol: {vol:,}"
        )
        
        signal_sent = False
        while datetime.now().time() < MARKET_CLOSE:
            if not self.get_bot_state():
                time.sleep(30)
                continue
            
            ltp = self.get_ltp()
            if ltp and not signal_sent:
                if ltp > high:
                    await self.send_telegram(f"📈 BUY Signal – ₹{ltp:.2f} > ₹{high:.2f}")
                    signal_sent = True
                elif ltp < low:
                    await self.send_telegram(f"📉 SELL Signal – ₹{ltp:.2f} < ₹{low:.2f}")
                    signal_sent = True
            time.sleep(60)

# Telegram command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bot = context.bot_data['trading_bot']
    bot.set_bot_state(True)
    await update.message.reply_text("✅ Bot Activated")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bot = context.bot_data['trading_bot']
    bot.set_bot_state(False)
    await update.message.reply_text("⛔ Bot Deactivated")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bot = context.bot_data['trading_bot']
    now = datetime.now().strftime('%H:%M:%S')
    status_text = (
        f"📊 Bot is {'🟢 ON' if bot.get_bot_state() else '🔴 OFF'}\n"
        f"Time: {now}\nSymbol: {SYMBOL}"
    )
    await update.message.reply_text(status_text)

async def holiday(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    today = datetime.today().weekday()
    msg = "📅 Market CLOSED (Weekend)" if today in [5, 6] else "📅 Market is OPEN"
    await update.message.reply_text(msg)

# Web server for keep-alive
def run_web():
    app = Flask(__name__)
    @app.route('/')
    def home():
        return "Bot is running!"
    app.run(host='0.0.0.0', port=8080)

def main():
    # Start keep-alive server
    Thread(target=run_web, daemon=True).start()

    # Initialize trading bot
    trading_bot = TradingBot()
    trading_bot.set_bot_state(False)

    # Set up Telegram bot
    application = Application.builder().token(trading_bot.telegram_token).build()
    application.bot_data['trading_bot'] = trading_bot
    
    # Add command handlers
    application.add_handler(CommandHandler("startbot", start))
    application.add_handler(CommandHandler("stopbot", stop))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("holidaycheck", holiday))

    # Start the bot
    application.run_polling()

    # Start trading loop
    application.create_task(trading_bot.run_orb_loop())

if __name__ == "__main__":
    main()
