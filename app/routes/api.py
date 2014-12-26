"""
=================
API/JSON functions
=================
"""

import json

from flask import Blueprint, Response
from app.config import config
from app.database import redis

api = Blueprint('api', __name__, url_prefix='/api')


@api.route('/volume/<instrument>')
def getvolumejson(instrument):
    """ Returns open orders from redis orderbook. """
    res = getvolume(instrument)
    jo = json.dumps(res)
    return Response(jo, mimetype='application/json')


@api.route('/high/<instrument>')
def gethighjson(instrument):
    """ Returns open orders from redis orderbook. """
    jo = json.dumps({'high': gethigh(instrument)})
    return Response(jo, mimetype='application/json')


@api.route('/low/<instrument>')
def getlowjson(instrument):
    """ Returns open orders from redis orderbook. """
    jo = json.dumps({'low': getlow(instrument)})
    return Response(jo, mimetype='application/json')


@api.route('/orders/<instrument>/<t>')
def getjsonorders(instrument, t):
    """ Returns open orders from redis orderbook. """
    orders = []
    if config.is_valid_instrument(instrument):
        if t == "bid":
            bids = redis.zrange(instrument + "/bid", 0, -1, withscores=True)
            for bid in bids:
                orders.append(
                    {"price": bid[1], "amount": redis.hget(bid[0], "amount")})
        else:
            asks = redis.zrange(instrument + "/ask", 0, -1, withscores=True)
            for ask in asks:
                orders.append(
                    {"price": ask[1], "amount": redis.hget(ask[0], "amount")})
        # So prices are not quoted in satoshis
        # TODO: move this client side?
        for order in orders:
            order['amount'] = float(
                order['amount']) / config.get_multiplier(instrument.split("_")[0])
    else:
        orders.append("Invalid trade pair!")
    jo = json.dumps(orders)
    return Response(jo, mimetype='application/json')
