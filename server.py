#!/usr/bin/env python3

import gzip
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
        print(self.command)
        print(self.headers)
        length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(length)
        gcode = gzip.decompress(data)
        filepath = PATH + self.path + "file"
        with open(filepath, "wb") as handle:
            # Needs line splitting?
            handle.write(gcode)
        self.send_response(HTTPStatus.OK)
        self.end_headers()

    def do_PUT(self):
        self.do_POST()

    def do_DELETE(self):
        self.do_POST()

    def do_OPTIONS(self):
        self.do_POST()


httpd = srv.HTTPServer(("192.168.178.50", 80), Handler)
httpd.serve_forever()
