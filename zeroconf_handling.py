#!/usr/bin/env python3

import socket
from time import sleep
import zeroconf as zc

zeroconf = zc.Zeroconf()

prop_dict = {
    b'type': b'printer', # Necessary to be noticed by Cura
    b'name': b'Super sayan printer', # Might have to be unique, is displayed everywhere
    b'machine': b'213482', # BOM-number, for now we disguise as an Ultimaker 3
    b'firmware_version': b'5.2.11', # Currently required in some tests
    }

info = zc.ServiceInfo(
    type_="_klipper._tcp.local.",
    name="Klipper Networked Printer._klipper._tcp.local.",
    addresses=[socket.inet_aton("192.168.178.50")], # TODO: automatically get IPv4-Address
    port=80, # Default HTTP port, this is where Cura sends to
    properties=prop_dict,
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
