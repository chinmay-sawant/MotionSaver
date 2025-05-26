import openmeteo_requests
import pandas as pd
import requests_cache
from retry_requests import retry
import pgeocode

# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)

# Replace with your desired pincode and country code
pincode = "400068"  # Example: Mumbai, India
country_code = "IN"

# Get latitude and longitude from pincode
nomi = pgeocode.Nominatim(country_code)
location = nomi.query_postal_code(pincode)
latitude = location.latitude
longitude = location.longitude

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

url = "https://api.open-meteo.com/v1/forecast"
params = {
	"latitude": latitude,
	"longitude": longitude,
	"hourly": [
		"temperature_2m", "relativehumidity_2m", "dewpoint_2m", "apparent_temperature",
		"precipitation", "rain", "showers", "snowfall", "pressure_msl",
		"surface_pressure", "cloudcover", "cloudcover_low", "cloudcover_mid",
		"cloudcover_high", "visibility", "windspeed_10m", "windspeed_80m",
		"windspeed_120m", "windspeed_180m", "winddirection_10m",
		"winddirection_80m", "winddirection_120m", "winddirection_180m",
		"shortwave_radiation", "direct_radiation", "diffuse_radiation",
		"direct_normal_irradiance", "terrestrial_radiation"
	],
	"daily": ["weathercode", "temperature_2m_max", "temperature_2m_min",
			  "apparent_temperature_max", "apparent_temperature_min",
			  "sunrise", "sunset", "uv_index_max", "precipitation_sum",
			  "rain_sum", "showers_sum", "snowfall_sum",
			  "windspeed_10m_max", "windgusts_10m_max",
			  "winddirection_10m_dominant"],
	"timezone": "auto",
	"forecast_days": 1  # Limit to today's data
}

responses = openmeteo.weather_api(url, params=params)

# Process first location
response = responses[0]
print(f"Coordinates {response.Latitude()}°N {response.Longitude()}°E")
print(f"Elevation {response.Elevation()} m asl")
print(f"Timezone {response.Timezone()} {response.TimezoneAbbreviation()}")
print(f"Timezone difference to GMT+0 {response.UtcOffsetSeconds()} s")

# Process hourly data
hourly = response.Hourly()
hourly_data = {"date": pd.date_range(
	start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
	end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
	freq=pd.Timedelta(seconds=hourly.Interval()),
	inclusive="left"
)}

# Add all hourly variables to the hourly_data dictionary
hourly_params = [
    "temperature_2m", "relativehumidity_2m", "dewpoint_2m", "apparent_temperature",
    "precipitation", "rain", "showers", "snowfall", "pressure_msl",
    "surface_pressure", "cloudcover", "cloudcover_low", "cloudcover_mid",
    "cloudcover_high", "visibility", "windspeed_10m", "windspeed_80m",
    "windspeed_120m", "windspeed_180m", "winddirection_10m",
    "winddirection_80m", "winddirection_120m", "winddirection_180m",
    "shortwave_radiation", "direct_radiation", "diffuse_radiation",
    "direct_normal_irradiance", "terrestrial_radiation"
]

for i in range(hourly.VariablesLength()):
    variable = hourly.Variables(i)
    hourly_data[hourly_params[i]] = variable.ValuesAsNumpy()

hourly_dataframe = pd.DataFrame(data=hourly_data)
print("\nHourly Data:")
print(hourly_dataframe)

# Process daily data
daily = response.Daily()
daily_data = {"date": pd.date_range(
	start=pd.to_datetime(daily.Time(), unit="s", utc=True),
	end=pd.to_datetime(daily.TimeEnd(), unit="s", utc=True),
	freq=pd.Timedelta(seconds=daily.Interval()),
	inclusive="left"
)}

# Add all daily variables to the daily_data dictionary
daily_params = ["weathercode", "temperature_2m_max", "temperature_2m_min",
                "apparent_temperature_max", "apparent_temperature_min",
                "sunrise", "sunset", "uv_index_max", "precipitation_sum",
                "rain_sum", "showers_sum", "snowfall_sum",
                "windspeed_10m_max", "windgusts_10m_max",
                "winddirection_10m_dominant"]

for i in range(daily.VariablesLength()):
    variable = daily.Variables(i)
    daily_data[daily_params[i]] = variable.ValuesAsNumpy()

daily_dataframe = pd.DataFrame(data=daily_data)

# Print today's weather forecast in one line
if not daily_dataframe.empty:
    today_data = daily_dataframe.iloc[0]
    weather_code = int(today_data['weathercode'])
    weather_description = WEATHER_CODES.get(weather_code, "Unknown weather code")
    temp_max = today_data['temperature_2m_max']
    temp_min = today_data['temperature_2m_min']
    
    print(f"\nToday's Weather: {weather_description}, Max Temp: {temp_max}°C, Min Temp: {temp_min}°C")

print("\nToday's Detailed Forecast:")
print(daily_dataframe)