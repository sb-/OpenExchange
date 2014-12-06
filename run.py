##############################
#app.py (core app)
##############################

import time

from flask import session

from app.database import db_session, redis
from app.models import *
from app.config import config
from app import app


"""
=================
Utility Functions
=================
"""



if __name__ == '__main__':
    app.run(host='0.0.0.0')


class NegativeBalanceError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)