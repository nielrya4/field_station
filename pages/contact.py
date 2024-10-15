from flask import Flask, render_template, request, redirect, url_for

def register(app):
    @app.route('/contact')
    def contact():
        return render_template("contact/contact.html")

    @app.route('/contact/send-message')
    def send_message():
        pass