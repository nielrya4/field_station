from flask import Flask, render_template, request, redirect, url_for

def register(app):
    @app.route('/gallery')
    def gallery():
        return render_template("gallery/gallery.html")
