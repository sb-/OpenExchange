import os
import unittest
import tempfile
from app import app
from app.database import init_db


class ExchangeTestCase(unittest.TestCase):
    """ Just modified the Flask example unit test, need to write orderbook tests."""
    def setUp(self):
        self.db_fd, app.config['DATABASE'] = tempfile.mkstemp()
        app.config['TESTING'] = True
        self.app = app.test_client()
        init_db()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(app.config['DATABASE'])

    def login(self, email, password):
        return self.app.post('/login', data=dict(
        email=email,
        password=password
        ), follow_redirects=True)

    #def register(self, name, email, password, confirm_password):
    #    return self.app.post('/register', data = dict(name=name,email=email,password=password,confirm_password=confirm_password), follow_redirects=True)

    def logout(self):
        return self.app.get('/logout', follow_redirects=True)

    def test_login_logout(self):
        rv = self.login('testbtc@mailinator.com', 'shit')
        assert 'Logged in!' in rv.data
        rv = self.logout()
        assert 'Successfully logged out!' in rv.data
        rv = self.login('adminx', 'default')
        assert 'Please check your email and username.' in rv.data
        rv = self.login('admin', 'defaultx')
        assert 'Please check your email and username.' in rv.data

    """def test_register(self):
        rv = self.login('testbtc@mailinator.com', 'shit')
        assert 'Logged in!' in rv.data
        rv = self.logout()
        assert 'Successfully logged out!' in rv.data
        rv = self.login('adminx', 'default')
        assert 'Please check your email and username.' in rv.data
        rv = self.login('admin', 'defaultx')
        assert 'Please check your email and username.' in rv.data"""


def logout(self):
    return self.app.get('/logout', follow_redirects=True)

if __name__ == '__main__':
    unittest.main()