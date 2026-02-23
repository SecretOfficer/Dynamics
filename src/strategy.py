def apply_strategy(df, params=None):
    """
    Applies the trading strategy to the DataFrame.
    """
    df = df.copy()
    
    if params is None:
        params = {}
    
    trend_ema_len = params.get('trend_ema', 200)
    fast_ema = params.get('fast_ema', 12)
    slow_ema = params.get('slow_ema', 26)
    signal_ema = params.get('signal_ema', 9)
    atr_period = params.get('atr_period', 14)
    atr_mult = params.get('atr_mult', 2.0)
    rsi_period = params.get('rsi_period', 14)
    rsi_upper = params.get('rsi_upper', 70)
    rsi_lower = params.get('rsi_lower', 30)

    # Dynamic Column Names
    trend_col = f'EMA_{trend_ema_len}'
    atr_col = f'ATR_{atr_period}'
    rsi_col = f'RSI_{rsi_period}'
    
    # helper for EMAs
    ema_fast_col = f'EMA_{fast_ema}'
    ema_slow_col = f'EMA_{slow_ema}'
    
    # Calculate Custom Cols if missing
    if trend_col not in df.columns:
        df[trend_col] = df['Close'].ewm(span=trend_ema_len, adjust=False).mean()
    if ema_fast_col not in df.columns:
        df[ema_fast_col] = df['Close'].ewm(span=fast_ema, adjust=False).mean()
    if ema_slow_col not in df.columns:
        df[ema_slow_col] = df['Close'].ewm(span=slow_ema, adjust=False).mean()
    if rsi_col not in df.columns:
        # standard RSI calculation if missing
        delta = df['Close'].diff()
        up, down = delta.copy(), delta.copy()
        up[up < 0] = 0
        down[down > 0] = 0
        _gain = up.ewm(com=(rsi_period - 1), min_periods=rsi_period).mean()
        _loss = down.abs().ewm(com=(rsi_period - 1), min_periods=rsi_period).mean()
        RS = _gain / _loss
        df[rsi_col] = 100 - (100 / (1 + RS))
        
    # MACD
    macd_series = df[ema_fast_col] - df[ema_slow_col]
    macd_signal_series = macd_series.ewm(span=signal_ema, adjust=False).mean()
    
    # Trend
    trend_up = df['Close'] > df[trend_col]
    trend_down = df['Close'] < df[trend_col]
    
    # MACD Cross
    prev_macd = macd_series.shift(1)
    prev_signal = macd_signal_series.shift(1)
    current_macd = macd_series
    current_signal = macd_signal_series
    
    crossover_up = (prev_macd < prev_signal) & (current_macd > current_signal)
    crossover_down = (prev_macd > prev_signal) & (current_macd < current_signal)
    
    # RSI Filter
    # Long: RSI < Upper (Not Overbought) OK?
    # Or Buy on Pullback: RSI < 50?
    # Let's simple filter: Don't buy if RSI > Upper. Don't sell if RSI < Lower.
    rsi_ok_long = df[rsi_col] < rsi_upper
    rsi_ok_short = df[rsi_col] > rsi_lower
    
    # Entries
    buy_signal = trend_up & crossover_up & rsi_ok_long
    sell_signal = trend_down & crossover_down & rsi_ok_short
    
    df['Signal'] = 0
    df.loc[buy_signal, 'Signal'] = 1
    df.loc[sell_signal, 'Signal'] = -1
    
    # Exits
    df.loc[trend_up & crossover_down, 'Signal'] = 2
    df.loc[trend_down & crossover_up, 'Signal'] = -2
    
    # Store ATR Mult in DF for backtester to use?
    # Backtester currently reads 'ATR_14' and uses hardcoded * 2.
    # We need to pass atr_mult to backtester or store 'ATR_Stop_Dist' column.
    
    # Better: Calculate 'ATR_Stop_Dist' column
    # Backtester should use this column if it exists, or param.
    # But backtester.py is hardcoded `prev_row['ATR_14']` and `2 * atr`.
    # I should modify Backtester to be generic or hack it here.
    # Hack: I'll modify backtester to look for `ATR_Stop_Dist` col?
    # Or just simpler:
    # I can't pass params to backtester easily without modifying it.
    # I will modify Backtester in `src/backtester.py` to accept `atr_mult` or look for specific column.
    # Let's make Backtester accept `atr_mult` in `__init__` or `run`?
    # Backtester init has `df` and `initial_capital`.
    # I'll update Backtester.
    
    return df

if __name__ == "__main__":
    from data_loader import download_data
    from indicators import calculate_indicators
    
    df = download_data("BTC-USD")
    df = calculate_indicators(df)
    df = apply_strategy(df)
    
    print(df[df['Signal'] != 0].tail())
