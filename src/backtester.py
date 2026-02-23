import pandas as pd
import numpy as np

class Backtester:
    def __init__(self, df, initial_capital=10000, commission=0.001, params=None):
        """
        initial_capital: USD
        commission: 0.1% per trade
        params: dict with:
            'atr_mult': float (SL distance in ATRs, default 1.5)
            'risk_per_trade': float (0.02 = 2% equity risk, default 0.02)
            'enable_trailing': bool (default False)
            'enable_partial_take_profit': bool (default False)
            'trailing_trigger_atr': float (ATR profit to trigger trail, default 2.0)
            'trailing_dist_atr': float (ATR distance for trail, default 1.5)
            'take_profit_atr': float (ATR distance for partial TP, default 3.0)
            'tp_size': float (Fraction to sell, default 0.5)
        """
        self.df = df.copy()
        self.initial_capital = initial_capital
        self.commission = commission
        self.balance = initial_capital
        self.position = 0 # Amount
        self.stop_loss = 0
        self.entry_price = 0 # Track entry price for TP/SL calculations
        self.trades = []
        self.equity_curve = []
        self.params = params if params else {}
        
        # Risk Params
        self.atr_mult = self.params.get('atr_mult', 1.5)
        self.risk_per_trade = self.params.get('risk_per_trade', 0.95) # Default to 95% if not specified (legacy behavior) or 0.02
        
        # Advanced Features
        self.enable_trailing = self.params.get('enable_trailing', False)
        self.enable_partial_tp = self.params.get('enable_partial_take_profit', False)
        
        self.trailing_trigger_atr = self.params.get('trailing_trigger_atr', 2.0)
        self.trailing_dist_atr = self.params.get('trailing_dist_atr', 1.5)
        
        self.take_profit_atr = self.params.get('take_profit_atr', 3.0)
        self.tp_size = self.params.get('tp_size', 0.5)
        
        self.partial_tp_hit = False # State to track if we already took partial profit in current trade

    def run(self):
        self.position = 0
        self.stop_loss = 0
        self.entry_price = 0
        self.partial_tp_hit = False
        
        for i in range(1, len(self.df)):
            curr_date = self.df.index[i]
            prev_row = self.df.iloc[i-1]
            curr_row = self.df.iloc[i]
            signal = prev_row['Signal']
            current_price = curr_row['Open']
            current_atr = prev_row['ATR_14'] # Use prev ATR for decisions at Open
            
            # Update Equity
            if self.position >= 0:
                current_equity = self.balance + (self.position * curr_row['Close'])
            else:
                cost_to_cover = abs(self.position) * curr_row['Close']
                current_equity = self.balance - cost_to_cover # Crude approximation for short equity
            
            self.equity_curve.append({'Date': curr_date, 'Equity': current_equity})

            # --- 1. Manage Existing Position (SL, TP, Trailing) ---
            if self.position != 0:
                # Check Stop Loss (Intraday High/Low check)
                sl_hit = False
                if self.position > 0:
                    if curr_row['Low'] <= self.stop_loss:
                        self.close_position(curr_date, self.stop_loss, "Stop Loss")
                        sl_hit = True
                elif self.position < 0:
                    if curr_row['High'] >= self.stop_loss:
                        self.close_position(curr_date, self.stop_loss, "Stop Loss")
                        sl_hit = True
                
                if sl_hit: continue # Move to next candle if stopped out
                
                # Check Partial Take Profit
                if self.enable_partial_tp and not self.partial_tp_hit:
                    # Target Prices
                    if self.position > 0:
                        tp_price = self.entry_price + (self.take_profit_atr * current_atr)
                        if curr_row['High'] >= tp_price:
                            # Execute Partial Sell
                            # Close portion
                            sell_amount = self.position * self.tp_size
                            self.close_partial(curr_date, tp_price, sell_amount, "Partial TP")
                            self.partial_tp_hit = True
                            # Move SL to Breakeven? Usually good idea
                            self.stop_loss = max(self.stop_loss, self.entry_price)
                            
                    elif self.position < 0:
                         tp_price = self.entry_price - (self.take_profit_atr * current_atr)
                         if curr_row['Low'] <= tp_price:
                             cover_amount = abs(self.position) * self.tp_size
                             self.close_partial(curr_date, tp_price, cover_amount, "Partial TP")
                             self.partial_tp_hit = True
                             self.stop_loss = min(self.stop_loss, self.entry_price)

                # Update Trailing Stop
                if self.enable_trailing:
                    if self.position > 0:
                        # If price moves in favor
                        # Simple Trail: Highest High - ATR? Or Trigger based?
                        # Logic: If Profit > Trigger, SL = Price - Trail_Dist
                        # Let's use Close price to update trail for Next candle? Or High?
                        # Conservative: Use High to trigger, Close to calculate?
                        # Let's use High/Low
                        
                        current_profit_dist = curr_row['High'] - self.entry_price
                        if current_profit_dist > (self.trailing_trigger_atr * current_atr):
                            new_sl = curr_row['High'] - (self.trailing_dist_atr * current_atr)
                            self.stop_loss = max(self.stop_loss, new_sl)
                            
                    elif self.position < 0:
                        current_profit_dist = self.entry_price - curr_row['Low']
                        if current_profit_dist > (self.trailing_trigger_atr * current_atr):
                            new_sl = curr_row['Low'] + (self.trailing_dist_atr * current_atr)
                            self.stop_loss = min(self.stop_loss, new_sl)


            # --- 2. Process Entry/Exit Signals ---
            # Signals operate on Close of Prev candle (Open of Current)
            
            # Simple State machine for Position Management
            
            # Signal 1: Go Long
            if signal == 1:
                if self.position < 0:
                    self.close_position(curr_date, current_price, "Reverse to Long")
                if self.position == 0:
                    self.open_long(curr_date, current_price, current_atr)
            
            # Signal -1: Go Short
            elif signal == -1:
                if self.position > 0:
                    self.close_position(curr_date, current_price, "Reverse to Short")
                if self.position == 0:
                    self.open_short(curr_date, current_price, current_atr)

            # Signal 2/ -2: Exits
            elif signal == 2 and self.position > 0:
                self.close_position(curr_date, current_price, "Exit Signal")
            elif signal == -2 and self.position < 0:
                self.close_position(curr_date, current_price, "Exit Signal")

        # Close final
        if self.position != 0:
            self.close_position(self.df.index[-1], self.df.iloc[-1]['Close'], "Final Close")
            
        return pd.DataFrame(self.trades), pd.DataFrame(self.equity_curve)

    def calculate_position_size(self, price, atr):
        # Position Size = (Equity * Risk%) / (Stop Distance)
        # Stop Distance = ATR * Mult
        
        # Determine Equity to base risk on
        # For Short, Balance is high because of proceeds? No, Balance is cash.
        # Use initial capital or current equity? Current Equity is compounding.
        # Estimate equity:
        if self.position == 0:
            equity = self.balance
        else:
            # Should be flat here if opening new
            equity = self.balance
            
        # Stop Distance
        stop_dist = atr * self.atr_mult
        
        if self.risk_per_trade > 0.5: 
            # Legacy/Aggressive mode: Risk % is actually Position % (e.g. 0.95)
            # Size = Equity * Fraction
            risk_amt = equity * self.risk_per_trade
            amount = risk_amt / price
        else:
            # Volatility Sizing Mode
            # Risk Amount = Equity * Risk% (e.g. 10,000 * 0.02 = 200)
            # Size = 200 / Stop_Dist
            risk_amt = equity * self.risk_per_trade
            amount = risk_amt / stop_dist
            
        return amount

    def open_long(self, date, price, atr):
        amount = self.calculate_position_size(price, atr)
        cost = amount * price
        
        # Check cash?
        if cost > self.balance:
            amount = self.balance / price
            cost = amount * price
            
        fee = cost * self.commission
        self.balance -= (cost + fee)
        self.position = amount
        self.entry_price = price
        self.stop_loss = price - (self.atr_mult * atr)
        self.partial_tp_hit = False
        self.trades.append({'Type': 'Buy Long', 'Date': date, 'Price': price, 'Amount': amount, 'Fee': fee, 'Balance': self.balance})

    def open_short(self, date, price, atr):
        amount = self.calculate_position_size(price, atr)
        
        # Margin Check?
        # Assuming we can short up to Equity value (1x)
        # Or just allow based on calculation.
        
        proceeds = amount * price
        fee = proceeds * self.commission
        self.balance += (proceeds - fee)
        self.position = -amount
        self.entry_price = price
        self.stop_loss = price + (self.atr_mult * atr)
        self.partial_tp_hit = False
        self.trades.append({'Type': 'Sell Short', 'Date': date, 'Price': price, 'Amount': amount, 'Fee': fee, 'Balance': self.balance})

    def close_position(self, date, price, reason):
        if self.position == 0: return
        
        amount = abs(self.position)
        if self.position > 0:
            value = amount * price
            fee = value * self.commission
            self.balance += (value - fee)
            self.trades.append({'Type': 'Sell Close', 'Date': date, 'Price': price, 'Amount': amount, 'Fee': fee, 'Balance': self.balance, 'Reason': reason})
        else:
            cost = amount * price
            fee = cost * self.commission
            self.balance -= (cost + fee)
            self.trades.append({'Type': 'Buy Close', 'Date': date, 'Price': price, 'Amount': amount, 'Fee': fee, 'Balance': self.balance, 'Reason': reason})
            
        self.position = 0
        self.stop_loss = 0
        self.entry_price = 0
        
    def close_partial(self, date, price, amount, reason):
        if self.position == 0: return
        
        # Reduce position
        if self.position > 0:
            self.position -= amount
            value = amount * price
            fee = value * self.commission
            self.balance += (value - fee)
            self.trades.append({'Type': 'Sell Partial', 'Date': date, 'Price': price, 'Amount': amount, 'Fee': fee, 'Balance': self.balance, 'Reason': reason})
        else:
            self.position += amount # Position is negative, so adding makes it closer to 0
            cost = amount * price
            fee = cost * self.commission
            self.balance -= (cost + fee)
            self.trades.append({'Type': 'Buy Partial', 'Date': date, 'Price': price, 'Amount': amount, 'Fee': fee, 'Balance': self.balance, 'Reason': reason})

    def get_metrics(self):
        if len(self.equity_curve) == 0:
            return {}
            
        equity_df = pd.DataFrame(self.equity_curve).set_index('Date')
        initial = self.initial_capital
        final = equity_df['Equity'].iloc[-1]
        
        # Total Return
        total_return = (final - initial) / initial * 100
        
        # Annualized Return
        days = (equity_df.index[-1] - equity_df.index[0]).days
        years = days / 365.25
        annualized_return = ((final / initial) ** (1 / years) - 1) * 100
        
        # Max Drawdown
        running_max = equity_df['Equity'].cummax()
        drawdown = (equity_df['Equity'] - running_max) / running_max
        max_drawdown = drawdown.min() * 100
        
        # Win Rate
        trades_df = pd.DataFrame(self.trades)
        wins = 0
        losses = 0
        if not trades_df.empty:
            # We need to pair open/close trades to calculate PnL per trade
            # Or simplified: checking balance change on Close signals?
            # Close trades have 'Balance' and 'Reason'.
            # A Close trade PnL is tricky to isolate from just the Balance because Balance changes on Entry too.
            # But we can track PnL in self.trades if we want.
            # Simplified approach: Look at 'Balance' of Close trades vs 'Balance' of previous Open trade?
            # No, Balance on Open decreases (Long) or increases (Short).
            
             # Let's iterate and track PnL properly
             # Or just use the 'Balance' impact?
             # Equity change is the best metric but difficult to attribute to single trade due to overlaps (though we don't overlap).
             
             # Re-implement Win Rate based on closing balance vs opening balance of that trade cycle
             # Since we are always in/out fully, we can track indices.
             
             closed_trades = trades_df[trades_df['Type'].str.contains('Close')]
             
             # This is an approximation. For true winrate we need per-trade PnL.
             # Let's just count based on logic:
             # Long: Exit Price > Entry Price
             # Short: Exit Price < Entry Price
             # (Adjusted for fees)
             
             # We can iterate through trades list
             last_entry = None
             for trade in self.trades:
                 if 'Buy Long' in trade['Type'] or 'Sell Short' in trade['Type']:
                     last_entry = trade
                 elif 'Close' in trade['Type'] and last_entry:
                     # Calculate PnL
                     entry_price = last_entry['Price']
                     exit_price = trade['Price']
                     amount = last_entry['Amount']
                     
                     if 'Long' in last_entry['Type']:
                         # Long PnL
                         gross_pnl = (exit_price - entry_price) * amount
                     else:
                         # Short PnL
                         gross_pnl = (entry_price - exit_price) * amount
                         
                     # Fees
                     entry_fee = last_entry['Fee']
                     exit_fee = trade['Fee']
                     net_pnl = gross_pnl - entry_fee - exit_fee
                     
                     if net_pnl > 0: wins += 1
                     else: losses += 1
                     last_entry = None

        if (wins + losses) > 0:
             win_rate = (wins / (wins + losses)) * 100
        else:
             win_rate = 0
             
        # Calculate Daily Returns based on Equity Curve
        equity_df = pd.DataFrame(self.equity_curve)
        if not equity_df.empty:
            equity_df['Return'] = equity_df['Equity'].pct_change()
            
            # Risk control
            std_dev = equity_df['Return'].std()
            downside_std_dev = equity_df[equity_df['Return'] < 0]['Return'].std()
            
            if std_dev == 0 or np.isnan(std_dev):
                sharpe = 0
            else:
                # Annualized Sharpe (Crypto is 365 days)
                sharpe = (equity_df['Return'].mean() / std_dev) * np.sqrt(365)
                
            if downside_std_dev == 0 or np.isnan(downside_std_dev):
                sortino = 0
            else:
                sortino = (equity_df['Return'].mean() / downside_std_dev) * np.sqrt(365)
        else:
            sharpe = 0
            sortino = 0
        
        return {
            "Initial Capital": initial,
            "Final Equity": final,
            "Total Return %": total_return,
            "Annualized Return %": annualized_return,
            "Max Drawdown %": max_drawdown,
            "Total Trades": wins + losses,
            "Win Rate %": win_rate,
            "Sharpe Ratio": sharpe,
            "Sortino Ratio": sortino
        }

if __name__ == "__main__":
    from data_loader import download_data
    from indicators import calculate_indicators
    from strategy import apply_strategy
    
    df = download_data("BTC-USD")
    df = calculate_indicators(df)
    df = apply_strategy(df)
    
    backtester = Backtester(df)
    trades, equity = backtester.run()
    metrics = backtester.get_metrics()
    
    print("\nMetrics:")
    for k, v in metrics.items():
        print(f"{k}: {v:.2f}")
