import tkinter as tk
from tkinter import ttk
import requests
import json
import threading
import time
from datetime import datetime
import os
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io import BytesIO
from PIL import Image, ImageTk

# Add central logging
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from screensaver_app.central_logger import get_logger, log_startup, log_shutdown, log_exception
logger = get_logger('StockWidget')

class StockWidget:
    def __init__(self, parent_root, transparent_key='#123456', screen_width=0, screen_height=0, initial_market="NASDAQ"):
        logger.info(f"Initializing StockWidget for market: {initial_market}")
        self.parent_root = parent_root 
        self.transparent_key = transparent_key
        # Define top gainers for each market (actual stock symbols)
        self.markets = {
            "NASDAQ": [
                "AAPL",     # Apple Inc.
                "MSFT",     # Microsoft Corporation
                "NVDA",     # NVIDIA Corporation
                "GOOGL",    # Alphabet Inc.
                "AMZN"      # Amazon.com Inc.
            ],
            "NYSE": [
                "BRK-B",    # Berkshire Hathaway Inc.
                "JNJ",      # Johnson & Johnson
                "V",        # Visa Inc.
                "PG",       # Procter & Gamble Company
                "UNH"       # UnitedHealth Group Incorporated
            ],
            "CRYPTO": [
                "BTC-USD",  # Bitcoin
                "ETH-USD",  # Ethereum
                "BNB-USD",  # Binance Coin
                "SOL-USD",  # Solana
                "ADA-USD"   # Cardano
            ],
            "NSE": [
                "RELIANCE.NS",   # Reliance Industries
                "HDFCBANK.NS",   # HDFC Bank
                "INFY.NS",       # Infosys
                "TCS.NS",        # Tata Consultancy Services
                "ICICIBANK.NS"   # ICICI Bank
            ],
            "BSE": [
                "RELIANCE.BO",   # Reliance Industries
                "HDFCBANK.BO",   # HDFC Bank
                "INFY.BO",       # Infosys
                "TCS.BO",        # Tata Consultancy Services
                "ICICIBANK.BO"   # ICICI Bank
            ]
        }
        self.current_market = initial_market
        self.update_interval = 30
        self.running = False
        self.initialized = False

        # Create window immediately but defer content creation to separate thread
        self.window = tk.Toplevel(self.parent_root)
        self.window.overrideredirect(True)
        self.window.attributes('-transparentcolor', self.transparent_key)
        self.window.configure(bg=self.transparent_key)
        self.window.attributes('-topmost', True) 

        widget_width = 350
        # Reduce widget height to fit 5 rows compactly (each row ~38px + title + padding)
        widget_height = 38 * 5 + 40

        if screen_width == 0: screen_width = self.parent_root.winfo_screenwidth()
        if screen_height == 0: screen_height = self.parent_root.winfo_screenheight()

        x_pos = screen_width - widget_width - 20
        y_pos = screen_height - widget_height - 20
        self.window.geometry(f"{widget_width}x{widget_height}+{x_pos}+{y_pos}")
        
        # Initialize UI components in separate thread to avoid blocking video
        self.init_thread = threading.Thread(target=self._initialize_widget_async, daemon=True)
        self.init_thread.start()
        
    def _initialize_widget_async(self):
        """Initialize widget content in separate thread"""
        try:
            # Small delay to ensure video starts smoothly
            time.sleep(0.5)
            
            # Schedule UI creation on main thread
            self.parent_root.after(0, self._create_widget_ui)
        except Exception as e:
            logger.error(f"Error in stock widget async initialization: {e}")
    
    def _create_widget_ui(self):
        """Create widget UI on main thread"""
        try:
            if not self.window.winfo_exists():
                return
                
            self.create_widget_content()
            self.initialized = True
            
        except Exception as e:
            logger.error(f"Error creating stock widget UI: {e}")
        
    def create_widget_content(self):
        """Create the content of the stock widget UI within its Toplevel window"""
        
        title_text = f"Top Gainers - {self.current_market}" 
        title_label = tk.Label(
            self.window, 
            text=title_text,
            bg=self.transparent_key, 
            fg='white',
            font=('Segoe UI', 14, 'bold')
        )
        title_label.pack(pady=(8, 10))
        
        self.stock_frame = tk.Frame(
            self.window, 
            bg=self.transparent_key, 
            relief='flat',
            bd=0
        )
        # Use pack with anchor and fill to ensure vertical stacking
        self.stock_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 2), anchor='s')

        self.stock_labels = {}
        self.stock_graphs = {}

        # Pre-populate with "Loading..." placeholders and graph canvas
        symbols_to_display = self.markets.get(self.current_market, [])
        
        # Clear any existing widgets to avoid overlap
        for widget in self.stock_frame.winfo_children():
            widget.destroy()
        
        for symbol in symbols_to_display:
            row_frame = tk.Frame(self.stock_frame, bg=self.transparent_key, height=34)
            # Use pack with side=TOP, anchor='w', fill=X, and minimal pady for compactness
            row_frame.pack(side=tk.TOP, anchor='w', fill=tk.X, pady=1, padx=0)

            symbol_label = tk.Label(
                row_frame,
                text=symbol,
                bg=self.transparent_key,
                fg='white',
                font=('Segoe UI', 10, 'bold'),
                width=11,
                anchor='w'
            )
            symbol_label.pack(side=tk.LEFT, padx=(0, 2))

            price_label = tk.Label(
                row_frame,
                text="Loading...",
                bg=self.transparent_key,
                fg='#AAAAAA',
                font=('Segoe UI', 10),
                width=13,
                anchor='e'
            )
            price_label.pack(side=tk.LEFT, padx=(0, 2))

            # Add a label for the graph image
            graph_label = tk.Label(
                row_frame,
                bg=self.transparent_key,
                width=70,
                height=24
            )
            graph_label.pack(side=tk.RIGHT, padx=(2, 0))

            self.stock_labels[symbol] = {
                'frame': row_frame,
                'symbol': symbol_label,
                'price': price_label,
                'graph': graph_label
            }
            self.stock_graphs[symbol] = None
            
        self.last_updated_label = None 

        # Start data fetching in separate thread
        self.data_thread = threading.Thread(target=self._start_data_fetching, daemon=True)
        self.data_thread.start()
        
    def _start_data_fetching(self):
        """Start data fetching in completely separate thread"""
        try:
            # Additional delay before first data fetch
            time.sleep(1.0)
            
            self.running = True
            self.update_stocks()
            self._schedule_updates()
            
        except Exception as e:
            logger.error(f"Error starting stock data fetching: {e}")
    
    def _schedule_updates(self):
        """Schedule periodic updates in separate thread"""
        def update_loop():
            while self.running and hasattr(self, 'window'):
                try:
                    if self.window.winfo_exists():
                        time.sleep(self.update_interval)
                        if self.running and self.window.winfo_exists():
                            self.update_stocks()
                    else:
                        break
                except Exception as e:
                    logger.error(f"Error in stock update loop: {e}")
                    break
        
        threading.Thread(target=update_loop, daemon=True).start()

    def on_market_change(self, new_market):
        """Handle market change event"""
        if new_market in self.markets:
            self.current_market = new_market
            self.clear_stock_display() # Clear current stocks
            self.create_widget_content() # Recreate content for new market
        else:
            logger.warning(f"Unknown market: {new_market}")
        
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

    def update_stock_display(self, stocks_data):
        """Update the stock display with new data"""
        if self.window.winfo_exists():
            self.parent_root.after(0, self._update_stock_display_ui, stocks_data)

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
