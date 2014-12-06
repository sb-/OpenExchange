##############################
#app.py (core app)
##############################

from flask import Flask, request, session, g, redirect, url_for, \
     abort, render_template, flash, jsonify, Response
from werkzeug import secure_filename
from app.database import init_db,  db_session, redis
from app.models import *
from cPickle import loads, dumps
import hashlib
from jsonrpc import ServiceProxy
import random
import inspect
import json
import time
from app.config import config
from app import app

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



if __name__ == '__main__':
    app.run(host='0.0.0.0')


class NegativeBalanceError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)