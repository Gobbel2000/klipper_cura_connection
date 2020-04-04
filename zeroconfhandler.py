import socket
import zeroconf as zc


class ZeroConfHandler(object):

    def __init__(self, module):
        self.module = module
        self.zeroconf = zc.Zeroconf()
        self.prop_dict = {
            # Necessary to be noticed by Cura
            b'type': b'printer',
            b'name': bytes(self.module.NAME),
            # BOM-number, for now we disguise as an Ultimaker 3
            b'machine': b'213482',
            b'firmware_version': b'5.2.11',
            # needs testing
            #b'cluster_size': 0,
            }

        self.info = zc.ServiceInfo(
            type_="_klipper._tcp.local.",
            name="Klipper Networked Printer._klipper._tcp.local.",
            address=socket.inet_aton(self.module.ADDRESS),
            port=80, # Default HTTP port, this is where Cura sends to
            properties=self.prop_dict,
            )

    def start(self):
        """Start the zeroconf service"""
        self.zeroconf.register_service(self.info, allow_name_change=True)

    def stop(self):
        """Stop the zeroconf service"""
        self.zeroconf.unregister_service(self.info)
        self.zeroconf.close()
