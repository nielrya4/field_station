
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
import base64
import io
import requests
from datetime import datetime, timedelta
import os
import pytz
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import List

class WeatherData:
    def __init__(self, temperature=None, humidity=None, dew_point=None, pressure=None, 
                 wind_speed=None, wind_gust=None, wind_direction=None, solar_radiation=None, 
                 rain=None, timestamp=None, weather_type=None):
        # Store all values in metric units
        self.temperature = temperature  # Celsius
        self.humidity = humidity  # Percentage
        self.dew_point = dew_point  # Celsius
        self.pressure = pressure  # mbar
        self.wind_speed = wind_speed  # km/h
        self.wind_gust = wind_gust  # km/h
        self.wind_direction = wind_direction  # degrees
        self.solar_radiation = solar_radiation  # W/m²
        self.rain = rain  # mm
        self.timestamp = timestamp
        self.weather_type = weather_type
    
    def temperature_fahrenheit(self):
        if self.temperature == '--' or self.temperature is None:
            return '--'
        return round(self.temperature * 9/5 + 32, 1)
    
    def dew_point_fahrenheit(self):
        if self.dew_point == '--' or self.dew_point is None:
            return '--'
        return round(self.dew_point * 9/5 + 32, 1)
    
    def pressure_inhg(self):
        if self.pressure == '--' or self.pressure is None:
            return '--'
        return round(self.pressure * 0.02953, 2)
    
    def wind_speed_mph(self):
        if self.wind_speed == '--' or self.wind_speed is None:
            return '--'
        return round(self.wind_speed * 0.621371, 1)
    
    def wind_gust_mph(self):
        if self.wind_gust == '--' or self.wind_gust is None:
            return '--'
        return round(self.wind_gust * 0.621371, 1)
    
    def rain_inches(self):
        if self.rain == '--' or self.rain is None:
            return '--'
        return round(self.rain * 0.0393701, 2)
    
    def to_dict(self):
        """Convert to dictionary format for template compatibility"""
        return {
            "temperature": self.temperature,
            "temperature_f": self.temperature_fahrenheit(),
            "humidity": self.humidity,
            "dew_point": self.dew_point,
            "dew_point_f": self.dew_point_fahrenheit(),
            "pressure": self.pressure,
            "pressure_inhg": self.pressure_inhg(),
            "wind_speed": self.wind_speed,
            "wind_speed_mph": self.wind_speed_mph(),
            "wind_gust": self.wind_gust,
            "wind_gust_mph": self.wind_gust_mph(),
            "wind_direction": self.wind_direction,
            "solar_radiation": self.solar_radiation,
            "rain": self.rain,
            "rain_in": self.rain_inches(),
            "timestamp": self.timestamp,
            "weather_type": self.weather_type
        }

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

    @app.route('/weather/request-data', methods=['POST'])
    def request_weather_data():
        try:
            data = request.get_json()
            
            # Extract parameters from request
            metrics = data.get('metrics', [])
            output_types = data.get('output_types', [])
            start_datetime = data.get('start_datetime')
            end_datetime = data.get('end_datetime')
            units = data.get('units', 'metric')
            
            # Validate required parameters
            if not metrics:
                return jsonify({'error': 'No metrics selected'}), 400
            if not output_types:
                return jsonify({'error': 'No output types selected'}), 400
            if not start_datetime or not end_datetime:
                return jsonify({'error': 'Start and end date/time are required'}), 400
            
            # Map frontend metric names to backend names
            metric_mapping = {
                'temperature': 'temperature',
                'relative_humidity': 'humidity',
                'dew_point': 'dew_point',
                'pressure': 'pressure',
                'wind_speed': 'wind_speed',
                'gust_speed': 'wind_gust',
                'wind_direction': 'wind_direction',
                'solar_radiation': 'solar_radiation',
                'rainfall': 'rain'
            }
            
            # Convert frontend metric names to backend names
            backend_metrics = []
            for metric in metrics:
                if metric in metric_mapping:
                    backend_metrics.append(metric_mapping[metric])
                else:
                    return jsonify({'error': f'Unknown metric: {metric}'}), 400
            
            # Convert output types to backend format
            backend_output_types = []
            for output_type in output_types:
                if output_type in ['xlsx', 'csv']:
                    backend_output_types.append('excel')
                elif output_type == 'html':
                    backend_output_types.append('plotly')
                elif output_type in ['svg', 'png']:
                    backend_output_types.append('matplotlib')
                else:
                    return jsonify({'error': f'Unknown output type: {output_type}'}), 400
            
            # Remove duplicates
            backend_output_types = list(set(backend_output_types))
            
            # Export the data
            results = export_weather_data(
                metrics=backend_metrics,
                output_types=backend_output_types,
                time_start=start_datetime,
                time_end=end_datetime,
                units=units
            )
            
            # Prepare response
            response_data = {
                'success': True,
                'files': []
            }
            
            # Handle plotly output (HTML)
            if 'plotly_data' in results:
                plot_files = results['plotly_data']
                for plot_file in plot_files:
                    if plot_file['type'] in output_types:
                        response_data['files'].append({
                            'filename': plot_file['filename'],
                            'type': plot_file['type'],
                            'description': plot_file['description'],
                            'data_url': plot_file['data_url']
                        })
            
            # Handle matplotlib output (PNG, SVG)
            if 'matplotlib_data' in results:
                plot_files = results['matplotlib_data']
                for plot_file in plot_files:
                    if plot_file['type'] in output_types:
                        response_data['files'].append({
                            'filename': plot_file['filename'],
                            'type': plot_file['type'],
                            'description': plot_file['description'],
                            'data_url': plot_file['data_url']
                        })
            
            # Handle excel output
            if 'excel_data' in results:
                excel_files = results['excel_data']
                for excel_file in excel_files:
                    if excel_file['type'] in output_types:
                        response_data['files'].append({
                            'filename': excel_file['filename'],
                            'type': excel_file['type'], 
                            'description': excel_file['description'],
                            'data_url': excel_file['data_url']
                        })
            
            return jsonify(response_data)
            
        except ValueError as e:
            return jsonify({
                'error': f"ValueError: {str(e)}",
                'error_type': 'ValueError',
                'debug_info': f"Line: {e.__traceback__.tb_lineno if e.__traceback__ else 'unknown'}"
            }), 400
        except Exception as e:
            import traceback
            return jsonify({
                'error': f"Server Error: {str(e)}",
                'error_type': type(e).__name__,
                'debug_info': traceback.format_exc()
            }), 500


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
    weather_data = WeatherData(
        temperature="--",
        humidity="--",
        dew_point="--",
        pressure="--",
        wind_speed="--",
        wind_gust="--",
        wind_direction="--",
        solar_radiation="--",
        rain="--",
        timestamp=current_time.strftime('%Y-%m-%d %H:%M:%S'),
        weather_type=("No Data", "partly_cloudy_day")
    )
    return weather_data.to_dict()

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
        
        # Create WeatherData instance with metric values
        weather_data = WeatherData(
            temperature=temperature,
            humidity=humidity,
            dew_point=dew_point,
            pressure=pressure,
            wind_speed=wind_speed,
            wind_gust=wind_gust,
            wind_direction=wind_direction,
            solar_radiation=solar_radiation,
            rain=rain,
            timestamp=latest_timestamp,
            weather_type=determine_weather_type_from_sensors(temperature, humidity, wind_speed)
        )
        
        return weather_data.to_dict()
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

