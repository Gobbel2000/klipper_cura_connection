import socket

import zeroconf as zc


class ZeroConfHandler:

    SERVICE_TYPE = "_ultimaker._tcp.local."

    def __init__(self, module):
        self.module = module
        self.zeroconf = zc.Zeroconf()
        self.prop_dict = {
            # Necessary to be noticed by Cura
            b'type': b'printer',
            b'name': self.module.NAME.encode(),
            # BOM-number, for now we disguise as an Ultimaker 3
            b'machine': b'213482',
            b'firmware_version': self.module.VERSION.encode(),
            }

        self.info = zc.ServiceInfo(
            type_=self.SERVICE_TYPE,
            name=self.module.NAME + "." + self.SERVICE_TYPE,
            addresses=[socket.inet_aton(self.module.ADDRESS)],
            port=80, # Default HTTP port, this is where Cura sends to
            properties=self.prop_dict,
            )

    def start(self):
        """Start the zeroconf service"""
        self.zeroconf.register_service(self.info)

    def stop(self):
        """Stop the zeroconf service"""
        self.zeroconf.close()
