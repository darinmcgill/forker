from __future__ import print_function
import socket
import time
import select
import os
import sys
import random


def listen(port=8081, forking=True):
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(('', port))
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
                    pid, status = os.waitpid(child, os.WNOHANG)
                    if pid:
                        children.remove(child)
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
