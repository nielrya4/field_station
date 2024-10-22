from flask import Flask, render_template, request, redirect, url_for
from flask_mail import Mail, Message
from dotenv import load_dotenv
import os
import smtplib


def register(app):
    @app.route('/contact', methods=['GET', 'POST'])
    def contact():
        if request.method == 'POST':
            load_dotenv()
            email_addr = os.getenv('EMAIL_ADDR', 'not found')
            email_pswd = os.getenv('EMAIL_PSWD', 'not found')
            email_trgt = os.getenv('EMAIL_TRGT', 'not found')

            app.config['MAIL_SERVER'] = 'smtp.gmail.com'
            app.config['MAIL_PORT'] = 587
            app.config['MAIL_USERNAME'] = email_addr
            app.config['MAIL_PASSWORD'] = email_pswd
            app.config['MAIL_USE_TLS'] = True
            app.config['MAIL_USE_SSL'] = False

            mail = Mail(app)

            sender_name = request.form.get('name_input', "No Name")
            sender_email = request.form.get('email_input', "No Email")
            sender_message = request.form.get('message_input', "No Message")
            try:
                msg = Message(subject=f"Field Station Message from {sender_name}",
                              body=f"Name: {sender_name}\nEmail: {sender_email}\nMessage: {sender_message}",
                              sender=email_addr,
                              recipients=[email_trgt])
                mail.send(msg)
            except Exception as e:
                print(f"Error sending email: {e}")
            return render_template("contact/contact_sent.html")
        return render_template("contact/contact.html")