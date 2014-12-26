#!/usr/bin/env bash
sudo apt-get update
sudo apt-get install -y python3 python-pip
sudo pip install -r requirements.txt
sudo apt-get install redis-server
wget https://bitcoin.org/bin/0.9.2.1/bitcoin-0.9.2.1-linux.tar.gz
wget https://download.litecoin.org/litecoin-0.8.7.2/linux/litecoin-0.8.7.2-linux.tar.xz
tar -zxf *.tar.gz
tar -xf *.tar.xz
mkdir /home/vagrant/.bitcoin
mkdir /home/vagrant/.litecoin
echo "rpcuser=litecoinrpc" > /home/vagrant/.litecoin/litecoin.conf
echo "rpcpassword=2UY1hkEMoaHrqF7SkmfkziN9HnANfNNz2uUBicbqV1wD" >> /home/vagrant/.litecoin/litecoin.conf
echo "rpcport=7332" >> /home/vagrant/.litecoin/litecoin.conf
echo "server=1" >> /home/vagrant/.litecoin/litecoin.conf

echo "rpcuser=bitcoinrpc" > /home/vagrant/.bitcoin/bitcoin.conf
echo "rpcpassword=94CpFcoCgO" >> /home/vagrant/.bitcoin/bitcoin.conf
echo "rpcport=8332" >> /home/vagrant/.bitcoin/bitcoin.conf
echo "server=1" >> /home/vagrant/.bitcoin/bitcoin.conf
sudo /home/vagrant/bitcoin-0.9.2.1-linux/bin/32/bitcoind -daemon -testnet
echo
sudo /home/vagrant/litecoin-0.8.7.2-linux/bin/32/litecoind -daemon -testnet
echo
sudo redis-server /etc/redis/redis.conf