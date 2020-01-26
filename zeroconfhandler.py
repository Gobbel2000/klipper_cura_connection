#!/usr/bin/env python2

import socket
import zeroconf as zc


class ZeroConfHandler:

    def __init__(self):
        self.zeroconf = zc.Zeroconf()
        self.prop_dict = {
            # Necessary to be noticed by Cura
            b'type': b'printer',
            # Might have to be unique, is displayed everywhere
            b'name': b'Super sayan printer',
            # BOM-number, for now we disguise as an Ultimaker 3
            b'machine': b'213482',
            # Currently required in some tests
            b'firmware_version': b'5.2.11',
            }

        self.info = zc.ServiceInfo(
            type_="_klipper._tcp.local.",
            name="Klipper Networked Printer._klipper._tcp.local.",
            address=socket.inet_aton("192.168.178.50"), # TODO: automatically get IPv4-Address
            port=80, # Default HTTP port, this is where Cura sends to
            properties=self.prop_dict,
            )

    def start(self):
        """Start the zeroconf service"""
        self.zeroconf.register_service(self.info)

    def stop(self):
        """Stop the zeroconf service"""
        self.zeroconf.unregister_service(self.info)
        self.zeroconf.close()

if __name__ == "__main__":
    from time import sleep
    handler = ZeroConfHandler()
    handler.start()
    while True:
        try:
            sleep(0.1)
        except KeyboardInterrupt:
            handler.stop()
            break
