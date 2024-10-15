from flask import Flask, render_template, request, redirect, url_for

def register(app):
    @app.route('/visit')
    def visit():  # put application's code here
        return render_template("visit/visit.html")
