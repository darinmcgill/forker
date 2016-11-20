#!/usr/bin/env python
from __future__ import print_function
import sys
import socket
import select
import os
import time
import glob
import stat
import re
import datetime
import base64
import hashlib
import struct
import random




def main(*args):
    port = 8080
    forking = (os.name == 'posix')
    reporting = False
    ws = False
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


        else:
            request = Request(sock=sock, remote_ip=addr[0], request_id=fork_id)
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