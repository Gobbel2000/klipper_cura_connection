#!/usr/bin/env python3

import socket
from time import sleep
import zeroconf as zc

zeroconf = zc.Zeroconf()

prop_dict = {
    b'type': b'printer',
    b'name': b'Super sayan printer',
    b'machine': b'213482',
    b'firmware_version': b'5.2.11', # This printer runs the most advanced of firmwares
    }

info = zc.ServiceInfo(
    type_="_klipper._tcp.local.",
    name="Klipper Networked Printer._klipper._tcp.local.",
    address=socket.inet_aton("192.168.178.50"),
    port=80,
    properties=prop_dict,
    server="talos.local.",
    )

zeroconf.register_service(info)

try:
    while True:
        sleep(0.1)
except KeyboardInterrupt:
    pass
finally:
    zeroconf.unregister_service(info)
    zeroconf.close()

