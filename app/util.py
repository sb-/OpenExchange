from flask import Blueprint, Response, session, render_template
from app.database import init_db,  db_session, redis
from app.config import config

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
