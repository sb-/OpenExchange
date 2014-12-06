##############################
#app.py (core app)
##############################

from app import app


if __name__ == '__main__':
    app.run(host='0.0.0.0')


class NegativeBalanceError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)