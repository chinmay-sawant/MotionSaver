import openmeteo_requests
import pandas as pd
import requests_cache
from retry_requests import retry
import pgeocode
import os
import sys

# Add central logging
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from central_logger import get_logger, log_startup, log_shutdown, log_exception
logger = get_logger('WeatherAPI')

# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)

# Weather codes mapping (WMO Weather interpretation codes (WW))
WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear", 
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Drizzle: Light intensity",
    53: "Drizzle: Moderate intensity",
    55: "Drizzle: Dense intensity",
    56: "Freezing Drizzle: Light intensity", 
    57: "Freezing Drizzle: Dense intensity",
    61: "Rain: Slight intensity",
    63: "Rain: Moderate intensity",
    65: "Rain: Heavy intensity",
    66: "Freezing Rain: Light intensity",
    67: "Freezing Rain: Heavy intensity",
    71: "Snow fall: Slight intensity",
    73: "Snow fall: Moderate intensity",
    75: "Snow fall: Heavy intensity",
    77: "Snow grains",
    80: "Rain showers: Slight intensity",
    81: "Rain showers: Moderate intensity", 
    82: "Rain showers: Violent intensity",
    85: "Snow showers: Slight intensity",
    86: "Snow showers: Heavy intensity",
    95: "Thunderstorm: Slight or moderate",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

# Weather icons mapping (simple text-based icons)
WEATHER_ICONS = {
    0: "☀️",    # Clear sky
    1: "🌤️",    # Mainly clear
    2: "⛅",    # Partly cloudy
    3: "☁️",    # Overcast
    45: "🌫️",   # Fog
    48: "🌫️",   # Depositing rime fog
    51: "🌦️",   # Drizzle: Light
    53: "🌦️",   # Drizzle: Moderate
    55: "🌧️",   # Drizzle: Dense
    56: "🌨️",   # Freezing Drizzle: Light
    57: "🌨️",   # Freezing Drizzle: Dense
    61: "🌧️",   # Rain: Slight
    63: "🌧️",   # Rain: Moderate
    65: "🌧️",   # Rain: Heavy
    66: "🌨️",   # Freezing Rain: Light
    67: "🌨️",   # Freezing Rain: Heavy
    71: "❄️",   # Snow fall: Slight
    73: "❄️",   # Snow fall: Moderate
    75: "❄️",   # Snow fall: Heavy
    77: "❄️",   # Snow grains
    80: "🌦️",   # Rain showers: Slight
    81: "🌧️",   # Rain showers: Moderate
    82: "⛈️",   # Rain showers: Violent
    85: "🌨️",   # Snow showers: Slight
    86: "🌨️",   # Snow showers: Heavy
    95: "⛈️",   # Thunderstorm: Slight or moderate
    96: "⛈️",   # Thunderstorm with slight hail
    99: "⛈️",   # Thunderstorm with heavy hail
}

