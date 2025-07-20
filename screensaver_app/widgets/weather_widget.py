import tkinter as tk
from tkinter import ttk
import threading
import time
import os
import sys

# Ensure parent directory is in sys.path for package imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Add central logging
from screensaver_app.central_logger import get_logger, log_startup, log_shutdown, log_exception
logger = get_logger('WeatherWidget')

from .weather_api import get_weather_data

class WeatherWidget:
    def __init__(self, parent, transparent_key, screen_width, screen_height, pincode="400068", country_code="IN"):
        logger.info(f"Initializing WeatherWidget for location {pincode}, {country_code}")
        self.parent = parent
        self.transparent_key = transparent_key
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.pincode = pincode
        self.country_code = country_code
        
        # Create toplevel window
        self.window = tk.Toplevel(parent)
        self.window.title("Weather Widget")
        self.window.attributes('-topmost', True)
        self.window.attributes('-transparentcolor', transparent_key)
        self.window.configure(bg=transparent_key)
        self.window.overrideredirect(True)
        
        # Position in top-right corner with margin
        widget_width = 320
        widget_height = 300
        x_pos = screen_width - widget_width - 20
        y_pos = 20
        
        self.window.geometry(f"{widget_width}x{widget_height}+{x_pos}+{y_pos}")
        logger.debug(f"WeatherWidget positioned at {x_pos}x{y_pos} with size {widget_width}x{widget_height}")
        
        # Weather data
        self.weather_data = None
        self.last_update = 0
        self.update_interval = 1800  # 30 minutes
        
        self.setup_ui()
        self.start_weather_updates()
    
    def setup_ui(self):
        """Setup the weather widget UI with transparent background"""
        # Title with transparent background
        title_label = tk.Label(
            self.window, 
            text="🌤️ Weather",
            bg=self.transparent_key, 
            fg='white',
            font=('Arial', 14, 'bold')
        )
        title_label.pack(pady=(10, 15))
        
        # Main content frame
        self.main_frame = tk.Frame(self.window, bg=self.transparent_key)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
        
        # Current weather display
        self.weather_display = tk.Frame(self.main_frame, bg=self.transparent_key)
        self.weather_display.pack(fill=tk.X, pady=5)
        
        self.icon_label = tk.Label(self.weather_display, text="❓", font=('Arial', 28), 
                                  fg='white', bg=self.transparent_key)
        self.icon_label.pack(side=tk.LEFT)
        
        self.temp_label = tk.Label(self.weather_display, text="--°C", font=('Arial', 18, 'bold'), 
                                  fg='white', bg=self.transparent_key)
        self.temp_label.pack(side=tk.LEFT, padx=(15, 0))
        
        # Description
        self.desc_label = tk.Label(self.main_frame, text="Loading...", font=('Arial', 11), 
                                  fg='#cccccc', bg=self.transparent_key)
        self.desc_label.pack(pady=(5, 10))
        
        # Details frame
        details_frame = tk.Frame(self.main_frame, bg=self.transparent_key)
        details_frame.pack(fill=tk.X, pady=5)
        
        self.wind_label = tk.Label(details_frame, text="Wind: -- km/h", font=('Arial', 10), 
                                  fg='#aaaaaa', bg=self.transparent_key)
        self.wind_label.pack(anchor=tk.W, pady=2)
        
        self.precip_label = tk.Label(details_frame, text="Precipitation: -- mm", font=('Arial', 10), 
                                    fg='#aaaaaa', bg=self.transparent_key)
        self.precip_label.pack(anchor=tk.W, pady=2)
        
        # Forecast section
        forecast_title = tk.Label(self.main_frame, text="Forecast:", font=('Arial', 12, 'bold'),
                                 fg='white', bg=self.transparent_key)
        forecast_title.pack(anchor=tk.W, pady=(15, 8))
        
        self.forecast_frame = tk.Frame(self.main_frame, bg=self.transparent_key)
        self.forecast_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Status label
        self.status_label = tk.Label(self.window, text="Updating...", font=('Arial', 9), 
                                    fg='#888888', bg=self.transparent_key)
        self.status_label.pack(side=tk.BOTTOM, pady=5)
    
    def update_weather_display(self):
        """Update the weather display with current data"""
        if not self.weather_data or "error" in self.weather_data:
            self.icon_label.config(text="❓")
            self.temp_label.config(text="--°C")
            self.desc_label.config(text="Weather unavailable")
            self.wind_label.config(text="Wind: -- km/h")
            self.precip_label.config(text="Precipitation: -- mm")
            self.status_label.config(text="Error loading weather")
            # Clear forecast
            for widget in self.forecast_frame.winfo_children():
                widget.destroy()
            return

        current = self.weather_data["current"]
        self.icon_label.config(text=current["icon"])
        temp_range = f"{current['temperature_min']:.0f}-{current['temperature_max']:.0f}°C"
        self.temp_label.config(text=temp_range)
        self.desc_label.config(text=current["description"])
        self.wind_label.config(text=f"Wind: {current['wind_speed']:.0f} km/h")
        self.precip_label.config(text=f"Precipitation: {current['precipitation']:.1f} mm")

        # Clear and update forecast
        for widget in self.forecast_frame.winfo_children():
            widget.destroy()

        forecast_data = self.weather_data.get("forecast", [])
        if isinstance(forecast_data, list) and len(forecast_data) > 0:
            # Show next 3 days with improved layout
            for i, forecast in enumerate(forecast_data[:3]):
                forecast_item = tk.Frame(self.forecast_frame, bg=self.transparent_key)
                forecast_item.pack(fill=tk.X, pady=4, padx=5)

                # Icon
                icon_label = tk.Label(
                    forecast_item, text=forecast.get('icon', '❓'), 
                    font=('Arial', 16), fg='white', bg=self.transparent_key, width=3
                )
                icon_label.pack(side=tk.LEFT)

                # Day name
                day_name = forecast.get('day_name', 'N/A')[:3]
                day_label = tk.Label(
                    forecast_item, text=day_name, font=('Arial', 11, 'bold'),
                    fg='white', bg=self.transparent_key, width=4, anchor='w'
                )
                day_label.pack(side=tk.LEFT, padx=(8, 5))
                
                # Temperature range
                temp_min = forecast.get('temperature_min', 0)
                temp_max = forecast.get('temperature_max', 0)
                temp_text = f"{temp_min:.0f}-{temp_max:.0f}°C"
                temp_label = tk.Label(
                    forecast_item, text=temp_text, font=('Arial', 10),
                    fg='#cccccc', bg=self.transparent_key, anchor='w'
                )                
                temp_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        else:
            no_forecast_label = tk.Label(
                self.forecast_frame, text="Forecast: Not available",
                font=('Arial', 10), fg='#888888', bg=self.transparent_key
            )
            no_forecast_label.pack(anchor=tk.W, pady=5)

        self.status_label.config(text=f"Updated: {time.strftime('%H:%M')}")
    def fetch_weather_data(self):
        """Fetch weather data in background thread"""
        try:
            logger.debug(f"Fetching weather data for {self.pincode}, {self.country_code}")
            self.weather_data = get_weather_data(self.pincode, self.country_code)
            self.last_update = time.time()
            logger.info("Weather data fetched successfully")
            # Schedule UI update on main thread
            self.window.after(0, self.update_weather_display)
        except Exception as e:
            logger.error(f"Error fetching weather data: {e}")
            self.weather_data = {"error": str(e)}
            self.window.after(0, self.update_weather_display)
    
    def start_weather_updates(self):
        """Start the weather update cycle"""
        def update_cycle():
            while True:
                try:
                    if hasattr(self, 'window') and self.window.winfo_exists():
                        current_time = time.time()
                        if current_time - self.last_update > self.update_interval:
                            self.fetch_weather_data()
                        time.sleep(60)  # Check every minute
                    else:
                        break
                except tk.TclError:
                    break               
                except Exception as e:
                    logger.error(f"Error in weather update cycle: {e}")
                    time.sleep(60)
        
        # Initial fetch
        threading.Thread(target=self.fetch_weather_data, daemon=True).start()
        
        # Start update cycle
        threading.Thread(target=update_cycle, daemon=True).start()
    
    def destroy(self):
        """Clean up the widget"""
        if hasattr(self, 'window'):
            self.window.destroy()
              