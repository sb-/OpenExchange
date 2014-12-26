from flask import Blueprint, Response, session, render_template
from database import init_db, db_session, redis
from config import config
import hashlib
from models import *
import time
from cPickle import loads, dumps
import sys, os.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir)))
#Above two lines needed to get jsonrpc from parent dir
from jsonrpc import ServiceProxy


def check_password_hash(h, pw):
    return hashlib.sha224(pw).hexdigest() == h

def generate_password_hash(pw):
    return hashlib.sha224(pw).hexdigest()


def home_page(p, **kwargs):
    return render_template(
        'index2.html',
        pair=p,
        volume=getvolume(p),
        low=getlow(p),
        high=gethigh(p),
        pairs=config.get_instruments(),
        **kwargs)


def account_page(**kwargs):
    return render_template(
        'account.html',
        currencies=config.get_currencies(),
        openorders=openorders(
            session['userid']),
        **kwargs)


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


def getvolume(instrument):
    """ Returns open orders from redis orderbook. """
    # TODO: add some error checking in here
    completed_book = instrument + "/completed"
    orders = redis.zrange(completed_book, 0, -1, withscores=True)
    quote_volume = 0.0
    base_volume = 0.0
    for order in orders:
        # I *REALLY* should not be doing this every time I go though, but it's temporary
        # Note this is evaluated before gethigh and getlow when the front page
        # is displayed so those values should be correct as well due to clean
        # in up here
        if not redis.exists(order[0]):
            redis.zrem(completed_book, order[0])
            continue
        quote_volume += float(redis.hget(order[0], 'quote_currency_amount'))
        base_volume += float(redis.hget(order[0], 'base_currency_amount'))
    return {
        "quote_currency_volume": quote_volume,
        "base_currency_volume": base_volume}


def gethigh(instrument):
    """ Returns 24 hour highest price on the given trade pair. """
    orders = redis.zrange(instrument + "/completed", -1, -1, withscores=True)
    if len(orders) < 1:
        return 0
    return orders[0][1]


def getlow(instrument):
    """ Returns 24 hour lowest price on the given trade pair. """
    orders = redis.zrange(instrument + "/completed", 0, 0, withscores=True)
    if len(orders) < 1:
        return 0
    return orders[0][1]


def generate_deposit_address(currency):
    addr = ""
    if config.is_valid_currency(currency):
        rpc = ServiceProxy(config.getRPC(currency))
        addr = rpc.getnewaddress()
    return addr


def is_logged_in(s):
    """ Checks if a user is logged in and has an uncorrupted session cookie. If the cookie is corrupt, it will clear it."""
    if 'logged_in' in s and 'userid' in s and 'expire' in s:
        u = User.query.filter(User.id == session['userid']).first()
        if not u:
            return False
        if s['expire'] > time.time():
            return True
    s.pop('logged_in', None)
    s.pop('userid', None)
    s.pop('expire', None)
    return False


def openorders(uid):
    if not is_logged_in(session):
        return home_page(
            "ltc_btc",
            danger="Please log in to perform that action.")
    orders = redis.smembers(str(uid) + "/orders")
    r = []
    for o in orders:
        c = redis.hgetall(o)
        base_currency = c['instrument'][0:c['instrument'].find("_")]
        quote_currency = c['instrument'][c['instrument'].find("_") + 1:]
        instrument = (base_currency + "/" + quote_currency).upper()
        r.append([instrument, c['ordertype'], c['price'] +
                  " " +
                  instrument, str(float(c['amount']) /
                                  config.get_multiplier(base_currency)) +
                  " " +
                  base_currency.upper(), o])
    return r


def check_balance(currency, userid):
    """ Used by the balance_processor ontext processor below. """
    if not is_logged_in(session):
        return home_page(
            "ltc_btc",
            danger="Please log in before performing that action!")
    current_user = User.query.filter(User.id == userid).first()
    baldict = {
        "btc": current_user.btc_balance,
        "ltc": current_user.ltc_balance}
    return baldict[currency]


def adjustbalance(currency, userid, amount, price=None):
    current_user = User.query.filter(User.id == userid).first()
    # TODO: This function really needs to be cleaned up...
    isminus = amount < 0
    if currency == "btc":
        if isminus and -1 * amount > current_user.btc_balance:
            raise NegativeBalanceError(
                "Error! Tried to withdraw more than balance! UserID: {} Currency: {} Amount: {}".format(
                    userid,
                    currency,
                    amount))
        current_user.btc_balance += amount
    elif currency == "ltc":
        if isminus and -1 * amount > current_user.ltc_balance:
            raise NegativeBalanceError(
                "Error! Tried to withdraw more than balance! UserID: {} Currency: {} Amount: {}".format(
                    userid,
                    currency,
                    amount))
        current_user.ltc_balance += amount
    else:
        print("ERROR IN ADJUSTBALANCE")
    db_session.commit()


def tradehistory(currency, uid):
    if not is_logged_in(session):
        return home_page(
            "ltc_btc",
            danger="Please log in to perform that action.")
    orders = CompletedOrder.query.filter(
        CompletedOrder.user == uid).filter(
        CompletedOrder.base_currency == str(currency)).all()
    orders2 = []
    for o in orders:
        if o.is_deposit:
            orders2.append(["DEPOSIT",
                            o.order_type,
                            o.price,
                            str(o.amount) + " " + str(o.base_currency).upper()])
        elif o.is_withdrawal:
            orders2.append(["WITHDRAWAL",
                            o.order_type,
                            o.price,
                            str(o.amount) + " " + str(o.base_currency).upper()])
        else:
            orders2.append([o.currency_pair, o.order_type, (str(o.price) +
                                                            " " +
                                                            o.quote_currency +
                                                            "/" +
                                                            o.base_currency).upper(), str(float(o.amount) /
                                                                                          config.get_multiplier(currency)) +
                            " " +
                            str(o.base_currency).upper()])
    return orders2
