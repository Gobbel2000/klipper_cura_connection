#!/usr/bin/env python2
"""
Handles the discovery and the server for the  connection with Cura.

This module does not fully run in a seperate thread, but the server
does,  which is doing most of the work  outside of initializing and
shutting down,  which is handled in the CuraConnectionModule class.
"""

import logging
import logging.handlers
import os
import socket
from threading import Thread

from contentmanager import ContentManager
import server
from zeroconfhandler import ZeroConfHandler

klippy_logger = logging.getLogger()
assert(klippy_logger.name == "root")
server_logger = logging.getLogger("root.server") # Inherits level
server_logger.propagate = False # Avoid Server logs in klippy logs


class CuraConnectionModule(object):

    def __init__(self, config):
        self.testing = config is None
        klippy_logger.info("Cura Connection Module initializing...")

        # Global variables
        self.VERSION = "5.2.11" # We need to disguise as Cura Connect for now
        self.ADDRESS = self.get_ip()
        self.SDCARD_PATH = os.path.expanduser("~/sdcard")
        self.MATERIAL_PATH = os.path.expanduser("~/materials")
        self.PATH = os.path.dirname(os.path.realpath(__file__))
        self.LOGFILE = os.path.join(self.PATH, "logs/server.log")

        self.configure_logging()

        self.content_manager = ContentManager(self)
        self.zeroconf_handler = ZeroConfHandler(self.ADDRESS)
        self.server = server.get_server(self)

        if self.testing:
            import site
            p = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
            site.addsitedir(p)
            import filament_manager
            self.filament_manager = filament_manager.load_config(None)
            return
        self.config = config
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.printer.register_event_handler(
                "klippy:connect", self.handle_connect)
        self.printer.register_event_handler("klippy:ready", self.handle_ready)
        self.printer.register_event_handler("klippy:disconnect", self.stop)
        self.printer.register_event_handler("klippy:shutdown", self.stop)
        self.printer.register_event_handler("klippy:exception", self.stop)

    def configure_logging(self):
        """Add log handler based on testing"""
        if self.testing:
            # Log to console in testing mode
            logging.basicConfig(level=logging.DEBUG)
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(levelname)s: \t%(message)s")
        else:
            with open(self.LOGFILE, "a") as fp:
                fp.write("\n=== RESTART ===\n\n")
            handler = logging.handlers.RotatingFileHandler(
                    filename=self.LOGFILE,
                    maxBytes=4194304, # max 4 MiB per file
                    backupCount=3, # up to 4 files total
                    delay=True, # Open file only once needed
                )
            formatter = logging.Formatter("%(levelname)s: \t%(message)s")
        handler.setFormatter(formatter)
        server_logger.addHandler(handler)

    def handle_connect(self):
        self.filament_manager = self.printer.lookup_object(
                "filament_manager", None)
        self.sdcard = self.printer.lookup_object("virtual_sdcard", None)

    def handle_ready(self):
        self.start()

    def start(self):
        """Start the zeroconf service and the server in a seperate thread"""
        self.zeroconf_handler.start() # Non-blocking
        klippy_logger.debug("Cura Connection Zeroconf service started")
        self.server_thread = Thread(
            target=self.server.serve_forever,
            name="Cura_Connection_Server")
        self.server_thread.start()
        klippy_logger.debug("Cura Connection Server started")

    def stop(self, *args):
        """This might take a little while, be patient"""
        klippy_logger.debug("Cura Connection shutting down server...")
        self.zeroconf_handler.stop()
        self.server.shutdown()
        self.server_thread.join()
        klippy_logger.debug("Cura Connection Server shut down")


    def send_print(self, filename):
        """Start a print in klipper"""
        path = os.path.join(self.SDCARD_PATH, filename)
        if self.testing:
            klippy_logger.info("Start printing {}".format(filename))
            self.content_manager.add_test_print(path)
            return
        self.reactor.register_async_callback(
                lambda e: self.sdcard.add_printjob(path))

    def send_queue(self, queue):
        self.sdcard.clear_queue()
        for e in queue[1:]:
            self.sdcard.add_printjob(*e)

    def queue_delete(self, index, filename):
        """
        Delete the print job from the queue.
        The index is checked as well as the filename in order to detect
        changes in the queue that have not yet been updated in the
        content manager.  In that case a LookupError is raised.
        """
        queue = self.sdcard.queued_files
        if os.path.basename(queue[index][0]) == filename:
            queue.pop(index)
            self.send_queue(queue)
        else:
            raise LookupError("Queues are desynchronised")

    def queue_move(self, old_index, new_index=1, filename):
        if new_index == 0:
            raise IndexError("Not allowed to move print job to index 0")
        queue = self.sdcard.queued_files
        if os.path.basename(queue[old_index][0]) == filename:
            to_move = queue.pop(old_index)
            queue.insert(new_index, to_move)
            self.send_queue(queue)
        else:
            raise LookupError("Queues are desynchronised")


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
