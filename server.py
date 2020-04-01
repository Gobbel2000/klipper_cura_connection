import email
#PYTHON3: from http import HTTPStatus
#PYTHON3: import http.server as srv
import httplib as HTTPStatus
import BaseHTTPServer as srv
import json
import logging
import os.path
import re
import threading

PRINTER_API = "/api/v1/"
CLUSTER_API = "/cluster-api/v1/"
MJPG_STREAMER_PORT = 8081

logger = logging.getLogger("root.server")


class Handler(srv.BaseHTTPRequestHandler):

    def __init__(self, request, client_address, server):
        """This is the worst thing ever but it somehow works"""
        self.module = server.module
        self.content_manager = self.module.content_manager
        self._size = None # For logging GET requests
        srv.BaseHTTPRequestHandler.__init__(
                self, request, client_address, server)

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
        elif self.path == "/print_jobs":
            self.send_response(HTTPStatus.MOVED_PERMANENTLY)
            self.send_header("Location", "https://youtu.be/dQw4w9WgXcQ")
            self.end_headers()
        else:
            m = self.handle_uuid_path()
            if m and m.group("suffix") == "/preview_image":
                self.get_preview_image(m.group("uuid"))
            else:
                # NOTE: send_error() calls end_headers()
                self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self):
        if self.headers.getmaintype() == "multipart":
            if self.path == CLUSTER_API + "print_jobs/":
                self.post_print_job()
            elif self.path == CLUSTER_API + "materials/":
                self.post_material()
        else:
            m = self.handle_uuid_path()
            if m and m.group("suffix") == "/action/move":
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
            self.wfile.write(json_content)

    def get_preview_image(self, uuid):
        """Send back the preview image for the print job with uuid"""
        #TODO actual image?
        path = os.path.join(self.module.PATH, "tux.png")
        self.send_response(HTTPStatus.OK, size=os.path.getsize(path))
        self.end_headers()
        chunksize = 1024**2 # 1 MiB
        with open(path, "rb") as fp:
            while True:
                chunk = fp.read(chunksize)
                if chunk == "":
                    break
                self.wfile.write(chunk)

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
        boundary = self.headers.getparam("boundary")
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
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()

    def post_material(self):
        boundary = self.headers.getparam("boundary")
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
            except AttributeError:
                self.send_error(HTTPStatus.CONFLICT, "Queue order has changed")
            else:
                self.send_response(HTTPStatus.NO_CONTENT)
                self.end_headers()

    def delete_print_job(self, uuid):
        """Delete print job with uuid from the queue"""
        index, print_job = self.content_manager.uuid_to_print_job(uuid)
        if not print_job:
            self.send_error(HTTPStatus.NOT_FOUND, "Print job not in queue")
        else:
            try:
                self.module.queue_delete(index, print_job.name)
            except AttributeError:
                self.send_error(HTTPStatus.CONFLICT, "Queue order has changed")
            else:
                self.send_response(HTTPStatus.NO_CONTENT)
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
            except AttributeError:
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
        message = ("%s - [%s] %s" %
                (self.address_string(),
                 self.log_date_time_string(),
                 format%args))
        logger.error(message)

    def log_message(self, format, *args):
        message = ("%s - [%s] %s" %
                (self.address_string(),
                 self.log_date_time_string(),
                 format%args))
        if (self.path == CLUSTER_API + "printers" or
            self.path == CLUSTER_API + "print_jobs"):
            # Put periodic requests to DEBUG
            logger.debug(message)
        else:
            logger.info(message)


