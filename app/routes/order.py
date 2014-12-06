"""
=================
Order functions
=================
"""


from flask import Blueprint, request
from app.util import home_page, is_logged_in
from app.database import redis
order = Blueprint('order', __name__, url_prefix='/order')


@order.route('/add', methods=['POST'])
def addorder():
    """ Checks balance and essential stuff, generates an order ID then adds order to a redis queue. """
    instrument = request.form['currency_pair']
    if not is_logged_in(session):
        return home_page(
            instrument,
            danger="Please log in to perform that action.")

    # They shouldn't be able to modify the trade pair, if it isnt valid either
    # I messed up somewhere or they are trying to do something wrong
    if not config.is_valid_instrument(instrument):
        return home_page(
            "ltc_btc",
            danger="Unknown Error, contact the administrator!")

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
        return home_page(
            instrument,
            danger="Please enter numerical values for price and amount!")
    if ramount < 1:  # TODO: find a good amount for this
        return home_page(instrument, danger="Transaction amount too low!")
    if rprice <= 0:
        return home_page(instrument, danger="Price must be greater than 0!")

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
            return home_page(
                instrument,
                danger="Balance too low to execute order!")
        else:
            adjustbalance(currency, session['userid'], -1 * total)
    elif request.form['ordertype'] == 'sell':
        currency = base_currency
        if check_balance(currency, uid) < ramount:
            return home_page(
                instrument,
                danger="Balance too low to execute order!")
        else:
            adjustbalance(currency, uid, -1 * ramount)
    else:
        # invalid order type, they must have been messing around
        return home_page(
            instrument,
            danger="Unknown Error, contact the administrator!")
    redis.hmset(orderid,
                {"ordertype": request.form['ordertype'],
                 "instrument": request.form['currency_pair'],
                 "amount": ramount,
                 "uid": uid,
                 "price": rprice})
    redis.rpush("order_queue", orderid)
    redis.sadd(str(uid) + "/orders", orderid)
    return home_page(instrument, dismissable="Order placed successfully!")


@order.route('/cancel/<old_order_id>', methods=['GET'])
def cancelorder(old_order_id):
    if not is_logged_in(session):
        return home_page(
            "ltc_btc",
            danger="Please log in to perform that action.")
    uid = session['userid']
    if old_order_id not in redis.smembers(str(uid) + "/orders"):
        return home_page(
            "ltc_btc",
            danger="Unable to cancel the specified order!")
    orderid = generate_password_hash(str(random.random()))
    redis.hmset(orderid, {"ordertype": 'cancel', "uid": uid, 'old_order_id': old_order_id})
    redis.rpush("order_queue", orderid)
    return home_page("ltc_btc", dismissable="Cancelled order!")
    # Note: their order may have already been filled by an order that is ahead
    # of the cancellation in the queue, so do not credit their account here
