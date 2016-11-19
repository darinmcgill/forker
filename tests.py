#!/usr/bin/env python
import unittest
import forker
import socket

example_requst = """GET /abc?xyz HTTP/1.1
Host: localhost:8080
Connection: keep-alive
Pragma: no-cache
Cache-Control: no-cache
Upgrade-Insecure-Requests: 1
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.71 Safari/537.36
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8
Accept-Encoding: gzip, deflate, sdch, br
Accept-Language: en-US,en;q=0.8
Cookie: Webstorm-197f4332=9586c36a-05ab-4fbe-afa7-267c446cf027

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
        client.send(example_requst)
        request = forker.Request(sock=server)
        self.assertEqual(request.method, "GET")



if __name__ == "__main__":
    unittest.main()