class MimeParser(object):
    """
    Parser for MIME messages which directly writes attached files.

    When calling parse() this class will parse all parts of a multipart
    MIME message, converting the parts to email.Message objects.
    If a part contains a file it is not added as a payload to that
    Message object but instead directly written to the directory
    specified by out_dir.
    If the file already exists and overwrite is set to False, it will
    be renamed (see _unique_path() for details).

    Arguments:
    fp          The file pointer to parse from
    boundary    The MIME boundary, as specified in the main headers
    length      Length of the body, as specified in the main headers
    out_dir     The directory where any files will be written into
    overwrite   In case a file with the same name exists overwrite it
                if True, write to a unique, indexed name otherwise.
                Defaults to True.
    """

    HEADERS = 0
    BODY = 1
    FILE = 2

    def __init__(self, fp, boundary, length, out_dir, overwrite=True):
        self.fp = fp
        self.boundary = boundary
        self.bytes_left = length
        self.out_dir = out_dir
        self.overwrite = overwrite
        self.submessages = []
        self.written_files = [] # All files that were written

        # What we are reading right now. One of:
        # self.HEADERS, self.BODY, self.FILE (0, 1, 2)
        self._state = None
        self._current_headers = ""
        self._current_body = ""
        self.fpath = "" # Path to the file to write to

    def parse(self):
        """
        Parse the entire file, returning a list of all submessages
        including headers and bodies, except for transmitted files
        which are directly written to disk.
        """
        while True:
            line = self.fp.readline()
            #TODO Be aware of unicode. This might need change for Python 3.
            self.bytes_left -= len(line)
            try:
                self._parse_line(line)
            except StopIteration:
                break
        return self.submessages, self.written_files

    def _parse_line(self, line):
        """
        Parse a single line by first checking for self._state changes.
        Raising StopIteration breaks the loop in self.parse().
        """
        # Previous message is finished
        if line.startswith("--" + self.boundary):
            if self._current_body:
                self.submessages[-1].set_payload(
                        self._current_body.rstrip("\r\n"))
                self._current_body = ""
            self._state = self.HEADERS # Read headers next
            # This is the last line of the MIME message
            if line.strip() == "--" + self.boundary + "--":
                raise StopIteration()
        # Parse dependent on _state
        elif self._state == self.HEADERS:
            self._parse_headers(line)
        elif self._state == self.BODY:
            self._parse_body(line)

        # FILE state is set after parsing headers and should be
        # handled before reading the next line.
        if self._state == self.FILE:
            self._write_file()

    def _parse_headers(self, line):
        """Add the new line to the headers or parse the full header"""
        if line == "\r\n": # End of headers
            headers_message = email.message_from_string(self._current_headers)
            self._current_headers = ""
            self.submessages.append(headers_message)
            self._start_body(headers_message)
        else:
            self._current_headers += line

    def _parse_body(self, line):
        self._current_body += line

    def _write_file(self):
        """
        Write the file following in fp directly to the disk.
        This does not happen line by line because with a lot of very
        short lines that is quite inefficient. Instead the file is copied
        in blocks with a size of 1024 bytes.
        Then parse the remaining lines that have been read into the
        buffer but do not belong to the file (everything past the first
        occurance of boundary).
        """
        logger.debug("Writing file: {}".format(self.fpath))
        self.written_files.append(self.fpath)

        # Use two buffers in case the boundary gets cut in half
        buf1 = self._safe_read()
        buf2 = self._safe_read()
        with open(self.fpath, "w") as write_fp:
            while self.boundary not in buf1 + buf2:
                write_fp.write(buf1)
                buf1 = buf2
                buf2 = self._safe_read()
            if self.bytes_left != 0:
                # Catch the rest of the last line
                remaining_lines = (
                        buf1 + buf2 + self.fp.readline()).splitlines(True)
            else:
                remaining_lines = (buf1 + buf2).splitlines(True)

            # We need an exception for the last line of the file to strip
            # the trailing "\r\n" (<CR><LF>)
            prev_line = ""
            # We take the index with us so we now where to pick up below
            for i, line in enumerate(remaining_lines):
                if self.boundary not in line:
                    write_fp.write(prev_line)
                    prev_line = line
                else:
                    # Now write the last line, but stripped
                    write_fp.write(prev_line.rstrip("\r\n"))
                    break
        # Parse all other lines left in the buffer normally
        # When reaching the end, StopIteration will be propagated up to parse()
        for line in remaining_lines[i:]:
            self._parse_line(line)

    def _safe_read(self):
        """Read a chunk that will not go past EOF"""
        buflen = min(self.bytes_left, 1024)
        self.bytes_left -= buflen
        return self.fp.read(buflen)

    def _start_body(self, headers):
        """Initiate reading of the body depending on whether it is a file"""
        name = headers.get_param("name", header="Content-Disposition")
        if name == "file":
            self.fpath = os.path.join(self.out_dir, headers.get_filename())
            if not self.overwrite:
                self.fpath = self._unique_path(self.fpath)
            self._state = self.FILE
        else:
            self._state = self.BODY

    @staticmethod
    def _unique_path(path):
        """
        Adjust a filename so that it doesn't overwrite an existing file.
        For example, if /path/to/file.txt exists, this function will
        return '/path/to/file-1.txt', then '/path/to/file-2.txt'
        and so on.
        """
        if not os.path.exists(path):
            return path
        root, ext = os.path.splitext(path)
        index = 1
        path = "{}-{}{}".format(root, index, ext)
        while os.path.exists(path):
            path = "{}-{}{}".format(root, index, ext)
            index += 1
        return path


class Server(srv.HTTPServer, threading.Thread):
    """Wrapper class to store the module in the server and add threading"""
    def __init__(self, server_address, RequestHandler, module):
        srv.HTTPServer.__init__(self, server_address, RequestHandler)
        threading.Thread.__init__(self)
        self.module = module

    run = srv.HTTPServer.serve_forever


def get_server(module):
    return Server((module.ADDRESS, 8080), Handler, module)
