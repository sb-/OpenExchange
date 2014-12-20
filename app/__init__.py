from flask import Flask, g, session
from flask.ext.mail import Mail, Message
from app.database import init_db, db_session, redis

app = Flask(__name__)
app.config.update(
    DEBUG=True,
    SECRET_KEY='CHANGE_THIS',
    # EMAIL SETTINGS
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=465,
    MAIL_USE_SSL=True,
    MAIL_USERNAME='admin@gmail.com',
    MAIL_PASSWORD='password'
)

from .config import config
from app.routes.api import api
from app.routes.home import home
from app.routes.account import account
from app.routes.order import order
from app.util import check_balance
from flask_bootstrap import Bootstrap


app.register_blueprint(api)
app.register_blueprint(home)
app.register_blueprint(order)
app.register_blueprint(account)

mail = Mail(app)
Bootstrap(app)

@app.before_request
def before_request():
    g.db = connect_db()


@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()


@app.context_processor
def balance_processor():
    """ Used to get balance of currencies from the template for the account page. Flask required this for a callable function from the template.
        For example, in the template one can do {{ getbalance("btc", 48549) }}. The division is done because this is what the front-end user sees,
        and they do not want prices in satoshis or cents"""
    def getbalance(c, uid):
        return "{:.4f}".format(
            check_balance(
                c,
                uid) /
            float(
                config.get_multiplier(c)))
    return dict(getbalance=getbalance)


def connect_db():
    init_db()
