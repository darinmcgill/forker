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


def listen(port=8081, forking=True):
    listener = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    listener.bind(('',port))
    listener.listen(128)
    next_id = int(time.time())
    children = set()
    while True:
        try:
            while next_id >= int(time.time()):
                time.sleep(0.1)
            r, w, e = select.select([listener], [], [], 1)
            if r:
                new_sock, addr = listener.accept()
            else: 
                for child in list(children):
                    pid,status = os.waitpid(child,os.WNOHANG)
                    if pid: children.remove(child)
                continue
        except KeyboardInterrupt:
            sys.exit(0)
        is_parent = forking and os.fork()
        random.seed()
        if is_parent:
            children.add(is_parent)
            new_sock.close()
            next_id += 1
        else:
            if forking:
                listener.close()
            yield (new_sock, addr, (port << 32) + next_id)




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
        if arg == "ws":
            ws = True
            continue
        if os.path.exists(arg):
            os.chdir(arg)
            continue

    for sock, addr, fork_id in listen(port=port, forking=forking):
        if ws:
            print("running WebSocketServer in echo mode")
            ws = WebSocketServer(sock)
            while True:
                for thing in ws.recvall():
                    print("echoing: %r" % thing)
                    how = BIN if isinstance(thing,bytearray) else TEXT
                    ws.send(thing,how)
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