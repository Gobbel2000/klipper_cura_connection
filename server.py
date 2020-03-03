#!/usr/bin/env python2

import email
import email.parser
#PYTHON3: from http import HTTPStatus
#PYTHON3: import http.server as srv
import httplib as HTTPStatus
import BaseHTTPServer as srv
import json
import os.path

from contentmanager import ContentManager

PATH = "http/"
RECEIVE_DIR = "received"
PRINTER_API = "/api/v1/"
CLUSTER_API = "/cluster-api/v1/"

class Handler(srv.BaseHTTPRequestHandler):

    content_manager = ContentManager()

    def do_HEAD(self):
        print("Callee:", self.client_address)
        print("Path:", self.path)
        self.send_response(HTTPStatus.OK)
        self.end_headers()

    def do_GET(self):
        """
        Implement a case-specific response, limited to the requests
        that we can expect from Cura.  For a summary of those see
        README.md
        """
        if self.path == PRINTER_API + "system":
            content = self.content_manager.get_system()
        elif self.path == CLUSTER_API + "printers":
            content = self.content_manager.get_printer_status()
        elif self.path == CLUSTER_API + "print_jobs":
            content = self.content_manager.get_print_jobs()
        else:
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()
            return
        self.send_response(HTTPStatus.OK)
        self.end_headers()
        json.dump(content, self.wfile)

    def do_POST(self):
        self.send_response(HTTPStatus.OK)
        self.end_headers()
        if self.headers.getmaintype() == "multipart":
            boundary = self.headers.getparam("boundary")
            length = int(self.headers.get("Content-Length", 0))
            parser = MimeParser(self.rfile, boundary, length)
            submessages = parser.parse()

    def do_PUT(self):
        self.do_POST()

    def do_DELETE(self):
        self.do_POST()

    #def log_message(self, format, *args):
    #    """Overwriting for specific logging"""
    #    message = ("%s - - [%s] %s\n" %
    #                     (self.address_string(),
    #                      self.log_date_time_string(),
    #                      format%args))


class MimeParser(object):
    """
    Parser for MIME messages which directly writes attached files.

    When calling parse() this class will parse all parts of a multipart
    MIME message, converting the parts to email.Message objects.
    If a part contains a file it is not added as a payload to that
    Message object but instead directly written to the directory
    specified by RECEIVE_DIR.
    If the file already exists, it will be renamed (see _unique_path()
    for details).

    Arguments:
    fp          The file pointer to parse from
    boundary    The MIME boundary, as specified in the main headers
    length      Length of the body, as specified in the main headers
    """

    HEADERS = 0
    BODY = 1
    FILE = 2

    def __init__(self, fp, boundary, length):
        self.fp = fp
        self.boundary = boundary
        self.bytes_left = length
        self.submessages = []

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
        return self.submessages

    def _parse_line(self, line):
        """
        Parse a single line by first checking for self._state changes.
        Raising StopIteration breaks the loop in self.parse().
        """
        # Previous message is finished
        if line.strip() == "--" + self.boundary:
            if self._current_body:
                self.submessages[-1].set_payload(self._current_body.rstrip("\r\n"))
                self._current_body = ""
            self._state = self.HEADERS # Read headers next
        # This is the last line of the MIME message
        elif line.strip() == "--" + self.boundary + "--":
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
        buflen = 1024

        # Use two buffers in case the boundary gets cut in half
        # Make sure to not attempt to read past the content length
        buflen = min(self.bytes_left, buflen)
        buf1 = self.fp.read(buflen)
        self.bytes_left -= buflen

        buflen = min(self.bytes_left, buflen)
        buf2 = self.fp.read(buflen)
        self.bytes_left -= buflen
        with open(self.fpath, "w") as write_fp:
            while self.boundary not in buf1 + buf2:
                write_fp.write(buf1)
                buf1 = buf2
                buflen = min(self.bytes_left, buflen)
                buf2 = self.fp.read(buflen)
                self.bytes_left -= buflen
            if self.bytes_left != 0:
                # Catch the rest of the last line
                remaining_lines = (buf1 + buf2 + self.fp.readline()).splitlines(True)
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

    def _start_body(self, headers):
        """Initiate reading of the body depending on whether it is a file"""
        name = headers.get_param("name", header="Content-Disposition")
        if name == "file":
            fpath = os.path.join(RECEIVE_DIR, headers.get_filename())
            self.fpath = self._unique_path(fpath)
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


def get_server():
    return srv.HTTPServer(("192.168.178.50", 8080), Handler)

if __name__ == "__main__":
    get_server().serve_forever()