def get_historical_weather_data(time_start: str, time_end: str):
    """
    Fetch historical weather data from the API for a given time range.
    
    Args:
        time_start: Start time in '%Y-%m-%d %H:%M:%S' format
        time_end: End time in '%Y-%m-%d %H:%M:%S' format
        
    Returns:
        List of weather readings with timestamps
    """
    api_token = "F3IhKKcqanCSo1SgFGPvhaIfs9sqxuPF4PFFHMsOwbOV1BbU"
    api_url = "https://api.licor.cloud/v1/data"
    
    headers = {
        "Authorization": f"Bearer {api_token}"
    }
    
    params = {
        "loggers": "22167865",
        "start_date_time": time_start,
        "end_date_time": time_end
    }
    
    try:
        response = requests.get(api_url, headers=headers, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        if not data.get('data'):
            print("No historical data returned from HOBOLINK API")
            return []
            
        return data['data']
        
    except requests.exceptions.RequestException as e:
        print(f"HOBOLINK API error: {e}")
        return []
    except Exception as e:
        print(f"Error fetching historical weather data: {e}")
        return []

def export_weather_data(metrics: List[str], output_types: List[str], time_start: str, time_end: str, units: str = 'metric'):
    """
    Export weather data for specified metrics and time range.
    
    Args:
        metrics: List of metrics to export. Available options:
                ['temperature', 'humidity', 'dew_point', 'pressure', 'wind_speed', 
                 'wind_gust', 'wind_direction', 'solar_radiation', 'rain']
        output_types: List of output formats: ['plotly', 'matplotlib', 'excel'] 
        time_start: Start time in '%Y-%m-%d %H:%M:%S' format
        time_end: End time in '%Y-%m-%d %H:%M:%S' format
        units: Unit system to use: 'metric' or 'imperial'
        
    Returns:
        Dictionary with output paths and/or figures
    """
    # Validate inputs
    valid_metrics = ['temperature', 'humidity', 'dew_point', 'pressure', 'wind_speed', 
                    'wind_gust', 'wind_direction', 'solar_radiation', 'rain']
    valid_outputs = ['plotly', 'matplotlib', 'excel']
    
    invalid_metrics = [m for m in metrics if m not in valid_metrics]
    invalid_outputs = [o for o in output_types if o not in valid_outputs]
    
    if invalid_metrics:
        raise ValueError(f"Invalid metrics: {invalid_metrics}. Valid options: {valid_metrics}")
    if invalid_outputs:
        raise ValueError(f"Invalid output types: {invalid_outputs}. Valid options: {valid_outputs}")
    
    # Parse time strings - input is in Mountain Time, convert to UTC for API
    try:
        # Parse as Mountain Time
        mountain_tz = pytz.timezone('US/Mountain')
        start_dt_naive = datetime.strptime(time_start, '%Y-%m-%d %H:%M:%S')
        end_dt_naive = datetime.strptime(time_end, '%Y-%m-%d %H:%M:%S')
        
        # Localize to Mountain Time
        start_dt_mountain = mountain_tz.localize(start_dt_naive)
        end_dt_mountain = mountain_tz.localize(end_dt_naive)
        
        # Convert to UTC for API call
        start_dt_utc = start_dt_mountain.astimezone(pytz.UTC)
        end_dt_utc = end_dt_mountain.astimezone(pytz.UTC)
        
        # Preserve original Mountain Time strings for display
        time_start_display = time_start
        time_end_display = time_end
        
        # Update time strings for API call
        time_start_utc = start_dt_utc.strftime('%Y-%m-%d %H:%M:%S')
        time_end_utc = end_dt_utc.strftime('%Y-%m-%d %H:%M:%S')
        
    except ValueError as e:
        raise ValueError(f"Invalid time format. Use '%Y-%m-%d %H:%M:%S': {e}")
    
    if start_dt_mountain >= end_dt_mountain:
        raise ValueError("Start time must be before end time")
    
    # Fetch historical data
    print(f"Fetching weather data from {time_start_utc} to {time_end_utc}...")
    raw_data = get_historical_weather_data(time_start_utc, time_end_utc)
    
    if not raw_data:
        raise ValueError("No data available for the specified time range")
    
    # Sensor ID mapping
    sensor_map = {
        'temperature': '21768159-1',
        'humidity': '21768159-2', 
        'dew_point': '21768159-3',
        'pressure': '21733030-1',
        'solar_radiation': '21742342-1',
        'wind_speed': '21755059-1',
        'wind_gust': '21755059-2', 
        'wind_direction': '21755059-3',
        'rain': '21764951-1'
    }
    
    # Process data into structured format
    processed_data = []
    mountain_tz = pytz.timezone('US/Mountain')
    
    for reading in raw_data:
        sensor_sn = reading.get('sensor_sn')
        timestamp_str = reading.get('timestamp', '')
        value = reading.get('value')
        
        if not timestamp_str or value is None:
            continue
            
        try:
            # Convert UTC timestamp to Mountain Time
            utc_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            mountain_time = utc_time.astimezone(mountain_tz)
            
            # Find metric name for this sensor
            metric_name = None
            for metric, sensor_id in sensor_map.items():
                if sensor_sn == sensor_id:
                    metric_name = metric
                    break
            
            if metric_name and metric_name in metrics:
                # Convert units to metric
                converted_value = float(value)
                if metric_name in ['wind_speed', 'wind_gust']:
                    # Convert from m/s to km/h
                    converted_value = round(converted_value * 3.6, 1)
                
                processed_data.append({
                    'timestamp': mountain_time,
                    'metric': metric_name,
                    'value': converted_value
                })
                
        except (ValueError, TypeError) as e:
            print(f"Error processing reading: {e}")
            continue
    
    if not processed_data:
        raise ValueError("No valid data found for specified metrics in the time range")
    
    # Convert to pandas DataFrame
    df = pd.DataFrame(processed_data)
    
    # Pivot to have metrics as columns
    df_pivot = df.pivot_table(index='timestamp', columns='metric', values='value', aggfunc='mean')
    df_pivot = df_pivot.sort_index()
    
    results = {}
    
    # Generate Plotly HTML (interactive, no Chrome needed)
    if 'plotly' in output_types:
        results['plotly_data'] = _create_plotly_html(df_pivot, metrics, time_start_display, time_end_display, units)
    
    # Generate matplotlib plots (static PNG/SVG)
    if 'matplotlib' in output_types:
        results['matplotlib_data'] = _create_matplotlib_plot(df_pivot, metrics, time_start_display, time_end_display, units)
    
    # Generate Excel file
    if 'excel' in output_types:
        results['excel_data'] = _create_excel_export(df_pivot, metrics, time_start_display, time_end_display, units)
    
    return results

def _create_plotly_html(df_pivot, metrics: List[str], time_start: str, time_end: str, units: str = 'metric'):
    """Create an interactive Plotly HTML file (no Chrome/Chromium needed)."""
    
    # Define units and colors for each metric
    metric_info = {
        'temperature': {'metric_unit': '°C', 'imperial_unit': '°F', 'color': 'red'},
        'humidity': {'metric_unit': '%', 'imperial_unit': '%', 'color': 'blue'},
        'dew_point': {'metric_unit': '°C', 'imperial_unit': '°F', 'color': 'orange'},
        'pressure': {'metric_unit': 'mbar', 'imperial_unit': 'inHg', 'color': 'purple'},
        'wind_speed': {'metric_unit': 'km/h', 'imperial_unit': 'mph', 'color': 'green'},
        'wind_gust': {'metric_unit': 'km/h', 'imperial_unit': 'mph', 'color': 'darkgreen'},
        'wind_direction': {'metric_unit': '°', 'imperial_unit': '°', 'color': 'brown'},
        'solar_radiation': {'metric_unit': 'W/m²', 'imperial_unit': 'W/m²', 'color': 'gold'},
        'rain': {'metric_unit': 'mm', 'imperial_unit': 'in', 'color': 'darkblue'}
    }
    
    # Convert data to imperial if requested
    df_plot = df_pivot.copy()
    if units == 'imperial':
        for metric in metrics:
            if metric in df_plot.columns:
                if metric == 'temperature':
                    df_plot[metric] = df_plot[metric] * 9/5 + 32
                elif metric == 'dew_point':
                    df_plot[metric] = df_plot[metric] * 9/5 + 32
                elif metric == 'pressure':
                    df_plot[metric] = df_plot[metric] * 0.02953
                elif metric in ['wind_speed', 'wind_gust']:
                    df_plot[metric] = df_plot[metric] * 0.621371
                elif metric == 'rain':
                    df_plot[metric] = df_plot[metric] * 0.0393701
    
    # Get appropriate unit label
    def get_unit(metric):
        return metric_info[metric][f'{units}_unit']
    
    if len(metrics) == 1:
        # Single metric - simple line plot
        fig = go.Figure()
        metric = metrics[0]
        if metric in df_plot.columns:
            fig.add_trace(go.Scatter(
                x=df_plot.index,
                y=df_plot[metric],
                mode='lines+markers',
                name=f"{metric.replace('_', ' ').title()}",
                line=dict(color=metric_info[metric]['color'])
            ))
            
            fig.update_layout(
                title=f"{metric.replace('_', ' ').title()} - {time_start} to {time_end}",
                xaxis_title="Time",
                yaxis_title=f"{metric.replace('_', ' ').title()} ({get_unit(metric)})",
                hovermode='x unified',
                width=1200,
                height=800
            )
    else:
        # Multiple metrics - subplot layout
        fig = make_subplots(
            rows=len(metrics), cols=1,
            subplot_titles=[f"{m.replace('_', ' ').title()}" for m in metrics],
            shared_xaxes=True,
            vertical_spacing=0.06
        )
        
        for i, metric in enumerate(metrics, 1):
            if metric in df_plot.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df_plot.index,
                        y=df_plot[metric],
                        mode='lines+markers',
                        name=metric.replace('_', ' ').title(),
                        line=dict(color=metric_info[metric]['color']),
                        showlegend=False
                    ),
                    row=i, col=1
                )
                
                fig.update_yaxes(
                    title_text=f"{get_unit(metric)}", 
                    row=i, col=1
                )
        
        fig.update_layout(
            title=f"Weather Data - {time_start} to {time_end}",
            width=1200,
            height=max(800, 200 * len(metrics))
        )
        
        fig.update_xaxes(title_text="Time", row=len(metrics), col=1)
    
    # Generate base filename
    safe_start = time_start.replace(' ', '_').replace(':', '-')
    safe_end = time_end.replace(' ', '_').replace(':', '-')
    base_filename = f"weather_data_{safe_start}_to_{safe_end}"
    
    # Generate HTML (no Chrome needed!)
    html_data = fig.to_html(include_plotlyjs='cdn')
    html_base64 = base64.b64encode(html_data.encode('utf-8')).decode('utf-8')
    
    return [{
        'filename': f"{base_filename}.html",
        'type': 'html',
        'description': f'Interactive Weather Plot (HTML) - {base_filename}',
        'data_url': f"data:text/html;base64,{html_base64}"
    }]

