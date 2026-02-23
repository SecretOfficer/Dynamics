import pandas as pd
import itertools
from data_loader import download_data
from indicators import calculate_indicators
from strategy import apply_strategy
from backtester import Backtester

def optimize():
    # Load Data
    ticker = "BTC-USD"
    print(f"Loading data for {ticker}...")
    df_raw = download_data(ticker, period="5y")
    
    # Pre-calculate base indicators (Volume, etc if needed, but we do dynamic mainly)
    # Actually calculate_indicators calculates defaults.
    # We might need to preload some columns if we want to be super fast, but for 5y Daily data (2000 rows), 
    # re-calculating EMAs in loop is fast enough (~100 iterations is instant).
    
    # Define Parameter Grid
    param_grid = {
        'trend_ema': [200], 
        'fast_ema': [15], # Lock to best found
        'slow_ema': [26],
        'signal_ema': [9],
        'atr_period': [14],
        'atr_mult': [1.5],
        'rsi_upper': [80],
        'rsi_lower': [25],
        # Focus on Risk Params
        'enable_trailing': [True, False],
        'trailing_trigger_atr': [1.5, 2.0, 3.0],
        'trailing_dist_atr': [1.0, 1.5],
        'enable_partial_take_profit': [True, False],
        'take_profit_atr': [2.0, 3.0, 4.0],
        'tp_size': [0.5],
        'risk_per_trade': [0.95] # Lock to High Risk for now to compare raw performance logic
    }
    
    keys, values = zip(*param_grid.items())
    combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
    
    print(f"Testing {len(combinations)} combinations...")
    
    results = []
    
    for i, params in enumerate(combinations):
        # Validation: Fast < Slow
        if params['fast_ema'] >= params['slow_ema']:
            continue
            
        try:
            # Prepare data
            # We copy df inside apply_strategy/calculate_indicators so safe to reuse df_raw or close
            
            # Use cached indicators if possible? 
            # For now, just call it.
            df = calculate_indicators(df_raw, extra_emas=[params['trend_ema'], params['fast_ema'], params['slow_ema']])
            
            # Apply Strategy
            df = apply_strategy(df, params)
            
            # Backtest
            bt = Backtester(df, initial_capital=10000, params=params)
            trades, equity = bt.run()
            metrics = bt.get_metrics()
            
            # Helper: Add params to metrics
            metrics.update(params)
            results.append(metrics)
            
            if i % 50 == 0:
                print(f"Processed {i}/{len(combinations)}...")
                
        except Exception as e:
            print(f"Error with params {params}: {e}")
            
    # Convert to DataFrame
    results_df = pd.DataFrame(results)
    
    if results_df.empty:
        print("No valid results found.")
        return

    # Sort by Annualized Return
    results_df = results_df.sort_values(by='Annualized Return %', ascending=False)
    
    print("\nTop 5 Configs:")
    print(results_df[['trend_ema', 'fast_ema', 'slow_ema', 'Annualized Return %', 'Max Drawdown %', 'Win Rate %']].head(5))
    
    # Save to CSV
    results_df.to_csv("optimization_results.csv")
    print("\noptimization_results.csv saved.")
    
    # Recommend Best
    best = results_df.iloc[0]
    print("\nBest Configuration:")
    print(best)

if __name__ == "__main__":
    optimize()
