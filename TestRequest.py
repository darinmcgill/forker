from __future__ import print_function
import unittest
from Request import *

_example_request = b"""GET /README.md?xyz HTTP/1.1
Host: localhost:8080
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8
Accept-Encoding: gzip, deflate, sdch, br
Accept-Language: en-US,en;q=0.8
Cookie:trail=6231214290744395; scent=6457421329820405

"""


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
        r = Request(method='GET', requested_path='/', headers={})
        out = r.serve()
        line = b"<a href='/README.md'>README.md</a>"
        self.assertTrue(line in out)

    def test_read(self):
        magic = b"Y43j99j8p4Mk8S8B"
        r = Request(method='GET', requested_path='/TestRequest.py', headers={})
        out = r.serve()
        self.assertTrue(magic in out)


if __name__ == "__main__":
    unittest.main()
