#!/usr/bin/env python
from __future__ import print_function
from __future__ import absolute_import
import sys
import os
import re
from .Request import Request
from .listen import listen
from .WebSocketServer import WebSocketServer, TEXT, BIN, Closed

__all__ = [Request, listen, WebSocketServer, TEXT, BIN, Closed]


def main(*args):
    port = 8080
    forking = (os.name == 'posix')
    reporting = False
    for arg in args:
        if re.match(r"^\d+$",arg):
            port = int(arg)
            continue
        if arg == "nofork":
            forking = False
            continue
        if arg == "report":
            reporting = True
            continue
        if os.path.exists(arg):
            os.chdir(arg)
            continue
    for sock, addr in listen(port, forking):
        request = Request(sock=sock, remote_ip=addr[0])
        if reporting:
            out = b"HTTP/1.0 200 OK\r\n"
            out += b"Content-type: text/plain\r\n\r\n"
            out += bytes(request)
            sock.sendall(out)
            print(request)
        else:
            sock.sendall(request.serve())
        sock.close()
        if forking:
            sys.exit(0)


if __name__ == "__main__":
    main(*sys.argv[1:])