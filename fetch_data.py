# fetch_data.py
from smartapi import SmartConnect
from config import API_KEY, CLIENT_ID, PASSWORD, DOB
from datetime import datetime, timedelta
import pandas as pd

def fetch_reliance_data():
    obj = SmartConnect(api_key=API_KEY)
    session = obj.generateSession(CLIENT_ID, PASSWORD, DOB)
    token = "2885"  # NSE RELIANCE token
    to_date = datetime.now()
    from_date = to_date - timedelta(days=30)

    data = obj.getCandleData(
        token=token,
        interval="FIVE_MINUTE",
        fromdate=from_date.strftime("%Y-%m-%d %H:%M"),
        todate=to_date.strftime("%Y-%m-%d %H:%M")
    )
    df = pd.DataFrame(data['data'], columns=["date", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    df.to_csv("reliance_data.csv")
    return df

if __name__ == "__main__":
    fetch_reliance_data()
