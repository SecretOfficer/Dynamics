import pandas as pd
from data_loader import download_data
from indicators import calculate_indicators
from strategy import apply_strategy
from backtester import Backtester

def main():
    ticker = "BTC-USD"
    print(f"Loading data for {ticker}...")
    df_raw = download_data(ticker, period="5y")
    
    # Common Params (Best from previous opt)
    common_params = {
        'trend_ema': 200,
        'fast_ema': 15,
        'slow_ema': 26,
        'signal_ema': 9,
        'atr_period': 14,
        'atr_mult': 1.5,
        'rsi_upper': 80,
        'rsi_lower': 25,
        # Risk Sizing
        'risk_per_trade': 0.95 # Comparisons using full equity to isolate strategy logic impact
    }
    
    # 1. Baseline Config
    params_base = common_params.copy()
    params_base.update({
        'enable_trailing': False,
        'enable_partial_take_profit': False
    })
    
    # 2. Risk Managed Config
    params_safe = common_params.copy()
    params_safe.update({
        'enable_trailing': True,
        'trailing_trigger_atr': 2.0,
        'trailing_dist_atr': 1.5,
        'enable_partial_take_profit': True,
        'take_profit_atr': 3.0, # at 3x ATR profit
        'tp_size': 0.5 # Sell 50%
    })

    # 3. Volatility Sizing Config (Smart Risk)
    params_vol = common_params.copy()
    params_vol.update({
        'risk_per_trade': 0.02, # Risk 2% of equity per trade
        'enable_trailing': False, # Keep base logic for fair comparison
        'enable_partial_take_profit': False
    })

    # Prepare Data
    df = calculate_indicators(df_raw, extra_emas=[200, 15, 26])
    df = apply_strategy(df, common_params) # Strategy signals are same for both
    
    print("\nRunning BASELINE Strategy (Fixed 95%)...")
    bt_base = Backtester(df, initial_capital=10000, params=params_base)
    _, _ = bt_base.run()
    m_base = bt_base.get_metrics()
    
    print("\nRunning SAFE Strategy (Trailing + Partial)...")
    bt_safe = Backtester(df, initial_capital=10000, params=params_safe)
    _, _ = bt_safe.run()
    m_safe = bt_safe.get_metrics()
    
    print("\nRunning VOLATILITY Strategy (2% Risk)...")
    bt_vol = Backtester(df, initial_capital=10000, params=params_vol)
    _, _ = bt_vol.run()
    m_vol = bt_vol.get_metrics()
    
    # Compare
    print("\n" + "="*70)
    print(f"{'Metric':<25} | {'Baseline':<10} | {'Safe':<10} | {'Vol Sizing':<10}")
    print("-" * 70)
    for k in ['Total Return %', 'Annualized Return %', 'Max Drawdown %', 'Win Rate %', 'Total Trades']:
        v1 = m_base.get(k, 0)
        v2 = m_safe.get(k, 0)
        v3 = m_vol.get(k, 0)
        print(f"{k:<25} | {v1:>10.2f} | {v2:>10.2f} | {v3:>10.2f}")
    print("="*70)

if __name__ == "__main__":
    main()
