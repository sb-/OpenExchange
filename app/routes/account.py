"""
=================
Account functions
=================
"""
from flask import Blueprint, session, request, flash
from app.util import is_logged_in, home_page, account_page, adjustbalance, check_balance, string_to_currency_unit, tradehistory
from app.database import db_session
from app.config import config
from app.models import *
account = Blueprint('account', __name__, url_prefix='/account')


@account.route('/withdraw/<currency>', methods=['GET', 'POST'])
def withdraw(currency):
    if not is_logged_in(session):
        flash("Please log in to perform that action.", "error")
        return home_page("ltc_btc")
    if not config.is_valid_currency(currency):
        flash("Invalid Currency!", "error")
        return account_page()
    if request.method == 'GET':
        return account_page(withdraw=currency)
    elif request.method == 'POST':
        if 'amount' not in request.form or 'address' not in request.form:
            flash("Please enter an address and an amount!", "error")
            return account_page()
        try:
            total = string_to_currency_unit(
                request.form['amount'],
                config.get_multiplier(currency))
        except:
            flash("Invalid amount!", "error")
            return account_page()
        if check_balance(currency, session['userid']) < total or total < 0:
            flash("Balance too low to execute withdrawal!", "error")
            return account_page()
        # TODO: add valid address checking
        adjustbalance(currency, session['userid'], -1 * total)
        co = CompletedOrder(
            currency +
            "_" +
            currency,
            "WITHDRAWAL",
            total,
            0,
            session['userid'],
            is_withdrawal=True,
            withdrawal_address=request.form['address'])
        db_session.add(co)
        db_session.commit()
        flash("Deposit to " + request.form['address'] + " completed!", "success")
        return account_page()


@account.route('/deposit/<currency>')
def deposit(currency):
    """ Returns deposit address for given currency from SQL. """
    if not is_logged_in(session):
        flash("Please log in to perform that action.", 'error')
        return home_page("ltc_btc")
    if not config.is_valid_currency(currency):
        flash("Invalid Currency!", "error")
        return account_page()
    addr = Address.query.filter(
        Address.currency == currency).filter(
        Address.user == session['userid']).first().address
    return account_page(deposit=addr)


@account.route('/history/<currency>')
def history(currency):
    if not is_logged_in(session):
        flash("Please log in to perform that action.", 'error')
        return home_page("ltc_btc")
    if not config.is_valid_currency(currency):
        flash("Invalid Currency!", 'error')
        return account_page()
    return account_page(
        history=currency,
        orders=tradehistory(
            currency,
            session['userid']))
