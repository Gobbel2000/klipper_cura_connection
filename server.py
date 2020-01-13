#!/usr/bin/env python3

import email.parser
import email.policy
from http import HTTPStatus
import http.server as srv
import os.path

PATH = "http/"


class Handler(srv.BaseHTTPRequestHandler):

    def do_HEAD(self):
        print("Callee:", self.client_address)
        print("Path:", self.path)
        self.send_response(HTTPStatus.OK)
        self.end_headers()

    def do_GET(self):
        print("wants this file:", self.path)
        filepath = PATH + self.path
        if os.path.isdir(filepath):
            filepath += "/index"
        try:
            with open(filepath, "rb") as handle:
                content = handle.read()
        except OSError as e:
            print(e)
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


httpd = srv.HTTPServer(("192.168.178.50", 80), Handler)
httpd.serve_forever()
