from flask import Flask, render_template, request, redirect, url_for

def register(app):
    @app.route('/facilities')
    def facilities():
        return render_template("facilities/facilities.html")
