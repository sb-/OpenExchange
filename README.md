#OpenExchange
OpenExchange is an open source cryptocurrency exchange built with Python, Flask, and Redis. It was built with the goal of having an easy to set up and extend exchange software available to all. 

### Status
OpenExchange has all the working core functionality. Deposits, withdrawals, exchange all work, and it is trivial to add new trade pairs and currencies to the software. 

### Getting Started
OpenExchange depends on having the JSONRPC, daemon, and redis modules. 

####Setup
1. Ensure Redis and all the cryptocurrency daemons (bitcoind, litecoind, etc) are up and running. 
2. Note: For development I used SQLite but change the database configuration in database.py if needed.
3. In config.py, change the 'daemon' setting on each of the currencies to point to your daemons.
4. Run 'python depositor.py start' and 'python worker.py start' to start the deposit/withdrawal daemons.
5. If you just want to run the dev server, run 'python app.py' in order to start the exchange (runs on port 5000).
Otherwise, you will need to configure the app to run on your webserver. Nginx + Tornado is an easy combination
to get up and running for a Flask app if you have not done this before. 

### Developer documentation
#### Redis layout https://github.com/sb-/OpenExchange/wiki/Redis-Structure
#### SQL layout https://github.com/sb-/OpenExchange/wiki/SQL-Structure

---
Contact the original author at sambarani@utexas.edu