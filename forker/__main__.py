from __future__ import print_function
from .Request import Request
from .listen import listen
import sys
import os
import re


def main(*args):
    port = 8080
    forking = (os.name == 'posix')
    reporting = False
    cgi = False
    echoing = False
    for arg in args:
        if re.match(r"^\d+$", arg):
            port = int(arg)
            continue
        if arg == "nofork":
            forking = False
            continue
        if arg == "report":
            reporting = True
            continue
        if arg == "cgi":
            cgi = True
            continue
        if os.path.exists(arg):
            os.chdir(arg)
            continue
        if arg == "echo":
            echoing = True
            continue
        else:
            raise ValueError("unrecoginzed argument %s" % arg)
    for sock, addr in listen(port, forking):
        try:
            request = Request(sock=sock, remote_ip=addr[0])
            if echoing:
                out = b"HTTP/1.0 200 OK\r\n"
                out += b"Content-type: application/octet-stream\r\n"
                out += b"Conent-length: %d\r\n" % len(request.raw)
                out += b"\r\n"
                out += request.raw
                sock.sendall(out)
                print(repr(request))
            elif reporting:
                out = b"HTTP/1.0 200 OK\r\n"
                out += b"Content-type: text/plain\r\n\r\n"
                out += bytes(request)
                sock.sendall(out)
                print(repr(request))
            else:
                sock.sendall(request.serve(allow_cgi=cgi))
        except TimeoutError as t:
            print(type(t), t)
        except ConnectionAbortedError as a:
            print(type(a), a)
        finally:
            sock.close()
            if forking:
                sys.exit(0)


if __name__ == "__main__":
    main(*sys.argv[1:])
