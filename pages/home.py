from flask import Flask, render_template, request, redirect, url_for

def register(app):
    @app.route('/')
    def hello_world():  # put application's code here
        return render_template("home/home.html")