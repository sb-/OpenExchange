##############################
#app.py (core app)
##############################

from flask import Flask, request, session, g, redirect, url_for, \
     abort, render_template, flash, jsonify, Response
from werkzeug import secure_filename
from database import init_db,  db_session, redis
from models import *
from cPickle import loads, dumps
import hashlib
from jsonrpc import ServiceProxy
import random
import inspect
import json
import time
from config import config
from decimal import ExtendedContext, Decimal, getcontext
from flask.ext.mail import Mail, Message


"""
=================
Flask configuration
=================
"""

app = Flask(__name__)
app.config.update(
    DEBUG=True,
    SECRET_KEY = 'CHANGE_THIS',
    #EMAIL SETTINGS
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=465,
    MAIL_USE_SSL=True,
    MAIL_USERNAME = 'admin@gmail.com',
    MAIL_PASSWORD = 'password'
    )

#app.config.from_object(__name__)

mail=Mail(app)


"""
=================
Request stuff
=================
"""
@app.before_request
def before_request():
    g.db = connect_db()

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()


"""
=================
Request Routing
=================
"""

""" Basic/Account stuff """
@app.route('/')
def home():    
    return home_page("ltc_btc")

@app.route('/account')
def account(): 
    if not is_logged_in(session):
        return home_page("ltc_btc",danger="Please log in to perform that action.")
    return account_page()

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user = User.query.filter(User.email==request.form['email']).first()
        if not user:
            return render_template('login2.html', error="Please check your email and username.")
        elif not check_password_hash(user.password, request.form['password']):
            return render_template('login2.html', error="Please check your email and username.")
        elif not user.activated:
            return render_template('login2.html', error="Please confirm your email before logging in.")
        else:
            session['logged_in'] = True
            session['userid'] = User.query.filter(User.email == request.form['email']).first().id
            session['expire'] = time.time() + 3600
            return home_page("ltc_btc",success="Logged in!")
    return render_template('login2.html')

