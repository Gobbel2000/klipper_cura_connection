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

from contentmanager import ContentManager
import server
from zeroconfhandler import ZeroConfHandler


class CuraConnectionModule(object):

    def __init__(self, config):
        logging.info("Cura Connection Module initializing...")

        # Global variables
        self.VERSION = "5.2.11" # We need to disguise as Cura Connect for now
        self.ADDRESS = self.get_ip()
        self.SDCARD_PATH = os.path.expanduser("~/sdcard")
        self.MATERIAL_PATH = os.path.expanduser("~/materials")

        self.content_manager = ContentManager(self)
        self.zeroconf_handler = ZeroConfHandler(self.ADDRESS)
        self.server = server.get_server(self)

        if config is None:
            self.testing = True
            return
        self.testing = False
        self.config = config
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.printer.register_event_handler("klippy:connect", self.handle_connect)
        self.printer.register_event_handler("klippy:disconnect", self.stop)
        self.printer.register_event_handler("klippy:shutdown", self.stop)
        self.printer.register_event_handler("klippy:exception", self.stop)

    def handle_connect(self):
        self.sdcard = self.printer.lookup_object("virtual_sdcard", None)
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

    def send_print(self, filename):
        """Start a print in klipper"""
        if self.testing:
            print("Start printing {}".format(filename))
            return
        path = os.path.join(self.SDCARD_PATH, filename)
        self.reactor.register_async_callback(lambda e: self.sdcard.add_printjob(path))

    @staticmethod
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
