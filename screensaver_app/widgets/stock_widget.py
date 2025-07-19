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
        
        # Position in bottom-right corner
        widget_width = 280
        widget_height = 200
        x_pos = screen_width - widget_width - 20
        y_pos = screen_height - widget_height - 80  # Account for taskbar
        
        self.symbols = symbols
        
        self.window.geometry(f"{widget_width}x{widget_height}+{x_pos}+{y_pos}")
        logger.debug(f"StockWidget positioned at {x_pos}x{y_pos} with size {widget_width}x{widget_height}")
        
        # Stock data
        self.stock_data = []
        self.last_update = 0
        self.update_interval = 300  # 5 minutes during market hours
        
        # Popular stock symbols by market
        self.stock_symbols = {
            "NASDAQ": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"],
            "NYSE": ["JPM", "JNJ", "PG", "V", "WMT"],
            "DOW": ["AAPL", "MSFT", "UNH", "GS", "HD"],
            "SP500": ["AAPL", "MSFT", "AMZN", "NVDA", "GOOGL"]
        }
        
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
            
            # Display stock information
            for stock in self.stock_data:
                stock_frame = tk.Frame(self.stock_list_frame, bg=self.transparent_key)
                stock_frame.pack(fill=tk.X, pady=3, padx=5)
                
                # Symbol
                symbol_label = tk.Label(
                    stock_frame, text=stock["symbol"], font=('Arial', 10, 'bold'),
                    fg='white', bg=self.transparent_key, width=6, anchor='w'
                )
                symbol_label.pack(side=tk.LEFT)
                
                # Price
                price_text = f"${stock['price']:.2f}"
                price_label = tk.Label(
                    stock_frame, text=price_text, font=('Arial', 10),
                    fg='white', bg=self.transparent_key, width=8, anchor='e'
                )
                price_label.pack(side=tk.LEFT, padx=(5, 0))
                
                # Change amount and percentage
                change = stock['change']
                change_percent = stock['change_percent']
                
                if change >= 0:
                    change_color = '#00ff88'
                    change_text = f"+${change:.2f} (+{change_percent:.1f}%)"
                else:
                    change_color = '#ff4444'
                    change_text = f"${change:.2f} ({change_percent:.1f}%)"
                
                change_label = tk.Label(
                    stock_frame, text=change_text, font=('Arial', 9),
                    fg=change_color, bg=self.transparent_key, anchor='e'
                )
                change_label.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(5, 0))
            
            # Update status
            self.status_label.config(text=f"Updated: {time.strftime('%H:%M')} • Demo Data")
            
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
                            symbols = self.symbols if self.symbols else self.stock_symbols.get(self.current_market, [])
                            stocks_data = self.fetch_stock_data(symbols)
                            self.stock_data = [
                                {
                                    "symbol": symbol,
                                    "price": data["price"],
                                    "change": data["change"],
                                    "change_percent": data["change_percent"]
                                }
                                for symbol, data in stocks_data.items()
                            ]
                            self.last_update = current_time
                            self.update_stock_display()
                        time.sleep(2)  # Check every 30 seconds
                    else:
                        break
                except tk.TclError:
                    break
                except Exception as e:
                    logger.error(f"Error in stock update cycle: {e}")
                    time.sleep(30)

        # Initial fetch and UI update
        def initial_fetch():
            symbols = self.symbols if self.symbols else self.stock_symbols.get(self.current_market, [])
            stocks_data = self.fetch_stock_data(symbols)
            self.stock_data = [
                {
                    "symbol": symbol,
                    "price": data["price"],
                    "change": data["change"],
                    "change_percent": data["change_percent"]
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

        for symbol in symbols:
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

  
    def _update_stock_display_ui(self, stocks_data):
        """Update stock display in main thread - optimized for performance and alignment"""
        if not self.window.winfo_exists():
            return
        current_time = datetime.now().strftime("%H:%M:%S")
        if not self.last_updated_label:
            self.last_updated_label = tk.Label(
                self.window,
                text=f"Updated: {current_time}",
                bg=self.transparent_key,
                fg='#AAAAAA',
                font=('Segoe UI', 8)
            )
            self.last_updated_label.pack(pady=(0, 3), side=tk.BOTTOM)
        else:
            self.last_updated_label.config(text=f"Updated: {current_time}")

        symbols_to_display = self.markets.get(self.current_market, [])
        for symbol in symbols_to_display:
            data = stocks_data.get(symbol)
            if symbol not in self.stock_labels:
                # This block is a fallback, ideally all labels are pre-created
                row_frame = tk.Frame(self.stock_frame, bg=self.transparent_key) 
                row_frame.pack(fill=tk.X, pady=2, padx=5)
                
                symbol_label = tk.Label(row_frame, text=symbol, bg=self.transparent_key, fg='white', font=('Segoe UI', 10, 'bold'), width=15, anchor='w')
                symbol_label.pack(side=tk.LEFT, padx=(0,5))
                
                price_label = tk.Label(row_frame, bg=self.transparent_key, fg='white', font=('Segoe UI', 10), width=18, anchor='e')
                price_label.pack(side=tk.RIGHT)
                
                self.stock_labels[symbol] = {'frame': row_frame, 'symbol': symbol_label, 'price': price_label}

            if not data: # If data for a symbol is missing after fetch
                self.stock_labels[symbol]['price'].config(text="N/A", fg='gray')
                # Update symbol name to just symbol if company name was previously shown
                self.stock_labels[symbol]['symbol'].config(text=symbol) 
                continue

            # Update existing labels
            price = data['price']
            change = data['change']
            change_percent = data['change_percent']
            
            color = '#00DD00' if change >= 0 else '#DD5555'
            sign = '+' if change >= 0 else ''
            
            currency_symbol = "₹" if self.current_market in ["NSE", "BSE"] else "$"
            
            formatted_price = f"{currency_symbol}{price:,.2f}"
            price_text = f"{formatted_price} ({sign}{change_percent:.2f}%)"
            
            display_name = data.get('name', symbol)
            max_name_len = 18
            shortened_name = display_name[:max_name_len] + '...' if len(display_name) > max_name_len else display_name
            
            self.stock_labels[symbol]['symbol'].config(text=shortened_name) # Update symbol/name
            self.stock_labels[symbol]['price'].config(text=price_text, fg=color) # Update price

            # --- Render and display the graph ---
            closes = data.get('history', [])
            dates = data.get('history_dates', [])
            if closes and len(closes) >= 2:
                fig, ax = plt.subplots(figsize=(1.8, 0.7), dpi=60)
                ax.plot(dates, closes, color='#00BFFF', marker='o', linewidth=2)
                ax.fill_between(dates, closes, min(closes), color='#00BFFF', alpha=0.15)
                ax.set_xticks(dates)
                ax.set_xticklabels(dates, fontsize=6)
                ax.set_yticklabels([])
                ax.set_yticks([])
                ax.set_frame_on(False)
                for spine in ax.spines.values():
                    spine.set_visible(False)
                plt.tight_layout(pad=0.2)
                buf = BytesIO()
                plt.savefig(buf, format='png', bbox_inches='tight', transparent=True, pad_inches=0.05)
                plt.close(fig)
                buf.seek(0)
                pil_img = Image.open(buf)
                photo = ImageTk.PhotoImage(pil_img)
                self.stock_labels[symbol]['graph'].config(image=photo)
                self.stock_labels[symbol]['graph'].image = photo
                self.stock_graphs[symbol] = photo
            else:
                self.stock_labels[symbol]['graph'].config(image='')
                self.stock_graphs[symbol] = None

    def update_stocks(self):
        """Update stock data in background thread"""
        if not self.running or not hasattr(self, 'window') or not self.window.winfo_exists():
            return
            
        def fetch_and_update():
            try:
                symbols = self.markets.get(self.current_market, [])
                stocks_data = self.fetch_stock_data(symbols)
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