def get_weather_data(pincode="400068", country_code="IN"):
    """
    Get weather data and return as structured dictionary
    
    Returns:
        dict: Weather data with current conditions and forecast
    """
    try:
        # Get latitude and longitude from pincode
        nomi = pgeocode.Nominatim(country_code)
        location = nomi.query_postal_code(pincode)
        latitude = location.latitude
        longitude = location.longitude
        
        if pd.isna(latitude) or pd.isna(longitude):
            return {"error": "Invalid pincode or location not found"}

        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": ["temperature_2m", "relativehumidity_2m", "precipitation", "windspeed_10m"],
            "daily": ["weathercode", "temperature_2m_max", "temperature_2m_min",
                     "apparent_temperature_max", "apparent_temperature_min",
                     "sunrise", "sunset", "uv_index_max", "precipitation_sum",
                     "windspeed_10m_max"],
            "timezone": "auto",
            "forecast_days": 5  # Get more days to ensure we have forecast data
        }

        responses = openmeteo.weather_api(url, params=params)
        response = responses[0]

        # Process daily data
        daily = response.Daily()
        daily_data = {"date": pd.date_range(
            start=pd.to_datetime(daily.Time(), unit="s", utc=True),
            end=pd.to_datetime(daily.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=daily.Interval()),
            inclusive="left"
        )}

        # Add daily variables
        daily_params = ["weathercode", "temperature_2m_max", "temperature_2m_min",
                       "apparent_temperature_max", "apparent_temperature_min",
                       "sunrise", "sunset", "uv_index_max", "precipitation_sum",
                       "windspeed_10m_max"]

        for i in range(daily.VariablesLength()):
            variable = daily.Variables(i)
            if i < len(daily_params):  # Ensure we don't go out of bounds
                daily_data[daily_params[i]] = variable.ValuesAsNumpy()

        daily_dataframe = pd.DataFrame(data=daily_data)
        logger.debug(f"Daily dataframe shape: {daily_dataframe.shape}")
        logger.debug(f"Daily dataframe columns: {daily_dataframe.columns.tolist()}")

        # Get today's data
        if not daily_dataframe.empty and len(daily_dataframe) > 0:
            today_data = daily_dataframe.iloc[0]
            weather_code = int(today_data['weathercode']) if not pd.isna(today_data['weathercode']) else 0
            
            weather_info = {
                "location": {
                    "pincode": pincode,
                    "country": country_code,
                    "latitude": float(latitude),
                    "longitude": float(longitude)
                },
                "current": {
                    "weather_code": weather_code,
                    "description": WEATHER_CODES.get(weather_code, "Unknown"),
                    "icon": WEATHER_ICONS.get(weather_code, "❓"),
                    "temperature_max": float(today_data['temperature_2m_max']) if not pd.isna(today_data['temperature_2m_max']) else 0,
                    "temperature_min": float(today_data['temperature_2m_min']) if not pd.isna(today_data['temperature_2m_min']) else 0,
                    "apparent_temp_max": float(today_data['apparent_temperature_max']) if not pd.isna(today_data['apparent_temperature_max']) else 0,
                    "apparent_temp_min": float(today_data['apparent_temperature_min']) if not pd.isna(today_data['apparent_temperature_min']) else 0,
                    "precipitation": float(today_data['precipitation_sum']) if not pd.isna(today_data['precipitation_sum']) else 0,
                    "wind_speed": float(today_data['windspeed_10m_max']) if not pd.isna(today_data['windspeed_10m_max']) else 0,
                    "uv_index": float(today_data['uv_index_max']) if not pd.isna(today_data['uv_index_max']) else 0
                },
                "forecast": []
            }
            
            # Add forecast for next days (skip today which is index 0)
            logger.debug(f"Processing forecast for {len(daily_dataframe)} days")
            for i in range(1, min(4, len(daily_dataframe))):  # Get next 3 days
                try:
                    forecast_data = daily_dataframe.iloc[i]
                    forecast_weather_code = int(forecast_data['weathercode']) if not pd.isna(forecast_data['weathercode']) else 0
                    
                    forecast_item = {
                        "date": forecast_data['date'].strftime('%Y-%m-%d'),
                        "day_name": forecast_data['date'].strftime('%A'),
                        "weather_code": forecast_weather_code,
                        "description": WEATHER_CODES.get(forecast_weather_code, "Unknown"),
                        "icon": WEATHER_ICONS.get(forecast_weather_code, "❓"),
                        "temperature_max": float(forecast_data['temperature_2m_max']) if not pd.isna(forecast_data['temperature_2m_max']) else 0,
                        "temperature_min": float(forecast_data['temperature_2m_min']) if not pd.isna(forecast_data['temperature_2m_min']) else 0,
                        "precipitation": float(forecast_data['precipitation_sum']) if not pd.isna(forecast_data['precipitation_sum']) else 0
                    }
                    
                    weather_info["forecast"].append(forecast_item)                    
                    logger.debug(f"Added forecast for day {i}: {forecast_item['day_name']}")
                    
                except Exception as e:
                    logger.error(f"Error processing forecast day {i}: {e}")
                    continue
            
            logger.debug(f"Total forecast items: {len(weather_info['forecast'])}")
            return weather_info
        else:
            return {"error": "No weather data available"}
            
    except Exception as e:        
        logger.error(f"Error in get_weather_data: {e}")
        return {"error": f"Failed to fetch weather data: {str(e)}"}

if __name__ == "__main__":
    # Test the function   
    weather_data = get_weather_data()
    if "error" not in weather_data:
        current = weather_data["current"]
        logger.info(f"Today's Weather: {current['description']} {current['icon']}")
        logger.info(f"Temperature: {current['temperature_min']}°C - {current['temperature_max']}°C")
        
        if weather_data["forecast"]:
            logger.info("\nForecast:")
            for forecast in weather_data["forecast"]:
                logger.info(f"{forecast['day_name']}: {forecast['description']} {forecast['icon']}, "
                      f"{forecast['temperature_min']}°C - {forecast['temperature_max']}°C")
    else:
        logger.error(f"Error: {weather_data['error']}")
