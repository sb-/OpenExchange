"""
=================
Home/Basic Stuff
=================
"""

from flask import Blueprint, session, request, render_template, flash

from app.util import home_page
from app.util import generate_password_hash, check_password_hash, generate_deposit_address, is_logged_in, account_page
from app.database import db_session, redis
from app.models import *
from app.config import config
import time
from wtforms import Form, BooleanField, TextField, PasswordField, validators

home = Blueprint('home', __name__, url_prefix='/')


""" Basic/Account stuff """
class RegistrationForm(Form):
    """Example form straight from Flask-WTF documentation. """
    username = TextField('Name', [validators.Length(min=4, max=25)])
    email = TextField('Email Address', [validators.Length(min=6, max=35)])
    password = PasswordField('New Password', [
        validators.Required(),
        validators.EqualTo('confirm', message='Passwords must match')
    ])
    confirm = PasswordField('Repeat Password')

class LoginForm(Form):
    """Example form straight from Flask-WTF documentation. """
    email = TextField('Email Address', [validators.Length(min=6, max=35)])
    password = PasswordField('Password', [validators.Required()])
    #accept_tos = BooleanField('I accept the TOS', [validators.Required()])

@home.route('/')
def homepage():
    # for rule in app.url_map.iter_rules():
    #	if "GET" in rule.methods:
    #		print(rule.endpoint + " " + url_for(rule.endpoint))
    return home_page("ltc_btc")


@home.route('account')
def account():
    if not is_logged_in(session):
        return home_page(
            "ltc_btc",
            danger="Please log in to perform that action.")
    return account_page()


@home.route('login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user = User.query.filter(User.email == request.form['email']).first()
        if not user:
            flash('Please check your email and username.', 'danger')
            return render_template('login2.html')
        elif not check_password_hash(user.password, request.form['password']):
            flash('Please check your email and username.', 'danger')
            return render_template('login2.html')
        elif not user.activated:
            flash('Please confirm your email before logging in.', 'error')
            return render_template('login2.html')
        else:
            session['logged_in'] = True
            session['userid'] = User.query.filter(
                User.email == request.form['email']).first().id
            session['expire'] = time.time() + 3600
            flash("Logged in!","dismissable")
            return home_page("ltc_btc")
    return render_template('login2.html')


@home.route('register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if "" in request.form.values():
            return render_template("register.html")
        if request.form['username'] in list(User.query.values(User.name)):
            flash('Please enter a password.', 'error')
            return render_template("register.html")
        if request.form['email'] in list(User.query.values(User.email)):
            flash('Please enter a valid email.', 'error')
            return render_template("register.html")
        if request.form['password'] != request.form['passwordconfirm']:
            flash('Passwords do not match.', 'error')
            return render_template("register.html")
        # TODO: error for when they try to register when logged in already
        u = User(
            request.form['username'],
            request.form['email'],
            generate_password_hash(
                request.form['password'].strip()))
        db_session.add(u)
        db_session.commit()

        """for currency in config.get_currencies():
            addr = generate_deposit_address(currency)
            a = Address(currency, addr, u.id)
            db_session.add(a)
        db_session.commit()
        if not send_confirm_email(u.id):
            flash('An error occured during registration. Please contact the administrator.', 'danger')
            return home_page("ltc_btc")"""
        flash('Successfully registered. Please check your email and confirm your account before logging in.', 'dismissable')
        return home_page("ltc_btc")

    if request.method == 'GET':
        return render_template("register.html")


@home.route("activate/<code>")
def activate_account(code):
    uid = redis.hget('activation_keys', code)
    if not uid:
        return home_page("ltc_btc", danger='Invalid registration code!')
    user = User.query.filter(User.id == uid).first()
    if not user or user.activated:
        return home_page(
            "ltc_btc",
            danger='Account already registered or invalid code!')
    user.activated = True
    redis.hdel('activation_keys', code)
    db_session.commit()
    flash("Account successfully registered!", "dismissable")
    return home_page("ltc_btc")


@home.route('logout')
def logout():
    session.pop('logged_in', None)
    session.pop('userid', None)
    flash("Successfully logged out!", "dismissable")
    return home_page("ltc_btc")


def send_confirm_email(uid):
    user = User.query.filter(User.id == uid).first()
    if user:
        if not user.activated:
            code = generate_password_hash(str(random.random()))
            redis.hset("activation_keys", code, str(uid))
            msg = Message(
                'Activation Code',
                sender="admin@gmail.org",
                recipients=[
                    user.email])
            msg.body = "Thank you for signing up at OpenExchange. Activate your account at http://localhost:5000/activate/{}".format(
                code)
            mail.send(msg)
            return True
    return False


@home.route('trade/<instrument>')
def trade_page(instrument):
    if not config.is_valid_instrument(instrument):
        flash('Invalid trade pair!', 'danger')
        return home_page("ltc_btc")
    return home_page(instrument)
