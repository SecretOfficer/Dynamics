import pandas as pd
from data_loader import download_data
from indicators import calculate_indicators
from strategy import apply_strategy
from backtester import Backtester

def main():
    # 1. Load Data
    ticker = "BTC-USD"
    print(f"Loading data for {ticker}...")
    df_raw = download_data(ticker, period="5y")
    
    # 2. Define Configurations
    
    # Config A: Aggressive (Trend Following Pure)
    # Optimized for Max Total Return
    params_aggressive = {
        'trend_ema': 200,
        'fast_ema': 15,
        'slow_ema': 26, 
        'signal_ema': 9,
        'atr_period': 14,
        'atr_mult': 1.5,
        'rsi_upper': 80,
        'rsi_lower': 25,
        'enable_trailing': False, 
        'enable_partial_take_profit': False,
        'risk_per_trade': 0.95
    }
    
    # Config B: Safe (Risk Managed)
    # Optimized for Win Rate and Lower Drawdown
    params_safe = params_aggressive.copy()
    params_safe.update({
        'enable_trailing': True,
        'trailing_trigger_atr': 3.0, # Wait for big move
        'trailing_dist_atr': 1.0,     # Then trail tight
        'enable_partial_take_profit': True,
        'take_profit_atr': 3.0,      # Bank 50% profit at 3x Risk
        'tp_size': 0.5,
        'risk_per_trade': 0.95       # Keep sizing same for comparison
    })
    
    # 3. Calculate Indicators
    df = calculate_indicators(df_raw, extra_emas=[200, 15, 26])
    
    # 4. Run Backtests
    print("\nRunning Backtests...")
    
    # Aggressive
    df_agg = apply_strategy(df.copy(), params_aggressive)
    bt_agg = Backtester(df_agg, initial_capital=10000, params=params_aggressive)
    tra_agg, _ = bt_agg.run()
    m_agg = bt_agg.get_metrics()
    
    # Safe
    df_safe = apply_strategy(df.copy(), params_safe)
    bt_safe = Backtester(df_safe, initial_capital=10000, params=params_safe)
    tra_safe, _ = bt_safe.run()
    m_safe = bt_safe.get_metrics()
    
    # 5. Print Comparison
    print("\n" + "="*65)
    print(f"{'METRIC':<25} | {'AGGRESSIVE':<15} | {'SAFE (RISK MGD)':<15}")
    print("="*65)
    
    metrics_to_show = ['Total Return %', 'Annualized Return %', 'Max Drawdown %', 'Win Rate %', 'Sharpe Ratio', 'Sortino Ratio', 'Total Trades']
    
    for k in metrics_to_show:
        v1 = m_agg.get(k, 0)
        v2 = m_safe.get(k, 0)
        print(f"{k:<25} | {v1:>12.2f}    | {v2:>12.2f}")
        
    print("-" * 65)
    print("\n[Analysis]")
    print(f"Aggressive: Higher Profit ({m_agg['Total Return %']:.0f}%) but deeper Drawdown.")
    print(f"Safe:       Higher Win Rate ({m_safe['Win Rate %']:.0f}%) but lower Profit ({m_safe['Total Return %']:.0f}%) due to early exits.")
    
    # Save Trade Logs
    tra_agg.to_csv("trades_aggressive.csv")
    tra_safe.to_csv("trades_safe.csv")
    print("\nTrades saved to trades_aggressive.csv and trades_safe.csv")

if __name__ == "__main__":
    main()
