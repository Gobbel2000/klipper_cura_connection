from http import HTTPStatus
import http.server as srv
import json
import logging
import re
import threading

from .custom_exceptions import QueuesDesynchronizedError
from .mimeparser import MimeParser

PRINTER_API = "/api/v1/"
CLUSTER_API = "/cluster-api/v1/"
MJPG_STREAMER_PORT = 8080

logger = logging.getLogger("root.server")


class Handler(srv.BaseHTTPRequestHandler):

    def __init__(self, request, client_address, server):
        self.module = server.module
        self.content_manager = self.module.content_manager
        self._size = None # For logging GET requests
        super().__init__(request, client_address, server)

    def do_GET(self):
        """
        Implement a case-specific response, limited to the requests
        that we can expect from Cura.  For a summary of those see
        README.md
        """
        if self.path == PRINTER_API + "system":
            self.get_json(self.content_manager.get_system())
        elif self.path == CLUSTER_API + "printers":
            self.get_json(self.content_manager.get_printer_status())
        elif self.path == CLUSTER_API + "print_jobs":
            self.get_json(self.content_manager.get_print_jobs())
        elif self.path == CLUSTER_API + "materials":
            self.get_json(self.content_manager.get_materials())
        elif self.path == "/?action=stream":
            self.get_stream()
        elif self.path == "/?action=snapshot":
            self.get_snapshot()
        elif (m := self.handle_uuid_path()) and (
                m.group("suffix") == "/preview_image"):
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
        elif (m := self.handle_uuid_path()) and (
                m.group("suffix") == "/action/move"):
            self.post_move_to_top(m.group("uuid"))
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_PUT(self):
        m = self.handle_uuid_path()
        if m and m.group("suffix") == "/action":
            # pause, print or abort
            self.put_action(m.group("uuid"))
        elif m and not m.group("suffix"):
            # force print job
            self.put_force(m.group("uuid"))
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_DELETE(self):
        m = self.handle_uuid_path()
        if m and not m.group("suffix"):
            # Delete print job from queue
            self.delete_print_job(m.group("uuid"))
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def handle_uuid_path(self):
        """
        Return the regex match for a path in form:
        /cluster-api/v1/print_jobs/<UUID>...
        with the uuid and the suffix (everything past the uuid) in their
        respective groups.
        """
        return re.match(r"^" + CLUSTER_API + r"print_jobs/"
                + r"(?P<uuid>[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})"
                + r"(?P<suffix>.*)$", self.path)


    def get_json(self, content):
        """Send an object JSON-formatted"""
        try:
            json_content = json.dumps(content)
        except TypeError:
            self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR,
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
            except QueuesDesynchronizedError:
                self.send_error(HTTPStatus.CONFLICT,
                        "Queue order has changed")
            except IOError:
                self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR,
                        "Failed to open preview image at " + thumbnail_path)

    def get_stream(self):
        """Redirect to the port on which mjpg-streamer is running"""
        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", "http://{}:{}/?action=stream".format(
            self.module.ADDRESS, MJPG_STREAMER_PORT))

    def get_snapshot(self):
        """Snapshot only sends a single image"""
        self.send_response(HTTPStatus.FOUND)
        self.send_header("Location", "http://{}:{}/?action=snapshot".format(
            self.module.ADDRESS, MJPG_STREAMER_PORT))

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
            for msg in submessages:
                name = msg.get_param("name", header="Content-Disposition")
                if name == "owner":
                    owner = msg.get_payload().strip()
            self.module.send_print(paths[0])
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
            self.module.filament_manager.read_single_file(paths[0])
            # Reply is checked specifically for 200
            self.send_response(HTTPStatus.OK)
            self.end_headers()

    def post_move_to_top(self, uuid):
        """Move print job with uuid to the top of the queue"""
        length = int(self.headers.get("Content-Length", 0))
        rdata = self.rfile.read(length)
        try:
            data = json.loads(rdata)
        except ValueError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Failed to read JSON")
            return
        old_index, print_job = self.content_manager.uuid_to_print_job(uuid)
        new_index = data.get("to_position")
        if not print_job:
            self.send_error(HTTPStatus.NOT_FOUND, "Print job not in Queue")
        elif data.get("list") != "queued" or not isinstance(new_index, int):
            self.send_error(HTTPStatus.BAD_REQUEST,
                    "Unexpected JSON content: " + rdata)
        else:
            try:
                self.module.queue_move(old_index, new_index, print_job.name)
            except IndexError as e:
                self.send_error(HTTPStatus.BAD_REQUEST, str(e))
            except QueuesDesynchronizedError:
                self.send_error(HTTPStatus.CONFLICT, "Queue order has changed")
            else:
                self.send_response(HTTPStatus.OK)
                self.end_headers()

    def delete_print_job(self, uuid):
        """Delete print job with uuid from the queue"""
        index, print_job = self.content_manager.uuid_to_print_job(uuid)
        if not print_job:
            self.send_error(HTTPStatus.NOT_FOUND, "Print job not in queue")
        else:
            try:
                self.module.queue_delete(index, print_job.name)
            except QueuesDesynchronizedError:
                self.send_error(HTTPStatus.CONFLICT, "Queue order has changed")
            else:
                self.send_response(HTTPStatus.OK)
                self.end_headers()

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
            try:
                if action == "print":
                    self.module.resume_print(print_job.name)
                elif action == "pause":
                    self.module.pause_print(print_job.name)
                elif action == "abort":
                    self.module.stop_print(print_job.name)
                else:
                    self.send_error(HTTPStatus.BAD_REQUEST,
                            "Unknown action: " + str(action))
            except QueuesDesynchronizedError:
                self.send_error(HTTPStatus.CONFLICT,
                        "Queue order has changed")

    def put_force(self, uuid):
        """
        Force a print job that requires configuration change
        This is not called until possibly configration changes are
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
        if self._size is not None:
            self.send_header("Content-Length", self._size)
            self._size = None

    def log_request(self, code="-", size="-"):
        """Add size to logging"""
        s = self._size + "B" if self._size is not None else size
        srv.BaseHTTPRequestHandler.log_request(self, code, s)

    def log_error(self, format, *args):
        """Similar to log_message, but log under loglevel ERROR"""
        # Overwrite format string. Default is "code %d, message %s"
        if format == "code %d, message %s":
            format = "Errorcode %d: %s"
        message = ("<%s> %s" %
                (self.address_string(),
                 format%args))
        logger.error(message)

    def log_message(self, format, *args):
        message = ("<%s> %s" %
                (self.address_string(),
                 format%args))
        if (self.path == CLUSTER_API + "printers" or
            self.path == CLUSTER_API + "print_jobs"):
            # Put periodic requests to DEBUG
            logger.debug(message)
        else:
            logger.info(message)


class Server(srv.HTTPServer, threading.Thread):
    """Wrapper class to store the module in the server and add threading"""
    def __init__(self, server_address, RequestHandler, module):
        super().__init__(server_address, RequestHandler)
        threading.Thread.__init__(self)
        self.module = module

    run = srv.HTTPServer.serve_forever


def get_server(module):
    return Server((module.ADDRESS, 8008), Handler, module)
