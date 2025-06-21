from SmartApi.smartConnect import SmartConnect
import pyotp
import pandas as pd
from datetime import datetime, time as dt_time
from telegram.ext import Updater, CommandHandler
import json, os, time as t
from flask import Flask
from threading import Thread
import requests

API_KEY = "CiF2inxi"
CLIENT_ID = "AAAA395482"
PIN = "0606"
TOTP_SECRET = "EHKKI4ZSK2NB5ASPA2ZQZTMDEU"

SYMBOL = "RELIANCE-EQ"
SYMBOL_TOKEN = "2885"
EXCHANGE = "NSE"
INTERVAL = "FIFTEEN_MINUTE"
MIN_VOLUME = 50000

TELEGRAM_TOKEN = "8016733264:AAF_gGVuvJzpZUohC9RdFkpyQu6VkHFVWGM"
CHAT_ID = "6439203415"
STATE_FILE = "bot_state.json"

# Keep-alive server for Render
app = Flask('')
@app.route('/')
def home():
    return "Bot is running!"
def run_web(): app.run(host='0.0.0.0', port=8080)
def keep_alive(): Thread(target=run_web).start()

def set_bot_state(active): json.dump({"active": active}, open(STATE_FILE, "w"))
def get_bot_state():
    if not os.path.exists(STATE_FILE): return False
    return json.load(open(STATE_FILE)).get("active", False)

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

def login():
    totp = pyotp.TOTP(TOTP_SECRET).now()
    obj = SmartConnect(api_key=API_KEY)
    data = obj.generateSession(CLIENT_ID, PIN, totp)
    if data.get("status") and "jwtToken" in data["data"]:
        send_telegram("✅ ORB Bot Logged in")
        return obj
    else:
        send_telegram("❌ Login Failed")
        exit()

def get_opening_range(obj):
    today = datetime.now().strftime('%Y-%m-%d')
    from_time = f"{today} 09:15"
    to_time = f"{today} 09:30"
    candles = obj.getCandleData({
        "exchange": EXCHANGE,
        "symboltoken": SYMBOL_TOKEN,
        "interval": INTERVAL,
        "tradingsymbol": SYMBOL,
        "fromdate": from_time,
        "todate": to_time
    })['data']
    df = pd.DataFrame(candles, columns=['Time', 'Open', 'High', 'Low', 'Close', 'Volume'])
    return df['High'].max(), df['Low'].min(), df['Volume'].sum()

def get_ltp(obj):
    try:
        data = obj.ltpData(exchange=EXCHANGE, tradingsymbol=SYMBOL, symboltoken=SYMBOL_TOKEN)
        return float(data['data']['ltp'])
    except: return None

def run_orb_loop():
    obj = login()
    while datetime.now().time() < dt_time(9, 30):
        t.sleep(10)
    high, low, vol = get_opening_range(obj)
    send_telegram(f"📌 ORB:\nHigh: ₹{high}\nLow: ₹{low}\nVol: {vol}")
    signal_sent = False
    while datetime.now().time() < dt_time(15, 15):
        if not get_bot_state(): t.sleep(30); continue
        ltp = get_ltp(obj)
        if ltp and not signal_sent:
            if ltp > high:
                send_telegram(f"📈 BUY Signal – ₹{ltp} > ₹{high}")
                signal_sent = True
            elif ltp < low:
                send_telegram(f"📉 SELL Signal – ₹{ltp} < ₹{low}")
                signal_sent = True
        t.sleep(60)

def start(update, context): set_bot_state(True); context.bot.send_message(chat_id=update.effective_chat.id, text="✅ Bot Activated")
def stop(update, context): set_bot_state(False); context.bot.send_message(chat_id=update.effective_chat.id, text="⛔ Bot Deactivated")
def status(update, context):
    now = datetime.now().strftime('%H:%M:%S')
    s = get_bot_state()
    msg = f"📊 Bot is {'🟢 ON' if s else '🔴 OFF'}\\nTime: {now}\\nSymbol: {SYMBOL}"
Time: {now}
Symbol: {SYMBOL}"
    context.bot.send_message(chat_id=update.effective_chat.id, text=msg)

def holiday(update, context):
    today = datetime.today().weekday()
    msg = "📅 Market CLOSED (Weekend)" if today in [5,6] else "📅 Market is OPEN"
    context.bot.send_message(chat_id=update.effective_chat.id, text=msg)

def main():
    keep_alive()
    set_bot_state(False)
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("startbot", start))
    dp.add_handler(CommandHandler("stopbot", stop))
    dp.add_handler(CommandHandler("status", status))
    dp.add_handler(CommandHandler("holidaycheck", holiday))
    updater.start_polling()
    run_orb_loop()

if __name__ == "__main__":
    main()
