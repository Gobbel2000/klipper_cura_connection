#!/usr/bin/env python3

from http import HTTPStatus
import http.server as srv
import sys
from time import sleep


class Handler(srv.BaseHTTPRequestHandler):

    def do_HEAD(self):
        print("Callee:", self.client_address)
        print("Path:", self.path)
        self.send_response(HTTPStatus.OK)
        self.end_headers()

    def do_GET(self):
        print("wants this file:", self.path)
        self.send_response(HTTPStatus.OK)
        self.end_headers()
        self.wfile.write(b"RESPOOOOOOONSE")

    def do_POST(self):
        print("Callee:", self.client_address)
        print(self.path)
        print(self.command)
        print(self.headers)
        length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(length)
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
