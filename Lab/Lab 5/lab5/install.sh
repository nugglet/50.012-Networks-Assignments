#!/bin/bash
# Installation script for 50.012 Networks Lab 5

sudo apt-get install -y quagga curl screen python-setuptools
sudo easy_install termcolor

# soft-link the conf files to allow students to edit them directly
sudo rm /etc/quagga/*
sudo ln -s $PWD/conf/bgpd-R1.conf /etc/quagga/
sudo ln -s $PWD/conf/bgpd-R2.conf /etc/quagga/
sudo ln -s $PWD/conf/bgpd-R3.conf /etc/quagga/
sudo ln -s $PWD/conf/bgpd-R4.conf /etc/quagga/
sudo ln -s $PWD/conf/zebra-R1.conf /etc/quagga/
sudo ln -s $PWD/conf/zebra-R2.conf /etc/quagga/
sudo ln -s $PWD/conf/zebra-R3.conf /etc/quagga/
sudo ln -s $PWD/conf/zebra-R4.conf /etc/quagga/
sudo chown quagga /etc/quagga/*.conf

# create /var/run/quagga, which mysteriously is not created by install
# Without it, zebra will not update host routes
sudo mkdir /var/run/quagga
sudo chown quagga /var/run/quagga
