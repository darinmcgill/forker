from __future__ import print_function
from __future__ import absolute_import
import hashlib
import base64
import time
import socket
import sys
import select
import struct
from .Request import Request

if sys.version_info >= (3, 0):
    unicode = str

_magic = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def my_ord(x):
    """
    :param x: usually a character, sometimes a number
    :return: an integer corresponding to the character input
    """
    if isinstance(x, int):
        return x
    return ord(x)


def my_chr(x, _z=bytearray(1)):
    """
    :param x: integer
    :param _z:
    :return: byte
    """
    _z[0] = x
    return bytes(_z)


def _sha1(x):
    assert isinstance(x, bytes)
    # print("x=%s" % x)
    out = hashlib.sha1(x).digest()
    # print("out=%s" % out)
    assert isinstance(out, bytes)
    return out


def _sign(x):
    # return base64.encodestring().strip()
    digested = _sha1(x + _magic)
    # print("len-digested=", len(digested))
    out = base64.standard_b64encode(digested)
    # print("encoded64 => ", repr(out))
    return out


def _ignore(*a, **b):
    return a, b

CONT = 0
TEXT = 1
BIN = 2
CLOSE = 8
PING = 9
PONG = 10


def _unmask(payload, mask):
    indv = list()
    abcd = list(map(my_ord, mask))
    for i in range(len(payload)):
        j = i % 4
        indv.append(my_chr(abcd[j] ^ my_ord(payload[i])))
    return b"".join(indv)


class Pong(Exception):
    pass


class Ping(Exception):
    pass


class Close(Exception):
    pass


class WebSocketServer(object):
    count = 0

    def __init__(self, sock, request=None, verbose=False):
        self.verbose = verbose
        self.request = request or Request(sock=sock)  # type: Request
        if self.verbose:
            print(self.request)
        assert isinstance(sock, socket.socket), type(sock)
        self.soc = sock
        self.fd = sock.fileno()
        self.verbose = False
        self.closed = False
        self.data = ""
        self.last_recv = time.time()
        sig = _sign(self.request.headers["sec-websocket-key"].encode())
        protocol = self.request.headers.get("sec-websocket-protocol", "")
        protocol = protocol.split(",")[0].strip().encode()
        out = b""
        out += b"HTTP/1.1 101 Switching Protocols\r\n"
        out += b"Upgrade: websocket\r\n"
        out += b"Connection: Upgrade\r\n"
        out += b"Sec-WebSocket-Accept: " + sig + b"\r\n"
        if protocol:
            out += b"Sec-WebSocket-Protocol: " + protocol + b"\r\n"
        out += b"\r\n"
        self.soc.sendall(out)
        self.lastSend = time.time()
        if self.verbose:
            print("=>%s<=" % out)
        WebSocketServer.count += 1
        self.instance = WebSocketServer.count

    def __hash__(self):
        return id(self)

    def fileno(self):
        return self.fd

    def recvall(self, timeout=None):
        # returns a list of strings
        if self.closed:
            raise StopIteration()
        assert self.data == "", self.data
        out = list()
        rlist, wlist, xlist = select.select([self.fd], [], [], timeout)
        if not rlist:  # timeout
            return list()
        self.data = self.soc.recv(4096)
        self.last_recv = time.time()
        if self.data == b"":
            self.soc.close()
            self.closed = True
            return out
        while self.data != "":
            try:
                out.append(self._recv1())
            except Pong:
                if self.verbose:
                    print("Pong!")
            except Close:
                self.data = ""
                self.close()
            except Ping:
                if self.verbose:
                    print("Ping!")
        return out

    def close(self):
        if self.closed:
            return
        msg = my_chr(128 | 8) + my_chr(0)
        try:
            self.soc.sendall(msg)
        except socket.error:
            pass
        finally:
            self.soc.close()
            self.closed = True

    def ping(self, payload=""):
        self.send(payload, kind=PING)

    def send(self, payload, kind=None):
        if isinstance(payload, unicode):
            payload = payload.encode()
            kind = kind or TEXT
        if isinstance(payload, (bytes, bytearray)):
            kind = kind or BIN
        assert kind, "TEXT or BIN not specified"
        if self.closed:
            raise StopIteration()
        msg = my_chr(128 | kind)
        length = len(payload)
        if length <= 125:
            msg += my_chr(length)
        else:
            if length <= 65535:
                msg += my_chr(126)
                msg += struct.pack(">H", length)
            else:
                msg += my_chr(127)
                msg += struct.pack(">Q", length)
        msg += bytes(payload)
        rlist, wlist, xlist = select.select([], [self.fd], [])
        _ignore(rlist, wlist, xlist)
        self.soc.sendall(msg)
        self.lastSend = time.time()

    def _recv1(self):
        assert self.data, "WebSocketServer._recv1: no data?"
        first = my_ord(self.data[0])
        fin = bool(first & 128)
        opcode = first & 15
        rsv1 = bool(first & 64)
        rsv2 = bool(first & 32)
        rsv3 = bool(first & 16)
        second = my_ord(self.data[1])
        masking = bool(second & 128)
        len0 = second & 127
        offset = 2
        length = None
        mask = None
        if len0 <= 125:
            length = len0
        if len0 == 126:
            length = struct.unpack("!H", self.data[2:4])[0]
            offset += 2
        if len0 == 127:
            length = struct.unpack("!Q", self.data[2:10])[0]
            offset += 8
        if masking:
            mask = self.data[offset:(offset+4)]
            offset += 4
        if self.verbose:
            print("-------------")
            print("fin=", fin)
            print("rsv1=", rsv1)
            print("rsv2=", rsv2)
            print("rsv3=", rsv3)
            print("opcode=", opcode)
            print("masking=", masking)
            print("length=", length)
        while len(self.data) < offset + length:
            self.data += self.soc.recv(4096)
            self.last_recv = time.time()
            if self.verbose:
                print("reading more...")
        payload = self.data[offset:(offset+length)]
        if len(self.data) == offset + length:
            if self.verbose:
                print("perfect length")
            self.data = ""
        else:
            if self.verbose:
                print("extra stuff")
            self.data = self.data[(offset+length):len(self.data)]
        if masking:
            payload = _unmask(payload, mask)
        if self.verbose:
            print("payload=>%s<=" % payload)
        if opcode == PONG:
            raise Pong()
        if opcode == CLOSE:
            raise Close(payload)
        if opcode == PING:
            self.send(payload, PONG)
            raise Ping()
        if not fin:
            if self.data == "":
                self.data = self.soc.recv(4096)
                self.last_recv = time.time()
            payload += self._recv1()
        if opcode == BIN:
            return bytearray(payload)
        if opcode == TEXT:
            return payload
        raise Exception("bad opcode")

if __name__ == "__main__":
    from .listen import listen
    for sock1, addr in listen(port=8080, forking=False):
        print("running WebSocketServer in echo mode", file=sys.stderr)
        ws = WebSocketServer(sock1)
        while True:
            for thing in ws.recvall():
                print("echoing: %r" % thing)
                how = BIN if isinstance(thing, bytearray) else TEXT
                ws.send(thing, how)
