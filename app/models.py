from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship, backref
from database import Base


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True)
    email = Column(String(120), unique=True)
    password = Column(String(120))
    btc_balance = Column(Integer)
    ltc_balance = Column(Integer)
    activated = Column(Boolean)
    #orders = relationship("Order",backref="users")

    def __init__(self, name, email, password):
        self.name = name
        self.email = email
        self.password = password
        self.btc_balance = 0
        self.ltc_balance = 0
        self.activated = False

    def __repr__(self):
        return '<User %r>' % (self.name)


class CompletedOrder(Base):
    __tablename__ = 'completedorders'
    id = Column(Integer, primary_key=True)
    currency_pair = Column(String(9))
    base_currency = Column(String(4))
    quote_currency = Column(String(4))
    order_type = Column(String(8))
    amount = Column(Integer)
    price = Column(Integer)
    time_started = Column(DateTime)
    time_ended = Column(DateTime)
    user = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_deposit = Column(Boolean)
    is_withdrawal = Column(Boolean)
    withdrawal_complete = Column(Boolean)
    withdrawal_address = Column(String(38))
    transaction_id = Column(String(36))  # I think I only need 32

    def __init__(
            self,
            currency_pair,
            order_type,
            amount,
            price,
            userid,
            is_deposit=False,
            is_withdrawal=False,
            withdrawal_address=None,
            transaction_id=None):
        self.currency_pair = currency_pair
        self.active = 1
        self.completed = 0
        self.order_type = order_type
        self.amount = amount
        self.price = price
        self.user = userid
        self.is_deposit = is_deposit
        self.is_withdrawal = is_withdrawal
        # The object will never be instantiated with a withdrawal already done
        self.withdrawal_complete = False
        self.withdrawal_address = withdrawal_address
        self.transaction_id = transaction_id
        # TODO: maybe have making deposits cleaner?
        self.base_currency = currency_pair[0:currency_pair.find("_")]
        self.quote_currency = currency_pair[currency_pair.find("_") + 1:]


class Address(Base):
    __tablename__ = 'addresses'
    id = Column(Integer, primary_key=True)
    currency = Column(String(3))
    address = Column(String(4))
    user = Column(Integer, ForeignKey("users.id"), nullable=False)

    def __init__(self, currency, address, user):
        self.currency = currency
        self.address = address
        self.user = user
