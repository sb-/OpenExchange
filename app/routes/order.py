"""
=================
Order functions
=================
"""


from flask import Blueprint, request, flash, session
from app.util import home_page, is_logged_in, string_to_currency_unit, generate_password_hash, check_balance, adjustbalance
from app.database import redis
from app.config import config
from decimal import Decimal, ExtendedContext, getcontext
import random
order = Blueprint('order', __name__, url_prefix='/order')


@order.route('/add', methods=['POST'])
def addorder():
    """ Checks balance and essential stuff, generates an order ID then adds order to a redis queue. """
    instrument = request.form['currency_pair']
    if not is_logged_in(session):
        flash("Please log in to perform that action.", "error")
        return home_page(instrument)

    # They shouldn't be able to modify the trade pair, if it isnt valid either
    # I messed up somewhere or they are trying to do something wrong
    if not config.is_valid_instrument(instrument):
        flash("Unknown Error, contact the administrator!", "error")
        return home_page("ltc_btc")

    base_currency = request.form['currency_pair'].split("_")[0]
    quote_currency = request.form['currency_pair'].split("_")[1]
    try:
        rprice = Decimal(request.form['price'])
        ramount = string_to_currency_unit(
            request.form['amount'],
            config.get_multiplier(base_currency))
        print(ramount)
    except Exception as e:
        print(e)
        flash("Please enter numerical values for price and amount!", "error")
        return home_page(instrument)
    if ramount < 1:  # TODO: find a good amount for this
        flash("Transaction amount too low!", "error")
        return home_page(instrument)
    if rprice <= 0:
        flash("Price must be greater than 0!", "error")
        return home_page(instrument)

    getcontext().prec = 6
    whole, dec = ExtendedContext.divmod(
        rprice * ramount / config.get_multiplier(base_currency), Decimal(1))
    total = int(
        whole *
        config.get_multiplier(base_currency) +
        dec *
        config.get_multiplier(base_currency))
    print("total: " + str(total))
    uid = session['userid']

    orderid = generate_password_hash(str(random.random()))
    instrument = request.form['currency_pair']
    bidtable = instrument + "/bid"
    asktable = instrument + "/ask"

    if request.form['ordertype'] == 'buy':
        currency = quote_currency
        if check_balance(currency, session['userid']) < total:
            flash("Balance too low to execute order!", "error")
            return home_page(instrument)
        else:
            adjustbalance(currency, session['userid'], -1 * total)
    elif request.form['ordertype'] == 'sell':
        currency = base_currency
        if check_balance(currency, uid) < ramount:
            flash("Balance too low to execute order!", "error")
            return home_page(instrument)
        else:
            adjustbalance(currency, uid, -1 * ramount)
    else:
        # invalid order type, they must have been messing around
        flash("Unknown Error, contact the administrator!", "error")
        return home_page(instrument)
    redis.hmset(orderid,
                {"ordertype": request.form['ordertype'],
                 "instrument": request.form['currency_pair'],
                 "amount": ramount,
                 "uid": uid,
                 "price": rprice})
    redis.rpush("order_queue", orderid)
    redis.sadd(str(uid) + "/orders", orderid)
    flash("Order placed successfully!","dismissable")
    return home_page(instrument)


@order.route('/cancel/<old_order_id>', methods=['GET'])
def cancelorder(old_order_id):
    if not is_logged_in(session):
        flash("Please log in to perform that action.", "error")
        return home_page("ltc_btc")
    uid = session['userid']
    if old_order_id not in redis.smembers(str(uid) + "/orders"):
        flash("Unable to cancel the specified order!", "error")
    else:
        orderid = generate_password_hash(str(random.random()))
        redis.hmset(orderid, {"ordertype": 'cancel', "uid": uid, 'old_order_id': old_order_id})
        redis.rpush("order_queue", orderid)
        flash("Cancelled order!", "dismissable")
    return home_page("ltc_btc")
    # Note: their order may have already been filled by an order that is ahead
    # of the cancellation in the queue, so do not credit their account here
