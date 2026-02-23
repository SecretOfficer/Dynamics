import yfinance as yf
import pandas as pd
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')

def download_data(ticker, period="5y", interval="1d", force_download=False):
    """
    Downloads historical data for the given ticker.
    
    Args:
        ticker (str): The stock/crypto ticker (e.g., "BTC-USD").
        period (str): The data period to download (e.g., "5y", "1y", "max").
        interval (str): The data interval (e.g., "1d", "1h").
        force_download (bool): If True, force re-download even if file exists.
        
    Returns:
        pd.DataFrame: The historical data.
    """
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    filename = f"{ticker}_{period}_{interval}.csv"
    filepath = os.path.join(DATA_DIR, filename)
    
    if os.path.exists(filepath) and not force_download:
        print(f"Loading data from {filepath}")
        df = pd.read_csv(filepath, index_col=0, parse_dates=True)
    else:
        print(f"Downloading data for {ticker}...")
        df = yf.download(ticker, period=period, interval=interval, progress=False)
        
        # yfinance might return multi-level columns if multiple tickers, but we are doing one by one.
        # Ensure we just get the OHLCV data.
        if isinstance(df.columns, pd.MultiIndex):
             df.columns = df.columns.get_level_values(0)

        # Basic cleaning
        df = df.dropna()
        
        if not df.empty:
            df.to_csv(filepath)
            print(f"Data saved to {filepath}")
        else:
            print(f"No data found for {ticker}")
            
    return df

if __name__ == "__main__":
    # Test the loader
    btc_df = download_data("BTC-USD", period="5y", interval="1d")
    print(btc_df.head())
    print(btc_df.tail())
