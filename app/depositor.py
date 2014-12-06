from jsonrpc import ServiceProxy
import cPickle
from .database import init_db, db_session, redis
from .models import *
from app import adjustbalance
from .config import config
import logging
import daemon

logging.basicConfig(filename=config.get_tx_log_file(), level=logging.DEBUG)
currencies = config.get_currencies()
init_db()


def handle_transactions():
    for currency in currencies:
        logging.info('Processing {} deposits'.format(currency))
        oldtransactions = CompletedOrder.query.filter().all()
        oldids = [x.transaction_id for x in oldtransactions]

        rpc = ServiceProxy(currencies[currency]['daemon'])
        transactions = [
            tx for tx in rpc.listtransactions() if tx['category'] == 'receive']
        newtransactions = []

        for tx in transactions:
            if tx['txid'] not in oldids:
                newtransactions.append(tx)
        for tx in newtransactions:
            addr = Address.query.filter(
                Address.address == str(
                    tx['address'])).first()
            if addr:
                logging.info(
                    "New Deposit! TXID: {} Amount: {} UserID: {}".format(
                        tx['txid'],
                        tx['amount'],
                        addr.user))
                adjustbalance(
                    currency, addr.user, int(
                        float(
                            tx['amount']) * currencies[currency]['multiplier']))
                co = CompletedOrder(
                    currency + "_" + currency,
                    "DEPOSIT",
                    float(
                        tx['amount']),
                    0,
                    addr.user,
                    is_deposit=True,
                    transaction_id=tx['txid'])
                db_session.add(co)

        logging.info('Processing {} withdrawals'.format(currency))
        withdrawals = CompletedOrder.query.filter(
            CompletedOrder.is_withdrawal).filter(
            CompletedOrder.withdrawal_complete == False).all()
        for withdrawal in withdrawals:
            # TODO: some proper error checking etc
            logging.info(
                "New Withdrawal! Amount: {}".format(
                    withdrawal.amount))
            sendaddr = withdrawal.withdrawal_address
            try:
                rpc.sendtoaddress(sendaddr, withdrawal.amount)
            except Exception as e:
                logging.warning(
                    "Error in executing withdrawal! ID: {} JSONRPC Error: {}".format(
                        withdrawal.id,
                        repr(
                            e.error)))
            withdrawal.withdrawal_complete = True
            db_session.add(withdrawal)
        db_session.commit()

with daemon.DaemonContext():
    while True:
        handle_transactions()
# handle_transactions()