def _create_matplotlib_plot(df_pivot, metrics: List[str], time_start: str, time_end: str, units: str = 'metric'):
    """Create matplotlib plots for the weather data and return in-memory files."""
    
    # Define units and colors for each metric
    metric_info = {
        'temperature': {'metric_unit': '°C', 'imperial_unit': '°F', 'color': 'red'},
        'humidity': {'metric_unit': '%', 'imperial_unit': '%', 'color': 'blue'},
        'dew_point': {'metric_unit': '°C', 'imperial_unit': '°F', 'color': 'orange'},
        'pressure': {'metric_unit': 'mbar', 'imperial_unit': 'inHg', 'color': 'purple'},
        'wind_speed': {'metric_unit': 'km/h', 'imperial_unit': 'mph', 'color': 'green'},
        'wind_gust': {'metric_unit': 'km/h', 'imperial_unit': 'mph', 'color': 'darkgreen'},
        'wind_direction': {'metric_unit': '°', 'imperial_unit': '°', 'color': 'brown'},
        'solar_radiation': {'metric_unit': 'W/m²', 'imperial_unit': 'W/m²', 'color': 'gold'},
        'rain': {'metric_unit': 'mm', 'imperial_unit': 'in', 'color': 'darkblue'}
    }
    
    # Convert data to imperial if requested
    df_plot = df_pivot.copy()
    if units == 'imperial':
        for metric in metrics:
            if metric in df_plot.columns:
                if metric == 'temperature':
                    df_plot[metric] = df_plot[metric] * 9/5 + 32
                elif metric == 'dew_point':
                    df_plot[metric] = df_plot[metric] * 9/5 + 32
                elif metric == 'pressure':
                    df_plot[metric] = df_plot[metric] * 0.02953
                elif metric in ['wind_speed', 'wind_gust']:
                    df_plot[metric] = df_plot[metric] * 0.621371
                elif metric == 'rain':
                    df_plot[metric] = df_plot[metric] * 0.0393701
    
    # Get appropriate unit label
    def get_unit(metric):
        return metric_info[metric][f'{units}_unit']
    
    # Generate base filename
    safe_start = time_start.replace(' ', '_').replace(':', '-')
    safe_end = time_end.replace(' ', '_').replace(':', '-')
    base_filename = f"weather_data_{safe_start}_to_{safe_end}"
    
    plot_files = []
    
    if len(metrics) == 1:
        # Single metric - simple line plot
        fig, ax = plt.subplots(figsize=(12, 6))
        metric = metrics[0]
        
        if metric in df_plot.columns:
            ax.plot(df_plot.index, df_plot[metric], 
                   color=metric_info[metric]['color'], 
                   linewidth=2, marker='o', markersize=3)
            ax.set_xlabel('Time', fontsize=12)
            ax.set_ylabel(f"{metric.replace('_', ' ').title()} ({get_unit(metric)})", fontsize=12)
            ax.set_title(f"{metric.replace('_', ' ').title()} - {time_start} to {time_end}", fontsize=14)
            ax.grid(True, alpha=0.3)
            
            # Format x-axis dates
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
            plt.xticks(rotation=45, ha='right')
            
        plt.tight_layout()
        
    else:
        # Multiple metrics - subplot layout
        fig, axes = plt.subplots(len(metrics), 1, figsize=(12, 3*len(metrics)), sharex=True)
        
        if len(metrics) == 1:
            axes = [axes]
        
        for i, metric in enumerate(metrics):
            if metric in df_plot.columns:
                axes[i].plot(df_plot.index, df_plot[metric], 
                           color=metric_info[metric]['color'], 
                           linewidth=2, marker='o', markersize=2)
                axes[i].set_ylabel(f"{get_unit(metric)}", fontsize=10)
                axes[i].set_title(f"{metric.replace('_', ' ').title()}", fontsize=11)
                axes[i].grid(True, alpha=0.3)
        
        # Set xlabel only on bottom plot
        axes[-1].set_xlabel('Time', fontsize=12)
        axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
        plt.xticks(rotation=45, ha='right')
        
        fig.suptitle(f"Weather Data - {time_start} to {time_end}", fontsize=14, y=0.995)
        plt.tight_layout()
    
    # Save as PNG
    png_buffer = io.BytesIO()
    plt.savefig(png_buffer, format='png', dpi=150, bbox_inches='tight')
    png_buffer.seek(0)
    png_base64 = base64.b64encode(png_buffer.getvalue()).decode('utf-8')
    plot_files.append({
        'filename': f"{base_filename}.png",
        'type': 'png',
        'description': f'Weather Plot (PNG) - {base_filename}',
        'data_url': f"data:image/png;base64,{png_base64}"
    })
    
    # Save as SVG
    svg_buffer = io.BytesIO()
    plt.savefig(svg_buffer, format='svg', bbox_inches='tight')
    svg_buffer.seek(0)
    svg_base64 = base64.b64encode(svg_buffer.getvalue()).decode('utf-8')
    plot_files.append({
        'filename': f"{base_filename}.svg",
        'type': 'svg',
        'description': f'Weather Plot (SVG) - {base_filename}',
        'data_url': f"data:image/svg+xml;base64,{svg_base64}"
    })
    
    # Close the figure to free memory
    plt.close(fig)
    
    return plot_files

