#!/bin/bash

set -e

# The klipper cura connection directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# Install zeroconf
cd $DIR
cd -P ../../../
if [ ! -d klippy-environment ]
then
    echo "Error: Klipper must be installed first, aborting installation"
    exit 1
fi
klippy-environment/bin/pip3 install -q zeroconf==0.38.1

echo iptables-persistent iptables-persistent/autosave_v4 boolean false | sudo debconf-set-selections
echo iptables-persistent iptables-persistent/autosave_v6 boolean false | sudo debconf-set-selections

# Install dependencies
sudo apt-get install --yes cmake libjpeg-dev gcc iptables-persistent

# Redirect port 80 -> 8008
sudo iptables -A PREROUTING -t nat -p tcp --dport 80 -j REDIRECT --to-ports 8008
sudo iptables-save -f /etc/iptables/rules.v4


# Install mjpg-streamer
cd /tmp
if [ -d mjpg-streamer ]
then
    # Delete if there is already an installation
    rm -rf mjpg-streamer
fi

git clone --depth 1 --branch v1.0.0 https://github.com/jacksonliam/mjpg-streamer.git
cd mjpg-streamer/mjpg-streamer-experimental
make
sudo make install

# Switch to the directory of the script
cd $DIR

# Start the service
echo "Starting service for mjpg-streamer"
sudo cp ./mjpg_streamer.service /etc/systemd/system/
sudo systemctl enable --now mjpg_streamer.service
