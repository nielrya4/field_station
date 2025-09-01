from flask import Flask, render_template, request, redirect, url_for
import requests
from datetime import datetime, timedelta
import os
import pytz

def register(app):
    @app.route('/weather')
    def weather():
        try:
            weather_data = get_hobolink_data()
            if weather_data:
                return render_template("weather/weather.html", weather_data=weather_data)
            else:
                return render_template("weather/weather.html", error="Unable to retrieve weather data")
        except Exception as e:
            return render_template("weather/weather.html", error=f"Weather data unavailable: {str(e)}")

def get_hobolink_data():
    api_token = "F3IhKKcqanCSo1SgFGPvhaIfs9sqxuPF4PFFHMsOwbOV1BbU"
    api_url = "https://api.licor.cloud/v1/data"
    
    logger_ids = [
        "21733030-1",  # pressure in mbar
        "21742342-1",  # Solar radiation
        "21755059-1",  # wind speed in m/s
        "21755059-2",  # gust speed in m/s
        "21755059-3",  # Wind direction in degrees
        "21764951-1",  # rain in mm
        "21768159-1",  # temperature in C
        "21768159-2",  # % RH
        "21768159-3"   # Dew point in C
    ]
    
    current_time = datetime.utcnow()
    start_time = current_time - timedelta(hours=1)
    
    headers = {
        "Authorization": f"Bearer {api_token}"
    }
    
    params = {
        "loggers": "22167865",
        "start_date_time": start_time.strftime('%Y-%m-%d %H:%M:%S'),
        "end_date_time": current_time.strftime('%Y-%m-%d %H:%M:%S')
    }
    try:
        response = requests.get(api_url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        if data.get('data'):
            return parse_hobolink_weather_data(data)
        else:
            print("No data returned from HOBOLINK API")
            return get_no_data_response()
            
    except requests.exceptions.RequestException as e:
        print(f"HOBOLINK API error: {e}")
        return get_no_data_response()
    except Exception as e:
        print(f"Error parsing weather data: {e}")
        return get_no_data_response()

def get_no_data_response():
    current_time = datetime.now()
    return {
        "temperature": "--",
        "temperature_f": "--",
        "humidity": "--",
        "dew_point": "--",
        "dew_point_f": "--",
        "pressure": "--",
        "pressure_inhg": "--",
        "wind_speed": "--",
        "wind_speed_mph": "--",
        "wind_gust": "--",
        "wind_gust_mph": "--",
        "wind_direction": "--",
        "solar_radiation": "--",
        "rain": "--",
        "rain_in": "--",
        "timestamp": current_time.strftime('%Y-%m-%d %H:%M:%S'),
        "weather_type": ("No Data", "partly_cloudy_day")
    }

def parse_hobolink_weather_data(raw_data):
    if not raw_data or 'data' not in raw_data or not raw_data['data']:
        return None
    
    try:
        # Find the most recent timestamp and filter to last 5 minutes
        all_timestamps = [reading.get('timestamp', '') for reading in raw_data['data'] if reading.get('timestamp')]
        if not all_timestamps:
            return None
        
        latest_timestamp = max(all_timestamps)
        latest_time = datetime.fromisoformat(latest_timestamp.replace('Z', '+00:00'))
        cutoff_time = latest_time - timedelta(minutes=5)
        
        # Group data by sensor serial number, only keeping readings from last 5 minutes
        sensor_readings = {}
        for reading in raw_data['data']:
            sensor_sn = reading.get('sensor_sn')
            timestamp = reading.get('timestamp', '')
            if sensor_sn and timestamp:
                reading_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                if reading_time >= cutoff_time:
                    if sensor_sn not in sensor_readings:
                        sensor_readings[sensor_sn] = []
                    sensor_readings[sensor_sn].append(reading)
        
        # Calculate averages for each sensor
        def get_averaged_value(sensor_id):
            if sensor_id not in sensor_readings:
                return '--'
            values = []
            for reading in sensor_readings[sensor_id]:
                try:
                    value = float(reading.get('value', 0))
                    values.append(value)
                except (ValueError, TypeError):
                    continue
            return round(sum(values) / len(values), 1) if values else '--'
        
        # Extract averaged values from each sensor
        temperature = get_averaged_value('21768159-1')
        humidity = get_averaged_value('21768159-2')
        dew_point = get_averaged_value('21768159-3')
        pressure = get_averaged_value('21733030-1')
        solar_radiation = get_averaged_value('21742342-1')
        wind_speed = get_averaged_value('21755059-1')
        wind_gust = get_averaged_value('21755059-2')
        wind_direction = get_averaged_value('21755059-3')
        rain = get_averaged_value('21764951-1')
        
        # Convert wind direction to integer
        if wind_direction != '--':
            wind_direction = int(wind_direction)
        
        # Convert wind speed from m/s to km/hr
        if wind_speed != '--':
            wind_speed = round(wind_speed * 3.6, 1)
                
        # Convert wind gust from m/s to km/hr
        if wind_gust != '--':
            wind_gust = round(wind_gust * 3.6, 1)
        
        # Get the latest timestamp and convert to Mountain Time
        all_timestamps = []
        for readings_list in sensor_readings.values():
            for reading in readings_list:
                if reading.get('timestamp'):
                    all_timestamps.append(reading['timestamp'])
        
        if all_timestamps:
            latest_utc_timestamp = max(all_timestamps)
            # Convert to Mountain Time (handles MST/MDT automatically)
            utc_time = datetime.fromisoformat(latest_utc_timestamp.replace('Z', '+00:00'))
            mountain_tz = pytz.timezone('US/Mountain')
            mountain_time = utc_time.astimezone(mountain_tz)
            latest_timestamp = mountain_time.strftime('%Y-%m-%d %H:%M:%S %Z')
        else:
            latest_timestamp = '--'
        
        # Calculate imperial values
        temp_f = round(temperature * 9/5 + 32, 1) if temperature != '--' else '--'
        dew_point_f = round(dew_point * 9/5 + 32, 1) if dew_point != '--' else '--'
        pressure_inhg = round(pressure * 0.02953, 2) if pressure != '--' else '--'
        wind_speed_mph = round(wind_speed * 0.621371, 1) if wind_speed != '--' else '--'
        wind_gust_mph = round(wind_gust * 0.621371, 1) if wind_gust != '--' else '--'
        rain_in = round(rain * 0.0393701, 2) if rain != '--' else '--'
        
        weather_data = {
            "temperature": temperature,
            "temperature_f": temp_f,
            "humidity": humidity,
            "dew_point": dew_point,
            "dew_point_f": dew_point_f,
            "pressure": pressure,
            "pressure_inhg": pressure_inhg,
            "wind_speed": wind_speed,
            "wind_speed_mph": wind_speed_mph,
            "wind_gust": wind_gust,
            "wind_gust_mph": wind_gust_mph,
            "wind_direction": wind_direction,
            "solar_radiation": solar_radiation,
            "rain": rain,
            "rain_in": rain_in,
            "timestamp": latest_timestamp,
            "weather_type": determine_weather_type_from_sensors(temperature, humidity, wind_speed)
        }
        
        return weather_data
    except Exception as e:
        print(f"Error parsing HOBOLINK weather data: {e}")
        return None

def determine_weather_type_from_sensors(temp, humidity, wind_speed):
    try:
        if temp == '--' or humidity == '--' or wind_speed == '--':
            return ("No Data", "partly_cloudy_day")
            
        temp_val = float(temp)
        humidity_val = float(humidity)
        wind_val = float(wind_speed)
        
        if humidity_val > 80 and temp_val > 0:
            return ("Foggy", "fog_day")
        elif wind_val > 25:
            return ("Windy", "wind")
        elif temp_val > 25:
            return ("Sunny", "clear_day")
        elif temp_val < 0:
            return ("Cold", "snow")
        else:
            return ("Partly Cloudy", "partly_cloudy_day")
    except (ValueError, TypeError):
        return ("No Data", "partly_cloudy_day")

