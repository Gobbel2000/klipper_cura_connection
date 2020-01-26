#!/usr/bin/env python3

import email.parser
import email.policy
from http import HTTPStatus
import http.server as srv
import os.path

PATH = "http/"
PRINTER_API = "/api/v1/"
CLUSTER_API = "/cluster_api/v1/"

class ContentManager:

    def get_system(self):
        return "[]"
    def get_print_jobs(self):
        return "[]"

    def get_printers(self):
        pass

manager = ContentManager()

class Handler(srv.BaseHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content_manager = manager

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
            content = self.content_manager.get_printers()
        elif self.path == CLUSTER_API + "print_jobs":
            content = self.content_manager.get_print_jobs()
        else:
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()
            return
        self.send_response(HTTPStatus.OK)
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        print("Callee:", self.client_address)
        print(self.path)
        print(self.headers)
        if self.headers.get_content_maintype() == "multipart":
            self.do_post_multipart()
        self.send_response(HTTPStatus.OK)
        self.end_headers()

    def do_post_multipart(self):
        b_headers = self.headers.as_bytes()
        length = int(self.headers.get("Content-Length", 0))
        # Read the entire body of the request. This call will block
        # if the transmission is slow.
        b_parts = self.rfile.read(length)
        b_form = b_headers + b_parts
        # Specifying the HTTP policy makes the parser return an
        # email.message.EmailMessage instead of *.Message object.
        # This is not compatible with Python <= 3.2
        parser = email.parser.BytesParser(policy=email.policy.HTTP)
        multipart = parser.parsebytes(b_form)
        assert(multipart.is_multipart())
        for part in multipart.iter_parts():
            disp = part.get("Content-Disposition").params
            if disp["name"] == "file":
                filename = PATH + self.path + disp["filename"]
                with open(filename, "w") as handle:
                    handle.write(part.get_content())

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


httpd = srv.HTTPServer(("192.168.178.50", 80), Handler)
httpd.serve_forever()
