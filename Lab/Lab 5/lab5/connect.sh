#!/bin/bash

# Script to connect to a router's bgpd shell.
router=${1:-R1}
echo "Connecting to $router shell"

sudo python run.py --node $router --cmd "telnet localhost bgpd"
#sudo python run.py --node $router --cmd "/usr/lib/quagga/bgpd -f conf/bgpd-$router.conf -d -i /tmp/bgpd-$router.pid > logs/$router-bgpd-stdout"
