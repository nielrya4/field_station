from flask import Flask, render_template, request, redirect, url_for
import requests
from datetime import datetime, timedelta

def register(app):
    @app.route('/weather')
    def weather():
        '''weather_data = get_data()
        revised_weather_data = {
            "temperature": weather_data["temperature"],
            "humidity": weather_data["humidity"],
            "pressure": weather_data["pressure"],
            "wind_speed": weather_data["wind_speed"],
        }
        return render_template("weather/weather.html", weather_data=revised_weather_data)'''
        return render_template("weather/weather.html")

def get_data(all_data=False):
    if all_data:
        formatted_time = "2024-01-01 00:00:00"
    else:
        current_time = datetime.now()
        one_hour_before = current_time - timedelta(hours=1)
        formatted_time = one_hour_before.strftime('%Y-%m-%d %H:%M:%S')
    params = {
        "loggers": 12345,
        "start_date_time": formatted_time
    }
    user_id = 12345
    response = requests.get(f'https://webservice.hobolink.com/ws/data/file/?format=json/user/?userId={user_id}', params=params )
    return response.json()

def filter_data(json_data):
    pass
