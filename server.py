#!/usr/bin/env python2

import email
#PYTHON3: from http import HTTPStatus
#PYTHON3: import http.server as srv
import httplib as HTTPStatus
import BaseHTTPServer as srv
import os.path

from contentmanager import ContentManager

PATH = "http/"
PRINTER_API = "/api/v1/"
CLUSTER_API = "/cluster_api/v1/"

class Handler(srv.BaseHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content_manager = ContentManager()

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
        print("Callee:", self.client_address)
        print(self.path)
        print(self.headers)
        if self.headers.get_content_maintype() == "multipart":
            self.do_post_multipart()
        self.send_response(HTTPStatus.OK)
        self.end_headers()

    def do_post_multipart(self):
        headers = self.headers.as_string()
        length = int(self.headers.get("Content-Length", 0))
        # Read the entire body of the request. This call will block
        # if the transmission is slow.
        parts = self.rfile.read(length)
        form = headers + parts
        multipart = email.message_from_string(form)
        assert(multipart.is_multipart())
        for part in multipart.get_payload():
            disp = part.get("Content-Disposition").params
            if part.get_param("name", header="Content-Disposition"):
                filename = PATH + self.path + part.get_filename()
                with open(filename, "w") as handle:
                    handle.write(part.get_payload())

    def do_PUT(self):
        self.do_POST()

    def do_DELETE(self):
        self.do_POST()

    def do_OPTIONS(self):
        self.do_POST()

    #def log_message(self, format, *args):
    #    """Overwriting for specific logging"""
    #    message = ("%s - - [%s] %s\n" %
    #                     (self.address_string(),
    #                      self.log_date_time_string(),
    #                      format%args))

def get_server():
    return srv.HTTPServer(("192.168.178.50", 80), Handler)

if __name__ == "__main__":
    get_server().serve_forever()
