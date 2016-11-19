#!/usr/bin/env python
import unittest
import forker
import socket

example_request = b"""GET /abc?xyz HTTP/1.1
Host: localhost:8080
Upgrade-Insecure-Requests: 1
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
        client.send(example_request)
        request = forker.Request(sock=server)
        client.close()
        server.close()
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.path, "/abc?xyz")
        self.assertEqual(request.headers["host"], "localhost:8080")
        self.assertFalse(request.body)
        self.assertEqual(request.cookies.get("scent"), "6457421329820405")
        self.assertEqual(request.cookies.get("trail"), "6231214290744395")


if __name__ == "__main__":
    unittest.main()
