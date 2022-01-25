from http import HTTPStatus
import http.server as srv
import json
import logging
import re
import threading
import time

from .mimeparser import MimeParser

logger = logging.getLogger("klipper_cura_connection")
threading.excepthook = lambda tp, val, tb: logger.exception("Exception in thread")

PRINTER_API = "/api/v1/"
CLUSTER_API = "/cluster-api/v1/"
MJPG_STREAMER_PORT = 8080


class Handler(srv.BaseHTTPRequestHandler):

    """
    Regex for a path in form:
    /cluster-api/v1/print_jobs/<UUID>...
    with the uuid and the suffix (everything past the uuid) in their
    respective groups "uuid" and "suffix".
    """
    uuid_regex = re.compile(r"^" + CLUSTER_API + r"print_jobs/"
            + r"(?P<uuid>[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})"
            + r"(?P<suffix>.*)$")

    # Keeps TCP connections alive
    protocol_version = "HTTP/1.1"

    def __init__(self, request, client_address, server):
        self.module = server.module
        self.reactor = server.module.reactor
        self.content_manager = self.module.content_manager
        self._size = None # For logging GET requests
        super().__init__(request, client_address, server)

    def do_GET(self):
        """
        Implement a case-specific response, limited to the requests
        that we can expect from Cura.  For a summary of those see
        README.md
        """
        if self.path == CLUSTER_API + "printers":
            self.get_json(self.content_manager.get_printer_status())
        elif self.path == CLUSTER_API + "print_jobs":
            self.get_json(self.content_manager.get_print_jobs())
        elif self.path == CLUSTER_API + "materials":
            self.get_json(self.content_manager.get_materials())
        elif self.path == "/?action=stream":
            self.get_stream()
        elif self.path == "/?action=snapshot":
            self.get_snapshot()
        elif self.path == PRINTER_API + "system":
            self.send_error(HTTPStatus.NOT_IMPLEMENTED)
        else:
            m = self.uuid_regex.match(self.path)
            if m and m.group("suffix") == "/preview_image":
                self.get_preview_image(m.group("uuid"))
            else:
                # NOTE: send_error() calls end_headers()
                self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self):
        if self.headers.get_content_maintype() == "multipart":
            if self.path == CLUSTER_API + "print_jobs/":
                self.post_print_job()
            elif self.path == CLUSTER_API + "materials/":
                self.post_material()
        else:
            m = self.uuid_regex.match(self.path)
            if m and m.group("suffix") == "/action/move":
                self.post_move_to_top(m.group("uuid"))
            else:
                self.send_error(HTTPStatus.NOT_FOUND)

    def do_PUT(self):
        m = self.uuid_regex.match(self.path)
        if m and m.group("suffix") == "/action":
            # pause, print or abort
            self.put_action(m.group("uuid"))
        elif m and not m.group("suffix"):
            # force print job
            self.put_force(m.group("uuid"))
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_DELETE(self):
        m = self.uuid_regex.match(self.path)
        if m and not m.group("suffix"):
            # Delete print job from queue
            self.delete_print_job(m.group("uuid"))
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def get_json(self, content):
        """Send an object JSON-formatted"""
        try:
            json_content = json.dumps(content)
        except TypeError:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR,
                    "JSON serialization failed")
        else:
            self.send_response(HTTPStatus.OK, size=len(json_content))
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json_content.encode())

    def get_preview_image(self, uuid):
        """Send back the preview image for the print job with uuid"""
        index, print_job = self.content_manager.uuid_to_print_job(uuid)
        if not print_job:
            self.send_error(HTTPStatus.NOT_FOUND, "Print job not in Queue")
        else:
            try:
                thumbnail_path = self.module.get_thumbnail_path(
                        index, print_job.name)
                with open(thumbnail_path, "rb") as fp:
                    image_data = fp.read()
                self.send_response(HTTPStatus.OK, size=len(image_data))
                self.send_header("Content-Type", "image/png")
                self.end_headers()
                self.wfile.write(image_data)
            except IOError:
                self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR,
                        "Failed to open preview image at " + thumbnail_path)

    def get_stream(self):
        """Redirect to the port on which mjpg-streamer is running"""
        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", "http://{}:{}/?action=stream".format(
            self.module.ADDRESS, MJPG_STREAMER_PORT))
        self.end_headers()

    def get_snapshot(self):
        """Snapshot only sends a single image"""
        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", "http://{}:{}/?action=snapshot".format(
            self.module.ADDRESS, MJPG_STREAMER_PORT))
        self.end_headers()

    def post_print_job(self):
        boundary = self.headers.get_boundary()
        length = int(self.headers.get("Content-Length", 0))
        try:
            parser = MimeParser(self.rfile, boundary, length,
                self.module.SDCARD_PATH, overwrite=False)
            submessages, paths = parser.parse()
        except Exception as e:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR,
                    "Parser failed: " + str(e))
        else:
            #for msg in submessages:
            #    name = msg.get_param("name", header="Content-Disposition")
            #    if name == "owner":
            #        owner = msg.get_payload().strip()
            for path in paths:
                self.reactor.cb(self.module.add_print, path)
            self.send_response(HTTPStatus.OK)
            self.end_headers()

    def post_material(self):
        boundary = self.headers.get_boundary()
        length = int(self.headers.get("Content-Length", 0))
        try:
            parser = MimeParser(self.rfile, boundary, length,
                    self.module.MATERIAL_PATH)
            submessages, paths = parser.parse()
        except Exception as e:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR,
                    "Parser failed: " + str(e))
        else:
            self.reactor.cb(self.read_material_file, paths[0])
            # Reply is checked specifically for 200
            self.send_response(HTTPStatus.OK)
            self.end_headers()

    @staticmethod
    def read_material_file(e, printer, path):
        printer.objects['filament_manager'].read_single_file(path)

    def post_move_to_top(self, uuid):
        """Move print job with uuid to the top of the queue"""
        length = int(self.headers.get("Content-Length", 0))
        rdata = self.rfile.read(length)
        try:
            data = json.loads(rdata)
        except ValueError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Failed to read JSON")
            return
        old_index, _ = self.content_manager.uuid_to_print_job(uuid)
        new_index = data.get("to_position")
        if old_index is None:
            self.send_error(HTTPStatus.NOT_FOUND, "Print job not in Queue")
        elif data.get("list") != "queued" or not isinstance(new_index, int):
            self.send_error(HTTPStatus.BAD_REQUEST,
                    "Unexpected JSON content: " + rdata)
        else:
            if self.reactor.cb(self.module.queue_move,
                    old_index, uuid, new_index-old_index, wait=True):
                self.send_response(HTTPStatus.OK)
                self.end_headers()
            else:
                self.send_error(HTTPStatus.CONFLICT, "Queue order has changed")

    def delete_print_job(self, uuid):
        """Delete print job with uuid from the queue"""
        index, print_job = self.content_manager.uuid_to_print_job(uuid)
        if not print_job:
            self.send_error(HTTPStatus.NOT_FOUND, "Print job not in queue")
        else:
            if self.reactor.cb(self.module.queue_delete, index, uuid, wait=True):
                self.send_response(HTTPStatus.OK)
                self.end_headers()
            else:
                self.send_error(HTTPStatus.CONFLICT, "Queue order has changed")

    def put_action(self, uuid):
        """
        Pause, Print or Abort a print job.
        This is only called for the current print job.
        """
        length = int(self.headers.get("Content-Length", 0))
        rdata = self.rfile.read(length)
        try:
            data = json.loads(rdata)
        except ValueError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Failed to read JSON")
            return
        index, print_job = self.content_manager.uuid_to_print_job(uuid)
        action = data.get("action")
        if not print_job:
            self.send_error(HTTPStatus.NOT_FOUND, "Print job not in Queue")
        elif index != 0: # This request is only handled for the current print
            self.send_error(HTTPStatus.BAD_REQUEST,
                    "Can only operate on current print job. Got " + str(index))
        else:
            res = True
            if action == "print":
                res = self.reactor.cb(self.module.resume_print, uuid, wait=True)
            elif action == "pause":
                res = self.reactor.cb(self.module.pause_print, uuid, wait=True)
            elif action == "abort":
                res = self.reactor.cb(self.module.stop_print, uuid, wait=True)
            else:
                self.send_error(HTTPStatus.BAD_REQUEST, "Unknown action: " + str(action))
            if not res:
                self.send_error(HTTPStatus.CONFLICT,
                    "Failed to " + str(action) + ", queue order has changed")

    def put_force(self, uuid):
        """
        Force a print job that requires configuration change
        This is not called until possibly configuration changes are
        implemented.
        """
        length = int(self.headers.get("Content-Length", 0))
        rdata = self.rfile.read(length)
        try:
            data = json.loads(rdata)
        except ValueError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Failed to read JSON")
            return
        index, print_job = self.content_manager.uuid_to_print_job(uuid)
        if not print_job:
            self.send_error(HTTPStatus.NOT_FOUND, "Print job not in Queue")
        elif data.get("force") is not True:
            self.send_error(HTTPStatus.BAD_REQUEST,
                    'Expected {"force": True}. Got: ' + rdata)
        else:
            self.send_error(HTTPStatus.NOT_IMPLEMENTED)


    def send_response(self, code, message=None, size=None):
        """
        Accept size as an argument (can be int or str) which sends the
        Content-Length header and takes care of logging the size as well.
        """
        if size is not None:
            self._size = str(size)
        srv.BaseHTTPRequestHandler.send_response(self, code, message)
        # Keep track of when the last request was handled
        # send_error() also calls here
        self.server.last_request = time.time()
        if self._size is not None:
            self.send_header("Content-Length", self._size)

    def log_request(self, code="-", size="-"):
        """Add size to logging"""
        if self._size is not None:
            size = self._size + "B"
        srv.BaseHTTPRequestHandler.log_request(self, code, size)

    def log_error(self, format, *args):
        """Similar to log_message, but log under loglevel ERROR"""
        # Overwrite format string. Default is "code %d, message %s"
        if format == "code %d, message %s":
            format = "Errorcode %d: %s"
        logger.error("<%s> " + format, self.address_string(), *args)

    def log_message(self, format, *args):
        logger.log(logging.INFO, "<%s> " + format, self.address_string(), *args)


class Server(srv.ThreadingHTTPServer, threading.Thread):
    """Wrapper class to store the module in the server and add threading"""
    def __init__(self, server_address, RequestHandler, module):
        super().__init__(server_address, RequestHandler)
        threading.Thread.__init__(self, name="Server-Thread")
        self.module = module
        self.last_request = 0 # Time of last request in seconds since epoch

    run = srv.HTTPServer.serve_forever


def get_server(module):
    return Server((module.ADDRESS, 8008), Handler, module)
