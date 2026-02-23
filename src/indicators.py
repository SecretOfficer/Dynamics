import pandas as pd
import numpy as np

def calculate_indicators(df, extra_emas=None):
    """
    Adds technical indicators to the DataFrame.
    extra_emas: list of integers for additional EMA spans.
    """
    df = df.copy()
    
    # Ensure 'Close' is present
    if 'Close' not in df.columns:
        raise ValueError("DataFrame must contain 'Close' column")

    close = df['Close']
    high = df['High']
    low = df['Low']

    # 1. Moving Averages
    # Default set
    spans = [12, 26, 50, 200]
    if extra_emas:
        spans.extend(extra_emas)
    spans = sorted(list(set(spans))) # Unique and sorted
    
    for span in spans:
        df[f'EMA_{span}'] = close.ewm(span=span, adjust=False).mean()
        
    df['SMA_50'] = close.rolling(window=50).mean()
    df['SMA_200'] = close.rolling(window=200).mean()

    # 2. RSI (Relative Strength Index)
    # Smoothed RSI (Standard Wilder's RSI)
    delta = close.diff()
    up, down = delta.copy(), delta.copy()
    up[up < 0] = 0
    down[down > 0] = 0
    _gain = up.ewm(com=(14 - 1), min_periods=14).mean()
    _loss = down.abs().ewm(com=(14 - 1), min_periods=14).mean()
    RS = _gain / _loss
    df['RSI_14'] = 100 - (100 / (1 + RS))


    # 3. MACD (Standard 12, 26, 9)
    df['MACD'] = df['EMA_12'] - df['EMA_26']
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

    # 4. Bollinger Bands
    df['BB_Middle'] = close.rolling(window=20).mean()
    df['BB_Std'] = close.rolling(window=20).std()
    df['BB_Upper'] = df['BB_Middle'] + (2 * df['BB_Std'])
    df['BB_Lower'] = df['BB_Middle'] - (2 * df['BB_Std'])

    # 5. ATR (Average True Range)
    # TR = Max(High - Low, abs(High - PrevClose), abs(Low - PrevClose))
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(window=14).mean() # Simple moving average of TR
    # Wilder's Smoothing for ATR
    df['ATR_14'] = tr.ewm(alpha=1/14, adjust=False).mean()

    return df.dropna()

if __name__ == "__main__":
    from data_loader import download_data
    df = download_data("BTC-USD")
    df = calculate_indicators(df)
    print(df[['Close', 'SMA_50', 'RSI_14', 'MACD', 'ATR_14']].tail())