def _create_excel_export(df_pivot, metrics: List[str], time_start: str, time_end: str, units: str = 'metric'):
    """Create an Excel export of the weather data and return in-memory files."""
    
    # Create base filename with timestamp
    safe_start = time_start.replace(' ', '_').replace(':', '-')
    safe_end = time_end.replace(' ', '_').replace(':', '-')
    base_filename = f"weather_data_{safe_start}_to_{safe_end}"
    
    # Reset index to make timestamp a column and format as string for Excel compatibility
    df_export = df_pivot.reset_index()
    df_export['timestamp'] = df_export['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # Convert data to imperial if requested
    if units == 'imperial':
        for metric in metrics:
            if metric in df_export.columns:
                if metric == 'temperature':
                    df_export[metric] = df_export[metric] * 9/5 + 32
                elif metric == 'dew_point':
                    df_export[metric] = df_export[metric] * 9/5 + 32
                elif metric == 'pressure':
                    df_export[metric] = df_export[metric] * 0.02953
                elif metric in ['wind_speed', 'wind_gust']:
                    df_export[metric] = df_export[metric] * 0.621371
                elif metric == 'rain':
                    df_export[metric] = df_export[metric] * 0.0393701
    
    df_export = df_export[['timestamp'] + [col for col in metrics if col in df_export.columns]]
    
    # Add units to column names
    unit_map = {
        'temperature': '°C' if units == 'metric' else '°F',
        'humidity': '%',
        'dew_point': '°C' if units == 'metric' else '°F',
        'pressure': 'mbar' if units == 'metric' else 'inHg',
        'wind_speed': 'km/h' if units == 'metric' else 'mph',
        'wind_gust': 'km/h' if units == 'metric' else 'mph',
        'wind_direction': '°',
        'solar_radiation': 'W/m²',
        'rain': 'mm' if units == 'metric' else 'in'
    }
    
    # Rename columns with units
    column_mapping = {'timestamp': 'Timestamp'}
    for col in df_export.columns:
        if col in unit_map:
            column_mapping[col] = f"{col.replace('_', ' ').title()} ({unit_map[col]})"
    
    df_export = df_export.rename(columns=column_mapping)
    
    # Generate in-memory files
    excel_files = []
    
    # Excel (.xlsx) export
    excel_buffer = io.BytesIO()
    df_export.to_excel(excel_buffer, index=False, sheet_name='Weather Data', engine='openpyxl')
    excel_buffer.seek(0)
    excel_base64 = base64.b64encode(excel_buffer.getvalue()).decode('utf-8')
    excel_files.append({
        'filename': f"{base_filename}.xlsx",
        'type': 'xlsx',
        'description': f'Weather Data Excel File - {base_filename}',
        'data_url': f"data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{excel_base64}"
    })
    
    # CSV export
    csv_buffer = io.StringIO()
    df_export.to_csv(csv_buffer, index=False)
    csv_data = csv_buffer.getvalue()
    csv_base64 = base64.b64encode(csv_data.encode('utf-8')).decode('utf-8')
    excel_files.append({
        'filename': f"{base_filename}.csv",
        'type': 'csv',
        'description': f'Weather Data CSV File - {base_filename}',
        'data_url': f"data:text/csv;base64,{csv_base64}"
    })
    
    print(f"Excel and CSV files generated in-memory: {base_filename}")
    return excel_files