@app.route('/register',methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if "" in request.form.values():
            return render_template("register.html")
        if request.form['username'] in list(User.query.values(User.name)):
            return render_template("register.html",error="Please enter a password.")
        if request.form['email'] in list(User.query.values(User.email)):
            return render_template("register.html",error="Please enter a valid email.")
        if request.form['password'] != request.form['passwordconfirm']:
            return render_template("register.html",error="Passwords do not match.")
        #TODO: error for when they try to register when logged in already
        u = User(request.form['username'], request.form['email'],generate_password_hash(request.form['password'].strip()))
        db_session.add(u)
        db_session.commit()

        for currency in config.get_currencies():
            addr = generate_deposit_address(currency)
            a = Address(currency,addr,u.id)
            db_session.add(a)
        db_session.commit()
        if not send_confirm_email(u.id):
            return home_page("ltc_btc", danger='An error occured during registration. Please contact the administrator.')
        return home_page("ltc_btc", dismissable='Successfully registered. Please check your email and confirm your account before logging in.')

    if request.method == 'GET':
        return render_template("register.html")

@app.route("/activate/<code>")       
def activate_account(code):
    uid = redis.hget('activation_keys', code)
    if not uid:
        return  home_page("ltc_btc", danger='Invalid registration code!')
    user = User.query.filter(User.id==uid).first()
    if not user or user.activated:
        return  home_page("ltc_btc", danger='Account already registered or invalid code!')
    user.activated = True
    redis.hdel('activation_keys', code)
    db_session.commit()
    return home_page("ltc_btc", dismissable='Account successfully registered!')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('userid', None)
    return home_page("ltc_btc", dismissable="Successfully logged out!")

""" Operations that actually involve currency. """
@app.route('/addorder',methods=['POST'])
def addorder():

    """ Checks balance and essential stuff, generates an order ID then adds order to a redis queue. """
    instrument = request.form['currency_pair']
    if not is_logged_in(session):
        return home_page(instrument, danger="Please log in to perform that action.")
    
    #They shouldn't be able to modify the trade pair, if it isnt valid either I messed up somewhere or they are trying to do something wrong
    if not config.is_valid_instrument(instrument):
        return home_page("ltc_btc", danger="Unknown Error, contact the administrator!") 

    base_currency = request.form['currency_pair'].split("_")[0]
    quote_currency = request.form['currency_pair'].split("_")[1]
    try:
        rprice = Decimal(request.form['price'])
        ramount = string_to_currency_unit(request.form['amount'], config.get_multiplier(base_currency))
        print(ramount)
    except Exception as e:
        print(e)
        return home_page(instrument, danger="Please enter numerical values for price and amount!") 
    if ramount < 1: #TODO: find a good amount for this
        return home_page(instrument, danger="Transaction amount too low!") 
    if rprice <= 0:
        return home_page(instrument, danger="Price must be greater than 0!") 

    getcontext().prec = 6
    whole, dec = ExtendedContext.divmod(rprice*ramount/config.get_multiplier(base_currency), Decimal(1))
    total = int(whole * config.get_multiplier(base_currency) + dec * config.get_multiplier(base_currency)) 
    print("total: " + str(total))
    uid = session['userid']

    orderid = generate_password_hash(str(random.random()))
    instrument = request.form['currency_pair']
    bidtable = instrument + "/bid"
    asktable = instrument + "/ask"

    if request.form['ordertype'] == 'buy': 
        currency = quote_currency
        if check_balance(currency,session['userid']) < total:
            return home_page(instrument, danger="Balance too low to execute order!")
        else:
            adjustbalance(currency,session['userid'],-1 * total)
    elif request.form['ordertype'] == 'sell':
        currency = base_currency
        if check_balance(currency, uid) < ramount:
            return home_page(instrument, danger="Balance too low to execute order!")
        else:
            adjustbalance(currency, uid, -1 * ramount)
    else:
        return home_page(instrument, danger="Unknown Error, contact the administrator!") #invalid order type, they must have been messing around
    redis.hmset(orderid, {"ordertype":request.form['ordertype'],"instrument":request.form['currency_pair'],"amount":ramount, "uid":uid,"price":rprice})
    redis.rpush("order_queue",orderid)
    redis.sadd(str(uid)+"/orders", orderid)
    return home_page(instrument, dismissable="Order placed successfully!")
   
@app.route('/cancelorder/<old_order_id>',methods=['GET'])
def cancelorder(old_order_id):
    if not is_logged_in(session):
        return home_page("ltc_btc",danger="Please log in to perform that action.")
    uid = session['userid']
    if old_order_id not in redis.smembers(str(uid)+"/orders"):
        return home_page("ltc_btc",danger="Unable to cancel the specified order!")    
    orderid = generate_password_hash(str(random.random()))
    redis.hmset(orderid, {"ordertype":'cancel', "uid":uid, 'old_order_id':old_order_id})
    redis.rpush("order_queue",orderid)
    return home_page("ltc_btc", dismissable="Cancelled order!")
    # Note: their order may have already been filled by an order that is ahead of the cancellation in the queue, so do not credit their account here

@app.route('/withdraw/<currency>', methods=['GET', 'POST'])
def withdraw(currency): 
    if not is_logged_in(session):
        return home_page("ltc_btc",danger="Please log in to perform that action.")
    if not config.is_valid_currency(currency):
        return account_page(danger="Invalid Currency!")
    if request.method == 'GET':
        return account_page(withdraw=currency)
    elif request.method == 'POST':
        if 'amount' not in request.form or 'address' not in request.form:
            return account_page(danger="Please enter an address and an amount!") #TODO: change this error
        try:
            total = string_to_currency_unit(request.form['amount'], config.get_multiplier(currency))
        except:
            return account_page(danger="Invalid amount!")
        if check_balance(currency,session['userid']) < total or total < 0:
            return account_page(danger="Balance too low to execute withdrawal!")
        #TODO: add valid address checking
        adjustbalance(currency,session['userid'],-1 * total)
        co = CompletedOrder(currency + "_" + currency, "WITHDRAWAL", total, 0, session['userid'], is_withdrawal=True, withdrawal_address=request.form['address'])
        db_session.add(co)
        db_session.commit()
        return account_page(success="Deposit to " + request.form['address'] + " completed!")

@app.route('/deposit/<currency>')
def deposit(currency):
    """ Returns deposit address for given currency from SQL. """
    if not is_logged_in(session):
        return home_page("ltc_btc",danger="Please log in to perform that action.")
    if not config.is_valid_currency(currency):
        return account_page(danger="Invalid Currency!")
    addr =  Address.query.filter(Address.currency==currency).filter(Address.user==session['userid']).first().address
    return account_page(deposit=addr)

@app.route('/history/<currency>')
def history(currency): 
    if not is_logged_in(session):
        return home_page("ltc_btc",danger="Please log in to perform that action.")
    if not config.is_valid_currency(currency):
        return account_page(danger="Invalid Currency!")
    return account_page(history=currency, orders=tradehistory(currency, session['userid']))


@app.route('/trade/<instrument>')
def trade_page(instrument):    
    if not config.is_valid_instrument(instrument):
        return home_page("ltc_btc", danger="Invalid trade pair!")
    return home_page(instrument)

@app.route('/getordersjson/<instrument>/<t>')
def getjsonorders(instrument,t):
    """ Returns open orders from redis orderbook. """
    orders = []
    if config.is_valid_instrument(instrument):
        if t == "bid":
            bids = redis.zrange(instrument+"/bid",0,-1,withscores=True)
            for bid in bids:
                orders.append({"price":bid[1], "amount":redis.hget(bid[0],"amount")})
        else:
            asks = redis.zrange(instrument+"/ask",0,-1,withscores=True)
            for ask in asks:
                orders.append({"price":ask[1], "amount":redis.hget(ask[0],"amount")})
        #So prices are not quoted in satoshis
        #TODO: move this client side?
        for order in orders:
            order['amount'] = float(order['amount'])/config.get_multiplier(instrument.split("_")[0])
    else:
        orders.append("Invalid trade pair!")
    jo = json.dumps(orders)
    return Response(jo,  mimetype='application/json')

"""
=================
API/JSON functions
=================
"""

@app.route('/volume/<instrument>')
def getvolumejson(instrument):
    """ Returns open orders from redis orderbook. """
    res = getvolume(instrument)
    jo = json.dumps(res)
    return Response(jo,  mimetype='application/json')

@app.route('/high/<instrument>')
def gethighjson(instrument):
    """ Returns open orders from redis orderbook. """
    jo = json.dumps({'high':gethigh(instrument)})
    return Response(jo,  mimetype='application/json')

@app.route('/low/<instrument>')
def getlowjson(instrument):
    """ Returns open orders from redis orderbook. """
    jo = json.dumps({'low':getlow(instrument)})
    return Response(jo,  mimetype='application/json')


"""
=================
Utility Functions
=================
"""
def check_balance(currency, userid):
    """ Used by the balance_processor ontext processor below. """
    if not is_logged_in(session):
        return home_page("ltc_btc",danger="Please log in before performing that action!")
    current_user = User.query.filter(User.id==userid).first()
    baldict = {"btc":current_user.btc_balance, "ltc":current_user.ltc_balance}
    return baldict[currency]

@app.context_processor
def balance_processor():
    """ Used to get balance of currencies from the template for the account page. Flask required this for a callable function from the template. 
        For example, in the template one can do {{ getbalance("btc", 48549) }}. The division is done because this is what the front-end user sees,
        and they do not want prices in satoshis or cents"""
    def getbalance(c, uid):
        return "{:.4f}".format(check_balance(c, uid)/float(config.get_multiplier(c)))
    return dict(getbalance=getbalance)

def adjustbalance(currency,userid,amount,price=None):
    current_user = User.query.filter(User.id==userid).first()
    #TODO: This function really needs to be cleaned up...
    isminus = amount < 0
    if currency == "btc":
        if isminus and -1 * amount > current_user.btc_balance:
            raise NegativeBalanceError("Error! Tried to withdraw more than balance! UserID: {} Currency: {} Amount: {}".format(userid, currency, amount))
        current_user.btc_balance += amount
    elif currency == "ltc":
        if isminus and -1 * amount > current_user.ltc_balance:
            raise NegativeBalanceError("Error! Tried to withdraw more than balance! UserID: {} Currency: {} Amount: {}".format(userid, currency, amount))
        current_user.ltc_balance += amount
    else:
        print("ERROR IN ADJUSTBALANCE")
    db_session.commit()

def check_password_hash(h, pw):
    return hashlib.sha224(pw).hexdigest() == h

def generate_password_hash(pw):
    return hashlib.sha224(pw).hexdigest()

def connect_db():
    init_db()

def is_logged_in(s):
    """ Checks if a user is logged in and has an uncorrupted session cookie. If the cookie is corrupt, it will clear it."""
    if 'logged_in' in s and 'userid' in s and 'expire' in s:
        u = User.query.filter(User.id==session['userid']).first()
        if not u:
            return False
        if s['expire'] > time.time():
            return True
    s.pop('logged_in', None)
    s.pop('userid', None)
    s.pop('expire', None)
    return False

def generate_deposit_address(currency):
    addr = ""
    if config.is_valid_currency(currency):
        rpc = ServiceProxy(config.getRPC(currency))
        addr = rpc.getnewaddress()
    return addr

def home_page(p, **kwargs):
    return render_template('index2.html', pair=p, volume=getvolume(p), low=getlow(p), high=gethigh(p), pairs=config.get_instruments(),**kwargs)

def account_page(**kwargs):
    return render_template('account.html', currencies=config.get_currencies(),openorders=openorders(session['userid']),**kwargs)

def string_to_currency_unit(s, prec):
    print(s, prec)
    if s.count('.') > 1:
        return
    if s.count('.') == 0:
        return int(s) * prec
    base, dec = s.split(".")
    total = prec * int(base)
    while prec > 1 and dec:
        prec /= 10
        total += int(dec[0]) * prec
        dec = dec[1:]
    return total

def send_confirm_email(uid):
    user = User.query.filter(User.id==uid).first()
    if user:
        if not user.activated:
            code = generate_password_hash(str(random.random()))
            redis.hset("activation_keys", code, str(uid))
            msg = Message('Activation Code', sender="admin@gmail.org", recipients=[user.email])
            msg.body = "Thank you for signing up at OpenExchange. Activate your account at http://localhost:5000/activate/{}".format(code)
            mail.send(msg)
            return True
    return False

""" Used by APIs/grab order information. """
def tradehistory(currency, uid):
    if not is_logged_in(session):
        return home_page("ltc_btc",danger="Please log in to perform that action.")
    orders = CompletedOrder.query.filter(CompletedOrder.user == uid).filter(CompletedOrder.base_currency==str(currency)).all()
    orders2 = []
    for o in orders:
        if o.is_deposit:
            orders2.append(["DEPOSIT",  o.order_type, o.price, str(o.amount) + " " + str(o.base_currency).upper()])
        elif o.is_withdrawal:
            orders2.append(["WITHDRAWAL",  o.order_type, o.price, str(o.amount) + " " + str(o.base_currency).upper()])
        else:
            orders2.append([o.currency_pair,  o.order_type, (str(o.price) + " " + o.quote_currency + "/" + o.base_currency).upper(), str(float(o.amount)/config.get_multiplier(currency))+ " " + str(o.base_currency).upper()])
    return orders2

def openorders(uid):
    if not is_logged_in(session):
        return home_page("ltc_btc",danger="Please log in to perform that action.")
    orders = redis.smembers(str(uid)+"/orders")
    r = []
    for o in orders:
        c = redis.hgetall(o)
        base_currency = c['instrument'][0:c['instrument'].find("_")]
        quote_currency = c['instrument'][c['instrument'].find("_")+1:]
        instrument = (base_currency+"/"+quote_currency).upper()
        r.append([instrument, c['ordertype'], c['price'] + " " + instrument, str(float(c['amount'])/config.get_multiplier(base_currency)) + " " + base_currency.upper(), o])
    return r

def getvolume(instrument):
    """ Returns open orders from redis orderbook. """
    #TODO: add some error checking in here
    completed_book = instrument+"/completed"
    orders = redis.zrange(completed_book,0,-1,withscores=True)
    quote_volume = 0.0
    base_volume = 0.0
    for order in orders:
        # I *REALLY* should not be doing this every time I go though, but it's temporary
        # Note this is evaluated before gethigh and getlow when the front page is displayed so those values should be correct as well due to clean in up here
        if not redis.exists(order[0]):
            redis.zrem(completed_book,order[0])
            continue
        quote_volume += float(redis.hget(order[0],'quote_currency_amount'))
        base_volume += float(redis.hget(order[0],'base_currency_amount'))
    return {"quote_currency_volume":quote_volume, "base_currency_volume":base_volume}

def gethigh(instrument):
    """ Returns 24 hour highest price on the given trade pair. """
    orders = redis.zrange(instrument+"/completed",-1,-1,withscores=True)
    if len(orders)  < 1: return 0
    return orders[0][1]

def getlow(instrument):
    """ Returns 24 hour lowest price on the given trade pair. """
    orders = redis.zrange(instrument+"/completed",0,0,withscores=True)
    if len(orders)  < 1: return 0
    return orders[0][1]


if __name__ == '__main__':
    app.run(host='0.0.0.0')


class NegativeBalanceError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)