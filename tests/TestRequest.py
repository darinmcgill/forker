#!/usr/bin/env python
from __future__ import print_function
import unittest
from forker import Request
import socket
import os
import sys

_example_request = b"""GET /README.md?xyz HTTP/1.1
Host: localhost:8080
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8
Accept-Encoding: gzip, deflate, sdch, br
Accept-Language: en-US,en;q=0.8
Cookie:trail=6231214290744395; scent=6457421329820405

"""

HELLO_WORLD = b"Hello world!\n"


def simple_app(environ, start_response):
    status = environ and '200 OK'
    response_headers = [('Content-type', 'text/plain')]
    start_response(status, response_headers)
    return [HELLO_WORLD]


class AppClass:

    def __init__(self, environ, start_response):
        self.environ = environ
        self.start = start_response

    def __iter__(self):
        status = '200 OK'
        response_headers = [('Content-type', 'text/plain')]
        self.start(status, response_headers)
        yield HELLO_WORLD


class TestRequest(unittest.TestCase):

    def test_socket(self):
        test_data = b"hello\nworld!"
        client, server = socket.socketpair()
        client.send(test_data)
        buff = server.recv(4096)
        self.assertEqual(buff, test_data)
        client.close()
        server.close()

    def test_request(self):
        client, server = socket.socketpair()
        client.send(_example_request)
        request = Request(sock=server)
        client.close()
        server.close()
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.requested_path, "/README.md")
        self.assertEqual(request.query_string, "xyz")
        self.assertEqual(request.headers["host"], "localhost:8080")
        self.assertFalse(request.body)
        self.assertEqual(request.cookies.get("scent"), "6457421329820405")
        self.assertEqual(request.cookies.get("trail"), "6231214290744395")

    def test_listing(self):
        r = Request(requested_path='/')
        out = r.serve()
        line = b"<a href='/cgi_example.sh'>cgi_example.sh</a>"
        self.assertTrue(line in out)

    def test_read(self):
        magic = b"Y43j99j8p4Mk8S8B"
        r = Request(requested_path='/TestRequest.py')
        out = r.serve()
        self.assertTrue(magic in out)

    def test_cgi(self):
        r = Request(requested_path='/cgi_example.sh', query_string="abc")
        out = r.serve(allow_cgi=True)
        # print(out.decode())
        self.assertTrue(b"QUERY_STRING=abc" in out)

    def test_wsgi1(self):
        client, server = socket.socketpair()
        client.send(_example_request)
        request = Request(sock=server)
        client.close()
        server.close()
        out = request.wsgi(simple_app)
        self.assertTrue(isinstance(out, bytes))
        self.assertTrue(b'\r\n\r\n' in out)
        self.assertTrue(HELLO_WORLD in out)
        self.assertTrue(out.startswith(b'HTTP/1.0 200 OK'))

    def test_wsgi2(self):
        client, server = socket.socketpair()
        client.send(_example_request)
        request = Request(sock=server)
        client.close()
        server.close()
        out = request.wsgi(AppClass)
        self.assertTrue(isinstance(out, bytes))
        self.assertTrue(b'\r\n\r\n' in out)
        self.assertTrue(HELLO_WORLD in out)
        self.assertTrue(out.startswith(b'HTTP/1.0 200 OK'))


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    sys.path.append("..")
    unittest.main()
