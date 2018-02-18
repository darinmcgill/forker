from __future__ import print_function
from .Request import Request, Timeout, Aborted
from .listen import listen
import sys
import os
import re


def main(*args):
    port = 8080
    forking = (os.name == 'posix')
    reporting = False
    cgi = False
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
    for sock, addr in listen(port, forking):
        try:
            request = Request(sock=sock, remote_ip=addr[0])
            if reporting:
                out = b"HTTP/1.0 200 OK\r\n"
                out += b"Content-type: text/plain\r\n\r\n"
                out += bytes(request)
                sock.sendall(out)
                print(repr(request))
            else:
                sock.sendall(request.serve(allow_cgi=cgi))
        except Timeout as t:
            print(type(t), t)
        except Aborted as a:
            print(type(a), a)
        finally:
            sock.close()
            if forking:
                sys.exit(0)


if __name__ == "__main__":
    main(*sys.argv[1:])
