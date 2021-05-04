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
import sys
from os.path import join, dirname

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
        self.PATH = os.path.dirname(os.path.realpath(__file__))
        self.LOGFILE = os.path.join(self.PATH, "logs/server.log")
        self.ADDRESS = None

        self.content_manager = self.zeroconf_handler = self.server = None

        self.configure_logging()

        self.reactor = config.get_reactor()
        self.metadata = gcode_metadata.load_config(config)
        self.reactor.register_evejklnt_handler("klippy:ready", self.handle_ready)
        self.reactor.register_event_handler("klippy:disconnect", self.handle_disconnect)
        self.server_logger.info("Cura Connection Module initialized...")


        self.do_test()
    @staticmethod
    def get_test(e, printer):
        return 777
    def do_test(self):
        self.server_logger.info(f"start test")
        start_time = self.reactor.monotonic()
        result = self.reactor.cb(self.get_test, wait='true')
        self.server_logger.info(f"got restult {result} in {self.reactor.monotonic() - start_time} seconds")


    def configure_logging(self):
        """Add log handler based on testing"""
        formatter = logging.Formatter(
                fmt="%(levelname)s: \t[%(asctime)s] %(message)s")
        if self.testing:
            # Log to console in testing mode
            logging.basicConfig(level=logging.DEBUG)
            handler = logging.StreamHandler()
        else:
            logging.basicConfig(level=logging.DEBUG)
            now = time.strftime(logging.Formatter.default_time_format)
            with open(self.LOGFILE, "a") as fp:
                fp.write(f"\n=== RESTART {now} ===\n\n")
            handler = logging.handlers.RotatingFileHandler(
                    filename=self.LOGFILE,
                    maxBytes=4194304, # max 4 MiB per file
                    backupCount=3, # up to 4 files total
                    delay=True, # Open file only once needed
                )
        handler.setFormatter(formatter)
        self.server_logger = logging.getLogger("root.server_logger")
        self.server_logger.addHandler(handler)
        sys.excepthook.append(lambda exc_type, exc_value, tb: self.server_logger.exception(str(exc_value)))

    def handle_ready(self):
        """
        Now it's safe to start the server once there is a network connection
        """
        logging.info("handle ready")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.wait_for_network()

    def wait_for_network(self, eventtime=0):
        """
        This function executes every 2 seconds until a network
        connection is established.  At that point the IPv4-Address is
        saved and the server started.
        """
        logging.info("waiting for network")
        try:
            self.sock.connect(("10.255.255.255", 1))
        except OSError:
            self.reactor.register_callback(self.wait_for_network,
                                           self.reactor.monotonic() + 2)
        else:
            logging.info("got network")
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
        self.server_logger.debug("Cura Connection Server started")

    def handle_disconnect(self, *args):
        """
        This might take a little while, be patient
        can be called before start() e.g. when klipper initialization fails
        """
        if self.server is None:
            # stop() is called before start()
            return
        self.zeroconf_handler.stop()
        self.server_logger.debug("Cura Connection Zeroconf shut down")
        if self.server.is_alive():
            self.server.shutdown()
            self.server.join()
            self.server_logger.debug("Cura Connection Server shut down")
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
        printer.objects['virtual_sdcard'].add_prinjob(path)

    @staticmethod
    def resume_print(e, printer, uuid):
        printer.objects['virtual_sdcard'].resume_printjob()

    @staticmethod
    def pause_print(e, printer, uuid):
        printer.objects['virtual_sdcard'].pause_printjob()

    @staticmethod
    def stop_print(e, printer, uuid):
        printer.objects['virtual_sdcard'].stop_printjob()

    @staticmethod
    def queue_delete(e, printer, index, uuid):
        """Delete the print job from the queue"""
        return printer.objects['virtual_sdcard'].remove_printjob(index, uuid)

    @staticmethod
    def queue_move(e, printer, index, uuid, move):
        return printer.objects['virtual_sdcard'].move_printjob(index, uuid, move)

    def get_thumbnail_path(self, index, filename):
        """Return the thumbnail path for the specified print"""
        path = self.sdcard.jobs[index].md.get_thumbnial_path()
        if not path or not os.exists(path):
            path = os.path.join(self.PATH, "default.png")
        return path


def load_config(config):
    """Entry point, called by Klippy"""
    module = CuraConnectionModule(config)
    return module
