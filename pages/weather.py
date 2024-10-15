from flask import Flask, render_template, request, redirect, url_for

def register(app):
    @app.route('/weather')
    def weather():  # put application's code here
        return render_template("weather/weather.html")
