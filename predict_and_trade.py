# predict_and_trade.py
import numpy as np
import pandas as pd
from tensorflow.keras.models import load_model
from sklearn.preprocessing import MinMaxScaler
from smartapi import SmartConnect
from config import API_KEY, CLIENT_ID, PASSWORD, DOB

model = load_model("lstm_model.h5")
scaler = MinMaxScaler()
scaler.min_, scaler.scale_ = np.load("scaler_min.npy"), 1 / (np.load("scaler_max.npy") - np.load("scaler_min.npy"))

df = pd.read_csv("reliance_data.csv")[["open", "high", "low", "close", "volume"]]
scaled = scaler.transform(df)
last_60 = np.expand_dims(scaled[-60:], axis=0)
predicted = model.predict(last_60)
predicted_price = scaler.inverse_transform([[0,0,0,predicted[0][0],0]])[0][3]
last_close = df["close"].iloc[-1]

signal = "HOLD"
if predicted_price > last_close * 1.002:
    signal = "BUY"
elif predicted_price < last_close * 0.998:
    signal = "SELL"

if signal in ["BUY", "SELL"]:
    obj = SmartConnect(api_key=API_KEY)
    session = obj.generateSession(CLIENT_ID, PASSWORD, DOB)
    token = "2885"
    order = obj.placeOrder(
        variety="NORMAL",
        tradingsymbol="RELIANCE-EQ",
        symboltoken=token,
        transactiontype=signal,
        exchange="NSE",
        ordertype="MARKET",
        producttype="INTRADAY",
        duration="DAY",
        quantity=1,
        price=0,
        squareoff=0,
        stoploss=0
    )
    print(f"{signal} Order Placed:", order)
else:
    print("No action taken")
