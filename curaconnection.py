#!/usr/bin/env python2
"""
Handles the discovery and the server for the  connection with Cura.

This module does not fully run in a seperate thread, but the server
does,  which is doing most of the work  outside of initializing and
shutting down,  which is handled in the CuraConnectionModule class.
"""

import logging
import os
import socket
from threading import Thread

from zeroconfhandler import ZeroConfHandler
import server

def get_ip():
    """https://stackoverflow.com/a/28950776"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

VERSION = "5.2.11" # We need to disguise as Cura Connect for now
ADDRESS = get_ip()
SDCARD_PATH = os.path.expanduser("~/sdcard")
MATERIAL_PATH = os.path.expanduser("~/materials")

class CuraConnectionModule(object):

    def __init__(self, config):
        logging.info("Cura Connection Module initializing...")

        self.zeroconf_handler = ZeroConfHandler(ADDRESS)
        self.server = server.get_server(ADDRESS)

        if config is None:
            return
        self.config = config
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.printer.register_event_handler("klippy:connect", self.handle_connect)
        self.printer.register_event_handler("klippy:disconnect", self.stop)
        self.printer.register_event_handler("klippy:shutdown", self.stop)
        self.printer.register_event_handler("klippy:exception", self.stop)

    def handle_connect(self):
        self.start()

    def start(self):
        """Start the zeroconf service and the server in a seperate thread"""
        self.zeroconf_handler.start() # Non-blocking
        self.server_thread = Thread(
            target=self.server.serve_forever,
            name="Cura_Connection_Server")
        self.server_thread.start()
        logging.info("Cura Connection Server started")

    def stop(self):
        """This might take a little while, be patient"""
        self.zeroconf_handler.stop()
        self.server.shutdown()
        self.server_thread.join()


def load_config(config):
    """Entry point, called by Klippy"""
    module = CuraConnectionModule(config)
    module.start()
    return module

if __name__ == "__main__":
    import time
    module = CuraConnectionModule(None)
    module.start()
    while True:
        try:
            time.sleep(0.1)
        except KeyboardInterrupt:
            module.stop()
            break
