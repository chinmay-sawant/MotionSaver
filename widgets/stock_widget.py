import tkinter as tk
from tkinter import ttk
import requests
import json
import threading
import time
from datetime import datetime

class StockWidget:
    def __init__(self, parent_root, transparent_key='#123456', screen_width=0, screen_height=0, initial_market="NASDAQ"): # Added initial_market
        self.parent_root = parent_root 
        self.transparent_key = transparent_key
        self.markets = {
            "NASDAQ": ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"],
            "NYSE": ["JPM", "JNJ", "V", "PG", "HD"],
            "CRYPTO": ["BTC-USD", "ETH-USD", "ADA-USD", "DOT-USD"],
            "NSE": ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS"],
            "BSE": ["RELIANCE.BO", "TCS.BO", "HDFCBANK.BO", "INFY.BO", "ICICIBANK.BO"]
        }
        self.current_market = initial_market # Set from argument
        self.update_interval = 30  # Refresh data every 30 seconds
        self.running = False

        self.window = tk.Toplevel(self.parent_root)
        self.window.overrideredirect(True)
        self.window.attributes('-transparentcolor', self.transparent_key)
        self.window.configure(bg=self.transparent_key)
        self.window.attributes('-topmost', True) 

        widget_width = 350 # Increased width for better text display
        widget_height = 200 # Adjusted height
        
        if screen_width == 0: screen_width = self.parent_root.winfo_screenwidth()
        if screen_height == 0: screen_height = self.parent_root.winfo_screenheight()

        x_pos = screen_width - widget_width - 20
        y_pos = screen_height - widget_height - 20
        self.window.geometry(f"{widget_width}x{widget_height}+{x_pos}+{y_pos}")
        
        self.create_widget_content()
        
    def create_widget_content(self):
        """Create the content of the stock widget UI within its Toplevel window"""
        
        title_text = f"Stock Market - {self.current_market}" # Display current market in title
        title_label = tk.Label(
            self.window, 
            text=title_text,
            bg=self.transparent_key, 
            fg='white',
            font=('Arial', 14, 'bold')
        )
        title_label.pack(pady=(8, 10)) # Increased bottom padding
        
        # Market selector and refresh button are removed.
        
        self.stock_frame = tk.Frame(
            self.window, 
            bg=self.transparent_key, 
            relief='flat',
            bd=0
        )
        self.stock_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5) # Added more padx
        
        self.stock_labels = {}
        self.start_updates()
        
    def clear_stock_display(self):
        """Clear current stock display"""
        for widget in self.stock_frame.winfo_children():
            widget.destroy()
        self.stock_labels.clear()
        
    def fetch_stock_data(self, symbols):
        """Fetch stock data using Yahoo Finance API alternative"""
        stocks_data = {}
        
        for symbol in symbols:
            try:
                # Use Yahoo Finance API with proper headers
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'chart' in data and data['chart']['result']:
                        result = data['chart']['result'][0]
                        meta = result['meta']
                        
                        # Get current price - ensure we get the latest data
                        current_price = meta.get('regularMarketPrice', 0)
                        # If no regularMarketPrice, try to get the latest price from the quote data
                        if current_price == 0 and 'indicators' in result and 'quote' in result['indicators']:
                            quotes = result['indicators']['quote'][0]
                            if quotes and 'close' in quotes and quotes['close']:
                                closes = [c for c in quotes['close'] if c is not None]
                                if closes:
                                    current_price = closes[-1]
                        
                        prev_close = meta.get('previousClose', 0)
                        change = current_price - prev_close if prev_close else 0
                        change_percent = (change / prev_close * 100) if prev_close else 0
                        
                        # Get company name if available
                        company_name = meta.get('shortName', symbol)
                        
                        stocks_data[symbol] = {
                            'name': company_name,
                            'price': current_price,
                            'change': change,
                            'change_percent': change_percent,
                            'timestamp': time.time()  # Add timestamp for freshness check
                        }
                        
            except Exception as e:
                print(f"Error fetching data for {symbol}: {e}")
                stocks_data[symbol] = {
                    'name': symbol,
                    'price': 0,
                    'change': 0,
                    'change_percent': 0,
                    'timestamp': time.time()
                }
                
        return stocks_data
        
    def update_stock_display(self, stocks_data): # Ensure this method checks if window exists
        """Update the stock display with new data"""
        if self.window.winfo_exists():
            self.parent_root.after(0, self._update_stock_display_ui, stocks_data)
        
    def _update_stock_display_ui(self, stocks_data):
        """Update stock display in main thread - optimized for performance and alignment"""
        if not self.window.winfo_exists(): 
            return

        # No need to check self.last_update_market as market is fixed per instance
        # self.clear_stock_display() # Clear previous entries before adding new ones
        # Optimized: Instead of full clear, update existing or add new.
        # For simplicity with fixed list, full clear is okay if list size is small.
        # Let's try updating/creating to avoid flicker.

        current_time = datetime.now().strftime("%H:%M:%S") # Added seconds to see updates
        
        if not hasattr(self, 'last_updated_label'):
            self.last_updated_label = tk.Label(
                self.window, 
                text=f"Updated: {current_time}",
                bg=self.transparent_key, 
                fg='#AAAAAA',
                font=('Arial', 8)
            )
            # Pack it at the bottom of self.window, after stock_frame
            self.last_updated_label.pack(pady=(0, 3), side=tk.BOTTOM)
        else:
            self.last_updated_label.config(text=f"Updated: {current_time}")

        # Get current symbols for the fixed market
        symbols_to_display = self.markets.get(self.current_market, [])
        
        # Remove labels for symbols no longer in the list (if any dynamic change happened, though not expected now)
        for symbol_key in list(self.stock_labels.keys()):
            if symbol_key not in stocks_data:
                self.stock_labels[symbol_key]['frame'].destroy()
                del self.stock_labels[symbol_key]

        for symbol in symbols_to_display: # Iterate in defined order
            data = stocks_data.get(symbol)
            if not data: # If data for a symbol is missing, skip or show placeholder
                if symbol not in self.stock_labels: # Create placeholder if not exists
                    row_frame = tk.Frame(self.stock_frame, bg=self.transparent_key)
                    row_frame.pack(fill=tk.X, pady=2, padx=5)
                    
                    symbol_label = tk.Label(row_frame, text=symbol, bg=self.transparent_key, fg='gray', font=('Arial', 10, 'bold'), width=15, anchor='w')
                    symbol_label.pack(side=tk.LEFT, padx=(0,5))
                    
                    price_label = tk.Label(row_frame, text="N/A", bg=self.transparent_key, fg='gray', font=('Arial', 10), width=18, anchor='e')
                    price_label.pack(side=tk.RIGHT)
                    self.stock_labels[symbol] = {'frame': row_frame, 'symbol': symbol_label, 'price': price_label}
                else: # Update existing placeholder
                    self.stock_labels[symbol]['price'].config(text="N/A", fg='gray')
                continue

            if symbol not in self.stock_labels:
                row_frame = tk.Frame(self.stock_frame, bg=self.transparent_key) 
                row_frame.pack(fill=tk.X, pady=2, padx=5) # Added padx for internal spacing
                
                # Symbol/Name Label - increased width
                symbol_label = tk.Label(
                    row_frame, 
                    text=symbol, 
                    bg=self.transparent_key, 
                    fg='white',
                    font=('Arial', 10, 'bold'),
                    width=15, # Increased width for longer names/symbols
                    anchor='w' # Align text to the left
                )
                symbol_label.pack(side=tk.LEFT, padx=(0,5)) # Add some space between symbol and price
                
                # Price Label - increased width
                price_label = tk.Label(
                    row_frame, 
                    bg=self.transparent_key, 
                    fg='white',
                    font=('Arial', 10),
                    width=18, # Increased width for price and change %
                    anchor='e' # Align text to the right
                )
                price_label.pack(side=tk.RIGHT)
                
                self.stock_labels[symbol] = {
                    'frame': row_frame,
                    'symbol': symbol_label,
                    'price': price_label
                }
            
            price = data['price']
            change = data['change']
            change_percent = data['change_percent']
            
            color = '#00DD00' if change >= 0 else '#DD5555'
            sign = '+' if change >= 0 else ''
            
            currency_symbol = "₹" if self.current_market in ["NSE", "BSE"] else "$"
            
            formatted_price = f"{currency_symbol}{price:,.2f}" # Restored 2 decimal places for price
            price_text = f"{formatted_price} ({sign}{change_percent:.2f}%)" # Restored 2 decimal places for %
            
            # Use company name if available, otherwise symbol
            display_name = data.get('name', symbol)
            # Truncate if too long for the allocated width
            max_name_len = 18 # Adjust based on font and width
            shortened_name = display_name[:max_name_len] + '...' if len(display_name) > max_name_len else display_name
            
            self.stock_labels[symbol]['symbol'].config(text=shortened_name)
            self.stock_labels[symbol]['price'].config(text=price_text, fg=color)

    def update_stocks(self):
        """Update stock data in background thread"""
        if not self.running or not self.window.winfo_exists(): # Check if window still exists
            return
            
        def fetch_and_update():
            symbols = self.markets.get(self.current_market, [])
            stocks_data = self.fetch_stock_data(symbols)
            if self.window.winfo_exists(): # Check again before calling update_stock_display
                self.update_stock_display(stocks_data)
            
        thread = threading.Thread(target=fetch_and_update, daemon=True)
        thread.start()
        
    def start_updates(self):
        """Start periodic updates"""
        self.running = True
        self.update_stocks()
        self.schedule_next_update()
        
    def schedule_next_update(self):
        """Schedule next update"""
        if self.running and self.window.winfo_exists(): # Check if window still exists
            self.parent_root.after(self.update_interval * 1000, self.update_stocks)
            self.parent_root.after(self.update_interval * 1000, self.schedule_next_update)
        
    def stop_updates(self):
        """Stop periodic updates"""
        self.running = False
        
    def destroy(self):
        """Clean up widget"""
        self.stop_updates()
        if hasattr(self, 'window') and self.window.winfo_exists():
            self.window.destroy()
