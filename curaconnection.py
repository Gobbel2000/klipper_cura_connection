#!/usr/bin/env python3
"""
Handles the discovery and the server for the  connection with Cura.

This module does not fully run in a seperate thread, but the server
does,  which is doing most of the work  outside of initializing and
shutting down,  which is handled in the CuraConnectionModule class.
"""

import logging
import logging.handlers
import os
import platform
import socket
import time
import site
from os.path import join, dirname

os.nice(15)
PATH = os.path.dirname(os.path.realpath(__file__))
LOGFILE = os.path.join(PATH, "logs/server.log")

logger = logging.getLogger("klipper_cura_connection")
formatter = logging.Formatter(fmt="%(levelname)s: \t[%(asctime)s] %(message)s")
handler = logging.handlers.RotatingFileHandler(
    filename=LOGFILE,
    maxBytes=4194304, # max 4 MiB per file
    backupCount=3, # up to 4 files total
    delay=True, # Open file only once needed
    )
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)
logger.propagate = False

from .contentmanager import ContentManager
from . import server
from .zeroconfhandler import ZeroConfHandler

klippy_dir = dirname(dirname(dirname(__file__)))
site.addsitedir(join(klippy_dir, "extras/")) # gcode_metadata
import gcode_metadata


class CuraConnectionModule:

    # How many seconds after the last request to consider disconnected
    # 4.2 allows missing just one update cycle (every 2sec)
    CONNECTION_TIMEOUT = 4.2

    def __init__(self, config):
        self.testing = config is None

        # Global variables
        self.VERSION = "5.2.11" # We need to disguise as Cura Connect for now
        self.NAME = platform.node()
        self.SDCARD_PATH = os.path.expanduser("~/Files")
        self.MATERIAL_PATH = os.path.expanduser("~/materials")
        self.ADDRESS = None

        self.content_manager = None
        self.zeroconf_handler = None
        self.server = None
        self.reactor = config.get_reactor()
        self.metadata = gcode_metadata.load_config(config)
        # These are loaded a bit late, they sometimes miss the klippy:connect event
        # klippy:ready works since it only occurs after kguis handle_connect reports back
        self.reactor.cb(self.load_object, "filament_manager")
        self.reactor.cb(self.load_object, "print_history")
        self.reactor.register_event_handler("klippy:ready", self.handle_ready)
        self.reactor.register_event_handler("klippy:disconnect", self.handle_disconnect)
        logger.info("\n\n=== Cura Connection Module initialized ===\n")

    def handle_ready(self):
        """
        Now it's safe to start the server once there is a network connection
        """
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.wait_for_network()

    def wait_for_network(self, eventtime=0):
        """
        This function executes every 2 seconds until a network
        connection is established.  At that point the IPv4-Address is
        saved and the server started.
        """
        try:
            self.sock.connect(("10.255.255.255", 1))
        except OSError:
            self.reactor.register_callback(self.wait_for_network,
                                           self.reactor.monotonic() + 2)
        else:
            self.ADDRESS = self.sock.getsockname()[0]
            self.sock.close()
            self.start()

    def start(self):
        """Start the zeroconf service, and the server in a seperate thread"""
        self.content_manager = ContentManager(self)
        self.zeroconf_handler = ZeroConfHandler(self)
        self.server = server.get_server(self)

        self.zeroconf_handler.start() # Non-blocking
        self.server.start() # Starts server thread
        logger.debug("Cura Connection Server started")

    def handle_disconnect(self, *args):
        """
        This might take a little while, be patient
        can be called before start() e.g. when klipper initialization fails
        """
        if self.server is None:
            # stop() is called before start()
            return
        self.zeroconf_handler.stop()
        logger.debug("Cura Connection Zeroconf shut down")
        if self.server.is_alive():
            self.server.shutdown()
            self.server.join()
            logger.debug("Cura Connection Server shut down")
        self.reactor.register_async_callback(self.reactor.end)

    def is_connected(self):
        """
        Return true if there currently is an active connection.
        Also see CONNECTION_TIMEOUT
        """
        return (self.server is not None and
                time.time() - self.server.last_request < self.CONNECTION_TIMEOUT)

    @staticmethod
    def add_print(e, printer, path):
        return printer.objects['virtual_sdcard'].add_print(path)

    @staticmethod
    def resume_print(e, printer, uuid):
        return printer.objects['virtual_sdcard'].resume_print()

    @staticmethod
    def pause_print(e, printer, uuid):
        return printer.objects['virtual_sdcard'].pause_print()

    @staticmethod
    def stop_print(e, printer, uuid):
        return printer.objects['virtual_sdcard'].stop_print()

    @staticmethod
    def queue_delete(e, printer, index, uuid):
        """Delete the print job from the queue"""
        return printer.objects['virtual_sdcard'].remove_print(index, uuid)

    @staticmethod
    def queue_move(e, printer, index, uuid, move):
        return printer.objects['virtual_sdcard'].move_print(index, uuid, move)

    def get_thumbnail_path(self, index, filename):
        """Return the thumbnail path for the specified print"""
        md = self.metadata.get_metadata(self.content_manager.klippy_jobs[index].path)
        path = md.get_thumbnail_path()
        if not path or not os.path.exists(path):
            path = os.path.join(self.PATH, "default.png")
        return path

    @staticmethod
    def load_object(e, printer, object_name):
        klipper_config = printer.objects['configfile'].read_main_config()
        printer.load_object(klipper_config, object_name)


def load_config(config):
    """Entry point, called by Klippy"""
    module = CuraConnectionModule(config)
    return module
