import tkinter as tk
import threading
import time
import os
import sys
import json
import urllib.request
import urllib.parse
import requests 
from datetime import datetime
import matplotlib.pyplot as plt
from io import BytesIO
from PIL import Image, ImageTk

# Add central logging
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from screensaver_app.central_logger import get_logger
logger = get_logger('StockWidget')

class StockWidget:
    def __init__(self, parent, transparent_key, screen_width, screen_height, initial_market="NASDAQ", symbols=None):
        logger.info(f"Initializing StockWidget for market: {initial_market}")
        self.parent = parent
        self.transparent_key = transparent_key
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.current_market = initial_market
        
        # Create toplevel window
        self.window = tk.Toplevel(parent)
        self.window.title("Stock Widget")
        self.window.attributes('-topmost', True)
        self.window.attributes('-transparentcolor', transparent_key)
        self.window.configure(bg=transparent_key)
        self.window.overrideredirect(True)
        
        # Position in bottom-right corner (closer to bottom)
        widget_width = 320  # Increased width for better layout
        widget_height = 240  # Increased height to fit all 5 stocks
        x_pos = screen_width - widget_width - 50  # Increased right padding
        y_pos = screen_height - widget_height - 50  # Increased bottom padding
        
        # Default symbols for each market
        self.stock_symbols = {
            "NASDAQ": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"],
            "NYSE": ["JPM", "JNJ", "PG", "V", "WMT"],
            "DOW": ["AAPL", "MSFT", "UNH", "GS", "HD"],
            "SP500": ["AAPL", "MSFT", "AMZN", "NVDA", "GOOGL"],
            "CRYPTO": ["BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "DOGE-USD"],
            "NSE": ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS"],
            "BSE": ["500325.BO", "500112.BO", "532540.BO", "500209.BO", "500875.BO"]
        }
        
        # Use the current market's symbols instead of the passed symbols parameter
        self.symbols = self.stock_symbols.get(self.current_market, self.stock_symbols["NASDAQ"])
        
        self.window.geometry(f"{widget_width}x{widget_height}+{x_pos}+{y_pos}")
        logger.debug(f"StockWidget positioned at {x_pos}x{y_pos} with size {widget_width}x{widget_height}")
        
        # Stock data
        self.stock_data = []
        self.last_update = 0
        self.update_interval = 300  # 5 minutes during market hours
        
        # Market names from GUI (referenced)
        self.market_names = ["NASDAQ", "NYSE", "CRYPTO", "NSE", "BSE"]
        
        self.setup_ui()
        self.start_stock_updates()
    
    def setup_ui(self):
        """Setup the stock widget UI"""
        # Header
        header_frame = tk.Frame(self.window, bg=self.transparent_key)
        header_frame.pack(fill=tk.X, padx=15, pady=(10, 5))
        
        icon_label = tk.Label(
            header_frame, text="📈", font=('Arial', 14),
            fg='white', bg=self.transparent_key
        )
        icon_label.pack(side=tk.LEFT)
        
        title_label = tk.Label(
            header_frame, text=f"{self.current_market} Stocks", 
            font=('Arial', 12, 'bold'), fg='white', bg=self.transparent_key
        )
        title_label.pack(side=tk.LEFT, padx=(8, 0))
        
        # Main content frame
        self.main_frame = tk.Frame(self.window, bg=self.transparent_key)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
        
        # Stock list frame
        self.stock_list_frame = tk.Frame(self.main_frame, bg=self.transparent_key)
        self.stock_list_frame.pack(fill=tk.BOTH, expand=True)
        
        # Initial loading message
        loading_label = tk.Label(
            self.stock_list_frame, text="Loading stock data...",
            font=('Arial', 10), fg='#cccccc', bg=self.transparent_key
        )
        loading_label.pack(pady=20)
        
        # Status label
        self.status_label = tk.Label(
            self.window, text="Fetching data...", font=('Arial', 8),
            fg='#888888', bg=self.transparent_key
        )
        self.status_label.pack(side=tk.BOTTOM, pady=5)

    def update_stock_display(self):
        """Update the stock display with current data"""
        import numpy as np
        try:
            # Clear existing stock items
            for widget in self.stock_list_frame.winfo_children():
                widget.destroy()

            if not self.stock_data:
                error_label = tk.Label(
                    self.stock_list_frame, text="No stock data available",
                    font=('Arial', 10), fg='#888888', bg=self.transparent_key
                )
                error_label.pack(pady=20)
                self.status_label.config(text="Error loading stocks")
                return

            # Show first 5 stocks (removed sorting by gains)
            top_stocks = self.stock_data[:5]

            for stock in top_stocks:
                stock_frame = tk.Frame(self.stock_list_frame, bg=self.transparent_key)
                stock_frame.pack(fill=tk.X, pady=1, padx=5)  # Reduced padding for compactness

                # Symbol - shortened and smaller
                symbol = stock["symbol"]
                # Shorten symbol for display
                if "." in symbol:
                    symbol = symbol.split(".")[0][:4]  # Remove suffix and limit to 4 chars
                else:
                    symbol = symbol[:4]  # Limit to 4 characters
                    
                symbol_label = tk.Label(
                    stock_frame, text=symbol, font=('Arial', 9, 'bold'),  # Smaller font
                    fg='white', bg=self.transparent_key, width=4, anchor='w'  # Reduced width
                )
                symbol_label.pack(side=tk.LEFT)

                # Price with currency conversion - smaller font and width
                price = stock['price']
                if self.current_market in ["NSE", "BSE"]:
                    price_text = f"₹{price:.0f}"  # Remove decimal for compactness
                else:
                    price_text = f"${price:.2f}"
                
                price_label = tk.Label(
                    stock_frame, text=price_text, font=('Arial', 9),  # Smaller font
                    fg='white', bg=self.transparent_key, width=6, anchor='e'  # Reduced width
                )
                price_label.pack(side=tk.LEFT, padx=(3, 0))  # Reduced padding

                # Transparent graph for past data using numpy - smaller and no timestamps
                closes = stock.get('history', [])
                dates = stock.get('history_dates', [])
                if closes and len(closes) >= 2:
                    import matplotlib.pyplot as plt
                    from io import BytesIO
                    from PIL import Image, ImageTk
                    closes_np = np.array(closes)
                    fig, ax = plt.subplots(figsize=(1.5, 0.5), dpi=50)  # Smaller graph
                    ax.plot(dates, closes_np, color='#00BFFF', linewidth=1.5)  # Removed markers
                    ax.fill_between(dates, closes_np, closes_np.min(), color='#00BFFF', alpha=0.15)
                    # Remove all axis elements including timestamps
                    ax.set_xticks([])
                    ax.set_yticks([])
                    ax.set_xticklabels([])
                    ax.set_yticklabels([])
                    ax.set_frame_on(False)
                    for spine in ax.spines.values():
                        spine.set_visible(False)
                    plt.tight_layout(pad=0.1)  # Reduced padding
                    fig.patch.set_alpha(0.0)  # Transparent background
                    ax.patch.set_alpha(0.0)
                    buf = BytesIO()
                    plt.savefig(buf, format='png', bbox_inches='tight', transparent=True, pad_inches=0.02)
                    plt.close(fig)
                    buf.seek(0)
                    pil_img = Image.open(buf)
                    photo = ImageTk.PhotoImage(pil_img)
                    graph_label = tk.Label(stock_frame, image=photo, bg=self.transparent_key)
                    graph_label.image = photo
                    graph_label.pack(side=tk.RIGHT, padx=(3, 0))  # Reduced padding

            # Update status (removed "Top 5 Gainers" text)
            self.status_label.config(text=f"Updated: {time.strftime('%H:%M')}")

        except Exception as e:
            logger.error(f"Error updating stock display: {e}")
    
    def start_stock_updates(self):
        """Start the stock update cycle"""
        def update_cycle():
            while True:
                try:
                    if hasattr(self, 'window') and self.window.winfo_exists():
                        current_time = time.time()
                        if current_time - self.last_update > self.update_interval:
                            # Use the symbols for the current market
                            symbols_to_fetch = self.stock_symbols.get(self.current_market, self.stock_symbols["NASDAQ"])
                            stocks_data = self.fetch_stock_data(symbols_to_fetch)
                            self.stock_data = [
                                {
                                    "symbol": symbol,
                                    "price": data["price"],
                                    "change": data["change"],
                                    "change_percent": data["change_percent"],
                                    "history": data.get("history", []),
                                    "history_dates": data.get("history_dates", [])
                                }
                                for symbol, data in stocks_data.items()
                            ]
                            self.last_update = current_time
                            self.update_stock_display()
                        time.sleep(20)  # Check every 20 seconds
                    else:
                        break
                except tk.TclError:
                    break
                except Exception as e:
                    logger.error(f"Error in stock update cycle: {e}")
                    time.sleep(30)

        # Initial fetch and UI update
        def initial_fetch():
            # Use the symbols for the current market
            symbols_to_fetch = self.stock_symbols.get(self.current_market, self.stock_symbols["NASDAQ"])
            stocks_data = self.fetch_stock_data(symbols_to_fetch)
            self.stock_data = [
                {
                    "symbol": symbol,
                    "price": data["price"],
                    "change": data["change"],
                    "change_percent": data["change_percent"],
                    "history": data.get("history", []),
                    "history_dates": data.get("history_dates", [])
                }
                for symbol, data in stocks_data.items()
            ]
            self.last_update = time.time()
            self.update_stock_display()

        threading.Thread(target=initial_fetch, daemon=True).start()
        threading.Thread(target=update_cycle, daemon=True).start()
    
    def destroy(self):
        """Clean up the widget"""
        if hasattr(self, 'window'):
            self.window.destroy()
            logger.warning(f"Unknown market: {self.current_market}")
        
    def clear_stock_display(self):
        """Clear current stock display"""
        for widget in self.stock_frame.winfo_children():
            widget.destroy()
        self.stock_labels.clear()
        
    def fetch_stock_data(self, symbols):
        """Fetch stock data using Yahoo Finance API alternative, including last 5 days for graph"""
        stocks_data = {}

        # Handle both list and dict inputs for symbols
        if isinstance(symbols, dict):
            symbol_list = []
            for v in symbols.values():
                if isinstance(v, list):
                    symbol_list.extend(v)
                else:
                    symbol_list.append(v)
        elif isinstance(symbols, list):
            symbol_list = symbols
        else:
            symbol_list = [symbols]

        for symbol in symbol_list:
            try:
                # Fetch chart data for last 5 days (interval=1d)
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if 'chart' in data and data['chart']['result']:
                        result = data['chart']['result'][0]
                        meta = result['meta']
                        # Get current price
                        current_price = meta.get('regularMarketPrice', 0)
                        if current_price == 0 and 'indicators' in result and 'quote' in result['indicators']:
                            quotes = result['indicators']['quote'][0]
                            if quotes and 'close' in quotes and quotes['close']:
                                closes = [c for c in quotes['close'] if c is not None]
                                if closes:
                                    current_price = closes[-1]
                        prev_close = meta.get('previousClose', 0)
                        change = current_price - prev_close if prev_close else 0
                        change_percent = (change / prev_close * 100) if prev_close else 0
                        company_name = meta.get('shortName', symbol)

                        # Get last 5 days' close prices for graph
                        closes = []
                        dates = []
                        if 'indicators' in result and 'quote' in result['indicators']:
                            closes = result['indicators']['quote'][0].get('close', [])
                        if 'timestamp' in result:
                            timestamps = result['timestamp']
                            # Convert timestamps to date strings
                            dates = [datetime.fromtimestamp(ts).strftime('%m-%d') for ts in timestamps]
                        # Only keep last 5 valid closes and dates
                        closes = [c for c in closes if c is not None]
                        if len(closes) > 5:
                            closes = closes[-5:]
                        if len(dates) > 5:
                            dates = dates[-5:]
                        # If closes and dates mismatch, pad or trim
                        if len(closes) != len(dates):
                            minlen = min(len(closes), len(dates))
                            closes = closes[-minlen:]
                            dates = dates[-minlen:]

                        stocks_data[symbol] = {
                            'name': company_name,
                            'price': current_price,
                            'change': change,
                            'change_percent': change_percent,
                            'timestamp': time.time(),
                            'history': closes,
                            'history_dates': dates
                        }
            except Exception as e:
                logger.error(f"Error fetching data for {symbol}: {e}")
                stocks_data[symbol] = {
                    'name': symbol,
                    'price': 0,
                    'change': 0,
                    'change_percent': 0,
                    'timestamp': time.time(),
                    'history': [],
                    'history_dates': []
                }
                
        # Sort by change_percent to get top gainers
        sorted_data = dict(sorted(stocks_data.items(), 
                                key=lambda x: x[1]['change_percent'], 
                                reverse=True))
        return sorted_data

    def update_stocks(self):
        """Update stock data in background thread"""
        if not self.running or not hasattr(self, 'window') or not self.window.winfo_exists():
            return
            
        def fetch_and_update():
            try:
                symbols = self.markets.get(self.current_market, [])
                stocks_data = self.fetch_stock_data(self.stock_symbols)
                if hasattr(self, 'window') and self.window.winfo_exists():
                    self.update_stock_display(stocks_data)
            except Exception as e:
                logger.error(f"Error in stock fetch and update: {e}")
            
        # Run in separate thread to avoid blocking anything
        threading.Thread(target=fetch_and_update, daemon=True).start()

    def start_updates(self):
        """Start periodic updates"""
        self.running = True
        self.update_stocks()
        self._schedule_updates()
        
    def stop_updates(self):
        """Stop periodic updates"""
        self.running = False
        
    def destroy(self):
        """Clean up widget"""
        self.stop_updates()
        if hasattr(self, 'window') and self.window.winfo_exists():
            self.window.destroy()
        self.update_stocks()
        self._schedule_updates()
        
    def stop_updates(self):
        """Stop periodic updates"""
        self.running = False
        
    def destroy(self):
        """Clean up widget"""
        self.stop_updates()
        if hasattr(self, 'window') and self.window.winfo_exists():
            self.window.destroy()
