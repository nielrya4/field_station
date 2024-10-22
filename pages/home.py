from flask import Flask, render_template, request, redirect, url_for

def register(app):
    @app.route('/')
    def home():
        return render_template("home/home.html")
