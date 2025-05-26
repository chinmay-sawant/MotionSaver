import tkinter as tk
from tkinter import ttk
import threading
import time
from .weather_api import get_weather_data

class WeatherWidget:
    def __init__(self, parent, transparent_key, screen_width, screen_height, pincode="400068", country_code="IN"):
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
        widget_width = 300
        widget_height = 200
        x_pos = screen_width - widget_width - 20
        y_pos = 20
        
        self.window.geometry(f"{widget_width}x{widget_height}+{x_pos}+{y_pos}")
        
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
            font=('Arial', 12, 'bold')
        )
        title_label.pack(pady=(5, 10))
        
        # Main content frame with transparent background
        self.main_frame = tk.Frame(self.window, bg=self.transparent_key)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Weather icon and temp with transparent background
        self.weather_display = tk.Frame(self.main_frame, bg=self.transparent_key)
        self.weather_display.pack(fill=tk.X, pady=3)
        
        self.icon_label = tk.Label(self.weather_display, text="❓", font=('Arial', 24), 
                                  fg='white', bg=self.transparent_key)
        self.icon_label.pack(side=tk.LEFT)
        
        self.temp_label = tk.Label(self.weather_display, text="--°C", font=('Arial', 16, 'bold'), 
                                  fg='white', bg=self.transparent_key)
        self.temp_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # Description with transparent background
        self.desc_label = tk.Label(self.main_frame, text="Loading...", font=('Arial', 10), 
                                  fg='#cccccc', bg=self.transparent_key)
        self.desc_label.pack(pady=2)
        
        # Details with transparent background
        self.wind_label = tk.Label(self.main_frame, text="Wind: -- km/h", font=('Arial', 9), 
                                  fg='#aaaaaa', bg=self.transparent_key)
        self.wind_label.pack(anchor=tk.W, pady=1)
        
        self.precip_label = tk.Label(self.main_frame, text="Precipitation: -- mm", font=('Arial', 9), 
                                    fg='#aaaaaa', bg=self.transparent_key)
        self.precip_label.pack(anchor=tk.W, pady=1)
        
        # Forecast frame with transparent background
        self.forecast_frame = tk.Frame(self.main_frame, bg=self.transparent_key)
        self.forecast_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Status label with transparent background
        self.status_label = tk.Label(self.window, text="Updating...", font=('Arial', 8), 
                                    fg='#888888', bg=self.transparent_key)
        self.status_label.pack(side=tk.BOTTOM, pady=2)
    
    def update_weather_display(self):
        """Update the weather display with current data"""
        if not self.weather_data or "error" in self.weather_data:
            self.icon_label.config(text="❓")
            self.temp_label.config(text="--°C")
            self.desc_label.config(text="Weather unavailable")
            self.wind_label.config(text="Wind: -- km/h")
            self.precip_label.config(text="Precipitation: -- mm")
            self.status_label.config(text="Error loading weather")
            
            # Clear forecast on error
            for widget in self.forecast_frame.winfo_children():
                widget.destroy()
            return
        
        current = self.weather_data["current"]
        
        # Update current weather
        self.icon_label.config(text=current["icon"])
        temp_range = f"{current['temperature_min']:.0f}-{current['temperature_max']:.0f}°C"
        self.temp_label.config(text=temp_range)
        self.desc_label.config(text=current["description"])
        
        # Update details
        self.wind_label.config(text=f"Wind: {current['wind_speed']:.0f} km/h")
        self.precip_label.config(text=f"Precipitation: {current['precipitation']:.1f} mm")
        
        # Clear and update forecast
        for widget in self.forecast_frame.winfo_children():
            widget.destroy()
        
        # Add forecast if available
        if self.weather_data.get("forecast") and len(self.weather_data["forecast"]) > 0:
            forecast_title = tk.Label(self.forecast_frame, text="Forecast:", font=('Arial', 9, 'bold'), 
                                    fg='white', bg=self.transparent_key)
            forecast_title.pack(anchor=tk.W, pady=(2, 1))
            
            for forecast in self.weather_data["forecast"][:2]:  # Show only next 2 days
                forecast_item = tk.Frame(self.forecast_frame, bg=self.transparent_key)
                forecast_item.pack(fill=tk.X, pady=1)
                
                day_text = f"{forecast['day_name'][:3]}: {forecast['icon']} {forecast['temperature_min']:.0f}-{forecast['temperature_max']:.0f}°C"
                tk.Label(forecast_item, text=day_text, font=('Arial', 8), 
                        fg='#cccccc', bg=self.transparent_key).pack(anchor=tk.W)
        else:
            # Show message if no forecast available
            no_forecast_label = tk.Label(self.forecast_frame, text="Forecast: Not available", 
                                        font=('Arial', 8), fg='#888888', bg=self.transparent_key)
            no_forecast_label.pack(anchor=tk.W, pady=2)
        
        self.status_label.config(text=f"Updated: {time.strftime('%H:%M')}")
    
    def fetch_weather_data(self):
        """Fetch weather data in background thread"""
        try:
            self.weather_data = get_weather_data(self.pincode, self.country_code)
            self.last_update = time.time()
            # Schedule UI update on main thread
            self.window.after(0, self.update_weather_display)
        except Exception as e:
            print(f"Error fetching weather data: {e}")
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
                    print(f"Error in weather update cycle: {e}")
                    time.sleep(60)
        
        # Initial fetch
        threading.Thread(target=self.fetch_weather_data, daemon=True).start()
        
        # Start update cycle
        threading.Thread(target=update_cycle, daemon=True).start()
    
    def destroy(self):
        """Clean up the widget"""
        if hasattr(self, 'window'):
            self.window.destroy()
