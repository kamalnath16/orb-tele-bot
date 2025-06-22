# train_lstm.py
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense

def create_dataset(data, time_step=60):
    X, y = [], []
    for i in range(len(data)-time_step-1):
        X.append(data[i:(i+time_step), :])
        y.append(data[i + time_step, 3])
    return np.array(X), np.array(y)

df = pd.read_csv("reliance_data.csv")
df = df[["open", "high", "low", "close", "volume"]].dropna()
scaler = MinMaxScaler()
scaled = scaler.fit_transform(df)

X, y = create_dataset(scaled)
model = Sequential([
    LSTM(50, return_sequences=True, input_shape=(X.shape[1], X.shape[2])),
    LSTM(50),
    Dense(1)
])
model.compile(optimizer="adam", loss="mse")
model.fit(X, y, epochs=10, batch_size=32)
model.save("lstm_model.h5")
np.save("scaler_min.npy", scaler.data_min_)
np.save("scaler_max.npy", scaler.data_max_)
