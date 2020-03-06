#!/usr/bin/env python2
"""
Handles the discovery and the server for the  connection with Cura.

This module does not fully run in a seperate thread, but the server
does,  which is doing most of the work  outside of initializing and
shutting down,  which is handled in the CuraConnectionModule class.
"""

import logging
from threading import Thread

from zeroconfhandler import ZeroConfHandler
import server

version = "5.2.11" # We need to disguise as Cura Connect for now
address = "192.168.178.50" #TODO this is not as flexible as it could be

class CuraConnectionModule(object):

    def __init__(self, config):
        logging.info("Cura Connection Module initializing...")

        self.zeroconf_handler = ZeroConfHandler(address)
        self.server = server.get_server(address)

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
