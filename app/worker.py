##############################
# worker.py (transaction processing)
##############################

from database import init_db, db_session, redis
from models import CompletedOrder
from util import adjustbalance, generate_password_hash
import random
from config import config
#import daemon


def fill_order():
    """ Typical limit order book implementation, handles orders in Redis and writes exchange history to SQL. """
    orderid = redis.blpop("order_queue")[1]
    order = redis.hgetall(orderid)
    print("FILLING ORDER: " + str(order))
    ordertype = order["ordertype"]

    # do this here, the canceled order hashes dont have all the info that
    # normal ones do
    if ordertype == "cancel":
        old_order_id = order['old_order_id']
        if redis.exists(old_order_id):
            old_order = redis.hgetall(old_order_id)
            redis.delete(old_order_id)
            cUID = old_order['uid']
            ramount = int(old_order["amount"])
            instrument = old_order["instrument"]
            price = float(old_order["price"])

            redis.lrem("order_queue", old_order_id)
            redis.srem(str(cUID) + "/orders", old_order_id)

            if old_order['ordertype'] == 'buy':
                redis.zrem(old_order['instrument'] + "/bid", old_order_id)
                adjustbalance(
                    instrument.split("_")[1],
                    cUID,
                    ramount *
                    price,
                    price)
            elif old_order['ordertype'] == 'sell':
                redis.zrem(old_order['instrument'] + "/ask", old_order_id)
                adjustbalance(instrument.split("_")[0], cUID, ramount, price)
        return

    ramount = int(order["amount"])
    instrument = order["instrument"]
    base_currency = instrument.split("_")[0]
    quote_currency = instrument.split("_")[1]
    bidtable = instrument + "/bid"
    asktable = instrument + "/ask"
    completedlist = instrument + "/completed"
    price = float(order["price"])
    uid = order["uid"]

    if ordertype == 'buy':
        lowesthash = redis.zrange(asktable, 0, 0)
        # search ask table to see if there are any orders that are at or below
        # this price
        lowestprice = 0.0
        norders = redis.zcard(asktable)
        if norders > 0:
            lowestprice = redis.zscore(asktable, lowesthash[0])
        amount_to_buy = 0
        if lowestprice > price or norders < 1:
            # if there are none, add straight to the orderbook
            redis.zadd(bidtable, orderid, price)
        else:
            orders = redis.zrangebyscore(asktable, 0, price)
            # Go through as many valid orders as needed
            for current in orders:
                camt = int(redis.hget(current, "amount"))
                cUID = redis.hget(current, "uid")
                if ramount < camt:
                    # Adjust their amount
                    amount_to_buy = ramount
                    ramount = 0
                    redis.hset(current, "amount", camt - amount_to_buy)
                    amount_to_credit = price * ramount
                    adjustbalance(
                        quote_currency,
                        cUID,
                        price *
                        amount_to_buy,
                        price)

                else:
                    # Our order is bigger than theirs, we can remove them from
                    # the books
                    amount_to_buy += camt
                    ramount -= camt
                    redis.delete(current)
                    redis.zrem(asktable, current)
                    redis.srem(str(cUID) + "/orders", current)
                    adjustbalance(quote_currency, cUID, price * camt, price)
                co = CompletedOrder(
                    instrument,
                    'sell',
                    amount_to_buy,
                    price,
                    cUID)
                db_session.add(co)
                completedtxredis = generate_password_hash(
                    current + str(random.random()))
                redis.hmset(
                    completedtxredis,
                    {
                        'price': price,
                        'quote_currency_amount': price *
                        amount_to_buy /
                        config.get_multiplier(quote_currency),
                        'base_currency_amount': amount_to_buy /
                        config.get_multiplier(base_currency)})
                # redis.expire(completedtxredis,86400) # 24 * 60 * 60
                redis.zadd(completedlist, completedtxredis, price)
                if ramount == 0:
                    redis.srem(str(uid) + "/orders", orderid)
                    # TODO: Write a completed transaction to SQL??
                    break
        if ramount != 0:
            redis.zadd(bidtable, orderid, price)
            redis.hset(orderid, "amount", ramount)
        if(amount_to_buy != 0):
            # TODO: Write a completed transaction to SQL
            adjustbalance(base_currency, uid, amount_to_buy, price)
            co = CompletedOrder(instrument, 'buy', amount_to_buy, price, uid)
            db_session.add(co)

    elif ordertype == 'sell':
        # search bid table to see if there are are at or above this price
        highesthash = redis.zrange(bidtable, -1, -1)
        norders = redis.zcard(bidtable)
        highestprice = 0
        if norders > 0:
            highestprice = redis.zscore(
                bidtable,
                highesthash[0])  # unsure why, but this workaround is needed for now
        if norders < 1 or highestprice < price:
            # if not add straight to the books
            redis.zadd(asktable, orderid, price)
        else:
            orders = redis.zrangebyscore(bidtable, price, '+inf')[::-1]
            amount_to_credit = 0
            for current in orders:
                camt = int(redis.hget(current, "amount"))
                cUID = redis.hget(current, "uid")
                if ramount < camt:
                    amount_to_credit += ramount
                    amount_to_sell = ramount
                    ramount = 0
                    redis.hset(current, "amount", camt - amount_to_sell)
                    amount_to_credit += ramount
                    adjustbalance(base_currency, cUID, amount_to_sell, price)

                else:
                    amount_to_credit += camt
                    amount_to_sell = camt
                    ramount -= camt
                    redis.delete(current)
                    redis.zrem(bidtable, current)
                    redis.srem(str(cUID) + "/orders", current)
                    adjustbalance(base_currency, cUID, amount_to_sell, price)

                co = CompletedOrder(
                    instrument,
                    'buy',
                    amount_to_sell,
                    price,
                    cUID)
                db_session.add(co)
                completedtxredis = generate_password_hash(
                    current + str(random.random()))
                redis.hmset(
                    completedtxredis,
                    {
                        'price': price,
                        'quote_currency_amount': price *
                        amount_to_sell /
                        config.get_multiplier(quote_currency),
                        'base_currency_amount': amount_to_sell /
                        config.get_multiplier(base_currency)})
                # redis.expire(completedtxredis,86400) # 24 * 60 * 60
                redis.zadd(completedlist, completedtxredis, price)

                if ramount == 0:
                    # TODO: Write a completed transaction to SQL
                    redis.srem(str(uid) + "/orders", orderid)
                    break
            if(ramount != 0):
                redis.zadd(asktable, orderid, price)
                redis.hset(orderid, "amount", ramount)
            if(amount_to_credit != 0):
                # TODO: Write a completed transaction to SQL
                adjustbalance(
                    quote_currency,
                    uid,
                    amount_to_credit *
                    price,
                    price)
                co = CompletedOrder(
                    instrument,
                    'sell',
                    amount_to_credit *
                    price,
                    price,
                    uid)
                db_session.add(co)
    else:
        pass  # TODO: throw an error, not a buy or sell

    # db_session.add(b)
    db_session.commit()


# with daemon.DaemonContext():
#    while True:
#        fill_order()

# For testing
while True:
    fill_order()
